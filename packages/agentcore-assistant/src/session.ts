import { EventEmitter } from 'eventemitter3'
import { z } from 'zod'
import type {
  TaskInput,
  TaskManifest,
  WorkUnit,
  BudgetInfo,
  AgentEvent,
  ApprovalRequiredEvent
} from '@agentcore/types'
import type { ToolCall, ToolResult, ToolDefinition } from '@agentcore/types'
import type { ApprovalManager } from './approval.js'
import type { ToolRegistry } from './registry.js'
import type { PermissionPolicy } from './policy.js'
import type { BridgeClient } from '@agentcore/types'
import type { StructuredError } from '@agentcore/types'

/**
 * Session state
 */
export const SessionStateSchema = z.enum([
  'created',
  'initializing',
  'running',
  'paused',
  'waiting_approval',
  'completed',
  'failed',
  'cancelled'
])

export type SessionState = z.infer<typeof SessionStateSchema>

/**
 * Session configuration
 */
export interface SessionConfig {
  sessionId: string
  taskInput: TaskInput
  bridge: BridgeClient
  toolRegistry: ToolRegistry
  approvalManager: ApprovalManager
  permissionPolicy: PermissionPolicy
  maxIterations: number
  maxToolCalls: number
  iterationTimeoutMs: number
  toolTimeoutMs: number
  retryPolicy: {
    maxRetries: number
    baseDelayMs: number
    maxDelayMs: number
    exponentialBase: number
    jitter: boolean
    retryableCategories: string[]
    retryableCodes: string[]
  }
  budgetLimits: {
    maxTotalCost?: string
    maxCostPerTool?: string
    reserveRatio: number
  }
  security: {
    allowedPaths: string[]
    blockedPaths: string[]
    secretRedaction: boolean
    promptInjectionDetection: boolean
    untrustedOutputMarking: boolean
  }
}

/**
 * Session class
 */
export class Session extends EventEmitter {
  public readonly sessionId: string
  public readonly taskId: string
  public state: SessionState = 'created'
  public manifest?: TaskManifest
  public workUnits: WorkUnit[] = []
  public budgetInfo?: BudgetInfo
  public currentIteration = 0
  public toolCallsCount = 0
  public startTime: Date
  public endTime?: Date
  public error?: StructuredError

  private config: SessionConfig
  private bridge: BridgeClient
  private toolRegistry: ToolRegistry
  private approvalManager: ApprovalManager
  private permissionPolicy: PermissionPolicy
  private eventUnsubscribe?: () => void

  constructor (config: SessionConfig) {
    super()
    this.config = config
    this.sessionId = config.sessionId
    this.taskId = config.taskInput.taskId || crypto.randomUUID()
    this.bridge = config.bridge
    this.toolRegistry = config.toolRegistry
    this.approvalManager = config.approvalManager
    this.permissionPolicy = config.permissionPolicy
    this.startTime = new Date()
  }

  /**
   * Initialize session
   */
  async initialize (): Promise<void> {
    this.state = 'initializing'
    this.emit('state:changed', this.state)

    try {
      // Connect to bridge
      await this.bridge.connect()

      // Initialize task via bridge
      const request = {
        type: 'initialize_task' as const,
        requestId: crypto.randomUUID(),
        timestamp: new Date().toISOString(),
        payload: { taskInput: this.config.taskInput }
      }

      const response = await this.bridge.send(request)

      if (response.type === 'error') {
        const errorPayload = response.payload as { error?: { message: string } }
        throw new Error(errorPayload.error?.message || 'Unknown error')
      }

      if (response.type !== 'task_initialized') {
        throw new Error(`Unexpected response: ${response.type}`)
      }

      this.manifest = response.payload.manifest as TaskManifest
      this.workUnits = this.manifest.workUnits || []

      // Subscribe to events
      this.eventUnsubscribe = await this.bridge.subscribeToEvents(
        this.taskId,
        event => {
          this.handleEvent(event)
        }
      )

      this.state = 'running'
      this.emit('state:changed', this.state)
    } catch (error) {
      this.state = 'failed'
      this.error = this.toStructuredError(error)
      this.emit('state:changed', this.state)
      this.emit('error', this.error)
      throw error
    }
  }

