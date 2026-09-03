# Source (`src/`)

The AgentCore Python package. `AgentCoreEngine` (in `core/`) coordinates the rest.

| Package | Purpose |
| --- | --- |
| `adapters/` | External provider adapters (`MultiProviderExecutor`) |
| `budget/` | Decimal-safe cost estimation and budget state |
| `checkpoint/` | `TaskManifest` and checkpoint/resume persistence |
| `cli/` | Command-line interface (`python -m src.cli`) |
| `core/` | Engine, orchestrator, planner, executor, modes, policies |
| `ingestion/` | Input routing for repos, text, structured data, PDFs, media |
| `mcp/` | Model Context Protocol (MCP) stdio server |
| `memory/` | Bounded local memory (governance, retrieval, safety, metrics) |
| `models/` | Model registry and capability-based routing |
| `observability/` | Shared read models for CLI/MCP consumers |
| `output/` | Artifact and output management |

See [README.md](../README.md) for the engine architecture and [AGENTS.md](../AGENTS.md) for conventions.
