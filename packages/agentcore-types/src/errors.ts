import { z } from 'zod'

/**
 * Structured error codes for cross-layer error handling
 * These codes are used by both Python and TypeScript layers
 */
export const ErrorCodeSchema = z.enum([
  // Rate limiting
  'RATE_LIMITED',
  // Authentication/Authorization
  'AUTH_FAILED',
  'PERMISSION_DENIED',
  'HUMAN_APPROVAL_REQUIRED',
  // Timeouts
  'TIMEOUT',
  'TOOL_TIMEOUT',
  'BRIDGE_TIMEOUT',
  // Context/Input
  'CONTEXT_TOO_LARGE',
  'INVALID_INPUT',
  'TOOL_VALIDATION_FAILED',
  'SCHEMA_VALIDATION_FAILED',
  // Budget
  'BUDGET_EXCEEDED',
  'BUDGET_RESERVE_REACHED',
  'COST_ESTIMATION_FAILED',
  // Dependencies
  'DEPENDENCY_UNAVAILABLE',
  'PROVIDER_NOT_CONFIGURED',
  'PROVIDER_ERROR',
  'MODEL_NOT_FOUND',
  // Execution
  'EXECUTION_FAILED',
  'OUTPUT_CONTRACT_FAILED',
  'ARTIFACT_WRITE_FAILED',
  // Checkpoint/Resume
  'CHECKPOINT_ERROR',
  'CHECKPOINT_NOT_FOUND',
  'CHECKPOINT_CORRUPTED',
  'RESUME_FAILED',
  'SOURCE_CHANGED',
  // Transport
  'BRIDGE_CONNECTION_FAILED',
  'BRIDGE_PROTOCOL_ERROR',
  'MCP_CONNECTION_FAILED',
  // Security
  'PATH_TRAVERSAL_DETECTED',
  'PROMPT_INJECTION_DETECTED',
  'SECRET_DETECTED',
  'UNTRUSTED_OUTPUT',
  // Cancellation
  'CANCELLED',
  'MAX_ITERATIONS_REACHED',
  'MAX_TOOL_CALLS_REACHED',
  // Internal
  'INTERNAL_ERROR',
  'CONFIGURATION_ERROR',
  'UNKNOWN_ERROR'
])

export type ErrorCode = z.infer<typeof ErrorCodeSchema>

/**
 * Error severity
 */
export const ErrorSeveritySchema = z.enum(['low', 'medium', 'high', 'critical'])
export type ErrorSeverity = z.infer<typeof ErrorSeveritySchema>

/**
 * Error category for classification
 */
export const ErrorCategorySchema = z.enum([
  'transient', // Retryable - network, rate limit, timeout
  'permanent', // Non-retryable - auth, validation, permission
  'budget', // Budget-related - may succeed with more budget
  'security', // Security violation - should not retry
  'user_action' // Requires user intervention - approval, config
])
export type ErrorCategory = z.infer<typeof ErrorCategorySchema>

/**
 * Structured error with full context
 */
export const StructuredErrorSchema = z.object({
  code: ErrorCodeSchema,
  message: z.string(),
  category: ErrorCategorySchema,
  severity: ErrorSeveritySchema,
  retryable: z.boolean(),
  details: z.unknown().optional(),
  correlationId: z.string().uuid().optional(),
  taskId: z.string().optional(),
  toolName: z.string().optional(),
  timestamp: z.string().datetime({ offset: true }),
  source: z.enum(['python', 'typescript', 'bridge', 'mcp', 'provider']),
  stackTrace: z.string().optional()
})

export type StructuredError = z.infer<typeof StructuredErrorSchema>

/**
 * Retry policy configuration
 */
export const RetryPolicySchema = z.object({
  maxRetries: z.number().int().nonnegative().default(2),
  baseDelayMs: z.number().int().positive().default(1000),
  maxDelayMs: z.number().int().positive().default(30000),
  exponentialBase: z.number().default(2),
  jitter: z.boolean().default(true),
  retryableCategories: z
    .array(ErrorCategorySchema)
    .default(['transient', 'budget']),
  retryableCodes: z
    .array(ErrorCodeSchema)
    .default([
      'RATE_LIMITED',
      'TIMEOUT',
      'TOOL_TIMEOUT',
      'BRIDGE_TIMEOUT',
      'PROVIDER_ERROR',
      'DEPENDENCY_UNAVAILABLE',
      'BUDGET_EXCEEDED'
    ])
})

export type RetryPolicy = z.infer<typeof RetryPolicySchema>

/**
 * Default retry policy
 */