  /**
   * Run the agent loop
   */
  async run (): Promise<TaskManifest> {
    if (this.state !== 'running') {
      throw new Error(`Session not running: ${this.state}`)
    }

    while (true) {
      const currentState = this.state as SessionState
      if (currentState !== 'running' && currentState !== 'waiting_approval') {
        break
      }
      // Check iteration limit
      if (this.currentIteration >= this.config.maxIterations) {
        this.error = this.createError(
          'MAX_ITERATIONS_REACHED',
          `Max iterations (${this.config.maxIterations}) reached`
        )
        this.state = 'failed'
        break
      }

      // Check tool calls limit
      if (this.toolCallsCount >= this.config.maxToolCalls) {
        this.error = this.createError(
          'MAX_TOOL_CALLS_REACHED',
          `Max tool calls (${this.config.maxToolCalls}) reached`
        )
        this.state = 'failed'
        break
      }

      this.currentIteration++
      this.emit('iteration:start', this.currentIteration)

      try {
        // Run next unit via bridge
        const request = {
          type: 'run_next_unit' as const,
          requestId: crypto.randomUUID(),
          timestamp: new Date().toISOString(),
          payload: {}
        }

        const response = await this.bridge.send(request)

        if (response.type === 'error') {
          const errorPayload = response.payload as { error?: StructuredError }
          const error = errorPayload.error
          if (error && this.isRetryableError(error)) {
            await this.handleRetry(error)
            continue
          }
          this.error =
            error || this.createError('INTERNAL_ERROR', 'Unknown error')
          this.state = 'failed'
          break
        }

        if (response.type === 'unit_completed') {
          this.manifest = response.payload.manifest as TaskManifest
          this.workUnits = this.manifest?.workUnits || []

          if (response.payload.success) {
            this.emit('unit:completed', response.payload.workUnitId)
          } else {
            const errorPayload = response.payload as { error?: StructuredError }
            this.emit(
              'unit:failed',
              response.payload.workUnitId,
              errorPayload.error
            )
          }

          // Check if task is complete
          if (this.manifest && this.isTaskComplete(this.manifest)) {
            this.state = 'completed'
            this.emit('state:changed', this.state)
            break
          }
        }
      } catch (error) {
        this.error = this.toStructuredError(error)
        if (this.isRetryableError(this.error)) {
          await this.handleRetry(this.error)
          continue
        }
        this.state = 'failed'
        break
      }
    }

    this.endTime = new Date()

    const finalState = this.state as SessionState
    if (finalState === 'running' || finalState === 'waiting_approval' || finalState === 'paused') {
      this.state = 'completed'
    }

    this.emit('state:changed', this.state)

    // Fetch final manifest
    if (this.bridge.isConnected()) {
      try {
        const request = {
          type: 'get_manifest' as const,
          requestId: crypto.randomUUID(),
          timestamp: new Date().toISOString(),
          payload: { taskId: this.taskId }
        }
        const response = await this.bridge.send(request)
        if (response.type === 'manifest') {
          this.manifest = response.payload.manifest as TaskManifest
        }
      } catch {
        // Ignore fetch errors
      }
    }

    return this.manifest!
  }

  /**
   * Pause session
   */
  pause (): void {
    if (this.state === 'running') {
      this.state = 'paused'
      this.emit('state:changed', this.state)
    }
  }

  /**
   * Resume session
   */
  resume (): void {
    if (this.state === 'paused') {
      this.state = 'running'
      this.emit('state:changed', this.state)
    }
  }

  /**
   * Cancel session
   */
  async cancel (reason: string = 'Cancelled by user'): Promise<void> {
    this.state = 'cancelled'
    this.error = this.createError('CANCELLED', reason)

    try {
      await this.bridge.send({
        type: 'cancel_task',
        requestId: crypto.randomUUID(),
        timestamp: new Date().toISOString(),
        payload: { taskId: this.taskId, reason }
      })
    } catch {
      // Ignore
    }

    this.endTime = new Date()
    this.emit('state:changed', this.state)
    this.emit('cancelled', reason)
  }

