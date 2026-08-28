# Credit-management integration draft

This document describes an optional application layer for collecting provider usage and enforcing account-level credit policies. It is not implemented by AgentCore itself and must not be confused with the engine’s local estimate/reserve accounting.

## Goal

Route authenticated provider requests through a server-side proxy, record provider usage, maintain a project balance, and apply transparent policy decisions. Keep provider billing reconciliation separate from request-time estimates.

## Suggested model

| Table | Minimum purpose |
| --- | --- |
| `projects` | Project identity and current credit balance. |
| `usage_records` | Project, provider request ID, model, token counts, estimated/actual cost, timestamp. |
| `policies` | Versioned threshold and authorization rules. |

Use the example schema in `examples/db/schema.sql` as a starting point, not a production migration. Add tenant isolation, idempotency, foreign keys, indexes, retention, and audit requirements for the target system.

## Safe flow

1. Authenticate and authorize the project before forwarding a request.
2. Apply a request-time allowance using an upper-bound estimate.
3. Send the request through a server-only provider client; never expose provider keys to the browser.
4. Persist the response usage and provider request ID idempotently.
5. Reconcile against provider data on a scheduled worker, retaining both estimates and verified amounts.
6. Notify on policy changes without including secrets or prompt contents.

The FastAPI and Express examples are illustrative proxy snippets. They need production authentication, rate limiting, secure secret management, error handling, observability, and provider-specific verification before deployment.

## Policy and security

Start with auto-top-up disabled. Only an explicitly authorized owner/admin workflow should create a purchase or payment action; an agent may recommend degradation or pause but must not spend money. Use least privilege, encrypt sensitive data at rest where required, redact logs, validate webhooks, rate-limit endpoints, and retain an auditable policy decision for each denied/degraded request.

## Next work

- Add migrations and tests for idempotent usage ingestion.
- Define provider reconciliation and dispute handling.
- Build a role-aware dashboard from verified data.
- Document notification delivery, retention, and incident response.
