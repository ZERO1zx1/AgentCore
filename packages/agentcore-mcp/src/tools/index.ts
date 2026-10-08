// MCP Tools - Exports
export * from "./repository.js";
export * from "./file.js";
export * from "./task.js";
export * from "./checkpoint.js";

import type { ToolDefinition } from "@agentcore/types";
import { repositoryTools } from "./repository.js";
import { fileTools } from "./file.js";
import { taskTools } from "./task.js";
import { checkpointTools } from "./checkpoint.js";

/**
 * All MCP tools
 */
export const allMcpTools = [
  ...repositoryTools,
  ...fileTools,
  ...taskTools,
  ...checkpointTools,
];

/**
 * Register all tools with agent registry
 */
export function registerTools(agent: any): void {
  const registry = agent.getToolRegistry?.()
  if (!registry) {
    throw new Error('Agent does not expose a tool registry')
  }
  for (const tool of allMcpTools) {
    registry.register(tool)
  }
}

/**
 * Get tools by category
 */
export function getToolsByCategory(category: string): ToolDefinition[] {
  return allMcpTools.filter(tool => tool.name.startsWith(category));
}
