# Budget-control reference

Use decimal-safe values and retain `estimated_cost`, `charged_cost`, `actual_cost`, and `cost_source` separately. An operation is admissible only when a conservative estimate leaves the reserve intact. Filter candidates by capability before total expected cost, including likely retries.

Retry transient failures or a changed hypothesis only; persist failures and their next hypothesis. On resume, verify fingerprints and artifact existence, invalidate changed inputs and dependent work only, and preserve independent completed units plus usage history.
