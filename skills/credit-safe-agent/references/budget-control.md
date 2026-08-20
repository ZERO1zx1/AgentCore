# Budget control

## Accounting

Use decimal-safe arithmetic for currency. Keep `estimated_cost`, `charged_cost`, `actual_cost`, and `cost_source` separate. Reconcile provider-reported usage when available without deleting the earlier estimate. Never log credentials or full private prompts with usage events.

An operation is admissible only when its conservative upper estimate leaves the reserve intact. Unknown-cost paid operations are not admissible near the reserve unless they are necessary P0 rescue work and a hard provider/tool limit prevents overspend.

## Routing

Filter candidates by required capabilities first (language, context, vision/audio, tool use, structured output), then compare total expected cost including retries. Cached results and focused context reduce both cost and variance. A cheaper incapable route that predictably retries is not credit-safe.

## Retry policy

Retry only transient failures or a changed hypothesis. Cap attempts per work unit. Do not repeat an identical paid call after a deterministic failure, invalid request, permission denial, or exhausted quota. Persist the failure and next hypothesis before retrying.

## Resume

On resume, verify source fingerprints and artifact existence. Invalidate only units whose inputs changed and their dependents. Preserve independent completed units and accumulated usage history.
