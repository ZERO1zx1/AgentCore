# Budget Policy

Manus Mini implements a rigorous budget management system to ensure that no paid work is ever lost.

## Budget States

- **NORMAL**: Full capabilities enabled.
- **CONSERVE**: Prefer lower-cost models for non-critical tasks.
- **CRITICAL**: Disable optional enhancements (P3/P4). Aggressive checkpointing enabled.
- **EMERGENCY**: Stop all paid execution. Use remaining reserve only for saving outputs and manifests.
- **EXHAUSTED**: All execution stopped.

## Emergency Reserve

The system reserves a portion of the initial budget (default 15%) as an **Emergency Output Reserve**. This reserve is strictly protected and used only for:
- Saving generated artifacts and code implementation.
- Writing the final task manifest and resume instructions.
- Serializing completed analysis.

## Task Priorities

| Priority | Description | Action Under Constraint |
| :--- | :--- | :--- |
| **P0** | Primary Deliverable | Protected until EMERGENCY state |
| **P1** | Correctness Critical | Protected until EMERGENCY state |
| **P2** | Validation | Reduced to targeted critical tests |
| **P3** | Enhancements | Dropped in CONSERVE/CRITICAL states |
| **P4** | Polish | Dropped in CONSERVE/CRITICAL states |
