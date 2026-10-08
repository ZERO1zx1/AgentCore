# Development Guide

## Quick Start

### Prerequisites

- Python 3.10+ (CI uses 3.11)
- Node.js 20.17+
- npm 10.8+

### Installation

```bash
# Python dependencies
python -m venv .venv
# Windows:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

python -m pip install -r requirements-dev.txt

# TypeScript dependencies
npm ci --prefix packages/agentcore-types
npm ci --prefix packages/agentcore-assistant
npm ci --prefix packages/agentcore-mcp

# Express example (optional)
npm ci --prefix examples/backend/express
```

### Running Tests

```bash
# Python tests
$env:TEMP=".test-temp"
$env:TMP=".test-temp"
python -m pytest tests -v

# Focused test
python -m pytest tests/test_e2e_pipeline.py -v

# Additional test suites
python -m pytest feat/low_cost_skill/tests -v
python -W error::ResourceWarning -m pytest plugin/ -v

# TypeScript build
npm run build --prefix packages/agentcore-types
npm run build --prefix packages/agentcore-assistant
npm run build --prefix packages/agentcore-mcp

# Express tests
npm test --prefix examples/backend/express
```

### Full Validation (CI equivalent)

```bash
# Python
python -m pytest tests -v
python -m pytest feat/low_cost_skill/tests -v
python -W error::ResourceWarning -m pytest plugin/ -v
python -m compileall src plugin feat examples/backend

# TypeScript
npm run typecheck --prefix packages/agentcore-types
npm run typecheck --prefix packages/agentcore-assistant
npm run typecheck --prefix packages/agentcore-mcp
```

## Project Structure

```
AgentCore/
├── src/                          # Python execution engine
│   ├── core/                     # Engine, planner, executor, orchestrator
│   ├── budget/                   # BudgetManager, CostEstimator
│   ├── checkpoint/               # TaskManifest, CheckpointManager
│   ├── models/                   # ModelRegistry, ModelRouter
│   ├── ingestion/                # InputRouter, PDF, text, structured, repo
│   ├── memory/                   # LocalMemoryStore, governance, safety
│   ├── output/                   # ArtifactManager, OutputManager
│   ├── mcp/                      # Python MCP server (legacy)
│   ├── cli/                      # CLI entry point
│   └── adapters/                 # Provider executors
├── packages/
│   ├── agentcore-types/          # Shared TypeScript contracts
│   │   ├── src/
│   │   │   ├── tool.ts           # ToolDefinition, ToolCall, ToolResult
│   │   │   ├── events.ts         # AgentEvent types
│   │   │   ├── task.ts           # TaskInput, TaskManifest, WorkUnit
│   │   │   ├── errors.ts         # StructuredError, ErrorCode, RetryPolicy
│   │   │   ├── budget.ts         # BudgetInfo, BudgetPreflight
│   │   │   ├── bridge.ts         # BridgeRequest, BridgeResponse
│   │   │   └── validation.ts     # Path, secret, injection protection
│   │   └── package.json
│   ├── agentcore-assistant/      # TypeScript assistant layer
│   │   ├── src/
│   │   │   ├── agent.ts          # Main Agent class
│   │   │   ├── registry.ts       # ToolRegistry
│   │   │   ├── policy.ts         # PermissionPolicy
│   │   │   ├── approval.ts       # ApprovalManager
│   │   │   ├── session.ts        # Session state machine
│   │   │   ├── bridge.ts         # StdioBridgeClient
│   │   │   ├── loop.ts           # Agent loop controller
│   │   │   ├── config.ts         # Configuration
│   │   │   └── errors.ts         # AssistantError
│   │   └── package.json
│   └── agentcore-mcp/            # MCP server
│       ├── src/
│       │   ├── server.ts         # AgentCoreMcpServer
│       │   ├── tools/            # Repository, file, task, checkpoint tools
│       │   └── resources/        # Task, budget, checkpoint, event resources
│       └── package.json
├── examples/
│   └── backend/
│       └── express/              # Credit-safe Express example
├── plugin/                       # OpenCode plugin (scanner, installer)
├── feat/
│   └── low_cost_skill/           # Low-cost skill POC
├── references/                   # Architecture docs
├── tests/                        # Python test suite
├── requirements.txt              # Python runtime deps
├── requirements-dev.txt          # Python dev deps
├── package.json                  # Root workspace config
└── AGENTS.md                     # Contributor guide
```

