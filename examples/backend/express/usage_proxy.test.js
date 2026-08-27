// examples/backend/express/usage_proxy.test.js
const test = require('node:test');
const assert = require('node:assert');
const crypto = require('node:crypto');
const os = require('node:os');
const path = require('node:path');
const fs = require('node:fs');
const sqlite3 = require('sqlite3');
const { open } = require('sqlite');
const { initDb, migrateDb, applyCharge, buildApp } = require('./usage_proxy.js');

function tmpDb() {
  return path.join(os.tmpdir(), `express_test_${crypto.randomUUID()}.db`);
}

async function freshDb() {
  const dbPath = tmpDb();
  const db = await open({ filename: dbPath, driver: sqlite3.Database });
  await db.exec('CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT, credit_balance TEXT)');
  await db.exec(
    `CREATE TABLE usage_records (id TEXT PRIMARY KEY, project_id TEXT, ts TEXT, provider TEXT, model TEXT,
     prompt_tokens INTEGER, completion_tokens INTEGER, estimated_cost TEXT,
     provider_request_id TEXT, is_estimated INTEGER)`
  );
  await migrateDb(db);
  return { db, dbPath };
}

test('migration adds missing columns and preserves rows, idempotent', async () => {
  const { db, dbPath } = await freshDb();
  await db.run(
    "INSERT INTO usage_records (id, project_id, ts, provider, model, prompt_tokens, completion_tokens, estimated_cost, provider_request_id, is_estimated) VALUES ('old1','p1','now','manus','m',1,2,'0.001','r',0)"
  );
  const cols = await db.all('PRAGMA table_info(usage_records)');
  const names = new Set(cols.map((c) => c.name));
  for (const c of ['actual_cost', 'cost_source', 'token_source', 'is_estimated']) {
    assert.ok(names.has(c), `missing column ${c}`);
  }
  const row = await db.get("SELECT id FROM usage_records WHERE id='old1'");
  assert.strictEqual(row.id, 'old1');
  await migrateDb(db); // idempotent
  await db.close();
  fs.unlinkSync(dbPath);
});

test('applyCharge deducts, rejects when over budget, never negative', async () => {
  const { db, dbPath } = await freshDb();
  await db.run("INSERT INTO projects (id,name,credit_balance) VALUES ('p1','d','0.0017')");
  const mk = (id) => [id, 'p1', 'manus', 'm', 5, 3, '0.000008', null, 'estimate', 'provider', 'r', 1];
  let r = await applyCharge(db, 'p1', 0.0017, mk('a'));
  assert.strictEqual(r.ok, true);
  assert.strictEqual(r.newBalance, '0');
  r = await applyCharge(db, 'p1', 0.0017, mk('b'));
  assert.strictEqual(r.ok, false);
  const bal = await db.get("SELECT credit_balance FROM projects WHERE id='p1'");
  assert.strictEqual(bal.credit_balance, '0');
  await db.close();
  fs.unlinkSync(dbPath);
});

test('concurrent deductions cannot both spend the same balance', async () => {
  const { db, dbPath } = await freshDb();
  await db.run("INSERT INTO projects (id,name,credit_balance) VALUES ('p1','d','0.0017')");
  const mk = (id) => [id, 'p1', 'manus', 'm', 5, 3, '0.000008', null, 'estimate', 'provider', 'r', 1];
  const results = await Promise.all([
    applyCharge(db, 'p1', 0.0017, mk('a')),
    applyCharge(db, 'p1', 0.0017, mk('b')),
  ]);
  assert.strictEqual(results.filter((x) => x.ok).length, 1);
  const bal = await db.get("SELECT credit_balance FROM projects WHERE id='p1'");
  assert.strictEqual(bal.credit_balance, '0');
  const count = await db.get('SELECT COUNT(*) AS count FROM usage_records');
  assert.strictEqual(count.count, 1);
  await db.close();
  fs.unlinkSync(dbPath);
});

test('a failed transaction cannot roll back the next queued charge', async () => {
  const { db, dbPath } = await freshDb();
  await db.run("INSERT INTO projects (id,name,credit_balance) VALUES ('p1','d','1.0')");
  const bad = ['same', 'p1', 'manus', 'm', 1, 1, '0.1', null, 'estimate', 'provider', 'r', 1];
  const good = ['same', 'p1', 'manus', 'm', 1, 1, '0.1', null, 'estimate', 'provider', 'r', 1];
  await applyCharge(db, 'p1', 0.1, bad);
  await assert.rejects(applyCharge(db, 'p1', 0.1, good));
  const afterFailure = await db.get("SELECT credit_balance FROM projects WHERE id='p1'");
  assert.strictEqual(afterFailure.credit_balance, '0.9');

  const next = ['next', 'p1', 'manus', 'm', 1, 1, '0.1', null, 'estimate', 'provider', 'r2', 1];
  const result = await applyCharge(db, 'p1', 0.1, next);
  assert.strictEqual(result.ok, true);
  assert.strictEqual(result.newBalance, '0.8');
  await db.close();
  fs.unlinkSync(dbPath);
});

test('GET /balance is read-only (no provider call)', async () => {
  const { db, dbPath } = await freshDb();
  await db.run("INSERT INTO projects (id,name,credit_balance) VALUES ('p1','d','5.0')");
  const app = buildApp(db);
  const server = app.listen(0);
  const { port } = server.address();
  const res = await fetch(`http://127.0.0.1:${port}/api/projects/p1/balance`);
  const j = await res.json();
  assert.strictEqual(j.balance, '5.0');
  server.close();
  await db.close();
  fs.unlinkSync(dbPath);
});
