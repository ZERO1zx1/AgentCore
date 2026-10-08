import { z } from 'zod'

/**
 * Budget state from Python engine (read-only in TypeScript)
 */
export const BudgetStateSchema = z.enum([
  'NORMAL',
  'CONSERVE',
  'CRITICAL',
  'EMERGENCY',
  'EXHAUSTED'
])
export type BudgetState = z.infer<typeof BudgetStateSchema>

/**
 * Budget info from Python engine
 */
export const BudgetInfoSchema = z.object({
  initial: z.string(),
  used: z.string(),
  remaining: z.string(),
  reserved: z.string(),
  reserveRatio: z.number(),
  unit: z.string(),
  state: BudgetStateSchema,
  executionMode: z.string().optional()
})

export type BudgetInfo = z.infer<typeof BudgetInfoSchema>

/**
 * Budget preflight request (TypeScript -> Python)
 */
export const BudgetPreflightRequestSchema = z.object({
  taskId: z.string(),
  estimatedCost: z.string(),
  isOptional: z.boolean().default(false),
  correlationId: z.string().uuid().optional()
})

export type BudgetPreflightRequest = z.infer<
  typeof BudgetPreflightRequestSchema
>

/**
 * Budget preflight response (Python -> TypeScript)
 */
export const BudgetPreflightResponseSchema = z.object({
  ok: z.boolean(),
  budgetInfo: BudgetInfoSchema.optional(),
  error: z
    .object({
      code: z.string(),
      message: z.string(),
      retryable: z.boolean()
    })
    .optional(),
  correlationId: z.string().uuid().optional()
})

export type BudgetPreflightResponse = z.infer<
  typeof BudgetPreflightResponseSchema
>

/**
 * Cost record from Python engine (read-only)
 */
export const CostRecordSchema = z.object({
  workUnitId: z.string(),
  provider: z.string(),
  modelId: z.string(),
  estimatedCost: z.string(), // Decimal as string
  chargedCost: z.string(), // Decimal as string
  actualCost: z.string().nullable().optional(), // Decimal as string or null
  costSource: z.enum(['estimate', 'provider']),
  inputTokens: z.number().int().nonnegative(),
  outputTokens: z.number().int().nonnegative(),
  totalTokens: z.number().int().nonnegative(),
  providerRequestId: z.string().optional(),
  success: z.boolean(),
  latencyMs: z.number().int().nonnegative().optional()
})

export type CostRecord = z.infer<typeof CostRecordSchema>

/**
 * Budget usage summary
 */
export const BudgetUsageSummarySchema = z.object({
  totalEstimated: z.string(),
  totalCharged: z.string(),
  totalActual: z.string().optional(),
  byProvider: z
    .record(
      z.object({
        estimated: z.string(),
        charged: z.string(),
        actual: z.string().optional(),
        calls: z.number().int().nonnegative()
      })
    )
    .default({}),
  byWorkUnit: z
    .record(
      z.object({
        estimated: z.string(),
        charged: z.string(),
        actual: z.string().optional(),
        calls: z.number().int().nonnegative()
      })
    )
    .default({})
})

export type BudgetUsageSummary = z.infer<typeof BudgetUsageSummarySchema>

/**
 * Budget limit configuration for agent loop
 */
export const BudgetLimitConfigSchema = z.object({
  maxTotalCost: z.string().optional(),
  maxCostPerTool: z.string().optional(),
  reserveRatio: z.number().default(0.15),
  warnAtPercentage: z.number().default(0.5),
  criticalAtPercentage: z.number().default(0.25),
  emergencyAtPercentage: z.number().default(0.1)
})

export type BudgetLimitConfig = z.infer<typeof BudgetLimitConfigSchema>

/**
 * Default budget limit configuration
 */
export const DEFAULT_BUDGET_LIMIT_CONFIG: BudgetLimitConfig = {
  reserveRatio: 0.15,
  warnAtPercentage: 0.5,
  criticalAtPercentage: 0.25,
  emergencyAtPercentage: 0.1
}

/**
 * Check if budget allows an operation
 * TypeScript reads budget info from Python but does NOT make budget decisions
 */
export function canAfford (
  budgetInfo: BudgetInfo,
  estimatedCost: string,
  isOptional: boolean = false
): { allowed: boolean; reason?: string } {
  const remaining = parseDecimal(budgetInfo.remaining)
  const reserved = parseDecimal(budgetInfo.reserved)
  const cost = parseDecimal(estimatedCost)
  const usable = remaining - reserved

  if (budgetInfo.state === 'EXHAUSTED') {
    return { allowed: false, reason: 'Budget exhausted' }
  }
  if (budgetInfo.state === 'EMERGENCY') {
    return { allowed: false, reason: 'Budget emergency - reserve reached' }
  }
  if (budgetInfo.state === 'CRITICAL' && isOptional) {
    return { allowed: false, reason: 'Budget critical - optional work skipped' }
  }
  if (cost > usable) {
    return {
      allowed: false,
      reason: `Insufficient usable budget: ${usable} < ${cost}`
    }
  }
  if (isOptional && cost > remaining - reserved) {
    return { allowed: false, reason: 'Optional work would breach reserve' }
  }
  return { allowed: true }
}

/**
 * Parse decimal string to number (for comparison only, not for arithmetic)
 */
function parseDecimal (s: string): number {
  return parseFloat(s)
}

/**
 * Format decimal for display
 */
export function formatDecimal (value: string, unit: string = 'USD'): string {
  const num = parseDecimal(value)
  if (unit === 'USD') {
    return `$${num.toFixed(2)}`
  }
  return `${num.toFixed(2)} ${unit}`
}

/**
 * Budget event for streaming
 */
export const BudgetEventSchema = z.object({
  type: z.enum(['warning', 'exhausted', 'reserve_reached', 'state_changed']),
  taskId: z.string(),
  previousState: BudgetStateSchema.optional(),
  currentState: BudgetStateSchema,
  budgetInfo: BudgetInfoSchema,
  timestamp: z.string().datetime({ offset: true })
})

export type BudgetEvent = z.infer<typeof BudgetEventSchema>
