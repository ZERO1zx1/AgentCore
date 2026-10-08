import { describe, expect, it } from 'vitest'
import { AgentCoreMcpServer } from '../dist/server.js'

describe('AgentCoreMcpServer', () => {
  it('constructs and registers all MCP tools', () => {
    const server = new AgentCoreMcpServer()
    expect(server.getAgent().getToolRegistry().list()).toHaveLength(16)
  })
})
