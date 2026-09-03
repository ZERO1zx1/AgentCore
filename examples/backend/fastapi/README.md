# FastAPI example (`examples/backend/fastapi/`)

A FastAPI usage proxy: `POST /api/agent/request`.

```bash
pip install fastapi uvicorn httpx
uvicorn usage_proxy:app --reload --port 8000
```

- `usage_proxy.py` — checks balance, forwards to provider, records usage, returns `{ provider_response, usage }`.
