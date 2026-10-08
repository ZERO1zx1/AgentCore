import { describe, expect, it } from 'vitest'
import { createAgent } from '../dist/agent.js'

describe('Agent', () => {
  it('creates a bounded assistant with an empty registry', () => {
    const agent = createAgent()
    expect(agent.getConfig().maxIterations).toBeGreaterThan(0)
    expect(agent.getConfig().maxToolCalls).toBeGreaterThan(0)
    expect(agent.getToolRegistry().list()).toEqual([])
  })
})
