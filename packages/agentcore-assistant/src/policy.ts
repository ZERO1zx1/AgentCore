import type {
  ToolDefinition,
  ToolExecutionContext,
  ToolRisk
} from '@agentcore/types'
import type { AssistantConfig } from './config.js'

/**
 * Permission decision
 */
export interface PermissionDecision {
  allowed: boolean
  reason?: string
  requiresApproval: boolean
  approvalTimeoutSeconds?: number
}

/**
 * Permission policy engine
 */
export class PermissionPolicy {
  private config: AssistantConfig

  constructor (config: AssistantConfig) {
    this.config = config
  }

  /**
   * Check if an action is allowed and if approval is required
   */
  checkPermission (
    tool: ToolDefinition,
    context: ToolExecutionContext
  ): PermissionDecision {
    // Check if path is allowed
    if (context.workingDirectory) {
      const pathCheck = this.checkPathAccess(context.workingDirectory)
      if (!pathCheck.allowed) {
        return {
          allowed: false,
          reason: pathCheck.reason,
          requiresApproval: false
        }
      }
    }

    // Check if command is allowed (for shell tools)
    if (
      tool.risk === 'dangerous' &&
      this.config.security.allowedCommands.length > 0
    ) {
      // Would check specific command against allowlist
    }

    // Determine if approval required
    const requiresApproval = this.requiresApproval(tool.risk)

    // Auto-approve read operations if configured
    if (tool.risk === 'read' && this.config.approval.autoApproveRead) {
      return { allowed: true, requiresApproval: false }
    }

    // Auto-approve write if configured
    if (tool.risk === 'write' && this.config.approval.autoApproveWrite) {
      return { allowed: true, requiresApproval: false }
    }

    return {
      allowed: true,
      requiresApproval,
      approvalTimeoutSeconds: this.config.approval.defaultTimeoutSeconds
    }
  }

  /**
   * Check if path is within allowed boundaries
   */
  checkPathAccess (path: string): { allowed: boolean; reason?: string } {
    const normalizedPath = path.replace(/\\/g, '/')

    // Check blocked paths first
    for (const blocked of this.config.security.blockedPaths) {
      const blockedNormalized = blocked.replace(/\\/g, '/')
      if (normalizedPath.includes(blockedNormalized)) {
        return { allowed: false, reason: `Path blocked: ${blocked}` }
      }
    }

    // Check allowed paths
    if (this.config.security.allowedPaths.length > 0) {
      let allowed = false
      for (const allowedPath of this.config.security.allowedPaths) {
        const allowedNormalized = allowedPath.replace(/\\/g, '/')
        if (
          normalizedPath.startsWith(allowedNormalized) ||
          normalizedPath === allowedNormalized
        ) {
          allowed = true
          break
        }
      }
      if (!allowed) {
        return { allowed: false, reason: `Path not in allowed list: ${path}` }
      }
    }

    return { allowed: true }
  }

  /**
   * Check if tool risk requires approval
   */
  private requiresApproval (risk: ToolRisk): boolean {
    return this.config.approval.requireApprovalFor.includes(risk)
  }

  /**
   * Get approval timeout for tool
   */
  getApprovalTimeout (tool: ToolDefinition): number {
    if (tool.risk === 'dangerous') {
      return this.config.approval.defaultTimeoutSeconds * 2 // Longer for dangerous
    }
    return this.config.approval.defaultTimeoutSeconds
  }

  /**
   * Check if tool is blocked by policy
   */
  isBlocked (tool: ToolDefinition): boolean {
    // Block dangerous tools if no commands allowed
    if (
      tool.risk === 'dangerous' &&
      this.config.security.allowedCommands.length === 0
    ) {
      return true
    }
    // Block external tools if no network allowed
    if (tool.risk === 'external') {
      // Could add network policy check here
    }
    return false
  }
}

/**
 * Create default permission policy
 */
export function createDefaultPolicy (config: AssistantConfig): PermissionPolicy {
  return new PermissionPolicy(config)
}
