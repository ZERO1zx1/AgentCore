import { EventEmitter } from 'eventemitter3'
import { spawn, ChildProcess } from 'child_process'
import { z } from 'zod'
import type {
  BridgeConfig,
  BridgeRequest,
  BridgeResponse,
  BridgeRequestType,
  BridgeResponseType,
  AgentEvent,
  TaskInput,
  TaskManifest,
  BudgetInfo,
  ToolCall,
  ToolResult,
  ToolExecutionContext,
  BridgeClient
} from '@agentcore/types'
import type { StructuredError } from '@agentcore/types'
import {
  validateBridgeRequest,
  validateBridgeResponse,
  createBridgeRequest
} from '@agentcore/types'

/**
 * Bridge client using stdio transport
 */
export class StdioBridgeClient extends EventEmitter implements BridgeClient {
  private process: ChildProcess | null = null
  private config: BridgeConfig
  private connected = false
  private requestId = 0
  private pendingRequests = new Map<
    string,
    {
      resolve: (response: BridgeResponse) => void
      reject: (error: Error) => void
      timeout: NodeJS.Timeout
    }
  >()
  private buffer = ''
  private eventSubscriptions = new Map<
    string,
    Set<(event: AgentEvent) => void>
  >()
  private responseBuffer = ''
  private isShuttingDown = false

  constructor (config: BridgeConfig) {
    super()
    this.config = config
  }

  /**
   * Generic request method for BridgeClient interface
   */
  async request<T extends BridgeRequest> (request: T): Promise<BridgeResponse> {
    return this.send(request)
  }

  /**
   * Connect to Python engine via stdio
   */
  async connect (): Promise<void> {
    if (this.connected) return

    return new Promise((resolve, reject) => {
      try {
        // Spawn Python process
        this.process = spawn(
          this.config.pythonExecutable,
          [this.config.engineModule, '--bridge', 'stdio'],
          {
            cwd: this.config.workingDirectory,
            env: { ...process.env, ...this.config.env },
            stdio: ['pipe', 'pipe', 'pipe']
          }
        )

        if (
          !this.process.stdout ||
          !this.process.stderr ||
          !this.process.stdin
        ) {
          throw new Error('Failed to create stdio pipes')
        }

        // Handle stdout - JSON lines
        this.process.stdout.on('data', (data: Buffer) => {
          this.buffer += data.toString()
          this.processBuffer()
        })

        // Handle stderr
        this.process.stderr.on('data', (data: Buffer) => {
          console.error(`[Python Bridge stderr] ${data.toString()}`)
        })

        // Handle process exit
        this.process.on('exit', (code, signal) => {
          this.connected = false
          if (!this.isShuttingDown) {
            this.emit(
              'error',
              new Error(
                `Python process exited with code ${code}, signal ${signal}`
              )
            )
            this.rejectPendingRequests(
              new Error(`Python process exited: ${code}`)
            )
          }
        })

        this.process.on('error', error => {
          this.connected = false
          this.emit('error', error)
          this.rejectPendingRequests(error)
        })

        // Wait for health check
        this.healthCheck()
          .then(() => {
            this.connected = true
            this.emit('connected')
            resolve()
          })
          .catch(reject)
      } catch (error) {
        reject(error)
      }
    })
  }

  /**
   * Disconnect from Python engine
   */
  async disconnect (): Promise<void> {
    this.isShuttingDown = true

    if (this.process) {
      this.process.kill('SIGTERM')

      // Wait for graceful shutdown
      await new Promise<void>(resolve => {
        const timeout = setTimeout(() => {
          if (this.process) {
            this.process.kill('SIGKILL')
          }
          resolve()
        }, 5000)

        this.process?.on('exit', () => {
          clearTimeout(timeout)
          resolve()
        })
      })

      this.process = null
    }

    this.connected = false
    this.rejectPendingRequests(new Error('Bridge disconnected'))
    this.emit('disconnected')
  }

  /**
   * Send request to Python engine
   */
  async send (request: BridgeRequest): Promise<BridgeResponse> {
    if (!this.connected || !this.process?.stdin) {
      throw new Error('Bridge not connected')
    }

    // Validate request
    const validation = validateBridgeRequest(request)
    if (!validation.ok) {
      throw new Error(
        `Invalid request: ${validation.errors.map(e => e.message).join(', ')}`
      )
    }

    return new Promise((resolve, reject) => {
      const id = request.requestId
      const timeout = setTimeout(() => {
        this.pendingRequests.delete(id)
        reject(new Error(`Request timeout: ${id}`))
      }, this.config.timeoutMs)

      this.pendingRequests.set(id, { resolve, reject, timeout })

      // Send request as JSON line
      const json = JSON.stringify(request)
      this.process!.stdin!.write(json + '\n')
    })
  }

