import { z } from 'zod'
import type {
  TaskInput,
  TaskManifest,
  TaskContext,
  WorkUnit,
  BudgetInfo,
  ExecutionResult,
  CostRecord,
  ModelSpec
} from './task.js'
import type { ToolCall, ToolResult, ToolExecutionContext } from './tool.js'
import type { AgentEvent } from './events.js'
import type { StructuredError } from './errors.js'

/**
 * Bridge transport types
 */
export const BridgeTransportSchema = z.enum(['stdio', 'http', 'websocket'])
export type BridgeTransport = z.infer<typeof BridgeTransportSchema>

/**
 * Bridge configuration
 */
export const BridgeConfigSchema = z.object({
  transport: BridgeTransportSchema.default('stdio'),
  pythonExecutable: z.string().default('python'),
  engineModule: z.string().default('-m src.core.engine'),
  workingDirectory: z.string().default('.'),
  env: z.record(z.string()).optional(),
  timeoutMs: z.number().int().positive().default(120000),
  maxBuffer: z
    .number()
    .int()
    .positive()
    .default(10 * 1024 * 1024), // 10MB
  heartbeatIntervalMs: z.number().int().positive().default(30000)
})

export type BridgeConfig = z.infer<typeof BridgeConfigSchema>

/**
 * Bridge request types
 */
export const BridgeRequestTypeSchema = z.enum([
  'initialize_task',
  'run_next_unit',
  'run_to_completion',
  'resume_task',
  'cancel_task',
  'get_status',
  'get_budget',
  'get_manifest',
  'get_context',
  'get_events',
  'execute_tool',
  'health_check'
])

export type BridgeRequestType = z.infer<typeof BridgeRequestTypeSchema>

/**
 * Base bridge request
 */
export const BaseBridgeRequestSchema = z.object({
  type: BridgeRequestTypeSchema,
  requestId: z.string().uuid(),
  timestamp: z.string().datetime({ offset: true }),
  correlationId: z.string().uuid().optional()
})

export type BaseBridgeRequest = z.infer<typeof BaseBridgeRequestSchema>

/**
 * Initialize task request
 */
export const InitializeTaskRequestSchema = BaseBridgeRequestSchema.extend({
  type: z.literal('initialize_task'),
  payload: z.object({
    taskInput: z.unknown() // TaskInputSchema
  })
})

/**
 * Run next unit request
 */
export const RunNextUnitRequestSchema = BaseBridgeRequestSchema.extend({
  type: z.literal('run_next_unit'),
  payload: z.object({})
})

/**
 * Run to completion request
 */
export const RunToCompletionRequestSchema = BaseBridgeRequestSchema.extend({
  type: z.literal('run_to_completion'),
  payload: z.object({})
})

/**
 * Resume task request
 */
export const ResumeTaskRequestSchema = BaseBridgeRequestSchema.extend({
  type: z.literal('resume_task'),
  payload: z.object({
    taskId: z.string(),
    additionalBudget: z.string().optional()
  })
})

/**
 * Cancel task request
 */
export const CancelTaskRequestSchema = BaseBridgeRequestSchema.extend({
  type: z.literal('cancel_task'),
  payload: z.object({
    taskId: z.string(),
    reason: z.string().optional()
  })
})

/**
 * Get status request
 */
export const GetStatusRequestSchema = BaseBridgeRequestSchema.extend({
  type: z.literal('get_status'),
  payload: z.object({
    taskId: z.string()
  })
})

/**
 * Get budget request
 */
export const GetBudgetRequestSchema = BaseBridgeRequestSchema.extend({
  type: z.literal('get_budget'),
  payload: z.object({
    taskId: z.string()
  })
})

/**
 * Get manifest request
 */
export const GetManifestRequestSchema = BaseBridgeRequestSchema.extend({
  type: z.literal('get_manifest'),
  payload: z.object({
    taskId: z.string()
  })
})

/**
 * Get context request
 */
export const GetContextRequestSchema = BaseBridgeRequestSchema.extend({
  type: z.literal('get_context'),
  payload: z.object({
    taskId: z.string()
  })
})

