"""examples/backend/fastapi/usage_proxy.py
Simple FastAPI proxy example that records token usage and deducts from project
balance. This is a minimal example for demo; adapt for your real DB and
provider client.

Cost provenance rules (honest accounting):
- Token provenance: "provider" when the upstream response includes BOTH
  "prompt_tokens" and "completion_tokens" keys, else "estimate".
- Cost provenance: cost_source is "provider" ONLY when the upstream response
  carries an explicit monetary cost. A local estimate_cost() calculation is
  ALWAYS treated as "estimate", even when provider token counts are present.
  The persisted `is_estimated` flag mirrors cost provenance.

Safety:
- The usage_records schema is migrated forward idempotently (ALTER TABLE ADD
  COLUMN) so an existing database is never recreated or truncated.
- The final affordability check, usage-record INSERT, and balance UPDATE run
  atomically in a single SQLite transaction (BEGIN IMMEDIATE) so the balance
  can never go negative and concurrent requests cannot double-spend.

Decision on rejected (over-budget) provider calls: they are NOT written to
usage_records and no balance is deducted. The 402 response is the audit signal;
persisting a non-charged row would risk being misread as a completed charge.
"""

import os
import sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
from decimal import Decimal
import uuid

DB_PATH = os.getenv('CREDIT_DB_PATH', 'credit_demo.db')
PROVIDER_URL = os.getenv('PROVIDER_URL', 'https://api.manus.example/v1/generate')
PROVIDER_KEY = os.getenv('PROVIDER_KEY', 'demo_key')  # do NOT commit real keys

app = FastAPI()

# Columns of usage_records that the current INSERT references. `ts` is supplied
# by the database (datetime('now')) and is intentionally excluded from params.
USAGE_PARAM_COLS = [
    "id", "project_id", "provider", "model", "prompt_tokens", "completion_tokens",
    "estimated_cost", "actual_cost", "cost_source", "token_source",
    "provider_request_id", "is_estimated",
]

# New columns added by forward migration (idempotent ALTER).
MIGRATION_COLUMNS = {
    "actual_cost": "TEXT",
    "cost_source": "TEXT",
    "token_source": "TEXT",
    "is_estimated": "INTEGER",
}


def _connect():
    # isolation_level=None => explicit transaction control (BEGIN/COMMIT/ROLLBACK).
    return sqlite3.connect(DB_PATH, isolation_level=None)


def migrate_db(conn):
    """Add any missing usage_records columns without touching existing data."""
    cur = conn.cursor()
    existing = {row[1] for row in cur.execute("PRAGMA table_info(usage_records)").fetchall()}
    for col, ctype in MIGRATION_COLUMNS.items():
        if col not in existing:
            cur.execute(f"ALTER TABLE usage_records ADD COLUMN {col} {ctype}")
    conn.commit()


