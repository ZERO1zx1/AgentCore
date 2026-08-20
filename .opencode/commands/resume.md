---
name: resume
description: Resume AgentCore task from last checkpoint
---

# /resume — Resume from Checkpoint

Resumes an AgentCore task from the last saved checkpoint, inspecting real persisted state.

## Usage

```
/resume [task_id] [--budget <amount>]
```

## Behavior

1. Lists available checkpoints if no task_id provided
2. Loads manifest for task_id
3. Shows:
   - Completed units (won't be re-executed)
   - Invalidated units (source changed)
   - Pending units (next to execute)
   - Remaining budget
   - Source fingerprints vs current
4. Optionally adds more budget
5. Re-initializes engine with resume_task_id
6. Continues from exact uncompleted chunk

## Output Example

```
Resuming task: demo_task
Manifest: .agentcore/checkpoints/demo_task_manifest.json (2026-08-20 12:30)

Progress: 3/5 units completed
Completed: unit_inspect, unit_implementation, unit_validation
Invalidated: unit_polish (source changed: src/core/engine.py)
Pending: unit_polish, unit_output

Budget: $10.00 initial, $7.50 used, $2.50 remaining, $1.50 reserved
State: CRITICAL

Source Changes:
- src/core/engine.py (fingerprint mismatch)

Ready to resume with unit_polish.
Run: python -m src.core.engine --resume demo_task --budget 20.0
```