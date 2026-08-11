# Model Routing Policy

AgentCore uses a capability-aware routing system to select the most cost-effective execution path.

## Model Tiers

| Tier | Capability | Example Tasks |
| :--- | :--- | :--- |
| **Tier 0** | Deterministic | Local parsing, regex, file manipulation |
| **Tier 1** | Economy | Classification, simple summarization |
| **Tier 2** | Balanced | Standard coding, instruction following |
| **Tier 3** | Strong | Complex debugging, architecture reasoning |
| **Tier 4** | Advanced | Multimodal analysis, reasoning-heavy tasks |

## Routing Rules

1. **Capability Match**: The system identifies the required capabilities (e.g., `vision`, `coding`, `reasoning`).
2. **Budget Constraint**: The router filters for models that fit within the current budget state (`NORMAL`, `CONSERVE`, `CRITICAL`).
3. **Efficiency Selection**: Among capable candidates, the router selects the least expensive reliable model according to the active `ExecutionMode`.

## Cost Guard

The system estimates the cost of the next operation before execution. If the estimated cost exceeds the usable budget or dips into the emergency reserve, the engine triggers a graceful pause and checkpoints the current state.
