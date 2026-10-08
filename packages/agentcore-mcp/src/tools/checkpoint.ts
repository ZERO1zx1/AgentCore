import { z } from 'zod'
import type { ToolDefinition } from '@agentcore/types'

/**
 * Get checkpoint tool
 */
export const getCheckpointTool: ToolDefinition = {
  name: 'agentcore_get_checkpoint',
  description: 'Get checkpoint/manifest for a task',
  inputSchema: z.object({
    taskId: z.string().describe('Task ID')
  }),
  risk: 'read',
  requiresApproval: false,
  estimatedCost: '0.001',
  timeoutSeconds: 10,
  retryable: true,
  maxRetries: 2
}

/**
 * List checkpoints tool
 */
export const listCheckpointsTool: ToolDefinition = {
  name: 'agentcore_list_checkpoints',
  description: 'List all checkpoints',
  inputSchema: z.object({
    limit: z.number().int().positive().default(50).describe('Maximum results')
  }),
  risk: 'read',
  requiresApproval: false,
  estimatedCost: '0.001',
  timeoutSeconds: 10,
  retryable: true,
  maxRetries: 2
}

/**
 * Get budget status tool
 */
export const getBudgetStatusTool: ToolDefinition = {
  name: 'agentcore_budget_status',
  description: 'Get budget status for a task',
  inputSchema: z.object({
    taskId: z.string().describe('Task ID')
  }),
  risk: 'read',
  requiresApproval: false,
  estimatedCost: '0.001',
  timeoutSeconds: 10,
  retryable: true,
  maxRetries: 2
}

/**
 * All checkpoint tools
 */
export const checkpointTools: ToolDefinition[] = [
  getCheckpointTool,
  listCheckpointsTool,
  getBudgetStatusTool
]
