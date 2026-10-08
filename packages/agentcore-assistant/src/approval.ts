import { EventEmitter } from 'eventemitter3'
import type { ToolCall, ToolDefinition, ToolRisk } from '@agentcore/types'
import type {
  AgentEvent,
  ApprovalRequiredEvent,
  ApprovalDecisionEvent
} from '@agentcore/types'

/**
 * Approval request
 */
export interface ApprovalRequest {
  id: string
  callId: string
  toolName: string
  input: unknown
  risk: ToolRisk
  reason: string
  timeoutSeconds: number
  requestedAt: string
  decidedAt?: string
  decision?: 'granted' | 'denied'
  decidedBy?: string
  decisionReason?: string
}

/**
 * Approval manager
 */
export class ApprovalManager extends EventEmitter {
  private pendingApprovals = new Map<string, ApprovalRequest>()
  private approvalHistory: ApprovalRequest[] = []
  private defaultTimeoutSeconds: number
  private autoApproveRead: boolean
  private autoApproveWrite: boolean
  private requireApprovalFor: ToolRisk[]

  constructor (
    options: {
      defaultTimeoutSeconds?: number
      autoApproveRead?: boolean
      autoApproveWrite?: boolean
      requireApprovalFor?: ToolRisk[]
    } = {}
  ) {
    super()
    this.defaultTimeoutSeconds = options.defaultTimeoutSeconds ?? 300
    this.autoApproveRead = options.autoApproveRead ?? true
    this.autoApproveWrite = options.autoApproveWrite ?? false
    this.requireApprovalFor = options.requireApprovalFor ?? [
      'write',
      'external',
      'dangerous'
    ]
  }

  /**
   * Request approval for a tool call
   */
  async requestApproval (
    call: ToolCall,
    tool: ToolDefinition,
    reason: string = `Tool ${tool.name} requires approval`
  ): Promise<'granted' | 'denied' | 'timeout'> {
    // Check if approval is needed
    if (!this.requiresApproval(tool.risk)) {
      return 'granted'
    }

    const request: ApprovalRequest = {
      id: crypto.randomUUID(),
      callId: call.id,
      toolName: tool.name,
      input: call.input,
      risk: tool.risk,
      reason,
      timeoutSeconds: this.getTimeoutForRisk(tool.risk),
      requestedAt: new Date().toISOString()
    }

    this.pendingApprovals.set(request.id, request)

    // Emit approval required event
    this.emit('approval:required', request)

    // Return promise that resolves when decision is made
    return new Promise(resolve => {
      const timeout = setTimeout(() => {
        if (this.pendingApprovals.has(request.id)) {
          this.pendingApprovals.delete(request.id)
          request.decidedAt = new Date().toISOString()
          request.decision = 'denied'
          request.decisionReason = 'Approval timeout'
          this.approvalHistory.push(request)
          this.emit('approval:timeout', request)
          resolve('timeout')
        }
      }, request.timeoutSeconds * 1000)

      // Store timeout reference for cleanup
      ;(request as any)._timeout = timeout
    })
  }

  /**
   * Grant approval
   */
  grantApproval (
    approvalId: string,
    decidedBy?: string,
    reason?: string
  ): boolean {
    const request = this.pendingApprovals.get(approvalId)
    if (!request) return false

    clearTimeout((request as any)._timeout)

    request.decidedAt = new Date().toISOString()
    request.decision = 'granted'
    request.decidedBy = decidedBy
    request.decisionReason = reason

    this.pendingApprovals.delete(approvalId)
    this.approvalHistory.push(request)

    this.emit('approval:granted', request)
    return true
  }

  /**
   * Deny approval
   */
  denyApproval (
    approvalId: string,
    decidedBy?: string,
    reason?: string
  ): boolean {
    const request = this.pendingApprovals.get(approvalId)
    if (!request) return false

    clearTimeout((request as any)._timeout)

    request.decidedAt = new Date().toISOString()
    request.decision = 'denied'
    request.decidedBy = decidedBy
    request.decisionReason = reason

    this.pendingApprovals.delete(approvalId)
    this.approvalHistory.push(request)

    this.emit('approval:denied', request)
    return true
  }

  /**
   * Check if approval is needed for tool risk
   */
  requiresApproval (risk: ToolRisk): boolean {
    if (risk === 'read' && this.autoApproveRead) return false
    if (risk === 'write' && this.autoApproveWrite) return false
    return this.requireApprovalFor.includes(risk)
  }

  /**
   * Get timeout for risk level
   */
  private getTimeoutForRisk (risk: ToolRisk): number {
    switch (risk) {
      case 'dangerous':
        return this.defaultTimeoutSeconds * 2
      case 'external':
        return this.defaultTimeoutSeconds
      case 'write':
        return this.defaultTimeoutSeconds
      default:
        return this.defaultTimeoutSeconds
    }
  }

  /**
   * Get pending approvals
   */
  getPendingApprovals (): ApprovalRequest[] {
    return Array.from(this.pendingApprovals.values())
  }

  /**
   * Get approval history
   */
  getHistory (): ApprovalRequest[] {
    return [...this.approvalHistory]
  }

  /**
   * Get approval by ID
   */
  getApproval (id: string): ApprovalRequest | undefined {
    return (
      this.pendingApprovals.get(id) ||
      this.approvalHistory.find(a => a.id === id)
    )
  }

  /**
   * Cancel pending approval
   */
  cancelApproval (approvalId: string): boolean {
    const request = this.pendingApprovals.get(approvalId)
    if (!request) return false

    clearTimeout((request as any)._timeout)
    request.decidedAt = new Date().toISOString()
    request.decision = 'denied'
    request.decisionReason = 'Cancelled by system'

    this.pendingApprovals.delete(approvalId)
    this.approvalHistory.push(request)
    this.emit('approval:cancelled', request)
    return true
  }

  /**
   * Clear all pending approvals
   */
  clearPending (): void {
    for (const request of this.pendingApprovals.values()) {
      clearTimeout((request as any)._timeout)
      request.decidedAt = new Date().toISOString()
      request.decision = 'denied'
      request.decisionReason = 'Cleared by system'
      this.approvalHistory.push(request)
    }
    this.pendingApprovals.clear()
  }
}

/**
 * Create default approval manager
 */
export function createDefaultApprovalManager (options?: {
  defaultTimeoutSeconds?: number
  autoApproveRead?: boolean
  autoApproveWrite?: boolean
  requireApprovalFor?: ToolRisk[]
}): ApprovalManager {
  return new ApprovalManager(options)
}
