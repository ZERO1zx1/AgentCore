import { z } from 'zod'
import type { ToolCall, ToolDefinition, ToolExecutionContext } from './tool.js'
import type { TaskInput, TaskManifest, BudgetInfo } from './task.js'
import type { AgentEvent } from './events.js'
import type { BridgeRequest, BridgeResponse } from './bridge.js'

/**
 * Validation result
 */
export interface ValidationResult<T> {
  ok: boolean
  data?: T
  errors: ValidationError[]
}

export interface ValidationError {
  path: string
  message: string
  code: string
}

/**
 * Validate data against Zod schema
 */
export function validate<T> (
  schema: z.ZodSchema<T>,
  data: unknown
): ValidationResult<T> {
  const result = schema.safeParse(data)
  if (result.success) {
    return { ok: true, data: result.data, errors: [] }
  }
  return {
    ok: false,
    errors: result.error.issues.map(issue => ({
      path: issue.path.join('.'),
      message: issue.message,
      code: issue.code
    }))
  }
}

/**
 * Validate tool call input against tool definition
 */
export function validateToolInput (
  tool: ToolDefinition,
  input: unknown
): ValidationResult<unknown> {
  // If inputSchema is a Zod schema, use it directly
  if (
    tool.inputSchema &&
    typeof tool.inputSchema === 'object' &&
    'safeParse' in tool.inputSchema
  ) {
    return validate(tool.inputSchema as z.ZodSchema, input)
  }
  // If inputSchema is a JSON Schema object, convert to Zod
  if (tool.inputSchema && typeof tool.inputSchema === 'object') {
    try {
      const zodSchema = jsonSchemaToZod(tool.inputSchema)
      return validate(zodSchema, input)
    } catch {
      // Fallback: basic object check
      if (input && typeof input === 'object') {
        return { ok: true, data: input, errors: [] }
      }
      return {
        ok: false,
        errors: [
          { path: '', message: 'Input must be an object', code: 'invalid_type' }
        ]
      }
    }
  }
  // No schema - allow any input
  return { ok: true, data: input, errors: [] }
}

/**
 * Convert JSON Schema to Zod schema (basic implementation)
 */
function jsonSchemaToZod (schema: unknown): z.ZodSchema {
  const s = schema as Record<string, unknown>
  const type = s['type'] as string

  switch (type) {
    case 'string':
      return z.string()
    case 'number':
      return z.number()
    case 'integer':
      return z.number().int()
    case 'boolean':
      return z.boolean()
    case 'array':
      return z.array(jsonSchemaToZod(s['items'] as Record<string, unknown>))
    case 'object':
      const properties = s['properties'] as Record<string, unknown> | undefined
      const required = (s['required'] as string[]) || []
      if (!properties) return z.record(z.unknown())
      const shape: Record<string, z.ZodSchema> = {}
      for (const [key, value] of Object.entries(properties)) {
        shape[key] = jsonSchemaToZod(value as Record<string, unknown>)
      }
      const obj = z.object(shape)
      return required.length > 0 ? obj.strict() : obj.partial()
    default:
      return z.unknown()
  }
}

/**
 * Validate task input
 */
export function validateTaskInput (input: unknown): ValidationResult<TaskInput> {
  // Import TaskInputSchema dynamically to avoid circular dependency
  const { TaskInputSchema } = require('./task.js')
  return validate(TaskInputSchema, input)
}

/**
 * Validate task manifest
 */
export function validateTaskManifest (
  manifest: unknown
): ValidationResult<TaskManifest> {
  const { TaskManifestSchema } = require('./task.js')
  return validate(TaskManifestSchema, manifest)
}

/**
 * Validate budget info
 */
export function validateBudgetInfo (
  budget: unknown
): ValidationResult<BudgetInfo> {
  const { BudgetInfoSchema } = require('./budget.js')
  return validate(BudgetInfoSchema, budget)
}

/**
 * Validate agent event
 */
export function validateAgentEvent (
  event: unknown
): ValidationResult<AgentEvent> {
  const { AgentEventSchema } = require('./events.js')
  return validate(AgentEventSchema, event)
}

/**
 * Validate bridge request
 */
export function validateBridgeRequest (
  request: unknown
): ValidationResult<BridgeRequest> {
  const { BridgeRequestSchema } = require('./bridge.js')
  return validate(BridgeRequestSchema, request)
}

/**
 * Validate bridge response
 */
export function validateBridgeResponse (
  response: unknown
): ValidationResult<BridgeResponse> {
  const { BridgeResponseSchema } = require('./bridge.js')
  return validate(BridgeResponseSchema, response)
}

/**
 * Path traversal protection
 */
export const PathTraversalSchema = z.string().refine(
  path => {
    // Check for path traversal attempts
    const normalized = path.replace(/\\/g, '/')
    if (normalized.includes('..')) return false
    if (normalized.startsWith('/')) return false
    if (normalized.match(/^[a-zA-Z]:/)) return false // Windows absolute paths
    return true
  },
  { message: 'Path traversal detected' }
)

/**
 * Sanitize file path for safety
 */
export function sanitizePath (
  path: string,
  baseDir: string
): { ok: boolean; path?: string; error?: string } {
  try {
    const resolvedBase = new URL(`file://${baseDir.replace(/\\/g, '/')}`)
      .pathname
    const resolvedPath = new URL(`file://${path.replace(/\\/g, '/')}`).pathname

    if (!resolvedPath.startsWith(resolvedBase)) {
      return { ok: false, error: 'Path escapes base directory' }
    }

    const result = PathTraversalSchema.safeParse(path)
    if (!result.success) {
      return { ok: false, error: 'Path traversal detected' }
    }

    return { ok: true, path: resolvedPath }
  } catch {
    return { ok: false, error: 'Invalid path' }
  }
}

