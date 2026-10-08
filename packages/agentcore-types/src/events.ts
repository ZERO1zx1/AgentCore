import { z } from 'zod'

/**
 * Canonical agent event types for streaming and observability
 */
export const AgentEventTypeSchema = z.enum([
  'task.started',
  'task.resumed',
  'plan.created',
  'plan.updated',
  'tool.requested',
  'tool.validated',
  'approval.required',
  'approval.granted',
  'approval.denied',
  'tool.started',
  'tool.completed',
  'tool.failed',
  'tool.retry',
  'checkpoint.saved',
  'checkpoint.loaded',
  'budget.warning',
  'budget.exhausted',
  'budget.reserve_reached',
  'context.loaded',
  'context.updated',
  'task.completed',
  'task.partially_completed',
  'task.failed',
  'task.cancelled',
  'agent.iteration',
  'agent.max_iterations_reached'
])

export type AgentEventType = z.infer<typeof AgentEventTypeSchema>

/**
 * Base event structure
 */
export const BaseEventSchema = z.object({
  type: AgentEventTypeSchema,
  taskId: z.string().min(1),
  timestamp: z.string().datetime({ offset: true }),
  correlationId: z.string().uuid().optional(),
  sessionId: z.string().optional()
})

export type BaseEvent = z.infer<typeof BaseEventSchema>

/**
 * Task started event
 */
export const TaskStartedEventSchema = BaseEventSchema.extend({
  type: z.literal('task.started'),
  data: z.object({
    prompt: z.string(),
    executionMode: z.enum(['AUTO', 'FULL', 'CREDIT_SAFE']),
    budget: z.string(),
    budgetUnit: z.string(),
    files: z.array(z.string()).default([]),
    repository: z.string().optional(),
    resumeTaskId: z.string().optional()
  })
})

export type TaskStartedEvent = z.infer<typeof TaskStartedEventSchema>

/**
 * Plan created event
 */
export const PlanCreatedEventSchema = BaseEventSchema.extend({
  type: z.literal('plan.created'),
  data: z.object({
    workUnits: z.array(
      z.object({
        id: z.string(),
        type: z.string(),
        priority: z.enum(['P0', 'P1', 'P2', 'P3', 'P4']),
        instruction: z.string(),
        requiredCapabilities: z.array(z.string()),
        estimatedCost: z.number(),
        dependencies: z.array(z.string()),
        optional: z.boolean()
      })
    ),
    totalUnits: z.number().int().positive(),
    requiredUnits: z.number().int().nonnegative()
  })
})

export type PlanCreatedEvent = z.infer<typeof PlanCreatedEventSchema>

/**
 * Tool requested event
 */
export const ToolRequestedEventSchema = BaseEventSchema.extend({
  type: z.literal('tool.requested'),
  data: z.object({
    callId: z.string().uuid(),
    toolName: z.string(),
    input: z.unknown(),
    estimatedCost: z.string(),
    requiresApproval: z.boolean(),
    risk: z.enum(['read', 'write', 'external', 'dangerous'])
  })
})

export type ToolRequestedEvent = z.infer<typeof ToolRequestedEventSchema>

/**
 * Approval required event
 */
export const ApprovalRequiredEventSchema = BaseEventSchema.extend({
  type: z.literal('approval.required'),
  data: z.object({
    callId: z.string().uuid(),
    toolName: z.string(),
    input: z.unknown(),
    risk: z.enum(['read', 'write', 'external', 'dangerous']),
    reason: z.string(),
    timeoutSeconds: z.number().int().positive().default(300)
  })
})

export type ApprovalRequiredEvent = z.infer<typeof ApprovalRequiredEventSchema>

/**
 * Approval granted/denied event
 */
export const ApprovalDecisionEventSchema = BaseEventSchema.extend({
  type: z.union([z.literal('approval.granted'), z.literal('approval.denied')]),
  data: z.object({
    callId: z.string().uuid(),
    toolName: z.string(),
    decision: z.enum(['granted', 'denied']),
    decidedBy: z.string().optional(),
    reason: z.string().optional()
  })
})

export type ApprovalDecisionEvent = z.infer<typeof ApprovalDecisionEventSchema>

/**
 * Tool completed event
 */
export const ToolCompletedEventSchema = BaseEventSchema.extend({
  type: z.literal('tool.completed'),
  data: z.object({
    callId: z.string().uuid(),
    toolName: z.string(),
    output: z.unknown().optional(),
    durationMs: z.number().int().nonnegative(),
    tokensUsed: z.number().int().nonnegative().optional(),
    costUsd: z.string().optional(),
    costSource: z.enum(['estimate', 'provider']).optional()
  })
})

