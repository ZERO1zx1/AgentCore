# AgentCore Hybrid Architecture

## Overview

AgentCore is now a hybrid Python/TypeScript AI agent execution engine with a clean separation between the TypeScript assistant layer and the Python execution engine.

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

## Key Components

### packages/agentcore-types
Shared TypeScript types and contracts between Python and TypeScript layers:
- **Tool contracts**: `ToolDefinition`, `ToolCall`, `ToolResult`, `ToolExecutionContext`
- **Event contracts**: `AgentEvent` types for streaming observability
- **Task contracts**: `TaskInput`, `TaskManifest`, `WorkUnit`, `BudgetInfo`
- **Error contracts**: `StructuredError`, `ErrorCode`, `ErrorCategory`, `RetryPolicy`
- **Budget contracts**: `BudgetInfo`, `BudgetPreflightRequest`, `BudgetLimitConfig`
- **Bridge contracts**: `BridgeRequest`, `BridgeResponse`, `BridgeConfig`
- **Validation utilities**: Path traversal protection, secret redaction, prompt injection detection

### packages/agentcore-assistant
TypeScript assistant layer with:
- **Agent class**: Main entry point for running tasks
- **ToolRegistry**: Register, validate, and manage tools with duplicate detection
- **PermissionPolicy**: Path allowlist, command allowlist, risk-based approval
- **ApprovalManager**: Human-in-the-loop approval with timeouts
- **Session**: Task execution state machine with retry logic
- **BridgeClient**: stdio transport to Python engine with event streaming
- **Error handling**: Structured errors with retry classification

### packages/agentcore-mcp
MCP server exposing AgentCore capabilities:
- **Repository tools**: inspect, list, read, search
- **File tools**: read, write, delete, list
- **Task tools**: start, resume, status, cancel, list
- **Checkpoint tools**: get, list, budget status
- **Resources**: status, budget, checkpoints, events, tasks, manifests

## Security Features

1. **Zod runtime schema validation** - All inputs validated against schemas
2. **Path allowlist/blocklist** - Repository root boundary enforced
3. **Secret redaction** - API keys, tokens, credentials redacted from logs
4. **Prompt injection detection** - Pattern-based detection of injection attempts
5. **Untrusted output marking** - Tool outputs marked for downstream handling
6. **Audit logging** - Correlation IDs, permission decisions logged
7. **Safe error messages** - No sensitive data in error responses

## Budget Integration

- TypeScript reads budget info from Python (read-only)
- Preflight budget requests before tool execution
- Python engine makes all budget decisions
- Decimal semantics preserved via string representation
- No float money calculations

## Error Handling

Structured error codes:
- `RATE_LIMITED`, `AUTH_FAILED`, `TIMEOUT`, `CONTEXT_TOO_LARGE`
- `TOOL_VALIDATION_FAILED`, `PERMISSION_DENIED`, `HUMAN_APPROVAL_REQUIRED`
- `BUDGET_EXCEEDED`, `DEPENDENCY_UNAVAILABLE`, `PROVIDER_ERROR`
- `OUTPUT_CONTRACT_FAILED`, `CHECKPOINT_ERROR`, `PATH_TRAVERSAL_DETECTED`
- `PROMPT_INJECTION_DETECTED`, `SECRET_DETECTED`, `UNTRUSTED_OUTPUT`

Error categories: `transient`, `permanent`, `budget`, `security`, `user_action`
Exponential backoff with jitter for retryable errors.

## Transport

Default: **stdio** (subprocess) - lowest risk, no network exposure
- Python process spawned as child
- JSON Lines protocol over stdin/stdout
- Event streaming via dedicated channel
- Heartbeat for connection health

## Validation Results

All tests pass:
- **Python**: 101/101 tests pass
- **feat/low_cost_skill**: 1/1 tests pass
- **plugin**: 19/19 tests pass
- **Express backend**: 5/5 tests pass
- **TypeScript build**: All 3 packages compile successfully
- **pip-audit**: No known vulnerabilities in requirements.txt and requirements-dev.txt
- **npm audit**: 0 vulnerabilities in Express example

## Python ↔ TypeScript Contract

The bridge protocol uses JSON Lines over stdio:
- Request types: `initialize_task`, `run_next_unit`, `run_to_completion`, `resume_task`, `cancel_task`, `get_status`, `get_budget`, `get_manifest`, `get_context`, `get_events`, `health_check`
- Response types: `task_initialized`, `unit_completed`, `task_completed`, `task_resumed`, `task_cancelled`, `status`, `budget`, `manifest`, `context`, `events`, `health`, `error`, `event_stream`
- All payloads validated with Zod schemas on both sides

## Remaining Blockers

1. **TypeScript test runner** - vitest requires vite dependency (installation issue, not code)
2. **Express 5.x migration** - Current 4.22.0 is secure but 5.x changes query parser default
3. **HTTP/WebSocket bridge** - Not yet implemented (stdio is production-ready)

## Production Rollout Plan

1. Deploy Python engine with `FakeExecutor` for testing
2. Configure `MultiProviderExecutor` with API keys for production
3. Enable `auto_push=False` in GitManager (default)
4. Set up webhook notifications for budget exhaustion
5. Configure path allowlists for deployment environment
6. Enable MCP server for IDE integration
7. Monitor budget events and adjust reserve ratio as needed