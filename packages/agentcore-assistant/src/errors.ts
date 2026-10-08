import type {
  StructuredError,
  ErrorCode,
  ErrorCategory,
  ErrorSeverity
} from '@agentcore/types'

/**
 * Assistant-specific error codes
 */
export const AssistantErrorCode = {
  SESSION_CREATION_FAILED: 'SESSION_CREATION_FAILED',
  SESSION_INITIALIZATION_FAILED: 'SESSION_INITIALIZATION_FAILED',
  BRIDGE_CONNECTION_FAILED: 'BRIDGE_CONNECTION_FAILED',
  BRIDGE_COMMUNICATION_FAILED: 'BRIDGE_COMMUNICATION_FAILED',
  TASK_INITIALIZATION_FAILED: 'TASK_INITIALIZATION_FAILED',
  TASK_EXECUTION_FAILED: 'TASK_EXECUTION_FAILED',
  TOOL_REGISTRATION_FAILED: 'TOOL_REGISTRATION_FAILED',
  TOOL_VALIDATION_FAILED: 'TOOL_VALIDATION_FAILED',
  PERMISSION_DENIED: 'PERMISSION_DENIED',
  APPROVAL_TIMEOUT: 'APPROVAL_TIMEOUT',
  APPROVAL_DENIED: 'APPROVAL_DENIED',
  BUDGET_EXCEEDED: 'BUDGET_EXCEEDED',
  MAX_ITERATIONS_REACHED: 'MAX_ITERATIONS_REACHED',
  MAX_TOOL_CALLS_REACHED: 'MAX_TOOL_CALLS_REACHED',
  CONTEXT_TOO_LARGE: 'CONTEXT_TOO_LARGE',
  SECURITY_VIOLATION: 'SECURITY_VIOLATION',
  CONFIGURATION_ERROR: 'CONFIGURATION_ERROR'
} as const

export type AssistantErrorCode =
  typeof AssistantErrorCode[keyof typeof AssistantErrorCode]

/**
 * Assistant error class
 */
export class AssistantError extends Error {
  public readonly code: AssistantErrorCode
  public readonly category: ErrorCategory
  public readonly severity: ErrorSeverity
  public readonly retryable: boolean
  public readonly details: unknown
  public readonly correlationId: string
  public readonly taskId?: string
  public readonly sessionId?: string

  constructor (
    code: AssistantErrorCode,
    message: string,
    options: {
      category?: ErrorCategory
      severity?: ErrorSeverity
      retryable?: boolean
      details?: unknown
      correlationId?: string
      taskId?: string
      sessionId?: string
      cause?: Error
    } = {}
  ) {
    super(message)
    this.name = 'AssistantError'
    this.code = code
    this.category = options.category || 'permanent'
    this.severity = options.severity || 'high'
    this.retryable = options.retryable || false
    this.details = options.details
    this.correlationId = options.correlationId || crypto.randomUUID()
    this.taskId = options.taskId
    this.sessionId = options.sessionId
    if (options.cause) {
      this.cause = options.cause
    }
  }

  toStructuredError (): StructuredError {
    return {
      code: this.code as ErrorCode,
      message: this.message,
      category: this.category,
      severity: this.severity,
      retryable: this.retryable,
      details: this.details,
      correlationId: this.correlationId,
      taskId: this.taskId,
      timestamp: new Date().toISOString(),
      source: 'typescript',
      stackTrace: this.stack
    }
  }
}

/**
 * Create assistant error from structured error
 */
export function fromStructuredError (error: StructuredError): AssistantError {
  return new AssistantError(error.code as AssistantErrorCode, error.message, {
    category: error.category,
    severity: error.severity,
    retryable: error.retryable,
    details: error.details,
    correlationId: error.correlationId,
    taskId: error.taskId
  })
}

/**
 * Check if error is assistant error
 */
export function isAssistantError (error: unknown): error is AssistantError {
  return error instanceof AssistantError
}

/**
 * Error factory functions
 */
