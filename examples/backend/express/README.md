# Express example (`examples/backend/express/`)

A Node/Express usage proxy: `POST /api/agent/request`.

```bash
npm install express node-fetch sqlite3 sqlite
node usage_proxy.js   # PORT=3000
```

- `usage_proxy.js` — checks balance, forwards to provider, records usage.
- `usage_proxy.test.js` — tests.
