import { z } from 'zod'

/**
 * Task input from user/client
 */
export const TaskInputSchema = z.object({
  taskId: z.string().uuid().optional(),
  prompt: z.string().min(1),
  executionMode: z.enum(['AUTO', 'FULL', 'CREDIT_SAFE']).default('AUTO'),
  budget: z.string().regex(/^\d+(\.\d+)?$/),
  budgetUnit: z.string().default('USD'),
  files: z.array(z.string()).default([]),
  repository: z.string().optional(),
  resumeTaskId: z.string().optional(),
  metadata: z.record(z.unknown()).optional(),
  requestedSkill: z.string().optional(),
  outputType: z.string().default('text')
})

export type TaskInput = z.infer<typeof TaskInputSchema>

/**
 * Task status from Python engine
 */
export const TaskStatusSchema = z.enum([
  'in_progress',
  'completed',
  'partially_completed',
  'paused_budget',
  'blocked',
  'failed',
  'cancelled'
])

export type TaskStatus = z.infer<typeof TaskStatusSchema>

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
  state: z.enum(['NORMAL', 'CONSERVE', 'CRITICAL', 'EMERGENCY', 'EXHAUSTED']),
  executionMode: z.string().optional()
})

export type BudgetInfo = z.infer<typeof BudgetInfoSchema>

/**
 * Work unit from Python planner
 */
export const WorkUnitSchema = z.object({
  id: z.string(),
  type: z.string(),
  priority: z.enum(['P0', 'P1', 'P2', 'P3', 'P4']),
  instruction: z.string(),
  requiredCapabilities: z.array(z.string()),
  estimatedCost: z.number(),
  dependencies: z.array(z.string()),
  optional: z.boolean(),
  status: z
    .enum(['pending', 'completed', 'skipped', 'failed', 'in_progress'])
    .default('pending'),
  inputRefs: z.array(z.string()).default([]),
  sourceRefs: z.array(z.string()).default([]),
  contextRefs: z.array(z.string()).default([]),
  outputRefs: z.array(z.string()).default([]),
  metadata: z.record(z.unknown()).default({})
})

export type WorkUnit = z.infer<typeof WorkUnitSchema>

/**
 * Task manifest (schema 3.0) from Python checkpoint
 */
export const TaskManifestSchema = z.object({
  schemaVersion: z.literal('3.0'),
  taskId: z.string(),
  status: TaskStatusSchema,
  executionMode: z.string(),
  createdAt: z.string().datetime({ offset: true }),
  updatedAt: z.string().datetime({ offset: true }),
  input: z.object({
    type: z.string(),
    sources: z.array(z.string()),
    repository: z.string().optional(),
    taskContextFingerprint: z.string().optional()
  }),
  progress: z.object({
    completedUnits: z.number().int().nonnegative(),
    totalUnits: z.number().int().positive(),
    currentUnit: z.string().nullable().optional()
  }),
  budget: BudgetInfoSchema,
  outputs: z.array(z.string()).default([]),
  validation: z.record(z.unknown()).default({}),
  modelHistory: z.array(z.unknown()).default([]),
  completedWork: z.array(z.string()).default([]),
  pendingWork: z.array(z.string()).default([]),
  errors: z.array(z.string()).default([]),
  reason: z.string().default('NONE'),
  usageHistory: z.array(z.unknown()).default([]),
  nextActions: z.array(z.string()).default([]),
  taskContext: z.unknown().optional(),
  workUnits: z.array(WorkUnitSchema).default([]),
  orchestration: z.record(z.unknown()).default({})
})

export type TaskManifest = z.infer<typeof TaskManifestSchema>

/**
 * Task context from Python engine
 */
export const TaskContextSchema = z.object({
  taskId: z.string(),
  userPrompt: z.string(),
  executionMode: z.string(),
  requestedOutputType: z.string(),
  inputSources: z.array(z.string()).default([]),
  sourceTypes: z.record(z.string()).default({}),
  sourceFingerprints: z.record(z.string()).default({}),
  repositoryContext: z.unknown().optional(),
  documentContext: z.record(z.unknown()).default({}),
  structuredContext: z.record(z.unknown()).default({}),
  assetContext: z.record(z.unknown()).default({}),
  relevantFiles: z.array(z.string()).default([]),
  persistedContextPaths: z.record(z.string()).default({}),
  metadata: z.record(z.unknown()).default({}),
  orchestration: z.record(z.unknown()).default({}),
  memoryHits: z.array(z.unknown()).default([])
})

export type TaskContext = z.infer<typeof TaskContextSchema>

/**
 * Execution result from Python executor
 */
export const ExecutionResultSchema = z.object({
  success: z.boolean(),
  outputText: z.string().optional(),
  usage: z
    .object({
      inputTokens: z.number().int().nonnegative(),
      outputTokens: z.number().int().nonnegative(),
      totalTokens: z.number().int().nonnegative()
    })
    .optional(),
  provider: z.string().optional(),
  modelId: z.string().optional(),
  providerRequestId: z.string().optional(),
  error: z.string().optional(),
  metadata: z.record(z.unknown()).default({})
})

export type ExecutionResult = z.infer<typeof ExecutionResultSchema>

/**
 * Cost accounting from Python engine
 */
export const CostRecordSchema = z.object({
  workUnitId: z.string(),
  provider: z.string(),
  modelId: z.string(),
  estimatedCost: z.number(),
  chargedCost: z.number(),
  actualCost: z.number().nullable().optional(),
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
 * Model spec from Python registry
 */
export const ModelSpecSchema = z.object({
  provider: z.string(),
  modelId: z.string(),
  tier: z.string(),
  inputPrice: z.string(), // Decimal as string
  outputPrice: z.string(), // Decimal as string
  capabilities: z.array(z.string()).default([]),
  inputModalities: z.array(z.string()).default(['text']),
  outputModalities: z.array(z.string()).default(['text']),
  contextSize: z.number().int().positive().optional(),
  enabled: z.boolean().default(true)
})

export type ModelSpec = z.infer<typeof ModelSpecSchema>
