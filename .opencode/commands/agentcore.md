---
name: agentcore
description: Load AgentCore project context, show status, and identify relevant skills
---

# /agentcore — AgentCore Entry Command

Loads the AgentCore project context and displays current status.

## Usage

```
/agentcore
```

## Behavior

1. Reads `AGENTS.md` for project instructions
2. Shows repository state (branch, working tree)
3. Displays current task/checkpoint if any
4. Shows budget state if a task is active
5. Identifies relevant skills (code-engineer, credit-safe-agent)
6. Lists recent `.agentcore/` activity

## Output Example

```
AgentCore — ZERO1zx1/AgentCore
Branch: main | Working Tree: clean

Current Task: demo_task (CREDIT_SAFE)
Checkpoint: .agentcore/checkpoints/demo_task_manifest.json
Budget: $7.50 / $10.00 used (CRITICAL)
Progress: 3/5 units completed

Relevant Skills:
- code-engineer (repository work)
- credit-safe-agent (budget-aware execution)

Recent Activity:
- 2026-08-20 12:30: Budget exhaustion checkpoint saved
- 2026-08-20 12:25: Git push attempted (fallback saved)
```