def init_db():
    conn = _connect()
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT,
        credit_balance TEXT -- store Decimal as string
    )
    ''')
    # Baseline schema intentionally omits the newer provenance columns so the
    # forward migration is exercised even on a freshly created database.
    cur.execute('''
    CREATE TABLE IF NOT EXISTS usage_records (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        ts TEXT,
        provider TEXT,
        model TEXT,
        prompt_tokens INTEGER,
        completion_tokens INTEGER,
        estimated_cost TEXT,
        provider_request_id TEXT,
        is_estimated INTEGER
    )
    ''')
    conn.commit()
    migrate_db(conn)
    conn.close()


init_db()


class Req(BaseModel):
    project_id: str
    prompt: str
    model: str = 'gpt-3.5-cheap'
    max_tokens: int = 128


# Pricing per token (example values) - configure via env in prod
PRICING = {
    'gpt-3.5-cheap': Decimal('0.000001'),
    'gpt-4-like': Decimal('0.00001')
}


def estimate_cost(prompt_tokens, completion_tokens, model):
    unit = PRICING.get(model, Decimal('0.00001'))
    return (Decimal(prompt_tokens + completion_tokens) * unit)


def apply_charge(conn, project_id, charged_cost, params):
    """Atomically validate balance, record usage, and deduct.

    Returns (True, new_balance_str) on success or (False, reason) if the
    confirmed cost exceeds the available balance. Uses BEGIN IMMEDIATE so
    concurrent requests serialize and cannot both spend the same balance.
    """
    cur = conn.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("SELECT credit_balance FROM projects WHERE id=?", (project_id,))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return False, "project not found"
        balance = Decimal(row[0])
        if balance < charged_cost:
            conn.rollback()
            return False, "insufficient credit"
        cols = ["id", "project_id", "ts", "provider", "model", "prompt_tokens",
                "completion_tokens", "estimated_cost", "actual_cost", "cost_source",
                "token_source", "provider_request_id", "is_estimated"]
        placeholders = ["?", "?", "datetime('now')", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?"]
        cur.execute(
            f"INSERT INTO usage_records ({','.join(cols)}) VALUES ({','.join(placeholders)})",
            params,
        )
        new_balance = balance - charged_cost
        cur.execute("UPDATE projects SET credit_balance=? WHERE id=?", (str(new_balance), project_id))
        conn.commit()
        return True, str(new_balance)
    except Exception:
        conn.rollback()
        raise


@app.get('/api/projects/{project_id}/balance')
async def get_balance(project_id: str):
    """Read-only balance lookup. Never calls the provider or deducts credit."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute('SELECT credit_balance FROM projects WHERE id=?', (project_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail='project not found')
    return {'project_id': project_id, 'balance': row[0]}


@app.post('/api/agent/request')
async def proxy(req: Req):
    conn = _connect()
    cur = conn.cursor()
    cur.execute('SELECT credit_balance FROM projects WHERE id=?', (req.project_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail='project not found')
    balance = Decimal(row[0])

    # Naive local token estimate (4 chars ~ 1 token).
    prompt_tokens_est = max(1, len(req.prompt) // 4)
    completion_tokens_est = req.max_tokens
    est_cost = estimate_cost(prompt_tokens_est, completion_tokens_est, req.model)

    # Preflight affordability check (estimated cost). Kept intentionally.
    if balance < est_cost:
        conn.close()
        raise HTTPException(status_code=402, detail='insufficient credit')

    # Proxy request to provider (demo).
    headers = {'Authorization': f'Bearer {PROVIDER_KEY}', 'Content-Type': 'application/json'}
    async with httpx.AsyncClient(timeout=30) as client:
        body = {'prompt': req.prompt, 'max_tokens': req.max_tokens, 'model': req.model}
        r = await client.post(PROVIDER_URL, json=body, headers=headers)

    if r.status_code >= 400:
        conn.close()
        raise HTTPException(status_code=502, detail='upstream provider error')

    data = r.json()

    # --- Token provenance (key presence, not truthiness) ---
    usage_meta = data.get('usage') or {}
    has_provider_tokens = ("prompt_tokens" in usage_meta) and ("completion_tokens" in usage_meta)
    prompt_tokens = usage_meta.get('prompt_tokens', prompt_tokens_est) if has_provider_tokens else prompt_tokens_est
    completion_tokens = usage_meta.get('completion_tokens', completion_tokens_est) if has_provider_tokens else completion_tokens_est
    token_source = 'provider' if has_provider_tokens else 'estimate'

    # --- Cost provenance (explicit monetary cost only) ---
    provider_request_id = data.get('id') or str(uuid.uuid4())
    provider_monetary = usage_meta.get('cost')
    est_cost_final = estimate_cost(prompt_tokens, completion_tokens, req.model)
    if provider_monetary is not None:
        cost_source = 'provider'
        actual_cost = str(Decimal(str(provider_monetary)))
        is_estimated = 0
    else:
        cost_source = 'estimate'
        actual_cost = None
        is_estimated = 1

    record_id = str(uuid.uuid4())
    params = (
        record_id, req.project_id, 'manus', req.model, prompt_tokens, completion_tokens,
        str(est_cost_final), actual_cost, cost_source, token_source, provider_request_id, is_estimated,
    )
    charged = Decimal(actual_cost) if actual_cost is not None else est_cost_final

    # Atomic final check + record + deduct (never goes negative).
    ok, result = apply_charge(conn, req.project_id, charged, params)
    conn.close()
    if not ok:
        raise HTTPException(
            status_code=402,
            detail='insufficient credit for provider-confirmed cost',
        )

    new_balance = result
    return {
        'provider_response': data,
        'usage': {
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'estimated_cost': str(est_cost_final),
            'actual_cost': actual_cost,
            'cost_source': cost_source,
            'token_source': token_source,
            'new_balance': new_balance,
        },
    }
