# Budget policy

`BudgetManager` uses `decimal.Decimal` and tracks initial, used, remaining, reserved, and usable budget. It does not discover provider balance or authorize spending.

| State | Trigger | Result |
| --- | --- | --- |
| `NORMAL` | More than 50% remains. | Regular routing. |
| `CONSERVE` | 50% or less remains. | Lower preferred tiers where capable. |
| `CRITICAL` | 25% or less remains. | Optional P3/P4 work is skipped. |
| `EMERGENCY` | 10% or less remains, or a reserve boundary is reached. | No new unit starts; state is persisted. |
| `EXHAUSTED` | No budget remains. | No execution starts; state is persisted/reported. |

The reserve is 15% by default and wins over percentage labels. `can_afford()` rejects an operation that would enter it. For every attempted unit, preserve `estimated_cost`, `charged_cost`, `actual_cost`, and `cost_source`. `actual_cost` is provider-confirmed only when returned by the adapter; otherwise the charged estimate is marked `estimate`.

P0 is the required deliverable, P1 core correctness/final output, P2 important validation, P3 enhancement, and P4 polish or experiments. See [execution modes](execution-modes.md) and [checkpointing](checkpointing.md).
