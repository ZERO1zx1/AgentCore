# Execution Modes

AgentCore supports three distinct execution modes to balance quality, cost, and speed.

| Mode | Priority | Strategy | Use Case |
| :--- | :--- | :--- | :--- |
| **AUTO** | Balanced | Dynamic adjustment based on task and budget | Default for most tasks |
| **FULL** | Quality | Uses best models and broad validation | Complex engineering and high-stakes analysis |
| **CREDIT_SAFE** | Efficiency | Aggressive cost reduction and checkpointing | Large-scale processing and budget-constrained tasks |

## Mode Selection Logic

- **AUTO**: Evaluates task complexity, input size, and remaining budget to decide whether to behave more like FULL or CREDIT_SAFE.
- **FULL**: Disables aggressive scope reduction. Prioritizes P0 and P1 work with the most capable models available.
- **CREDIT_SAFE**: Enables relevance filtering, aggressive checkpointing, and prefers lower-tier capable models.

## Budget Awareness in All Modes

Regardless of the selected mode, AgentCore always:
- Reserves an emergency output buffer (default 15%).
- Checkpoints meaningful progress to prevent loss of paid work.
- Gracefully stops before budget exhaustion.
