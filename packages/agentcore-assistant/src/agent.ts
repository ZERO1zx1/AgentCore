import type { TaskInput, TaskManifest, BridgeClient } from '@agentcore/types'
import type { AssistantConfig } from './config.js'
import type { BridgeConfig } from '@agentcore/types'
import { mergeConfig, DEFAULT_ASSISTANT_CONFIG } from './config.js'
import { createBridge } from './bridge.js'
import { createDefaultRegistry } from './registry.js'
import { createDefaultPolicy } from './policy.js'
import { createDefaultApprovalManager } from './approval.js'
import { createSession, Session, SessionConfig } from './session.js'
import {
  runAgentLoop,
  runAgentLoopStreaming,
  createLoopController
} from './loop.js'

/**
 * Main Agent class - entry point for running AgentCore tasks
 */
export class Agent {
  private config: AssistantConfig
  private bridge: BridgeClient
  private toolRegistry: ReturnType<typeof createDefaultRegistry>
  private permissionPolicy: ReturnType<typeof createDefaultPolicy>

  constructor (config: Partial<AssistantConfig> = {}) {
    this.config = mergeConfig(config)
    this.bridge = createBridge(this.config.bridge)
    this.toolRegistry = createDefaultRegistry()
    this.permissionPolicy = createDefaultPolicy(this.config)
  }

  getToolRegistry () {
    return this.toolRegistry
  }

  getPermissionPolicy () {
    return this.permissionPolicy
  }

  /**
   * Run a task to completion
   */
  async runTask (taskInput: TaskInput): Promise<TaskManifest> {
    // Create session
    const session = this.createSession(taskInput)

    // Run agent loop
    const manifest = await runAgentLoop(session, {
      maxIterations: this.config.maxIterations,
      maxToolCalls: this.config.maxToolCalls,
      iterationTimeoutMs: this.config.iterationTimeoutMs,
      toolTimeoutMs: this.config.toolTimeoutMs
    })

    return manifest
  }

  /**
   * Run a task with streaming events
   */
  async runTaskStreaming (
    taskInput: TaskInput,
    eventHandler: (event: any) => Promise<void>
  ): Promise<TaskManifest> {
    const session = this.createSession(taskInput)

    const manifest = await runAgentLoopStreaming(session, {
      maxIterations: this.config.maxIterations,
      maxToolCalls: this.config.maxToolCalls,
      iterationTimeoutMs: this.config.iterationTimeoutMs,
      toolTimeoutMs: this.config.toolTimeoutMs,
      eventHandler
    })

    return manifest
  }

  /**
   * Resume a task from checkpoint
   */
  async resumeTask (
    taskId: string,
    additionalBudget?: string
  ): Promise<TaskManifest> {
    const taskInput: TaskInput = {
      taskId: crypto.randomUUID(),
      prompt: 'Resume task',
      executionMode: 'AUTO',
      budget: additionalBudget || '0',
      budgetUnit: 'USD',
      files: [],
      outputType: 'text',
      resumeTaskId: taskId
    }

    return this.runTask(taskInput)
  }

  /**
   * Create a session for a task
   */
  createSession (taskInput: TaskInput): Session {
    const sessionId = crypto.randomUUID()

    const registry = createDefaultRegistry()
    const policy = createDefaultPolicy(this.config)
    const approvalManager = createDefaultApprovalManager({
      defaultTimeoutSeconds: this.config.approval.defaultTimeoutSeconds,
      autoApproveRead: this.config.approval.autoApproveRead,
      autoApproveWrite: this.config.approval.autoApproveWrite,
      requireApprovalFor: this.config.approval.requireApprovalFor
    })

    const sessionConfig: SessionConfig = {
      sessionId,
      taskInput,
      bridge: this.bridge,
      toolRegistry: registry,
      approvalManager,
      permissionPolicy: policy,
      maxIterations: this.config.maxIterations,
      maxToolCalls: this.config.maxToolCalls,
      iterationTimeoutMs: this.config.iterationTimeoutMs,
      toolTimeoutMs: this.config.toolTimeoutMs,
      retryPolicy: this.config.retryPolicy,
      budgetLimits: this.config.budgetLimits,
      security: this.config.security
    }

    return createSession(sessionConfig)
  }

  /**
   * Get bridge client for direct access
   */
  getBridge () {
    return this.bridge
  }

  /**
   * Get configuration
   */
  getConfig (): AssistantConfig {
    return this.config
  }

  /**
   * Connect bridge
   */
  async connect (): Promise<void> {
    await this.bridge.connect()
  }

  /**
   * Disconnect bridge
   */
  async disconnect (): Promise<void> {
    await this.bridge.disconnect()
  }

  /**
   * Check if connected
   */
  isConnected (): boolean {
    return this.bridge.isConnected()
  }
}

/**
 * Create agent with default configuration
 */
export function createAgent (config?: Partial<AssistantConfig>): Agent {
  return new Agent(config)
}

/**
 * Quick run function for simple tasks
 */
export async function quickRun (
  prompt: string,
  options: {
    budget?: string
    executionMode?: 'AUTO' | 'FULL' | 'CREDIT_SAFE'
    files?: string[]
    repository?: string
    config?: Partial<AssistantConfig>
  } = {}
): Promise<TaskManifest> {
  const agent = createAgent(options.config)

  const taskInput: TaskInput = {
    taskId: crypto.randomUUID(),
    prompt,
    executionMode: options.executionMode || 'AUTO',
    budget: options.budget || '10.0',
    budgetUnit: 'USD',
    files: options.files || [],
    repository: options.repository,
    outputType: 'text'
  }

  try {
    await agent.connect()
    return await agent.runTask(taskInput)
  } finally {
    await agent.disconnect()
  }
}

/**
 * Default export
 */
export default Agent