export const DEFAULT_RETRY_POLICY: RetryPolicy = {
  maxRetries: 2,
  baseDelayMs: 1000,
  maxDelayMs: 30000,
  exponentialBase: 2,
  jitter: true,
  retryableCategories: ['transient', 'budget'],
  retryableCodes: [
    'RATE_LIMITED',
    'TIMEOUT',
    'TOOL_TIMEOUT',
    'BRIDGE_TIMEOUT',
    'PROVIDER_ERROR',
    'DEPENDENCY_UNAVAILABLE',
    'BUDGET_EXCEEDED'
  ]
}

/**
 * Check if error is retryable based on policy
 */
export function isRetryableError (
  error: StructuredError,
  policy: RetryPolicy = DEFAULT_RETRY_POLICY
): boolean {
  if (!error.retryable) return false
  if (policy.retryableCategories.includes(error.category)) return true
  if (policy.retryableCodes.includes(error.code)) return true
  return false
}

/**
 * Calculate retry delay with exponential backoff and jitter
 */
export function calculateRetryDelay (
  attempt: number,
  policy: RetryPolicy = DEFAULT_RETRY_POLICY
): number {
  const delay = Math.min(
    policy.baseDelayMs * Math.pow(policy.exponentialBase, attempt),
    policy.maxDelayMs
  )
  if (policy.jitter) {
    return delay * (0.5 + Math.random() * 0.5)
  }
  return delay
}

/**
 * Create structured error from unknown error
 */
export function createStructuredError (
  error: unknown,
  context: Partial<
    Pick<StructuredError, 'taskId' | 'toolName' | 'correlationId' | 'source'>
  > = {}
): StructuredError {
  const timestamp = new Date().toISOString()
  const correlationId = context.correlationId ?? crypto.randomUUID()

  if (error instanceof StructuredErrorImpl) {
    return error.toJSON()
  }

  if (error instanceof Error) {
    const code = classifyErrorCode(error.message)
    return {
      code,
      message: error.message,
      category: classifyErrorCategory(code),
      severity: classifyErrorSeverity(code),
      retryable: isRetryableCode(code),
      details: { originalError: error.name },
      correlationId,
      taskId: context.taskId,
      toolName: context.toolName,
      timestamp,
      source: context.source ?? 'typescript',
      stackTrace: error.stack
    }
  }

  return {
    code: 'UNKNOWN_ERROR',
    message: String(error),
    category: 'permanent',
    severity: 'medium',
    retryable: false,
    correlationId,
    taskId: context.taskId,
    toolName: context.toolName,
    timestamp,
    source: context.source ?? 'typescript'
  }
}

/**
 * Error class implementation
 */
export class StructuredErrorImpl extends Error {
  public readonly code: ErrorCode
  public readonly category: ErrorCategory
  public readonly severity: ErrorSeverity
  public readonly retryable: boolean
  public readonly details: unknown
  public readonly correlationId: string
  public readonly taskId?: string
  public readonly toolName?: string
  public readonly timestamp: string
  public readonly source: StructuredError['source']

  constructor (error: StructuredError) {
    super(error.message)
    this.name = 'StructuredError'
    this.code = error.code
    this.category = error.category
    this.severity = error.severity
    this.retryable = error.retryable
    this.details = error.details
    this.correlationId = error.correlationId ?? crypto.randomUUID()
    this.taskId = error.taskId
    this.toolName = error.toolName
    this.timestamp = error.timestamp
    this.source = error.source
  }

  toJSON (): StructuredError {
    return {
      code: this.code,
      message: this.message,
      category: this.category,
      severity: this.severity,
      retryable: this.retryable,
      details: this.details,
      correlationId: this.correlationId,
      taskId: this.taskId,
      toolName: this.toolName,
      timestamp: this.timestamp,
      source: this.source,
      stackTrace: this.stack
    }
  }
}

/**
 * Classify error code from message
 */
