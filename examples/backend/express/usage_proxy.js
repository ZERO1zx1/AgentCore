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

async function initDb() {
  const db = await open({ filename: DB_PATH, driver: sqlite3.Database });
  await db.exec(`CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT, credit_balance TEXT)`);
  await db.exec(`CREATE TABLE IF NOT EXISTS usage_records (id TEXT PRIMARY KEY, project_id TEXT, ts TEXT, provider TEXT, model TEXT, prompt_tokens INTEGER, completion_tokens INTEGER, estimated_cost TEXT, provider_request_id TEXT, is_estimated INTEGER)`);
  return db;
}

function estimateTokens(text) {
  return Math.max(1, Math.floor(text.length / 4));
}

function estimateCost(promptTokens, completionTokens, model) {
  const pricing = { 'gpt-3.5-cheap': 0.000001, 'gpt-4-like': 0.00001 };
  const unit = pricing[model] || 0.00001;
  return (promptTokens + completionTokens) * unit;
}

(async () => {
  const db = await initDb();
  const app = express();
  app.use(express.json());

  app.post('/api/agent/request', async (req, res) => {
    const { project_id, prompt, model = 'gpt-3.5-cheap', max_tokens = 128 } = req.body;
    const row = await db.get('SELECT credit_balance FROM projects WHERE id = ?', project_id);
    if (!row) return res.status(404).send('project not found');
    const balance = parseFloat(row.credit_balance);

    const promptTokens = estimateTokens(prompt);
    const completionTokens = max_tokens;
    const estCost = estimateCost(promptTokens, completionTokens, model);

    if (balance < estCost) return res.status(402).send('insufficient credit');

    // proxy to provider
    const response = await fetch(PROVIDER_URL, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${PROVIDER_KEY}` }, body: JSON.stringify({ prompt, max_tokens, model }) });
    if (!response.ok) return res.status(502).send('upstream error');
    const data = await response.json();

    const usage = data.usage || {};
    const prompt_tokens = usage.prompt_tokens || promptTokens;
    const completion_tokens = usage.completion_tokens || completionTokens;
    const realCost = estimateCost(prompt_tokens, completion_tokens, model);

    const recordId = crypto.randomUUID();
    await db.run('INSERT INTO usage_records (id, project_id, ts, provider, model, prompt_tokens, completion_tokens, estimated_cost, provider_request_id, is_estimated) VALUES (?, datetime("now"), ?, ?, ?, ?, ?, ?, ?, ?)', [recordId, project_id, 'manus', model, prompt_tokens, completion_tokens, realCost.toString(), data.id || recordId, 0]);

    const newBalance = (balance - realCost).toString();
    await db.run('UPDATE projects SET credit_balance = ? WHERE id = ?', newBalance, project_id);

    res.json({ provider_response: data, usage: { prompt_tokens, completion_tokens, cost: realCost, new_balance: newBalance } });
  });

  const port = process.env.PORT || 3000;
  app.listen(port, () => console.log(`Proxy listening on ${port}`));
})();
