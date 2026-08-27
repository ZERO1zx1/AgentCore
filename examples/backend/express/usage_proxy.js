// examples/backend/express/usage_proxy.js
// Minimal Express proxy that estimates cost and records usage in SQLite (demo).
const express = require('express');
const fetch = require('node-fetch');
const sqlite3 = require('sqlite3');
const { open } = require('sqlite');
const crypto = require('crypto');

const DB_PATH = process.env.CREDIT_DB_PATH || 'credit_demo.db';
const PROVIDER_URL = process.env.PROVIDER_URL || 'https://api.manus.example/v1/generate';
const PROVIDER_KEY = process.env.PROVIDER_KEY || 'demo_key';

// New columns added by forward migration (idempotent ALTER).
const MIGRATION_COLUMNS = {
  actual_cost: 'TEXT',
  cost_source: 'TEXT',
  token_source: 'TEXT',
  is_estimated: 'INTEGER',
};

// sqlite3 exposes a serialized statement queue, but separate async functions
// can still interleave their BEGIN/SELECT/UPDATE sequences on one connection.
// Keep an application-level transaction tail per Database object so a failed
// request can never roll back another request's transaction.
const chargeQueues = new WeakMap();

function enqueueCharge(db, operation) {
  const previous = chargeQueues.get(db) || Promise.resolve();
  const run = previous.catch(() => undefined).then(operation);
  chargeQueues.set(db, run.catch(() => undefined));
  return run;
}

function estimateTokens(text) {
  return Math.max(1, Math.floor(text.length / 4));
}

function estimateCost(promptTokens, completionTokens, model) {
  const pricing = { 'gpt-3.5-cheap': 0.000001, 'gpt-4-like': 0.00001 };
  const unit = pricing[model] || 0.00001;
  return (promptTokens + completionTokens) * unit;
}

async function migrateDb(db) {
  const cols = await db.all('PRAGMA table_info(usage_records)');
  const existing = new Set(cols.map((c) => c.name));
  for (const [col, type] of Object.entries(MIGRATION_COLUMNS)) {
    if (!existing.has(col)) {
      await db.run(`ALTER TABLE usage_records ADD COLUMN ${col} ${type}`);
    }
  }
}

async function initDb() {
  const db = await open({ filename: DB_PATH, driver: sqlite3.Database });
  await db.exec(`CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT, credit_balance TEXT)`);
  // Baseline schema omits newer provenance columns so the forward migration runs.
  await db.exec(
    `CREATE TABLE IF NOT EXISTS usage_records (
      id TEXT PRIMARY KEY, project_id TEXT, ts TEXT, provider TEXT, model TEXT,
      prompt_tokens INTEGER, completion_tokens INTEGER, estimated_cost TEXT,
      provider_request_id TEXT, is_estimated INTEGER)`
  );
  await migrateDb(db);
  return db;
}

// Atomically validate balance, record usage, and deduct.
// Returns { ok: true, newBalance } or { ok: false, error }. Uses BEGIN IMMEDIATE
// so concurrent requests serialize and cannot double-spend the same balance.
// Rejected (over-budget) calls are NOT recorded and no balance is deducted; the
// 402 response is the audit signal.
async function applyCharge(db, projectId, chargedCost, params) {
  return enqueueCharge(db, async () => {
    let transactionStarted = false;
    try {
      await db.run('BEGIN IMMEDIATE');
      transactionStarted = true;
      const row = await db.get('SELECT credit_balance FROM projects WHERE id = ?', projectId);
      if (!row) {
        await db.run('ROLLBACK');
        transactionStarted = false;
        return { ok: false, error: 'project not found' };
      }
      const balance = parseFloat(row.credit_balance);
      if (balance < chargedCost) {
        await db.run('ROLLBACK');
        transactionStarted = false;
        return { ok: false, error: 'insufficient credit' };
      }
      const cols = [
        'id', 'project_id', 'ts', 'provider', 'model', 'prompt_tokens',
        'completion_tokens', 'estimated_cost', 'actual_cost', 'cost_source',
        'token_source', 'provider_request_id', 'is_estimated',
      ];
      const ph = ['?', '?', "datetime('now')", '?', '?', '?', '?', '?', '?', '?', '?', '?', '?'];
      await db.run(`INSERT INTO usage_records (${cols.join(',')}) VALUES (${ph.join(',')})`, params);
      const newBalance = (balance - chargedCost).toString();
      await db.run('UPDATE projects SET credit_balance = ? WHERE id = ?', newBalance, projectId);
      await db.run('COMMIT');
      transactionStarted = false;
      return { ok: true, newBalance };
    } catch (e) {
      if (transactionStarted) {
        try {
          await db.run('ROLLBACK');
        } catch {
          // Preserve the original transaction failure.
        }
      }
      throw e;
    }
  });
}

