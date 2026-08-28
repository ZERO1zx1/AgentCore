# Execution modes

Mode changes preferred routing and optional-work policy; it never waives capability requirements, budget reserve, validation, or authorization.

| Mode | Preferred routing | Optional work |
| --- | --- | --- |
| `AUTO` | Tier 2 when normal, Tier 1 when conserving/critical. | Skip P3/P4 at critical or worse. |
| `FULL` | Tier 3 for coding, Tier 2 otherwise, while normal/conserve. | Retained at normal; critical/emergency rules still apply. |
| `CREDIT_SAFE` | Tier 2 for coding, Tier 1 otherwise. | Skipped once the state is not normal. |

Routing is capability-first. If the preferred tier lacks a capable enabled model, the registry falls back to the least-priced capable model. If no capable model exists, the unit is blocked as `PROVIDER_NOT_CONFIGURED`. See [budget policy](budget-policy.md) and [model routing](model-routing.md).
