# Core (`src/core/`)

The execution engine and its orchestration.

- `engine.py` — `AgentCoreEngine`: coordinates routing, planning, scheduling, execution, budget, artifacts, and checkpoints.
- `orchestrator.py` — `AdaptiveOrchestrator`.
- `planner.py` — `Planner` / `Scheduler` and `WorkUnit` definitions.
- `executor.py` — `OperationExecutor` interface and the `FakeExecutor` demo.
- `modes.py` — `ExecutionMode` (`AUTO`, `FULL`, `CREDIT_SAFE`).
- `task.py` — `TaskInput`.
- `policy.py` — operating policy rules.
- `route_learning.py` — local route-health learning.
- `context.py` / `context_resolver.py` — task context resolution.
- `runtime_config.py` — `RuntimeConfig`.
- `notifications.py` — notification helpers.
- `execution_result.py` — `ExecutionResult`.
