// MCP Resources - Exports
export * from './task.js'
export * from './budget.js'
export * from './checkpoint.js'
export * from './events.js'

import { registerResources as registerTaskResources } from './task.js'
import { registerResources as registerBudgetResources } from './budget.js'
import { registerResources as registerCheckpointResources } from './checkpoint.js'
import { registerResources as registerEventResources } from './events.js'

/**
 * Register all resources with MCP server
 */
export function registerResources (server: any): void {
  registerTaskResources(server)
  registerBudgetResources(server)
  registerCheckpointResources(server)
  registerEventResources(server)
}