function buildApp(db) {
  const app = express();
  app.use(express.json());

  // Read-only balance lookup. Never calls the provider or deducts credit.
  app.get('/api/projects/:project_id/balance', async (req, res) => {
    const { project_id } = req.params;
    const row = await db.get('SELECT credit_balance FROM projects WHERE id = ?', project_id);
    if (!row) return res.status(404).send('project not found');
    res.json({ project_id, balance: row.credit_balance });
  });

  app.post('/api/agent/request', async (req, res) => {
    const { project_id, prompt, model = 'gpt-3.5-cheap', max_tokens = 128 } = req.body;
    const row = await db.get('SELECT credit_balance FROM projects WHERE id = ?', project_id);
    if (!row) return res.status(404).send('project not found');
    const balance = parseFloat(row.credit_balance);

    const promptTokens = estimateTokens(prompt);
    const completionTokens = max_tokens;
    const estCost = estimateCost(promptTokens, completionTokens, model);

    // Preflight affordability check (estimated cost). Kept intentionally.
    if (balance < estCost) return res.status(402).send('insufficient credit');

    // Proxy to provider.
    const response = await fetch(PROVIDER_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${PROVIDER_KEY}` },
      body: JSON.stringify({ prompt, max_tokens, model }),
    });
    if (!response.ok) return res.status(502).send('upstream error');
    const data = await response.json();

    // --- Token provenance (key presence, not truthiness) ---
    const usage = data.usage || {};
    const hasProviderTokens = ('prompt_tokens' in usage) && ('completion_tokens' in usage);
    const pt = hasProviderTokens ? usage.prompt_tokens : promptTokens;
    const ct = hasProviderTokens ? usage.completion_tokens : completionTokens;
    const tokenSource = hasProviderTokens ? 'provider' : 'estimate';

    // --- Cost provenance (explicit monetary cost only) ---
    const providerMonetary = usage.cost;
    const estCostFinal = estimateCost(pt, ct, model);
    let costSource, actualCost, isEstimated;
    if (providerMonetary !== undefined && providerMonetary !== null) {
      costSource = 'provider';
      actualCost = String(providerMonetary);
      isEstimated = 0;
    } else {
      costSource = 'estimate';
      actualCost = null;
      isEstimated = 1;
    }

    const recordId = crypto.randomUUID();
    const params = [
      recordId, project_id, 'manus', model, pt, ct,
      estCostFinal.toString(), actualCost, costSource, tokenSource, data.id || recordId, isEstimated,
    ];
    const charged = actualCost !== null ? parseFloat(actualCost) : estCostFinal;

    const result = await applyCharge(db, project_id, charged, params);
    if (!result.ok) {
      return res.status(402).send('insufficient credit for provider-confirmed cost');
    }
    res.json({
      provider_response: data,
      usage: {
        prompt_tokens: pt,
        completion_tokens: ct,
        estimated_cost: estCostFinal,
        actual_cost: actualCost,
        cost_source: costSource,
        token_source: tokenSource,
        new_balance: result.newBalance,
      },
    });
  });

  return app;
}

// Only start a server when executed directly (not when imported by tests).
if (require.main === module) {
  initDb()
    .then((db) => {
      const app = buildApp(db);
      const port = process.env.PORT || 3000;
      app.listen(port, () => console.log(`Proxy listening on ${port}`));
    })
    .catch((e) => {
      console.error('Failed to start proxy:', e);
      process.exit(1);
    });
}

module.exports = { initDb, migrateDb, applyCharge, buildApp, estimateCost, estimateTokens };
