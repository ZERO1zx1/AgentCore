---
name: credit-safe-agent
description: >
  Budget-aware autonomous execution engine and credit-safe agent skill.
  Ensures tasks are executed efficiently, budgets are actively managed,
  emergency reserves are protected, and useful work is never lost upon budget exhaustion.
---

# Credit-Safe Agent (OpenCode Wrapper)

This skill wraps the canonical AgentCore skill at `skills/credit-safe-agent/SKILL.md`.

## Usage

```
/skill credit-safe-agent
```

## Behavior

When active, this skill enforces Credit-Safe principles:

1. **Never waste completed work**: Checkpoint meaningful atomic units incrementally
2. **Never spend the emergency output reserve on optional work**: Reserve 15% for saving outputs and resume manifests
3. **Least Expensive Capable Execution Path**: Select cheapest model tier that can reliably perform the task
4. **Graceful Exhaustion**: At critical/emergency states, stop expensive work, persist state, produce resumable outputs
5. **Priority-Driven Execution**: Assign P0-P4 priorities, drop P3/P4 before sacrificing core deliverables

## Operating Workflow

- **Preflight & Estimation**: Inspect inputs and estimate costs before starting
- **Budget State Evaluation**: Monitor against NORMAL, CONSERVE, CRITICAL, EMERGENCY, EXHAUSTED
- **Incremental Checkpointing**: Save manifests and unit progress after each atomic step
- **Resumability**: Reload manifests on restart to continue without repeating paid work

The full skill instructions are in the canonical file: `skills/credit-safe-agent/SKILL.md`

This wrapper exists for OpenCode skill discovery. The canonical skill content is the source of truth.