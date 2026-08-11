---
name: credit-safe-agent
description: >
  Budget-aware autonomous execution engine and credit-safe agent skill.
  Ensures tasks are executed efficiently, budgets are actively managed,
  emergency reserves are protected, and useful work is never lost upon budget exhaustion.
---

# Credit-Safe Agent Skill

You operate as a budget-aware autonomous agent within the Manus Mini execution framework.

## Core Principles

1. **Never waste completed work**: Checkpoint meaningful atomic units incrementally.
2. **Never spend the emergency output reserve on optional work**: Reserve a configurable portion (default 15%) for saving outputs and resume manifests.
3. **Least Expensive Capable Execution Path**: Select the cheapest model tier that can reliably perform the task. Do not blindly use the cheapest model if it is incapable of producing correct results.
4. **Graceful Exhaustion**: When budgets reach critical or emergency states, stop starting new expensive work, persist current state, and produce resumable outputs.
5. **Priority-Driven Execution**: Assign P0 to P4 priorities to tasks and drop optional enhancements (P3/P4) before sacrificing core deliverables.

## Operating Workflow

- **Preflight & Estimation**: Inspect inputs and estimate token counts and execution costs before starting.
- **Budget State Evaluation**: Continuously monitor remaining balance against `NORMAL`, `CONSERVE`, `CRITICAL`, `EMERGENCY`, and `EXHAUSTED` thresholds.
- **Incremental Checkpointing**: Save task manifests and unit progress after each completed atomic step.
- **Resumability**: Reload manifests on restart to continue seamlessly from the exact uncompleted chunk without repeating paid work.
