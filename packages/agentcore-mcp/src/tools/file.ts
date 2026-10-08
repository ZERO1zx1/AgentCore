import { z } from 'zod'
import type { ToolDefinition } from '@agentcore/types'

/**
 * Read file tool
 */
export const readFileTool: ToolDefinition = {
  name: 'read_file',
  description: 'Read content of a file',
  inputSchema: z.object({
    path: z.string().describe('File path'),
    encoding: z
      .enum(['utf-8', 'base64', 'hex'])
      .default('utf-8')
      .describe('File encoding'),
    maxChars: z
      .number()
      .int()
      .positive()
      .default(50000)
      .describe('Maximum characters')
  }),
  risk: 'read',
  requiresApproval: false,
  estimatedCost: '0.001',
  timeoutSeconds: 10,
  retryable: true,
  maxRetries: 2
}

/**
 * Write file tool
 */
export const writeFileTool: ToolDefinition = {
  name: 'write_file',
  description: 'Write content to a file',
  inputSchema: z.object({
    path: z.string().describe('File path'),
    content: z.string().describe('Content to write'),
    encoding: z
      .enum(['utf-8', 'base64', 'hex'])
      .default('utf-8')
      .describe('Content encoding'),
    createDirs: z
      .boolean()
      .default(true)
      .describe('Create parent directories if needed')
  }),
  risk: 'write',
  requiresApproval: true,
  estimatedCost: '0.001',
  timeoutSeconds: 10,
  retryable: false,
  maxRetries: 0
}

/**
 * Delete file tool
 */
export const deleteFileTool: ToolDefinition = {
  name: 'delete_file',
  description: 'Delete a file',
  inputSchema: z.object({
    path: z.string().describe('File path'),
    recursive: z
      .boolean()
      .default(false)
      .describe('Delete directory recursively')
  }),
  risk: 'dangerous',
  requiresApproval: true,
  estimatedCost: '0.001',
  timeoutSeconds: 10,
  retryable: false,
  maxRetries: 0
}

/**
 * List directory tool
 */
export const listDirectoryTool: ToolDefinition = {
  name: 'list_directory',
  description: 'List contents of a directory',
  inputSchema: z.object({
    path: z.string().describe('Directory path'),
    recursive: z.boolean().default(false).describe('List recursively'),
    includeHidden: z.boolean().default(false).describe('Include hidden files')
  }),
  risk: 'read',
  requiresApproval: false,
  estimatedCost: '0.001',
  timeoutSeconds: 10,
  retryable: true,
  maxRetries: 2
}

/**
 * All file tools
 */
export const fileTools: ToolDefinition[] = [
  readFileTool,
  writeFileTool,
  deleteFileTool,
  listDirectoryTool
]
