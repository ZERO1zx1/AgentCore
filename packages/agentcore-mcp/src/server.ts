import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
} from '@modelcontextprotocol/sdk/types.js'
import { z } from 'zod'
import type { Agent, AssistantConfig } from '@agentcore/assistant'
import { createAgent } from '@agentcore/assistant'
import type { TaskInput, TaskManifest } from '@agentcore/types'
import { registerTools } from './tools/index.js'
import { registerResources } from './resources/index.js'

/**
 * MCP Server configuration
 */
export const McpServerConfigSchema = z.object({
  agentConfig: z
    .object({
      maxIterations: z.number().int().positive().default(50),
      maxToolCalls: z.number().int().positive().default(100),
      bridge: z
        .object({
          transport: z.enum(['stdio', 'http', 'websocket']).default('stdio'),
          pythonExecutable: z.string().default('python'),
          engineModule: z.string().default('-m src.core.engine'),
          workingDirectory: z.string().default('.'),
          timeoutMs: z.number().int().positive().default(120000),
          maxBuffer: z.number().int().positive().default(10 * 1024 * 1024),
          heartbeatIntervalMs: z.number().int().positive().default(30000),
        })
        .default({}),
      approval: z
        .object({
          defaultTimeoutSeconds: z.number().int().positive().default(300),
          autoApproveRead: z.boolean().default(true),
          autoApproveWrite: z.boolean().default(false),
          requireApprovalFor: z
            .array(z.enum(['read', 'write', 'external', 'dangerous']))
            .default(['write', 'external', 'dangerous']),
        })
        .default({}),
      security: z
        .object({
          allowedPaths: z.array(z.string()).default(['.']),
          blockedPaths: z
            .array(z.string())
            .default([
              '.git',
              '.env',
              'node_modules',
              '.agentcore',
              '__pycache__',
            ]),
          allowedCommands: z.array(z.string()).default([]),
          blockedCommands: z.array(z.string()).default([]),
          secretRedaction: z.boolean().default(true),
          promptInjectionDetection: z.boolean().default(true),
          untrustedOutputMarking: z.boolean().default(true),
        })
        .default({}),
    })
    .default({}),
  serverName: z.string().default('agentcore'),
  serverVersion: z.string().default('0.1.0'),
})

export type McpServerConfig = z.infer<typeof McpServerConfigSchema>

/**
 * AgentCore MCP Server
 */
export class AgentCoreMcpServer {
  private server: Server
  private agent: Agent
  private config: McpServerConfig
  private transport: StdioServerTransport | null = null

  constructor (config: Partial<McpServerConfig> = {}) {
    this.config = McpServerConfigSchema.parse(config)

    // Create agent
    this.agent = createAgent(this.config.agentConfig)

    // Create MCP server
    this.server = new Server(
      {
        name: this.config.serverName,
        version: this.config.serverVersion
      },
      {
        capabilities: {
          tools: {},
          resources: {},
        }
      }
    )

    // Register handlers
    this.registerHandlers()
    // Populate the assistant registry before ListTools/CallTool handlers run.
    registerTools(this.agent)

    // Register resources from modules
    registerResources(this.server)
  }

  /**
   * Register MCP handlers
   */
  private registerHandlers (): void {
    // List tools
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      const tools = this.agent.getToolRegistry()?.list() || []
      return {
        tools: tools.map(tool => ({
          name: tool.name,
          description: tool.description,
          inputSchema: tool.inputSchema
        }))
      }
    })

    // Call tool
    this.server.setRequestHandler(CallToolRequestSchema, async request => {
      const { name, arguments: args } = request.params

      // Get tool from registry
      const tool = this.agent.getToolRegistry()?.get(name)
      if (!tool) {
        throw new Error(`Tool not found: ${name}`)
      }

      // Validate input
      const validation = this.agent.getToolRegistry()?.validateInput(name, args)
      if (validation && !validation.ok) {
        throw new Error(
          `Invalid input: ${validation.errors.join(', ')}`
        )
      }

      // Check permission
      const permission = this.agent.getPermissionPolicy()?.checkPermission(tool, {
        taskId: 'mcp-task',
        sessionId: 'mcp-session',
        workingDirectory: process.cwd()
      })

      if (!permission?.allowed) {
        throw new Error(`Permission denied: ${permission?.reason}`)
      }

      // For MCP, we need to create a task and run it
      // This is a simplified implementation
      const taskInput: TaskInput = {
        taskId: crypto.randomUUID(),
        prompt: `MCP Tool: ${name}`,
        executionMode: 'AUTO',
        budget: '10.0',
        budgetUnit: 'USD',
        files: [],
        repository: process.cwd(),
        outputType: 'text',
      }

      const manifest = await this.agent.runTask(taskInput)

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(
              {
                status: manifest.status,
                outputs: manifest.outputs,
                errors: manifest.errors
              },
              null,
              2
            )
          }
        ]
      }
    })

    // List resources
    this.server.setRequestHandler(ListResourcesRequestSchema, async () => {
      return {
        resources: [
          {
            uri: 'agentcore://status',
            name: 'AgentCore Status',
            description: 'Current AgentCore engine status',
            mimeType: 'application/json'
          },
          {
            uri: 'agentcore://budget',
            name: 'Budget Status',
            description: 'Current budget information',
            mimeType: 'application/json'
          },
          {
            uri: 'agentcore://checkpoints',
            name: 'Checkpoints',
            description: 'List of available checkpoints',
            mimeType: 'application/json'
          }
        ]
      }
    })

    // Read resource - delegate to registered resource handlers
    // Resources are handled by the registerResources function
  }

  /**
   * Start the MCP server
   */
  async start (): Promise<void> {
    // Connect agent bridge
    await this.agent.connect()

    // Create stdio transport
    this.transport = new StdioServerTransport()

    // Connect server to transport
    await this.server.connect(this.transport)
  }

  /**
   * Stop the MCP server
   */
  async stop (): Promise<void> {
    await this.agent.disconnect()
    if (this.transport) {
      await this.transport.close()
    }
  }

  /**
   * Get agent instance
   */
  getAgent (): Agent {
    return this.agent
  }
}

/**
 * Create and start MCP server
 */
export async function createMcpServer (
  config?: Partial<McpServerConfig>
): Promise<AgentCoreMcpServer> {
  const server = new AgentCoreMcpServer(config)
  await server.start()
  return server
}

/**
 * Run MCP server (for CLI usage)
 */
export async function runMcpServer (
  config?: Partial<McpServerConfig>
): Promise<void> {
  const server = await createMcpServer(config)

  // Handle shutdown signals
  process.on('SIGINT', async () => {
    await server.stop()
    process.exit(0)
  })

  process.on('SIGTERM', async () => {
    await server.stop()
    process.exit(0)
  })

  // Keep running
  await new Promise(() => {})
}
