"""skill_low_cost.py
Minimal low-cost skill for agent integration.
- Cheap-first tiered calls
- Simple prompt trimming/summarization (placeholder)
- Optional Redis cache (if REDIS_URL set and aioredis installed)
- Records usage to sqlite (demo)

This is a demo POC: adapt DB, provider client, pricing, and policy engine for production.
"""
import os
import json
import sqlite3
import hashlib
import asyncio
from decimal import Decimal
import httpx

# Optional redis
try:
    import aioredis
except Exception:
    aioredis = None

DB = os.getenv("CREDIT_DB_PATH", "credit_demo.db")
REDIS_URL = os.getenv("REDIS_URL", None)
PROVIDER_URL = os.getenv("PROVIDER_URL", "https://api.manus.example/v1/generate")
PROVIDER_KEY = os.getenv("PROVIDER_KEY", "demo_key")

CHEAP_MODEL = os.getenv("CHEAP_MODEL", "gpt-3.5-cheap")
EXP_MODEL = os.getenv("EXP_MODEL", "gpt-4-like")
MAX_TOKENS_DEFAULT = int(os.getenv("MAX_TOKENS_DEFAULT", "128"))
CACHE_TTL = int(os.getenv("CACHE_TTL_SEC", 60*60*24))  # 24h

# Pricing map for estimates (per-token)
PRICING = {
    CHEAP_MODEL: Decimal(os.getenv("PRICE_CHEAP", "0.000001")),
    EXP_MODEL: Decimal(os.getenv("PRICE_EXP", "0.00001")),
}

# --- DB helpers (sqlite demo) ---
def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS usage_records (
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
    )""")
    conn.commit()
    conn.close()

init_db()

# --- Token estimator fallback ---
def estimate_tokens(text: str) -> int:
    # Fallback: naive 4 chars ~= 1 token
    return max(1, len(text) // 4)

def cost_estimate(prompt_tokens: int, completion_tokens: int, model: str) -> Decimal:
    unit = PRICING.get(model, Decimal("0.00001"))
    return (Decimal(prompt_tokens + completion_tokens) * unit)

# --- Cache helpers ---
async def get_redis():
    if not REDIS_URL or not aioredis:
        return None
    return await aioredis.from_url(REDIS_URL)

def prompt_hash(obj) -> str:
    s = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(s.encode()).hexdigest()

# --- Provider call (can be replaced by adapter) ---
async def call_provider(model, prompt, max_tokens=MAX_TOKENS_DEFAULT):
    headers = {"Authorization": f"Bearer {PROVIDER_KEY}", "Content-Type": "application/json"}
    payload = {"model": model, "prompt": prompt, "max_tokens": max_tokens}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(PROVIDER_URL, json=payload, headers=headers)
    r.raise_for_status()
    return r.json()

# --- Skill API (single entry) ---
async def low_cost_request(project_id: str, prompt: str, prefer_stream=False):
    """
    1) Summarize/trim prompt if too long (caller can provide summarized context)
    2) Check cache; if hit, return cached response
    3) Call CHEAP_MODEL; if result seems insufficient, escalate to EXP_MODEL
    4) Write usage record and return
    """
    # 1) trim/summarize - simple truncation (replace with real summarizer for production)
    if len(prompt) > 4000:
        prompt = prompt[-4000:]

    key = prompt_hash({"project_id": project_id, "prompt": prompt, "max_tokens": MAX_TOKENS_DEFAULT, "model": CHEAP_MODEL})
    # 2) cache
    redis = await get_redis()
    if redis:
        cached = await redis.get(key)
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass

    # 3) call cheap model
    cheap_resp = await call_provider(CHEAP_MODEL, prompt, MAX_TOKENS_DEFAULT)
    # heuristic: if cheap response is short or includes 'I don't know' escalate
    cheap_text = (cheap_resp.get("text") or "")
    if len(cheap_text) < 30 or "don't know" in cheap_text.lower() or "i don't know" in cheap_text.lower():
        exp_resp = await call_provider(EXP_MODEL, prompt, MAX_TOKENS_DEFAULT * 2)
        chosen = exp_resp
        used_model = EXP_MODEL
    else:
        chosen = cheap_resp
        used_model = CHEAP_MODEL

    # parse usage if provider returns it
    usage = chosen.get("usage") or {}
    prompt_tokens = usage.get("prompt_tokens", estimate_tokens(prompt))
    completion_tokens = usage.get("completion_tokens", max(1, len((chosen.get("text") or "")) // 4))
    est_cost = cost_estimate(prompt_tokens, completion_tokens, used_model)

    # record usage (sqlite demo)
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    rec_id = hashlib.sha256((project_id + key).encode()).hexdigest()
    cur.execute("INSERT OR REPLACE INTO usage_records (id, project_id, ts, provider, model, prompt_tokens, completion_tokens, estimated_cost, provider_request_id, is_estimated) VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?)",
                (rec_id, project_id, "manus", used_model, prompt_tokens, completion_tokens, str(est_cost), chosen.get("id", rec_id), 0))
    conn.commit()
    conn.close()

    result = {"model": used_model, "response": chosen.get("text"), "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "cost": str(est_cost)}}

    # set cache
    if redis:
        try:
            await redis.set(key, json.dumps(result, ensure_ascii=False), ex=CACHE_TTL)
        except Exception:
            pass

    return result

# Simple synchronous wrapper for quick scripts
def low_cost_request_sync(project_id: str, prompt: str):
    return asyncio.get_event_loop().run_until_complete(low_cost_request(project_id, prompt))
