# AgentCore Examples

Reference implementations for integrating AgentCore-style credit accounting
into an application. These are minimal demos — adapt to your real database,
provider client, and auth.

## Layout

```
examples/
├── backend/
│   ├── fastapi/usage_proxy.py    # FastAPI proxy: POST /api/agent/request
│   └── express/usage_proxy.js    # Express proxy: POST /api/agent/request
├── db/schema.sql                 # Shared SQLite schema (projects, usage_records)
├── frontend/
│   ├── CreditBadge.jsx           # React badge using POST /api/agent/request
│   ├── main.jsx                  # Demo app entry
│   ├── index.html
│   └── package.json              # Vite + React
└── README.md
```

## Flow

1. Client sends `POST /api/agent/request` with `{ project_id, prompt, model }`.
2. Proxy checks the project balance; if insufficient, returns `402`.
3. Proxy forwards to the provider, estimates/records token usage.
4. Proxy deducts cost and returns:
   `{ provider_response, usage: { prompt_tokens, completion_tokens, cost, new_balance } }`.
5. Frontend (`CreditBadge.jsx`) displays the resulting balance and cost.

There is intentionally no read-only balance endpoint in the examples — the
frontend uses the `new_balance` returned by the request proxy.

## Run

### FastAPI

```bash
pip install fastapi uvicorn httpx
cd examples/backend/fastapi
uvicorn usage_proxy:app --reload --port 8000
```

### Express

```bash
cd examples/backend/express
npm install express node-fetch sqlite3 sqlite
node usage_proxy.js            # PORT=3000
```

### Frontend

```bash
cd examples/frontend
npm install
npm run dev                    # proxy on same origin, or configure Vite proxy
```

## Seed a Project

```sql
INSERT INTO projects (id, name, credit_balance) VALUES ('demo-project', 'Demo', '10.0');
```