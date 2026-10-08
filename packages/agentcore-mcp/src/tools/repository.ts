import { z } from 'zod'
import type { ToolDefinition } from '@agentcore/types'

/**
 * Repository inspection tool
 */
export const inspectRepositoryTool: ToolDefinition = {
  name: 'inspect_repository',
  description: 'Inspect repository structure, files, and metadata',
  inputSchema: z.object({
    path: z.string().default('.').describe('Repository path to inspect'),
    includeGit: z.boolean().default(true).describe('Include git status'),
    maxFiles: z
      .number()
      .int()
      .positive()
      .default(500)
      .describe('Maximum files to list')
  }),
  risk: 'read',
  requiresApproval: false,
  estimatedCost: '0.001',
  timeoutSeconds: 30,
  retryable: true,
  maxRetries: 2
}

/**
 * List repository files tool
 */
export const listRepositoryFilesTool: ToolDefinition = {
  name: 'list_repository_files',
  description: 'List files in repository with filtering options',
  inputSchema: z.object({
    path: z.string().default('.').describe('Repository path'),
    pattern: z.string().optional().describe('Glob pattern to filter files'),
    extensions: z
      .array(z.string())
      .optional()
      .describe('Filter by file extensions'),
    maxResults: z
      .number()
      .int()
      .positive()
      .default(100)
      .describe('Maximum results')
  }),
  risk: 'read',
  requiresApproval: false,
  estimatedCost: '0.001',
  timeoutSeconds: 30,
  retryable: true,
  maxRetries: 2
}

/**
 * Get file content tool
 */
export const getFileContentTool: ToolDefinition = {
  name: 'get_file_content',
  description: 'Read content of a specific file',
  inputSchema: z.object({
    path: z.string().describe('File path relative to repository root'),
    maxChars: z
      .number()
      .int()
      .positive()
      .default(10000)
      .describe('Maximum characters to read')
  }),
  risk: 'read',
  requiresApproval: false,
  estimatedCost: '0.001',
  timeoutSeconds: 10,
  retryable: true,
  maxRetries: 2
}

/**
 * Search repository tool
 */
export const searchRepositoryTool: ToolDefinition = {
  name: 'search_repository',
  description: 'Search for patterns in repository files',
  inputSchema: z.object({
    path: z.string().default('.').describe('Repository path'),
    pattern: z.string().describe('Search pattern (regex)'),
    filePattern: z.string().optional().describe('File pattern to search in'),
    maxResults: z
      .number()
      .int()
      .positive()
      .default(50)
      .describe('Maximum results')
  }),
  risk: 'read',
  requiresApproval: false,
  estimatedCost: '0.01',
  timeoutSeconds: 60,
  retryable: true,
  maxRetries: 2
}

/**
 * All repository tools
 */
export const repositoryTools: ToolDefinition[] = [
  inspectRepositoryTool,
  listRepositoryFilesTool,
  getFileContentTool,
  searchRepositoryTool
]
