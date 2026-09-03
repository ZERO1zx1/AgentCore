# Budget (`src/budget/`)

Decimal-safe budget accounting.

- `estimator.py` — cost estimation for work units.
- `state.py` — budget state (used / remaining / reserved) and the default 15% reserve.

Costs are never presented as confirmed billing unless a provider adapter
supplies them.
