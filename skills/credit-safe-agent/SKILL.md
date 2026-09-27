---
name: credit-safe-agent
description: Plan and execute resumable work under budgets or uncertain costs while preserving reserves and preventing wasteful retries.
---

# Credit-Safe Agent

Make progress with the least expensive capable route. Prefer deterministic local work and existing artifacts; use paid or external operations only when they are necessary for the requested outcome. Preserve the configured 15% reserve by default.

Split work into dependency-aware atomic units and rank them by required outcome, not polish. Before an operation, confirm capability, estimate worst-case cost including plausible retries, and verify that the reserve remains intact. After each paid operation, record the result and re-evaluate the remaining plan. Checkpoint every completed unit so interruption does not force repetition.

Track `estimated_cost`, `charged_cost`, `actual_cost`, and `cost_source` separately using decimal-safe values. Estimates are not billing. Retry only for a transient failure or a materially changed hypothesis; otherwise preserve the failure and next action. Never treat available budget as authorization for external mutations.

When the reserve would be breached, cost is unknown, or budget is exhausted, stop new paid work, persist usable state, and report the exact resume condition. On resume, verify input fingerprints and artifact existence; invalidate only changed inputs and dependent units, preserving independent completed work and usage history. See [budget control](references/budget-control.md).
