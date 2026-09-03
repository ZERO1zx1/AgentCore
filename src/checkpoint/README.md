# Checkpoint (`src/checkpoint/`)

Persistence and resume support.

- `manifest.py` — `TaskManifest` schema (3.0) for a task's state.
- `manager.py` — `CheckpointManager` for saving/loading manifests.

Checkpoints are stored under `.agentcore/checkpoints/`.
