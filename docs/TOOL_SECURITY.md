# Tool Security

## Overview

AgentCore's TypeScript assistant layer implements comprehensive security controls for tool execution. All tools must pass through multiple validation layers before execution.

## Tool Definition Security

### Risk Levels

Every tool must declare a risk level:
- **read**: Reads files, lists directories, inspects repository (auto-approved by default)
- **write**: Writes files, creates artifacts (requires approval by default)
- **external**: Makes network calls, calls external APIs (requires approval by default)
- **dangerous**: Shell commands, git push, destructive operations (requires approval by default)

### Tool Schema Validation

All tool inputs are validated against Zod schemas at runtime:
```typescript
// Tool definition includes inputSchema
{
  name: "write_file",
  risk: "write",
  inputSchema: z.object({
    path: z.string(),
    content: z.string(),
  }),
  requiresApproval: true,
}
```

## Permission Policy

### Path Allowlist/Blocklist

```typescript
security: {
  allowedPaths: [".", "/workspace"],
  blockedPaths: [".git", ".env", "node_modules", ".agentcore", "__pycache__"],
}
```

- Path traversal attempts (`../`, absolute paths) are blocked
- Windows and Unix path separators both handled
- Symlinks resolved before checking

### Command Allowlist/Blocklist

```typescript
security: {
  allowedCommands: ["python", "npm", "git status"],
  blockedCommands: ["rm -rf", "sudo", "chmod 777", "format", "mkfs"],
}
```

- Only explicitly allowed commands can execute
- Dangerous commands explicitly blocked

## Human Approval

### Default Approval Requirements

| Risk Level | Default Approval | Auto-Approve Config |
|------------|------------------|---------------------|
| read | No | `autoApproveRead: true` |
| write | Yes | `autoApproveWrite: false` |
| external | Yes | N/A |
| dangerous | Yes | N/A |

### Approval Flow

1. Tool execution requested
2. Permission policy checks path/command allowlists
3. If approval required:
   - Emit `approval.required` event
   - Wait for human decision (default 300s timeout)
   - On grant: proceed with execution
   - On deny/timeout: emit `tool.failed` with `HUMAN_APPROVAL_REQUIRED`

### Approval API

```typescript
// Grant approval
approvalManager.grantApproval(approvalId, "user@example.com", "Approved for deployment");

// Deny approval
approvalManager.denyApproval(approvalId, "user@example.com", "Not needed");

// Check pending
const pending = approvalManager.getPendingApprovals();
```

## Secret Redaction

### Automatic Redaction

Secrets are automatically redacted from:
- Logs
- Error messages
- Event streams
- Audit logs

### Detected Patterns

- OpenAI API keys: `sk-...`
- Anthropic API keys: `sk-ant-...`
- GitHub tokens: `ghp_...`, `github_pat_...`
- Google API keys: `AIza...`
- Private keys: `-----BEGIN PRIVATE KEY-----`
- Generic base64 secrets (40+ chars)

### Implementation

```typescript
import { redactSecrets, redactSecretsInObject } from "@agentcore/types";

const safeLog = redactSecrets(userInput);
const safeObject = redactSecretsInObject(apiResponse);
```

## Prompt Injection Detection

### Detected Patterns

The system detects common injection attempts:
- "ignore previous instructions"
- "override safety rules"
- "bypass validation"
- "disregard rules"
- "system: you are now..."
- "act as if you are..."
- "pretend to be..."
- "output only..."
- "do not include..."
- "hide the..."
- "secretly output..."

### Response

On detection:
1. Tool execution blocked
2. `SECURITY_VIOLATION` error emitted
3. Audit log entry created
4. Session may be terminated

```typescript
import { detectPromptInjection } from "@agentcore/types";

const { detected, patterns } = detectPromptInjection(userInput);
if (detected) {
  throw new Error(`Prompt injection detected: ${patterns.join(", ")}`);
}
```

## Untrusted Output Marking

### Purpose

Tool outputs from external sources (web, APIs, user files) are marked as untrusted to prevent downstream injection.

### Marking

```typescript
const UNTRUSTED_PREFIX = "[UNTRUSTED_OUTPUT] ";
const UNTRUSTED_SUFFIX = " [/UNTRUSTED_OUTPUT]";

function markUntrusted(output: string): string {
  return `${UNTRUSTED_PREFIX}${output}${UNTRUSTED_SUFFIX}`;
}
```

### Handling

Downstream consumers should:
1. Check `isUntrusted(output)` before using in prompts
2. Use `extractTrusted(output)` to get clean content
3. Never directly concatenate untrusted output into prompts

## Audit Logging

### Logged Events

- Tool execution requests
- Permission decisions (allow/deny)
- Approval grants/denials
- Budget preflight checks
- Security violations
- Error occurrences

### Log Entry Structure

```typescript
interface AuditLogEntry {
  timestamp: string;
  correlationId: string;
  taskId?: string;
  sessionId?: string;
  userId?: string;
  action: string;
  resource: string;
  decision: "allow" | "deny" | "error";
  reason?: string;
  metadata?: Record<string, unknown>;
}
```

### Correlation IDs

Every request gets a unique correlation ID for tracing:
- Generated at session start
- Propagated through all tool calls
- Included in all log entries
- Returned in error responses

## Network Security

### Default: No Network

By default, tools cannot make network requests:
- `external` risk tools require explicit allowlist
- `allowedCommands` must include network tools
- DNS resolution blocked unless allowed

### Allowlist Configuration

```typescript
security: {
  allowedCommands: ["curl", "wget", "python -m http.client"],
  // Or for specific tools:
  toolOverrides: {
    "http_request": { allowNetwork: true, allowedDomains: ["api.example.com"] }
  }
}
```

## Configuration

### Complete Security Config

```typescript
const config = {
  security: {
    allowedPaths: [".", "/workspace"],
    blockedPaths: [".git", ".env", "node_modules", ".agentcore", "__pycache__"],
    allowedCommands: ["python", "npm", "git"],
    blockedCommands: ["rm -rf", "sudo", "chmod 777"],
    secretRedaction: true,
    promptInjectionDetection: true,
    untrustedOutputMarking: true,
  },
  approval: {
    defaultTimeoutSeconds: 300,
    autoApproveRead: true,
    autoApproveWrite: false,
    requireApprovalFor: ["write", "external", "dangerous"],
  },
};
```

## Best Practices

1. **Least Privilege**: Only grant minimum required permissions
2. **Explicit Allowlists**: Use allowlists, not blocklists
3. **Audit Regularly**: Review audit logs for anomalies
4. **Test Injection**: Regularly test prompt injection detection
5. **Rotate Secrets**: Use short-lived tokens where possible
5. **Monitor Approvals**: Alert on approval denials/timeouts