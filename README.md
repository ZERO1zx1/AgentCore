# AgentCore

AgentCore is a **hybrid Python/TypeScript AI agent execution engine** with a clean separation between the TypeScript assistant layer and the Python execution engine. It provides provider-agnostic, budget-aware execution for repositories, text, data, PDFs, and verified media attachments.

## Architecture

```text
User / OpenCode / Web Client
          |
          v
TypeScript Assistant Layer (packages/agentcore-assistant)
 ├── Agent loop
 ├── Tool registry (packages/agentcore-types)
 ├── MCP server/client (packages/agentcore-mcp)
 ├── Zod schema validation
 ├── Permission and approval policy
 ├── Streaming events
 ├── Session/context adapter
 └── Python bridge client (stdio transport)
          |
          v
Python AgentCore Engine (src/)
 ├── InputRouter
 ├── Planner / Scheduler
 ├── ModelRouter
 ├── BudgetManager
 ├── CheckpointManager
 ├── Memory
 ├── OperationExecutor
 └── Artifact/report manager
```

## Key Features

- **Provider-agnostic**: Swap LLM providers (OpenAI, Anthropic, Gemini, Ollama) via `OperationExecutor` adapter
- **Budget-aware**: Decimal-only money, 15% reserve, preflight checks, provider-confirmed costs
- **Resumable**: Checkpoint/resume with granular source invalidation (schema 3.0)
- **Secure by default**: Path allowlists, secret redaction, prompt injection detection, human approval
- **MCP integration**: Standard MCP server for IDE/client integration
- **Streaming events**: Real-time observability via structured event stream

## Quick Start

### Python Engine Only

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest tests -v
```

```python
from src.core.engine import AgentCoreEngine
from src.core.executor import FakeExecutor
from src.core.task import TaskInput

engine = AgentCoreEngine(executor=FakeExecutor())
engine.initialize_task(TaskInput(
    prompt="Inspect this repository and summarize its structure",
    task_id="demo", repository=".", budget=10.0,
))
print(engine.run_to_completion())
```

### Full Hybrid Stack (TypeScript + Python)

```bash
# Python dependencies
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows
python -m pip install -r requirements-dev.txt

# TypeScript dependencies
npm ci --prefix packages/agentcore-types
npm ci --prefix packages/agentcore-assistant
npm ci --prefix packages/agentcore-mcp

# Run TypeScript agent
node packages/agentcore-assistant/dist/agent.js
```

```typescript
import { createAgent } from "@agentcore/assistant";

const agent = createAgent({
  budgetLimits: { maxTotalCost: "10.0" },
  security: { allowedPaths: ["."] },
});

const manifest = await agent.runTask({
  prompt: "Analyze this repository",
  taskId: "demo",
  budget: "10.0",
  repository: ".",
});
```

### MCP Server

```bash
# Start MCP server
node packages/agentcore-mcp/dist/index.js
```

Then configure your MCP client (e.g., VS Code, Cursor) to connect.

## Modes and Budget Safety

| Mode | Intent |
| --- | --- |
| `AUTO` | Practical default; adapts preferred tier to budget state. |
| `FULL` | Prefers stronger coding routes while the budget allows. |
| `CREDIT_SAFE` | Prefers the lowest capable route and drops optional work early. |

The engine reserves 15% of the initial budget by default. It distinguishes `estimated_cost`, `charged_cost`, `actual_cost`, and `cost_source`; only adapter-supplied cost can be provider-confirmed. See [Budget policy](references/budget-policy.md) and [execution modes](references/execution-modes.md).

## Provider Adapters

Implement `OperationExecutor.execute(unit_type, model_id, prompt, context)` and return `ExecutionResult`. Register accurate production `ModelSpec` values in an injected `ModelRegistry`. Media delivered as verified path descriptors in `context["attachments"]` (path, MIME, modality, size, SHA-256). Binary/base64 content never appended to prompts.

Built-in adapters:
- `FakeExecutor` - Offline demo, deterministic
- `MultiProviderExecutor` - OpenAI, Anthropic, Gemini, Ollama

## Security

- **Path allowlists/blocklists** - Repository root boundary enforced
- **Secret redaction** - API keys, tokens automatically redacted from logs
- **Prompt injection detection** - Pattern-based injection prevention
- **Human approval** - Required for write, external, dangerous operations
- **Audit logging** - Correlation IDs, permission decisions tracked
- **Untrusted output marking** - Tool outputs marked for safe handling

See [Tool Security](docs/TOOL_SECURITY.md) for details.

## Development

```bash
# Python tests
$env:TEMP=".test-temp"; $env:TMP=".test-temp"
python -m pytest tests -v

# TypeScript build
npm run build --prefix packages/agentcore-types
npm run build --prefix packages/agentcore-assistant
npm run build --prefix packages/agentcore-mcp

# Full validation (CI)
python -m pytest tests -v
python -m pytest feat/low_cost_skill/tests -v
python -W error::ResourceWarning -m pytest plugin/ -v
python -m compileall src plugin feat examples/backend

npm run typecheck --prefix packages/agentcore-types
npm run typecheck --prefix packages/agentcore-assistant
npm run typecheck --prefix packages/agentcore-mcp
```

See [Development Guide](docs/DEVELOPMENT.md) for details.

## Documentation

### Deep Research Scan

```bash
python -m src.cli full-scan --repo . --deep-research
python -m src.cli deep-scan --repo . --approve-research --package pypdf --request-limit 20
```

Collect local static/import/duplicate evidence, then approved public GitHub,
PyPI and OSV evidence with explicit request limits. Reports include HTML,
Markdown, JSON and black/white architecture diagrams. See
[implemented scope and boundaries](docs/DEEP_RESEARCH_SCAN.md) and the
[deep-research agent workflow](skills/deep-research-scan/SKILL.md).

- [Hybrid Architecture](docs/HYBRID_ARCHITECTURE.md) - Architecture overview
- [Tool Security](docs/TOOL_SECURITY.md) - Security controls
- [Development Guide](docs/DEVELOPMENT.md) - Contributing guide
- [References](references/) - Budget, checkpointing, model routing, execution modes

## License

MIT License.