export const Errors = {
  sessionCreationFailed: (
    message: string,
    options?: { cause?: Error; taskId?: string; sessionId?: string }
  ) =>
    new AssistantError('SESSION_CREATION_FAILED', message, {
      ...options,
      severity: 'critical'
    }),

  sessionInitializationFailed: (
    message: string,
    options?: { cause?: Error; taskId?: string; sessionId?: string }
  ) =>
    new AssistantError('SESSION_INITIALIZATION_FAILED', message, {
      ...options,
      severity: 'high'
    }),

  bridgeConnectionFailed: (message: string, options?: { cause?: Error }) =>
    new AssistantError('BRIDGE_CONNECTION_FAILED', message, {
      category: 'transient',
      retryable: true,
      severity: 'high',
      ...options
    }),

  bridgeCommunicationFailed: (
    message: string,
    options?: { cause?: Error; taskId?: string }
  ) =>
    new AssistantError('BRIDGE_COMMUNICATION_FAILED', message, {
      category: 'transient',
      retryable: true,
      severity: 'high',
      ...options
    }),

  taskInitializationFailed: (
    message: string,
    options?: { cause?: Error; taskId?: string }
  ) =>
    new AssistantError('TASK_INITIALIZATION_FAILED', message, {
      severity: 'high',
      ...options
    }),

  taskExecutionFailed: (
    message: string,
    options?: { cause?: Error; taskId?: string; sessionId?: string }
  ) =>
    new AssistantError('TASK_EXECUTION_FAILED', message, {
      severity: 'high',
      ...options
    }),

  toolRegistrationFailed: (
    message: string,
    options?: { cause?: Error; details?: unknown }
  ) =>
    new AssistantError('TOOL_REGISTRATION_FAILED', message, {
      severity: 'medium',
      ...options
    }),

  toolValidationFailed: (
    message: string,
    options?: { cause?: Error; taskId?: string; details?: unknown }
  ) =>
    new AssistantError('TOOL_VALIDATION_FAILED', message, {
      severity: 'medium',
      ...options
    }),

  permissionDenied: (
    message: string,
    options?: { cause?: Error; taskId?: string; details?: unknown }
  ) =>
    new AssistantError('PERMISSION_DENIED', message, {
      category: 'user_action',
      severity: 'high',
      ...options
    }),

  approvalTimeout: (
    message: string,
    options?: { cause?: Error; taskId?: string }
  ) =>
    new AssistantError('APPROVAL_TIMEOUT', message, {
      category: 'user_action',
      retryable: false,
      severity: 'medium',
      ...options
    }),

  approvalDenied: (
    message: string,
    options?: { cause?: Error; taskId?: string }
  ) =>
    new AssistantError('APPROVAL_DENIED', message, {
      category: 'user_action',
      severity: 'medium',
      ...options
    }),

  budgetExceeded: (
    message: string,
    options?: { cause?: Error; taskId?: string }
  ) =>
    new AssistantError('BUDGET_EXCEEDED', message, {
      category: 'budget',
      retryable: true,
      severity: 'high',
      ...options
    }),

  maxIterationsReached: (
    message: string,
    options?: { taskId?: string; sessionId?: string }
  ) =>
    new AssistantError('MAX_ITERATIONS_REACHED', message, {
      severity: 'medium',
      ...options
    }),

  maxToolCallsReached: (
    message: string,
    options?: { taskId?: string; sessionId?: string }
  ) =>
    new AssistantError('MAX_TOOL_CALLS_REACHED', message, {
      severity: 'medium',
      ...options
    }),

  contextTooLarge: (
    message: string,
    options?: { cause?: Error; taskId?: string }
  ) =>
    new AssistantError('CONTEXT_TOO_LARGE', message, {
      category: 'transient',
      retryable: true,
      severity: 'medium',
      ...options
    }),

  securityViolation: (
    message: string,
    options?: { cause?: Error; taskId?: string; details?: unknown }
  ) =>
    new AssistantError('SECURITY_VIOLATION', message, {
      category: 'security',
      severity: 'critical',
      retryable: false,
      ...options
    }),

  configurationError: (
    message: string,
    options?: { cause?: Error; details?: unknown }
  ) =>
    new AssistantError('CONFIGURATION_ERROR', message, {
      severity: 'high',
      ...options
    })
}
