# Source (`src/`)

The AgentCore Python execution engine. `AgentCoreEngine` (in `core/`) coordinates the rest.

This is the **Python execution layer** of the hybrid architecture. The TypeScript assistant layer lives in `packages/agentcore-assistant/`.

| Package | Purpose |
| --- | --- |
| `adapters/` | External provider adapters (`MultiProviderExecutor`, `FakeExecutor`) |
| `budget/` | Decimal-safe cost estimation and budget state (`BudgetManager`, `CostEstimator`) |
| `checkpoint/` | `TaskManifest` schema 3.0 and checkpoint/resume persistence |
| `cli/` | Command-line interface (`python -m src.cli`) |
| `core/` | Engine, orchestrator, planner, executor, modes, policies, runtime config |
| `ingestion/` | Input routing for repos, text, structured data, PDFs, media |
| `mcp/` | Model Context Protocol (MCP) stdio server (Python-side, legacy) |
| `memory/` | Bounded local memory (governance, retrieval, safety, metrics) |
| `models/` | Model registry and capability-based routing |
| `observability/` | Shared read models for CLI/MCP consumers |
| `output/` | Artifact and output management |

## Key Classes

- `AgentCoreEngine` - Main entry point, coordinates task execution
- `BudgetManager` - Budget state machine with 15% reserve
- `CheckpointManager` - Persists/resumes `TaskManifest` schema 3.0
- `ModelRouter` - Capability-first model selection with health learning
- `InputRouter` - Routes files/repos to processors, builds `TaskContext`
- `OperationExecutor` - Abstract interface for provider adapters

## Bridge Protocol

The Python engine exposes a stdio bridge for the TypeScript assistant layer:

- Request types: `initialize_task`, `run_next_unit`, `run_to_completion`, `resume_task`, `cancel_task`, `get_status`, `get_budget`, `get_manifest`, `get_context`, `get_events`, `health_check`
- Response types: `task_initialized`, `unit_completed`, `task_completed`, `task_resumed`, `task_cancelled`, `status`, `budget`, `manifest`, `context`, `events`, `health`, `error`, `event_stream`
- JSON Lines over stdin/stdout with event streaming channel

## Conventions

See [AGENTS.md](../AGENTS.md) for contributor conventions.
See [README.md](../README.md) for hybrid architecture overview.