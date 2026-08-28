# Checkpointing and resuming

`CheckpointManager` writes `.agentcore/checkpoints/{task_id}_manifest.json` by default, after initialization and each attempted unit. It retains the newest 100 manifests unless `max_manifests` is changed.

Schema 3.0 manifests store task input, progress, budget snapshot, outputs, errors, usage/model history, serialized context, work units, and orchestration route. They are inspectable resume state, not a secret store.

Set `TaskInput.resume_task_id` to restore state. AgentCore recomputes source fingerprints, reopens completed units affected by a changed source, and also reopens dependent units; unrelated completed work remains complete. A larger supplied resume budget can raise the initial budget but does not erase recorded usage.

At emergency/exhausted state, AgentCore saves a partial manifest and calls configured Git/notification managers. Automated Git persistence is restricted to the explicit checkpoint file and must never stage unrelated work. See [output contract](output-contract.md).
