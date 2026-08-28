# Low-cost Agent Skill

> Proof of concept only. This module is not wired into `AgentCoreEngine` or its budget/checkpoint state; model names and prices must be verified with the selected provider.

This folder contains a small proof-of-concept "low-cost" skill that can be integrated into an AI agent to reduce credit usage by:
- Calling a cheap model first and escalating only when necessary (tiered flow)
- Summarizing/trimming prompts before sending
- Caching responses to avoid duplicate calls
- Recording usage locally (sqlite demo)

Files:
- skill_low_cost.py — main POC skill
- tests/test_skill.py — unit tests (mocked provider)

Important notes:
- This is a demo. Replace sqlite with your production DB, and swap call_provider with your provider adapter.
- Do NOT commit real provider keys. Use env vars or a secret manager.

Environment variables (examples):
- CREDIT_DB_PATH: path to sqlite DB (default credit_demo.db)
- PROVIDER_URL: upstream provider endpoint
- PROVIDER_KEY: provider API key
- REDIS_URL: optional Redis URL for caching
- CHEAP_MODEL / EXP_MODEL: model names
- PRICE_CHEAP / PRICE_EXP: per-token pricing for estimation

Recommended defaults and policies:
- cheap model: gpt-3.5-cheap
- max_tokens_default: 128
- cache TTL: 24h
- alert_low_threshold: $1.00 (notify)
- auto_degrade_threshold: $0.5 (force cheap model / shorten max_tokens)
- block_threshold: $0.1 (deny non-essential requests)

How to run locally (quick):
1. Install dependencies: httpx, pytest (for tests). Optional: aioredis.
2. Run tests: pytest feat/low_cost_skill/tests
3. Use skill_low_cost.low_cost_request_sync("proj-1", "Hello world") in scripts for quick manual testing.
