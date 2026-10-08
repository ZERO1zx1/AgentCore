import { z } from 'zod'

/**
 * Tool risk levels for permission policy
 * - read: reads files, lists directories, inspects repository
 * - write: writes files, creates artifacts
 * - external: makes network calls, calls external APIs
 * - dangerous: shell commands, git push, destructive operations
 */
export const ToolRiskSchema = z.enum(['read', 'write', 'external', 'dangerous'])
export type ToolRisk = z.infer<typeof ToolRiskSchema>

/**
 * Tool definition with schema validation and metadata
 */
export const ToolDefinitionSchema = z.object({
  name: z.string().min(1),
  description: z.string().min(1),
  inputSchema: z.unknown(), // Zod schema or JSON Schema
  risk: ToolRiskSchema,
  requiresApproval: z.boolean().default(false),
  estimatedCost: z.string().default('0'),
  timeoutSeconds: z.number().int().positive().default(60),
  retryable: z.boolean().default(true),
  maxRetries: z.number().int().nonnegative().default(2)
})

export type ToolDefinition = z.infer<typeof ToolDefinitionSchema>

/**
 * Tool call from agent to tool
 */
export const ToolCallSchema = z.object({
  id: z.string().uuid(),
  taskId: z.string().min(1),
  name: z.string().min(1),
  input: z.unknown(),
  correlationId: z.string().optional()
})

export type ToolCall = z.infer<typeof ToolCallSchema>

/**
 * Tool result returned to agent
 */
export const ToolResultSchema = z.object({
  callId: z.string().uuid(),
  ok: z.boolean(),
  output: z.unknown().optional(),
  error: z
    .object({
      code: z.string(),
      message: z.string(),
      retryable: z.boolean(),
      details: z.unknown().optional()
    })
    .optional(),
  metadata: z
    .object({
      durationMs: z.number().int().nonnegative().optional(),
      tokensUsed: z.number().int().nonnegative().optional(),
      costUsd: z.string().optional()
    })
    .optional()
})

export type ToolResult = z.infer<typeof ToolResultSchema>

/**
 * Tool execution context passed to tool handlers
 */
export const ToolExecutionContextSchema = z.object({
  taskId: z.string(),
  sessionId: z.string(),
  workingDirectory: z.string(),
  budgetRemaining: z.string().optional(),
  userId: z.string().optional(),
  permissions: z.array(z.string()).optional()
})

export type ToolExecutionContext = z.infer<typeof ToolExecutionContextSchema>

/**
 * Tool registry interface
 */
export interface ToolRegistry {
  register(definition: ToolDefinition): void
  unregister(name: string): boolean
  get(name: string): ToolDefinition | undefined
  list(): ToolDefinition[]
  validateInput(name: string, input: unknown): { ok: boolean; errors: string[] }
  checkPermission(
    name: string,
    context: ToolExecutionContext
  ): { allowed: boolean; reason?: string }
  estimateCost(name: string, input: unknown): string
  detectDuplicateCall(call: ToolCall, recentCalls: ToolCall[]): ToolCall | null
}