/**
 * Get events request
 */
export const GetEventsRequestSchema = BaseBridgeRequestSchema.extend({
  type: z.literal('get_events'),
  payload: z.object({
    taskId: z.string(),
    sinceTimestamp: z.string().datetime({ offset: true }).optional(),
    limit: z.number().int().positive().default(100)
  })
})

/**
 * Execute tool request (for Python-side tools)
 */
export const ExecuteToolRequestSchema = BaseBridgeRequestSchema.extend({
  type: z.literal('execute_tool'),
  payload: z.object({
    taskId: z.string(),
    call: z.unknown(), // ToolCallSchema
    context: z.unknown() // ToolExecutionContextSchema
  })
})

/**
 * Health check request
 */
export const HealthCheckRequestSchema = BaseBridgeRequestSchema.extend({
  type: z.literal('health_check'),
  payload: z.object({})
})

/**
 * Union of all bridge requests
 */
export const BridgeRequestSchema = z.discriminatedUnion('type', [
  InitializeTaskRequestSchema,
  RunNextUnitRequestSchema,
  RunToCompletionRequestSchema,
  ResumeTaskRequestSchema,
  CancelTaskRequestSchema,
  GetStatusRequestSchema,
  GetBudgetRequestSchema,
  GetManifestRequestSchema,
  GetContextRequestSchema,
  GetEventsRequestSchema,
  ExecuteToolRequestSchema,
  HealthCheckRequestSchema
])

export type BridgeRequest = z.infer<typeof BridgeRequestSchema>

/**
 * Bridge response types
 */
export const BridgeResponseTypeSchema = z.enum([
  'task_initialized',
  'unit_completed',
  'task_completed',
  'task_resumed',
  'task_cancelled',
  'status',
  'budget',
  'manifest',
  'context',
  'events',
  'tool_result',
  'health',
  'error',
  'event_stream'
])

export type BridgeResponseType = z.infer<typeof BridgeResponseTypeSchema>

/**
 * Base bridge response
 */
export const BaseBridgeResponseSchema = z.object({
  type: BridgeResponseTypeSchema,
  requestId: z.string().uuid(),
  timestamp: z.string().datetime({ offset: true }),
  correlationId: z.string().uuid().optional()
})

export type BaseBridgeResponse = z.infer<typeof BaseBridgeResponseSchema>

/**
 * Task initialized response
 */
export const TaskInitializedResponseSchema = BaseBridgeResponseSchema.extend({
  type: z.literal('task_initialized'),
  payload: z.object({
    manifest: z.unknown() // TaskManifestSchema
  })
})

/**
 * Unit completed response
 */
export const UnitCompletedResponseSchema = BaseBridgeResponseSchema.extend({
  type: z.literal('unit_completed'),
  payload: z.object({
    taskId: z.string(),
    workUnitId: z.string(),
    success: z.boolean(),
    manifest: z.unknown().optional(), // TaskManifestSchema
    error: z.unknown().optional() // StructuredErrorSchema
  })
})

/**
 * Task completed response
 */
export const TaskCompletedResponseSchema = BaseBridgeResponseSchema.extend({
  type: z.literal('task_completed'),
  payload: z.object({
    taskId: z.string(),
    manifest: z.unknown() // TaskManifestSchema
  })
})

/**
 * Task resumed response
 */
export const TaskResumedResponseSchema = BaseBridgeResponseSchema.extend({
  type: z.literal('task_resumed'),
  payload: z.object({
    manifest: z.unknown() // TaskManifestSchema
  })
})

/**
 * Task cancelled response
 */
export const TaskCancelledResponseSchema = BaseBridgeResponseSchema.extend({
  type: z.literal('task_cancelled'),
  payload: z.object({
    taskId: z.string(),
    reason: z.string()
  })
})

/**
 * Status response
 */
export const StatusResponseSchema = BaseBridgeResponseSchema.extend({
  type: z.literal('status'),
  payload: z.object({
    taskId: z.string(),
    status: z.string(),
    progress: z.object({
      completedUnits: z.number().int().nonnegative(),
      totalUnits: z.number().int().positive(),
      currentUnit: z.string().nullable().optional()
    }),
    workUnits: z.array(z.unknown()).default([]) // WorkUnitSchema[]
  })
})