  /**
   * Handle incoming event
   */
  private handleEvent (event: AgentEvent): void {
    this.emit('event', event)

    switch (event.type) {
      case 'budget.warning':
      case 'budget.exhausted':
      case 'budget.reserve_reached':
        this.emit('budget:warning', event)
        break
      case 'approval.required':
        this.handleApprovalRequired(event as ApprovalRequiredEvent)
        break
      case 'checkpoint.saved':
        this.emit('checkpoint:saved', event)
        break
      case 'tool.completed':
        this.toolCallsCount++
        break
      case 'tool.failed':
        this.toolCallsCount++
        break
    }
  }

  /**
   * Handle approval required event
   */
  private async handleApprovalRequired (
    event: ApprovalRequiredEvent
  ): Promise<void> {
    this.state = 'waiting_approval'
    this.emit('state:changed', this.state)

    const call: ToolCall = {
      id: event.data.callId,
      taskId: event.taskId,
      name: event.data.toolName,
      input: event.data.input,
      correlationId: event.correlationId
    }

    const tool = this.toolRegistry.get(event.data.toolName)
    if (!tool) {
      this.emit(
        'error',
        this.createError(
          'MODEL_NOT_FOUND',
          `Tool not found: ${event.data.toolName}`
        )
      )
      return
    }

    const result = await this.approvalManager.requestApproval(
      call,
      tool,
      event.data.reason
    )

    if (result === 'granted') {
      this.state = 'running'
      this.emit('state:changed', this.state)
    } else {
      this.state = 'failed'
      this.error = this.createError(
        'HUMAN_APPROVAL_REQUIRED',
        `Approval ${result}`
      )
      this.emit('state:changed', this.state)
    }
  }

  /**
   * Handle retry with exponential backoff
   */
  private async handleRetry (error: StructuredError): Promise<void> {
    const policy = this.config.retryPolicy
    const delay = Math.min(
      policy.baseDelayMs *
        Math.pow(policy.exponentialBase, this.currentIteration),
      policy.maxDelayMs
    )

    const jitteredDelay = policy.jitter
      ? delay * (0.5 + Math.random() * 0.5)
      : delay

    this.emit('retry:scheduled', { error, delay: jitteredDelay })

    await new Promise(resolve => setTimeout(resolve, jitteredDelay))
  }

  /**
   * Check if error is retryable
   */
  private isRetryableError (error: StructuredError): boolean {
    const policy = this.config.retryPolicy
    if (!error.retryable) return false
    if (policy.retryableCategories.includes(error.category)) return true
    if (policy.retryableCodes.includes(error.code as any)) return true
    return false
  }

  /**
   * Check if task is complete
   */
  private isTaskComplete (manifest: TaskManifest): boolean {
    return (
      manifest.status === 'completed' ||
      manifest.status === 'partially_completed' ||
      manifest.status === 'failed' ||
      manifest.status === 'blocked'
    )
  }

  /**
   * Convert error to structured error
   */
  private toStructuredError (error: unknown): StructuredError {
    if (error instanceof Error) {
      return {
        code: 'INTERNAL_ERROR',
        message: error.message,
        category: 'permanent',
        severity: 'high',
        retryable: false,
        correlationId: crypto.randomUUID(),
        taskId: this.taskId,
        timestamp: new Date().toISOString(),
        source: 'typescript',
        stackTrace: error.stack
      }
    }
    return {
      code: 'UNKNOWN_ERROR',
      message: String(error),
      category: 'permanent',
      severity: 'medium',
      retryable: false,
      correlationId: crypto.randomUUID(),
      taskId: this.taskId,
      timestamp: new Date().toISOString(),
      source: 'typescript'
    }
  }

  private createError (code: string, message: string): StructuredError {
    return {
      code: code as any,
      message,
      category: 'permanent',
      severity: 'high',
      retryable: false,
      correlationId: crypto.randomUUID(),
      taskId: this.taskId,
      timestamp: new Date().toISOString(),
      source: 'typescript'
    }
  }

  /**
   * Cleanup
   */
  async dispose (): Promise<void> {
    if (this.eventUnsubscribe) {
      this.eventUnsubscribe()
    }
    await this.bridge.disconnect()
  }
}

/**
 * Create session
 */
export function createSession (config: SessionConfig): Session {
  return new Session(config)
}
