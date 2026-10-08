import { EventEmitter } from 'eventemitter3'
import { z } from 'zod'
import type {
  ToolDefinition,
  ToolCall,
  ToolResult,
  ToolExecutionContext,
  ToolRegistry as ToolRegistryInterface
} from '@agentcore/types'
import type { ValidationResult } from '@agentcore/types'
import { validateToolInput } from '@agentcore/types'

/**
 * In-memory tool registry implementation
 */
export class ToolRegistry
  extends EventEmitter
  implements ToolRegistryInterface
{
  private tools = new Map<string, ToolDefinition>()
  private recentCalls: ToolCall[] = []
  private maxRecentCalls = 100

  register (definition: ToolDefinition): void {
    const validated = this.validateDefinition(definition)
    if (!validated.ok) {
      throw new Error(
        `Invalid tool definition: ${validated.errors.join(', ')}`
      )
    }

    const existing = this.tools.get(definition.name)
    if (existing) {
      this.emit('tool:updated', {
        name: definition.name,
        old: existing,
        new: definition
      })
    } else {
      this.emit('tool:registered', definition)
    }
    this.tools.set(definition.name, definition)
  }

  unregister (name: string): boolean {
    const tool = this.tools.get(name)
    if (!tool) return false
    this.tools.delete(name)
    this.emit('tool:unregistered', tool)
    return true
  }

  get (name: string): ToolDefinition | undefined {
    return this.tools.get(name)
  }

  list (): ToolDefinition[] {
    return Array.from(this.tools.values())
  }

  validateInput (
    name: string,
    input: unknown
  ): { ok: boolean; errors: string[] } {
    const tool = this.tools.get(name)
    if (!tool) {
      return { ok: false, errors: [`Tool not found: ${name}`] }
    }
    const result = validateToolInput(tool, input)
    return {
      ok: result.ok,
      errors: result.errors.map(e => `${e.path}: ${e.message}`)
    }
  }

  checkPermission (
    name: string,
    context: ToolExecutionContext
  ): { allowed: boolean; reason?: string } {
    const tool = this.tools.get(name)
    if (!tool) {
      return { allowed: false, reason: `Tool not found: ${name}` }
    }

    // Check if path is allowed
    if (context.workingDirectory) {
      // This would be enhanced with actual path checking
    }

    return { allowed: true }
  }

  estimateCost (name: string, input: unknown): string {
    const tool = this.tools.get(name)
    if (!tool) return '0'

    // Simple estimation based on tool's estimatedCost
    // In reality, this would analyze the input to estimate tokens
    return tool.estimatedCost
  }

  detectDuplicateCall (
    call: ToolCall,
    recentCalls: ToolCall[] = this.recentCalls
  ): ToolCall | null {
    // Check for exact duplicate (same tool, same input)
    for (const recent of recentCalls) {
      if (
        recent.name === call.name &&
        JSON.stringify(recent.input) === JSON.stringify(call.input) &&
        recent.taskId === call.taskId
      ) {
        return recent
      }
    }
    return null
  }

  /**
   * Record a tool call for duplicate detection
   */
  recordCall (call: ToolCall): void {
    this.recentCalls.unshift(call)
    if (this.recentCalls.length > this.maxRecentCalls) {
      this.recentCalls = this.recentCalls.slice(0, this.maxRecentCalls)
    }
  }

  /**
   * Get recent calls for duplicate detection
   */
  getRecentCalls (): ToolCall[] {
    return [...this.recentCalls]
  }

  /**
   * Clear recent calls history
   */
  clearHistory (): void {
    this.recentCalls = []
  }

  /**
   * Validate tool definition
   */
  private validateDefinition (definition: ToolDefinition): {
    ok: boolean
    errors: string[]
  } {
    const schema = z.object({
      name: z
        .string()
        .min(1)
        .regex(/^[a-zA-Z][a-zA-Z0-9_-]*$/),
      description: z.string().min(1),
      inputSchema: z.unknown(),
      risk: z.enum(['read', 'write', 'external', 'dangerous']),
      requiresApproval: z.boolean().default(false),
      estimatedCost: z.string().default('0'),
      timeoutSeconds: z.number().int().positive().default(60),
      retryable: z.boolean().default(true),
      maxRetries: z.number().int().nonnegative().default(2)
    })
    const result = schema.safeParse(definition)
    if (result.success) {
      return { ok: true, errors: [] }
    }
    return {
      ok: false,
      errors: result.error.issues.map(e => `${e.path.join('.')}: ${e.message}`)
    }
  }
}

/**
 * Create default tool registry with built-in tools
 */
export function createDefaultRegistry (): ToolRegistry {
  const registry = new ToolRegistry()

  // Built-in tools would be registered here
  // For now, registry is empty - tools are registered by the session/agent

  return registry
}