## Adding a New Tool

### 1. Define Tool in TypeScript

```typescript
// packages/agentcore-assistant/src/tools/my_tool.ts
import { ToolDefinition } from "@agentcore/types";

export const myTool: ToolDefinition = {
  name: "my_tool",
  description: "Does something useful",
  inputSchema: z.object({
    param1: z.string(),
    param2: z.number().optional(),
  }),
  risk: "write",
  requiresApproval: true,
  estimatedCost: "0.01",
  timeoutSeconds: 30,
};
```

### 2. Register Tool

```typescript
// In session setup or agent config
const registry = createDefaultRegistry();
registry.register(myTool);
```

### 3. Implement Handler (Python side if needed)

If the tool needs Python execution, add to `src/core/executor.py` or create a new provider adapter.

## Adding a New MCP Tool

### 1. Create Tool Definition

```typescript
// packages/agentcore-mcp/src/tools/my_tool.ts
import { ToolDefinition } from "@agentcore/types";

export const myMcpTool: ToolDefinition = {
  name: "agentcore_my_tool",
  description: "MCP-accessible tool",
  inputSchema: z.object({...}),
  risk: "read",
  requiresApproval: false,
};
```

### 2. Add to Tool Index

```typescript
// packages/agentcore-mcp/src/tools/index.ts
export const allMcpTools = [
  ...repositoryTools,
  ...fileTools,
  ...taskTools,
  ...checkpointTools,
  myMcpTool,  // Add here
];
```

## Debugging

### Python Debugging

```bash
# Run with debug logging
python -m src.core.engine --prompt "test" --task-id debug --budget 10

# With breakpoints (VS Code)
# Add to launch.json:
{
  "type": "python",
  "request": "launch",
  "module": "src.core.engine",
  "args": ["--prompt", "test", "--task-id", "debug", "--budget", "10"],
  "console": "integratedTerminal",
}
```

### TypeScript Debugging

```bash
# Build with source maps
npm run build --prefix packages/agentcore-assistant

# Debug with Node inspector
node --inspect-brk packages/agentcore-assistant/dist/agent.js
```

### Bridge Debugging

```bash
# Enable bridge debug logs
DEBUG=bridge python -m src.core.engine --bridge stdio

# Or in TypeScript
const bridge = createBridge({ transport: "stdio", timeoutMs: 60000 });
bridge.on("event", (e) => console.log("[EVENT]", e));
```

## Common Issues

### Python: pypdf not available

```bash
pip install pypdf>=6.1.3
```

### TypeScript: Module not found

```bash
# Rebuild dependencies
npm run build --prefix packages/agentcore-types
npm run build --prefix packages/agentcore-assistant
npm run build --prefix packages/agentcore-mcp
```

### Bridge Connection Failed

1. Check Python executable path in config
2. Verify `-m src.core.engine` works: `python -m src.core.engine --help`
3. Check working directory permissions
4. Ensure stdio pipes not blocked by antivirus

### Budget Errors

- `BUDGET_EXCEEDED`: Increase budget or reduce scope
- `DEPENDENCY_UNAVAILABLE`: Install missing dependency (e.g., pypdf)
- `RESERVE_REACHED`: 15% reserve hit, cannot start new work

## Code Style

### Python

- Black formatting: `black src/`
- Type hints required
- Docstrings for public functions
- Decimal for money: `Decimal(str(value))`

### TypeScript

- ESLint: `npm run lint --prefix packages/agentcore-assistant`
- Strict mode enabled
- Zod schemas for all external data
- No `any` types (use `unknown`)

## Contributing

1. Read AGENTS.md
2. Run full test suite before committing
3. No `git add -A` - stage specific files
4. No auto-commit/push
5. Update docs for behavior changes

## Release Process

1. Update version in `package.json` and `pyproject.toml`
2. Run full validation suite
3. Create git tag
4. Publish to npm (TypeScript) and PyPI (Python)