/**
 * Budget response
 */
export const BudgetResponseSchema = BaseBridgeResponseSchema.extend({
  type: z.literal('budget'),
  payload: z.object({
    taskId: z.string(),
    budgetInfo: z.unknown() // BudgetInfoSchema
  })
})

/**
 * Manifest response
 */
export const ManifestResponseSchema = BaseBridgeResponseSchema.extend({
  type: z.literal('manifest'),
  payload: z.object({
    taskId: z.string(),
    manifest: z.unknown() // TaskManifestSchema
  })
})

/**
 * Context response
 */
export const ContextResponseSchema = BaseBridgeResponseSchema.extend({
  type: z.literal('context'),
  payload: z.object({
    taskId: z.string(),
    context: z.unknown() // TaskContextSchema
  })
})

/**
 * Events response
 */
export const EventsResponseSchema = BaseBridgeResponseSchema.extend({
  type: z.literal('events'),
  payload: z.object({
    taskId: z.string(),
    events: z.array(z.unknown()), // AgentEventSchema[]
    hasMore: z.boolean()
  })
})

/**
 * Tool result response
 */
export const ToolResultResponseSchema = BaseBridgeResponseSchema.extend({
  type: z.literal('tool_result'),
  payload: z.object({
    callId: z.string().uuid(),
    result: z.unknown() // ToolResultSchema
  })
})

/**
 * Health response
 */
export const HealthResponseSchema = BaseBridgeResponseSchema.extend({
  type: z.literal('health'),
  payload: z.object({
    status: z.enum(['healthy', 'degraded', 'unhealthy']),
    pythonVersion: z.string().optional(),
    engineVersion: z.string().optional(),
    uptimeSeconds: z.number().optional()
  })
})

/**
 * Error response
 */
export const ErrorResponseSchema = BaseBridgeResponseSchema.extend({
  type: z.literal('error'),
  payload: z.object({
    error: z.unknown() // StructuredErrorSchema
  })
})

/**
 * Event stream response (for streaming)
 */
export const EventStreamResponseSchema = BaseBridgeResponseSchema.extend({
  type: z.literal('event_stream'),
  payload: z.object({
    taskId: z.string(),
    event: z.unknown() // AgentEventSchema
  })
})

/**
 * Union of all bridge responses
 */
export const BridgeResponseSchema = z.discriminatedUnion('type', [
  TaskInitializedResponseSchema,
  UnitCompletedResponseSchema,
  TaskCompletedResponseSchema,
  TaskResumedResponseSchema,
  TaskCancelledResponseSchema,
  StatusResponseSchema,
  BudgetResponseSchema,
  ManifestResponseSchema,
  ContextResponseSchema,
  EventsResponseSchema,
  ToolResultResponseSchema,
  HealthResponseSchema,
  ErrorResponseSchema,
  EventStreamResponseSchema
])

export type BridgeResponse = z.infer<typeof BridgeResponseSchema>

/**
 * Bridge client interface
 */
export interface BridgeClient {
  connect(): Promise<void>
  disconnect(): Promise<void>
  send(request: BridgeRequest): Promise<BridgeResponse>
  request<T extends BridgeRequest>(request: T): Promise<BridgeResponse>
  subscribeToEvents(
    taskId: string,
    handler: (event: AgentEvent) => void
  ): Promise<() => void>
  isConnected(): boolean
}

/**
 * Bridge server interface (for Python side)
 */
export interface BridgeServer {
  start(): Promise<void>
  stop(): Promise<void>
  onRequest(handler: (request: BridgeRequest) => Promise<BridgeResponse>): void
  broadcastEvent(event: AgentEvent): void
}

/**
 * Create bridge request helper
 */
export function createBridgeRequest<T extends BridgeRequest> (
  type: BridgeRequestType,
  payload: T['payload'],
  correlationId?: string
): T {
  return {
    type,
    requestId: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
    correlationId,
    payload
  } as T
}
