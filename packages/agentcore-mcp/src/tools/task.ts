import { z } from 'zod'
import type { ToolDefinition } from '@agentcore/types'

/**
 * Start AgentCore task tool
 */
export const startTaskTool: ToolDefinition = {
  name: 'agentcore_start_task',
  description: 'Start a new AgentCore task',
  inputSchema: z.object({
    prompt: z.string().describe('Task prompt/goal'),
    executionMode: z
      .enum(['AUTO', 'FULL', 'CREDIT_SAFE'])
      .default('AUTO')
      .describe('Execution mode'),
    budget: z.string().default('10.0').describe('Budget in USD'),
    budgetUnit: z.string().default('USD').describe('Budget unit'),
    files: z.array(z.string()).default([]).describe('Input files'),
    repository: z.string().optional().describe('Repository path'),
    taskId: z.string().optional().describe('Optional task ID'),
    metadata: z.record(z.unknown()).optional().describe('Additional metadata')
  }),
  risk: 'external',
  requiresApproval: false,
  estimatedCost: '0.1',
  timeoutSeconds: 300,
  retryable: true,
  maxRetries: 2
}

/**
 * Resume AgentCore task tool
 */
export const resumeTaskTool: ToolDefinition = {
  name: 'agentcore_resume_task',
  description: 'Resume an AgentCore task from checkpoint',
  inputSchema: z.object({
    taskId: z.string().describe('Task ID to resume'),
    additionalBudget: z
      .string()
      .optional()
      .describe('Additional budget to add'),
    executionMode: z
      .enum(['AUTO', 'FULL', 'CREDIT_SAFE'])
      .optional()
      .describe('Override execution mode')
  }),
  risk: 'external',
  requiresApproval: false,
  estimatedCost: '0.1',
  timeoutSeconds: 300,
  retryable: true,
  maxRetries: 2
}

/**
 * Get task status tool
 */
export const getTaskStatusTool: ToolDefinition = {
  name: 'agentcore_task_status',
  description: 'Get status of an AgentCore task',
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
 * Cancel task tool
 */
export const cancelTaskTool: ToolDefinition = {
  name: 'agentcore_cancel_task',
  description: 'Cancel a running AgentCore task',
  inputSchema: z.object({
    taskId: z.string().describe('Task ID'),
    reason: z.string().optional().describe('Cancellation reason')
  }),
  risk: 'dangerous',
  requiresApproval: true,
  estimatedCost: '0.001',
  timeoutSeconds: 30,
  retryable: false,
  maxRetries: 0
}

/**
 * List tasks tool
 */
export const listTasksTool: ToolDefinition = {
  name: 'agentcore_list_tasks',
  description: 'List all AgentCore tasks/checkpoints',
  inputSchema: z.object({
    status: z
      .enum(['all', 'running', 'completed', 'failed', 'blocked'])
      .default('all')
      .describe('Filter by status'),
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
 * All task tools
 */
export const taskTools: ToolDefinition[] = [
  startTaskTool,
  resumeTaskTool,
  getTaskStatusTool,
  cancelTaskTool,
  listTasksTool
]
