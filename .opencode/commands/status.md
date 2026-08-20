---
name: status
description: Show AgentCore repository, task, checkpoint, and budget state
---

# /status — AgentCore Status

Displays current AgentCore state from real persisted data.

## Usage

```
/status
```

## Behavior

Inspects actual files and shows:

- **Repository**: Git branch, status, uncommitted changes
- **Current Task**: Active task ID from checkpoints
- **Checkpoint**: Latest manifest file and timestamp
- **Budget State**: Initial/used/remaining/reserved from manifest
- **Progress**: Completed/total units, current unit
- **Execution Mode**: AUTO/FULL/CREDIT_SAFE
- **Skills**: Which skills are relevant for current work

## Data Sources

- `.agentcore/checkpoints/*.json` — Task manifests
- `.agentcore/tasks/*/` — Per-task artifacts
- `.agentcore/notifications.log` — Budget exhaustion events
- `.agentcore/git_fallback/` — Failed git push payloads
- `git status` — Working tree state