  /**
   * Subscribe to events for a task
   */
  async subscribeToEvents (
    taskId: string,
    handler: (event: AgentEvent) => void
  ): Promise<() => void> {
    let handlers = this.eventSubscriptions.get(taskId)
    if (!handlers) {
      handlers = new Set()
      this.eventSubscriptions.set(taskId, handlers)
    }
    handlers.add(handler)

    // Return unsubscribe function
    return () => {
      handlers?.delete(handler)
      if (handlers?.size === 0) {
        this.eventSubscriptions.delete(taskId)
      }
    }
  }

  /**
   * Check if connected
   */
  isConnected (): boolean {
    return this.connected
  }

  /**
   * Health check
   */
  private async healthCheck (): Promise<void> {
    const request = createBridgeRequest('health_check', {})
    const response = await this.send(request)
    if (response.type !== 'health') {
      throw new Error('Health check failed')
    }
    if (response.payload.status !== 'healthy') {
      throw new Error(`Python engine unhealthy: ${response.payload.status}`)
    }
  }

  /**
   * Process buffer for JSON lines
   */
  private processBuffer (): void {
    const lines = this.buffer.split('\n')
    this.buffer = lines.pop() || ''

    for (const line of lines) {
      if (!line.trim()) continue

      try {
        const response = JSON.parse(line)
        this.handleResponse(response)
      } catch (error) {
        console.error(`[Bridge] Failed to parse response: ${line}`, error)
      }
    }
  }

  /**
   * Handle response from Python engine
   */
  private handleResponse (response: BridgeResponse): void {
    // Validate response
    const validation = validateBridgeResponse(response)
    if (!validation.ok) {
      console.error(
        `[Bridge] Invalid response: ${validation.errors
          .map(e => e.message)
          .join(', ')}`
      )
      return
    }

    // Handle event stream
    if (response.type === 'event_stream') {
      const event = response.payload.event as AgentEvent
      const handlers = this.eventSubscriptions.get(event.taskId)
      if (handlers) {
        for (const handler of handlers) {
          try {
            handler(event)
          } catch (error) {
            console.error(`[Bridge] Event handler error:`, error)
          }
        }
      }
      this.emit('event', event)
      return
    }

    // Handle regular request response
    const pending = this.pendingRequests.get(response.requestId)
    if (pending) {
      clearTimeout(pending.timeout)
      this.pendingRequests.delete(response.requestId)

      if (response.type === 'error') {
        const errorPayload = response.payload as { error?: { message: string } }
        pending.reject(
          new Error(errorPayload.error?.message || 'Unknown error')
        )
      } else {
        pending.resolve(response)
      }
    }
  }

  /**
   * Reject all pending requests
   */
  private rejectPendingRequests (error: Error): void {
    for (const [, pending] of this.pendingRequests) {
      clearTimeout(pending.timeout)
      pending.reject(error)
    }
    this.pendingRequests.clear()
  }
}

/**
 * Bridge client factory
 */
export function createBridgeClient (config: BridgeConfig): StdioBridgeClient {
  return new StdioBridgeClient(config)
}

/**
 * HTTP bridge client (for future use)
 */
export class HttpBridgeClient extends EventEmitter implements BridgeClient {
  private config: BridgeConfig
  private baseUrl: string
  private connected = false
  private eventSubscriptions = new Map<
    string,
    Set<(event: AgentEvent) => void>
  >()

  constructor (config: BridgeConfig) {
    super()
    this.config = config
    this.baseUrl = `http://localhost:${
      (config.env as Record<string, string | undefined>)?.[ "PORT"] || 8080
    }`
  }

  async connect (): Promise<void> {
    // Implementation for HTTP transport
    throw new Error('HTTP bridge not implemented yet')
  }

  async disconnect (): Promise<void> {
    this.connected = false
  }

  async send (request: BridgeRequest): Promise<BridgeResponse> {
    throw new Error('HTTP bridge not implemented yet')
  }

  async request<T extends BridgeRequest> (request: T): Promise<BridgeResponse> {
    return this.send(request)
  }

  async subscribeToEvents (
    taskId: string,
    handler: (event: AgentEvent) => void
  ): Promise<() => void> {
    return () => {}
  }

  isConnected (): boolean {
    return this.connected
  }
}

/**
 * Create bridge client based on config
 */
export function createBridge (config: BridgeConfig) {
  switch (config.transport) {
    case 'stdio':
      return createBridgeClient(config)
    case 'http':
      return new HttpBridgeClient(config)
    default:
      throw new Error(`Unsupported transport: ${config.transport}`)
  }
}
