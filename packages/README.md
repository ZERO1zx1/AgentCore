# TypeScript Packages

This directory contains the TypeScript assistant layer packages for AgentCore's hybrid architecture.

## Package Overview

```
packages/
├── agentcore-types/      # Shared contracts and schemas
├── agentcore-assistant/  # Agent loop, tool registry, approval, bridge
├── agentcore-mcp/        # MCP server with tools and resources
```

## Packages

### @agentcore/types

Shared TypeScript types and Zod schemas defining the contracts between Python and TypeScript layers.

**Exports:**
- `ToolDefinition`, `ToolCall`, `ToolResult`, `ToolExecutionContext`
- `AgentEvent` types (`task.started`, `tool.requested`, `approval.required`, etc.)
- `TaskInput`, `TaskManifest`, `WorkUnit`, `BudgetInfo`
- `StructuredError`, `ErrorCode`, `ErrorCategory`, `RetryPolicy`
- `BudgetInfo`, `BudgetPreflightRequest`, `BudgetLimitConfig`
- `BridgeRequest`, `BridgeResponse`, `BridgeConfig`
- Validation utilities: `sanitizePath`, `redactSecrets`, `detectPromptInjection`

**Build:** `npm run build --prefix packages/agentcore-types`

### @agentcore/assistant

TypeScript assistant layer with agent loop, tool registry, permission policy, approval manager, session management, and Python bridge client.

**Exports:**
- `Agent` - Main entry point for running tasks
- `ToolRegistry` - Register, validate, manage tools
- `PermissionPolicy` - Path/command allowlists, risk-based approval
- `ApprovalManager` - Human-in-the-loop approval with timeouts
- `Session` - Task execution state machine with retry logic
- `StdioBridgeClient` - stdio transport to Python engine
- `createAgent`, `quickRun` - Convenience functions

**Dependencies:** `@agentcore/types`, `zod`, `uuid`, `eventemitter3`

**Build:** `npm run build --prefix packages/agentcore-assistant`

### @agentcore/mcp

MCP server exposing AgentCore capabilities via standard MCP protocol.

**Exports:**
- `AgentCoreMcpServer` - MCP server with tools and resources
- Tools: `inspect_repository`, `list_repository_files`, `get_file_content`, `search_repository`, `read_file`, `write_file`, `delete_file`, `list_directory`, `agentcore_start_task`, `agentcore_resume_task`, `agentcore_task_status`, `agentcore_cancel_task`, `agentcore_list_tasks`, `agentcore_get_checkpoint`, `agentcore_list_checkpoints`, `agentcore_budget_status`
- Resources: `agentcore://status`, `agentcore://budget`, `agentcore://checkpoints`, `agentcore://events`, `agentcore://task/{id}`, `agentcore://manifest/{id}`, `agentcore://outputs/{id}`

**Dependencies:** `@agentcore/types`, `@agentcore/assistant`, `@modelcontextprotocol/sdk`, `zod`, `uuid`

**Build:** `npm run build --prefix packages/agentcore-mcp`

## Development

### Install Dependencies

```bash
# From repo root
npm ci --prefix packages/agentcore-types
npm ci --prefix packages/agentcore-assistant
npm ci --prefix packages/agentcore-mcp

# Or all at once (requires npm workspaces)
npm install
```

### Build All

```bash
npm run build --prefix packages/agentcore-types
npm run build --prefix packages/agentcore-assistant
npm run build --prefix packages/agentcore-mcp
```

### Type Check All

```bash
npm run typecheck --prefix packages/agentcore-types
npm run typecheck --prefix packages/agentcore-assistant
npm run typecheck --prefix packages/agentcore-mcp
```

### Run Tests

```bash
npm test --prefix packages/agentcore-types
npm test --prefix packages/agentcore-assistant
npm test --prefix packages/agentcore-mcp
```

## Architecture

```
User / Client
    |
    v
@agentcore/assistant (Agent loop, tools, approval, session)
    |
    v
@agentcore/types (Shared contracts)
    |
    v
@agentcore/mcp (MCP server)
    |
    v
Python Bridge (stdio) -> AgentCoreEngine (Python)
```

## Contracts

The `@agentcore/types` package defines all contracts between layers:

1. **Tool Contract** - `ToolDefinition`, `ToolCall`, `ToolResult`
2. **Event Contract** - `AgentEvent` discriminated union
3. **Task Contract** - `TaskInput`, `TaskManifest`, `WorkUnit`, `BudgetInfo`
4. **Error Contract** - `StructuredError`, `ErrorCode`, `RetryPolicy`
5. **Budget Contract** - `BudgetInfo`, `BudgetPreflightRequest`
6. **Bridge Contract** - `BridgeRequest`, `BridgeResponse`
7. **Validation** - Path, secret, injection protection

## Adding a New Tool

### 1. Define in @agentcore/assistant

```typescript
// packages/agentcore-assistant/src/tools/my_tool.ts
import { ToolDefinition } from "@agentcore/types";

export const myTool: ToolDefinition = {
  name: "my_tool",
  description: "Does something useful",
  inputSchema: z.object({...}),
  risk: "write",
  requiresApproval: true,
  estimatedCost: "0.01",
  timeoutSeconds: 30,
};
```

### 2. Register

```typescript
const registry = createDefaultRegistry();
registry.register(myTool);
```

### 3. (Optional) Add to MCP

```typescript
// packages/agentcore-mcp/src/tools/my_tool.ts
export const myMcpTool: ToolDefinition = { ... };

// Add to packages/agentcore-mcp/src/tools/index.ts
export const allMcpTools = [..., myMcpTool];
```

## Security

All packages enforce security at their boundaries:

- `@agentcore/types`: Path traversal, secret redaction, prompt injection detection
- `@agentcore/assistant`: Permission policy, approval manager, audit logging
- `@agentcore/mcp`: Schema validation on all MCP requests

See [Tool Security](../docs/TOOL_SECURITY.md) for details.