export type ToolCompletedEvent = z.infer<typeof ToolCompletedEventSchema>

/**
 * Tool failed event
 */
export const ToolFailedEventSchema = BaseEventSchema.extend({
  type: z.literal('tool.failed'),
  data: z.object({
    callId: z.string().uuid(),
    toolName: z.string(),
    error: z.object({
      code: z.string(),
      message: z.string(),
      retryable: z.boolean(),
      details: z.unknown().optional()
    }),
    attempt: z.number().int().positive(),
    maxRetries: z.number().int().nonnegative()
  })
})

export type ToolFailedEvent = z.infer<typeof ToolFailedEventSchema>

/**
 * Checkpoint saved event
 */
export const CheckpointSavedEventSchema = BaseEventSchema.extend({
  type: z.literal('checkpoint.saved'),
  data: z.object({
    checkpointId: z.string(),
    completedUnits: z.number().int().nonnegative(),
    totalUnits: z.number().int().positive(),
    budgetUsed: z.string(),
    budgetRemaining: z.string(),
    status: z.enum([
      'in_progress',
      'completed',
      'partially_completed',
      'paused_budget',
      'blocked',
      'failed'
    ])
  })
})

export type CheckpointSavedEvent = z.infer<typeof CheckpointSavedEventSchema>

/**
 * Budget warning event
 */
export const BudgetWarningEventSchema = BaseEventSchema.extend({
  type: z.literal('budget.warning'),
  data: z.object({
    state: z.enum(['NORMAL', 'CONSERVE', 'CRITICAL', 'EMERGENCY', 'EXHAUSTED']),
    used: z.string(),
    remaining: z.string(),
    reserved: z.string(),
    reserveRatio: z.number(),
    percentage: z.number()
  })
})

export type BudgetWarningEvent = z.infer<typeof BudgetWarningEventSchema>

/**
 * Task completed event
 */
export const TaskCompletedEventSchema = BaseEventSchema.extend({
  type: z.union([
    z.literal('task.completed'),
    z.literal('task.partially_completed'),
    z.literal('task.failed'),
    z.literal('task.cancelled')
  ]),
  data: z.object({
    status: z.enum([
      'COMPLETED',
      'PARTIALLY_COMPLETED',
      'FAILED',
      'BLOCKED',
      'CANCELLED'
    ]),
    completedUnits: z.number().int().nonnegative(),
    totalUnits: z.number().int().positive(),
    outputs: z.array(z.string()).default([]),
    errors: z.array(z.string()).default([]),
    budgetUsed: z.string(),
    budgetRemaining: z.string(),
    durationMs: z.number().int().nonnegative().optional()
  })
})

export type TaskCompletedEvent = z.infer<typeof TaskCompletedEventSchema>

/**
 * Agent iteration event
 */
export const AgentIterationEventSchema = BaseEventSchema.extend({
  type: z.literal('agent.iteration'),
  data: z.object({
    iteration: z.number().int().positive(),
    maxIterations: z.number().int().positive(),
    currentTool: z.string().optional(),
    remainingBudget: z.string().optional()
  })
})

export type AgentIterationEvent = z.infer<typeof AgentIterationEventSchema>

/**
 * Union of all event types
 */
// Some event families intentionally accept more than one literal `type` value
// (for example approval.granted/approval.denied). Zod's discriminatedUnion
// requires every option to expose one single literal discriminator at schema
// construction time, so use a regular union here to keep those valid event
// families runtime-safe.
export const AgentEventSchema = z.union([
  TaskStartedEventSchema,
  PlanCreatedEventSchema,
  ToolRequestedEventSchema,
  ApprovalRequiredEventSchema,
  ApprovalDecisionEventSchema,
  ToolCompletedEventSchema,
  ToolFailedEventSchema,
  CheckpointSavedEventSchema,
  BudgetWarningEventSchema,
  TaskCompletedEventSchema,
  AgentIterationEventSchema,
  BaseEventSchema.extend({
    type: z.union([
      z.literal('task.resumed'),
      z.literal('plan.updated'),
      z.literal('tool.validated'),
      z.literal('tool.started'),
      z.literal('tool.retry'),
      z.literal('checkpoint.loaded'),
      z.literal('budget.exhausted'),
      z.literal('budget.reserve_reached'),
      z.literal('context.loaded'),
      z.literal('context.updated'),
      z.literal('agent.max_iterations_reached')
    ]),
    data: z.unknown()
  })
])

export type AgentEvent = z.infer<typeof AgentEventSchema>

/**
 * Event stream interface for streaming events
 */
export interface EventStream {
  subscribe(handler: (event: AgentEvent) => void): () => void
  publish(event: AgentEvent): void
  close(): void
}
