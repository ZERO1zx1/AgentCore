"""examples/backend/fastapi/usage_proxy.py
Simple FastAPI proxy example that records estimated token usage and deducts from project balance.
This is a minimal example for demo; adapt for your real DB and provider client.
"""
import os
import sqlite3
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import httpx
from decimal import Decimal
import uuid

DB_PATH = os.getenv('CREDIT_DB_PATH', 'credit_demo.db')
PROVIDER_URL = os.getenv('PROVIDER_URL', 'https://api.manus.example/v1/generate')
PROVIDER_KEY = os.getenv('PROVIDER_KEY', 'demo_key')  # do NOT commit real keys

app = FastAPI()

# Simple DB helpers (sqlite for demo)
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT,
        credit_balance TEXT -- store Decimal as string
    )
    ''')
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

@app.post('/api/agent/request')
async def proxy(req: Req):
    # Basic project existence check
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT credit_balance FROM projects WHERE id=?', (req.project_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail='project not found')
    balance = Decimal(row[0])

    # Here we could run a cheap local tokenizer to estimate prompt tokens
    prompt_tokens_est = max(1, len(req.prompt) // 4)  # naive estimate: 4 chars ~ 1 token
    completion_tokens_est = req.max_tokens
    est_cost = estimate_cost(prompt_tokens_est, completion_tokens_est, req.model)

    # Policy check: if not enough balance, deny or degrade
    MIN_REQUIRED = est_cost
    if balance < MIN_REQUIRED:
        conn.close()
        raise HTTPException(status_code=402, detail='insufficient credit')

    # Proxy request to provider (demo)
    headers = {'Authorization': f'Bearer {PROVIDER_KEY}', 'Content-Type': 'application/json'}
    async with httpx.AsyncClient(timeout=30) as client:
        body = {'prompt': req.prompt, 'max_tokens': req.max_tokens, 'model': req.model}
        r = await client.post(PROVIDER_URL, json=body, headers=headers)

    if r.status_code >= 400:
        conn.close()
        raise HTTPException(status_code=502, detail='upstream provider error')

    data = r.json()

    # Try to read provider usage metadata if present; otherwise use estimates
    provider_request_id = data.get('id') or str(uuid.uuid4())
    usage_meta = data.get('usage') or {}
    prompt_tokens = usage_meta.get('prompt_tokens', prompt_tokens_est)
    completion_tokens = usage_meta.get('completion_tokens', completion_tokens_est)
    # compute cost
    real_cost = estimate_cost(prompt_tokens, completion_tokens, req.model)

    # record usage
    record_id = str(uuid.uuid4())
    cur.execute('''INSERT INTO usage_records (id, project_id, ts, provider, model, prompt_tokens, completion_tokens, estimated_cost, provider_request_id, is_estimated)
                   VALUES (?, ?, datetime('now'), ?, ?, ?, ?, ?, ?, ?)
                ''', (record_id, req.project_id, 'manus', req.model, prompt_tokens, completion_tokens, str(real_cost), provider_request_id, 0))

    # deduct from balance
    new_balance = balance - real_cost
    cur.execute('UPDATE projects SET credit_balance=? WHERE id=?', (str(new_balance), req.project_id))
    conn.commit()
    conn.close()

    # Return provider response along with our bookkeeping info (do NOT include secrets)
    return {'provider_response': data, 'usage': {'prompt_tokens': prompt_tokens, 'completion_tokens': completion_tokens, 'cost': str(real_cost), 'new_balance': str(new_balance)}}