function classifyErrorCode (message: string): ErrorCode {
  const lower = message.toLowerCase()

  if (lower.includes('rate limit') || lower.includes('429'))
    return 'RATE_LIMITED'
  if (
    lower.includes('auth') ||
    lower.includes('unauthorized') ||
    lower.includes('401') ||
    lower.includes('403')
  )
    return 'AUTH_FAILED'
  if (lower.includes('permission') || lower.includes('forbidden'))
    return 'PERMISSION_DENIED'
  if (lower.includes('approval') || lower.includes('human'))
    return 'HUMAN_APPROVAL_REQUIRED'
  if (lower.includes('timeout') || lower.includes('timed out')) return 'TIMEOUT'
  if (lower.includes('context') && lower.includes('large'))
    return 'CONTEXT_TOO_LARGE'
  if (lower.includes('validation') || lower.includes('schema'))
    return 'SCHEMA_VALIDATION_FAILED'
  if (lower.includes('budget') && lower.includes('exceed'))
    return 'BUDGET_EXCEEDED'
  if (lower.includes('reserve')) return 'BUDGET_RESERVE_REACHED'
  if (lower.includes('dependency') || lower.includes('unavailable'))
    return 'DEPENDENCY_UNAVAILABLE'
  if (lower.includes('provider') && lower.includes('not configur'))
    return 'PROVIDER_NOT_CONFIGURED'
  if (lower.includes('provider') || lower.includes('model'))
    return 'PROVIDER_ERROR'
  if (lower.includes('execution') || lower.includes('failed'))
    return 'EXECUTION_FAILED'
  if (lower.includes('output') && lower.includes('contract'))
    return 'OUTPUT_CONTRACT_FAILED'
  if (lower.includes('checkpoint') && lower.includes('not found'))
    return 'CHECKPOINT_NOT_FOUND'
  if (lower.includes('checkpoint')) return 'CHECKPOINT_ERROR'
  if (lower.includes('resume')) return 'RESUME_FAILED'
  if (lower.includes('source') && lower.includes('chang'))
    return 'SOURCE_CHANGED'
  if (lower.includes('bridge') && lower.includes('connect'))
    return 'BRIDGE_CONNECTION_FAILED'
  if (lower.includes('bridge') || lower.includes('protocol'))
    return 'BRIDGE_PROTOCOL_ERROR'
  if (lower.includes('mcp') && lower.includes('connect'))
    return 'MCP_CONNECTION_FAILED'
  if (lower.includes('traversal') || lower.includes('..'))
    return 'PATH_TRAVERSAL_DETECTED'
  if (lower.includes('injection') || lower.includes('prompt'))
    return 'PROMPT_INJECTION_DETECTED'
  if (
    lower.includes('secret') ||
    lower.includes('credential') ||
    lower.includes('token')
  )
    return 'SECRET_DETECTED'
  if (lower.includes('untrusted')) return 'UNTRUSTED_OUTPUT'
  if (lower.includes('cancel') || lower.includes('abort')) return 'CANCELLED'
  if (lower.includes('max iteration') || lower.includes('max tool'))
    return 'MAX_ITERATIONS_REACHED'
  if (lower.includes('config')) return 'CONFIGURATION_ERROR'

  return 'UNKNOWN_ERROR'
}

function classifyErrorCategory (code: ErrorCode): ErrorCategory {
  const transientCodes: ErrorCode[] = [
    'RATE_LIMITED',
    'TIMEOUT',
    'TOOL_TIMEOUT',
    'BRIDGE_TIMEOUT',
    'PROVIDER_ERROR',
    'DEPENDENCY_UNAVAILABLE'
  ]
  const budgetCodes: ErrorCode[] = [
    'BUDGET_EXCEEDED',
    'BUDGET_RESERVE_REACHED',
    'COST_ESTIMATION_FAILED'
  ]
  const securityCodes: ErrorCode[] = [
    'PATH_TRAVERSAL_DETECTED',
    'PROMPT_INJECTION_DETECTED',
    'SECRET_DETECTED',
    'UNTRUSTED_OUTPUT'
  ]
  const userActionCodes: ErrorCode[] = [
    'HUMAN_APPROVAL_REQUIRED',
    'PERMISSION_DENIED',
    'AUTH_FAILED',
    'PROVIDER_NOT_CONFIGURED'
  ]

  if (transientCodes.includes(code)) return 'transient'
  if (budgetCodes.includes(code)) return 'budget'
  if (securityCodes.includes(code)) return 'security'
  if (userActionCodes.includes(code)) return 'user_action'
  return 'permanent'
}

function classifyErrorSeverity (code: ErrorCode): ErrorSeverity {
  const criticalCodes: ErrorCode[] = [
    'SECRET_DETECTED',
    'PROMPT_INJECTION_DETECTED',
    'PATH_TRAVERSAL_DETECTED',
    'UNTRUSTED_OUTPUT'
  ]
  const highCodes: ErrorCode[] = [
    'AUTH_FAILED',
    'PERMISSION_DENIED',
    'BUDGET_EXCEEDED',
    'CHECKPOINT_ERROR',
    'RESUME_FAILED',
    'PROVIDER_NOT_CONFIGURED'
  ]
  const lowCodes: ErrorCode[] = ['RATE_LIMITED', 'TIMEOUT', 'TOOL_TIMEOUT']

  if (criticalCodes.includes(code)) return 'critical'
  if (highCodes.includes(code)) return 'high'
  if (lowCodes.includes(code)) return 'low'
  return 'medium'
}

function isRetryableCode (code: ErrorCode): boolean {
  const retryableCodes: ErrorCode[] = [
    'RATE_LIMITED',
    'TIMEOUT',
    'TOOL_TIMEOUT',
    'BRIDGE_TIMEOUT',
    'PROVIDER_ERROR',
    'DEPENDENCY_UNAVAILABLE',
    'BUDGET_EXCEEDED'
  ]
  return retryableCodes.includes(code)
}