/**
 * Secret redaction patterns
 */
const SECRET_PATTERNS = [
  /sk-[a-zA-Z0-9]{20,}/g, // OpenAI API keys
  /sk-ant-[a-zA-Z0-9_-]{20,}/g, // Anthropic API keys
  /ghp_[a-zA-Z0-9]{36}/g, // GitHub personal access tokens
  /github_pat_[a-zA-Z0-9_]{20,}/g, // GitHub fine-grained tokens
  /gho_[a-zA-Z0-9]{36}/g, // GitHub OAuth tokens
  /ghu_[a-zA-Z0-9]{36}/g, // GitHub user tokens
  /ghs_[a-zA-Z0-9]{36}/g, // GitHub server tokens
  /ghr_[a-zA-Z0-9]{36}/g, // GitHub refresh tokens
  /xoxb-[a-zA-Z0-9-]{20,}/g, // Slack bot tokens
  /xoxp-[a-zA-Z0-9-]{20,}/g, // Slack user tokens
  /xapp-[a-zA-Z0-9-]{20,}/g, // Slack app tokens
  /AIza[a-zA-Z0-9_-]{35}/g, // Google API keys
  /ya29\.[a-zA-Z0-9_-]{20,}/g, // Google OAuth tokens
  /[a-zA-Z0-9+/]{40,}={0,2}/g, // Generic base64 secrets (conservative)
  /-----BEGIN [A-Z ]*PRIVATE KEY-----/g // Private keys
]

/**
 * Redact secrets from string
 */
export function redactSecrets (text: string): string {
  let result = text
  for (const pattern of SECRET_PATTERNS) {
    result = result.replace(pattern, '[REDACTED]')
  }
  return result
}

/**
 * Redact secrets from object recursively
 */
export function redactSecretsInObject (obj: unknown): unknown {
  if (typeof obj === 'string') {
    return redactSecrets(obj)
  }
  if (Array.isArray(obj)) {
    return obj.map(redactSecretsInObject)
  }
  if (obj && typeof obj === 'object') {
    const result: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(obj)) {
      // Skip keys that look like secrets
      if (/^(password|secret|token|key|credential|auth)$/i.test(key)) {
        result[key] = '[REDACTED]'
      } else {
        result[key] = redactSecretsInObject(value)
      }
    }
    return result
  }
  return obj
}

/**
 * Prompt injection detection
 */
const INJECTION_PATTERNS = [
  /ignore\s+(?:previous|prior|above|earlier)\s+(?:instructions?|prompts?|rules?)/i,
  /override\s+(?:instructions?|prompts?|rules?|policies?)/i,
  /bypass\s+(?:safety|security|validation|checks?)/i,
  /disregard\s+(?:instructions?|prompts?|rules?)/i,
  /forget\s+(?:instructions?|prompts?|rules?)/i,
  /system\s*:\s*you\s+are\s+now/i,
  /act\s+as\s+(?:if|though)\s+you\s+are/i,
  /pretend\s+to\s+be/i,
  /roleplay\s+as/i,
  /simulate\s+(?:a\s+)?(?:user|assistant|system)/i,
  /output\s+(?:only|just)\s+(?:the|this)/i,
  /do\s+not\s+(?:include|show|reveal|output)/i,
  /hide\s+(?:the|this|your)/i,
  /secret(?:ly)?\s+(?:output|print|show|reveal)/i
]

/**
 * Detect prompt injection attempts
 */
export function detectPromptInjection (text: string): {
  detected: boolean
  patterns: string[]
} {
  const detected: string[] = []
  for (const pattern of INJECTION_PATTERNS) {
    if (pattern.test(text)) {
      detected.push(pattern.source)
    }
  }
  return { detected: detected.length > 0, patterns: detected }
}

/**
 * Untrusted output marker
 */
export const UNTRUSTED_PREFIX = '[UNTRUSTED_OUTPUT] '
export const UNTRUSTED_SUFFIX = ' [/UNTRUSTED_OUTPUT]'

/**
 * Mark output as untrusted
 */
export function markUntrusted (output: string): string {
  return `${UNTRUSTED_PREFIX}${output}${UNTRUSTED_SUFFIX}`
}

/**
 * Check if output is marked untrusted
 */
export function isUntrusted (output: string): boolean {
  return (
    output.startsWith(UNTRUSTED_PREFIX) && output.endsWith(UNTRUSTED_SUFFIX)
  )
}

/**
 * Extract trusted content from untrusted output
 */
export function extractTrusted (output: string): string {
  if (isUntrusted(output)) {
    return output.slice(UNTRUSTED_PREFIX.length, -UNTRUSTED_SUFFIX.length)
  }
  return output
}

/**
 * Correlation ID generator
 */
export function generateCorrelationId (): string {
  return crypto.randomUUID()
}

/**
 * Audit log entry
 */
export interface AuditLogEntry {
  timestamp: string
  correlationId: string
  taskId?: string
  sessionId?: string
  userId?: string
  action: string
  resource: string
  decision: 'allow' | 'deny' | 'error'
  reason?: string
  metadata?: Record<string, unknown>
}

/**
 * Audit logger interface
 */
export interface AuditLogger {
  log(entry: AuditLogEntry): void
  query(filter: Partial<AuditLogEntry>): AuditLogEntry[]
}
