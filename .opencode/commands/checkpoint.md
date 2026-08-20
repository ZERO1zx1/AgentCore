---
name: checkpoint
description: Manually trigger AgentCore checkpoint save
---

# /checkpoint — Manual Checkpoint

Forces an immediate checkpoint save of the current AgentCore task state.

## Usage

```
/checkpoint [task_id]
```

## Behavior

1. Loads current task manifest (or specified task_id)
2. Persists current context, work units, usage history
3. Saves to `.agentcore/checkpoints/{task_id}_manifest.json`
4. Updates `.agentcore/tasks/{task_id}/checkpoints/`
5. Reports saved state

## Use Cases

- Before risky operations
- Before switching tasks
- After significant progress
- Before budget might be exhausted

## Output Example

```
Checkpoint saved for task: demo_task
Manifest: .agentcore/checkpoints/demo_task_manifest.json
Context: 3 work units, 2 completed, 1 in_progress
Budget: $7.50 / $10.00 used
Artifacts: 4 files in .agentcore/tasks/demo_task/artifacts/
```