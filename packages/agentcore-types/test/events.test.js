import { describe, expect, it } from 'vitest'
import { AgentEventSchema } from '../dist/events.js'

const base = { taskId: 'task-1', timestamp: '2026-10-08T00:00:00.000Z' }

describe('AgentEventSchema', () => {
  it('accepts approval granted and denied events', () => {
    for (const decision of ['granted', 'denied']) {
      expect(AgentEventSchema.safeParse({
        ...base,
        type: `approval.${decision}`,
        data: {
          callId: '550e8400-e29b-41d4-a716-446655440000',
          toolName: 'read_file',
          decision
        }
      }).success).toBe(true)
    }
  })

  it('accepts task terminal events', () => {
    for (const type of ['task.completed', 'task.partially_completed', 'task.failed', 'task.cancelled']) {
      expect(AgentEventSchema.safeParse({
        ...base,
        type,
        data: {
          status: type === 'task.completed' ? 'COMPLETED' : 'FAILED',
          completedUnits: 1,
          totalUnits: 1,
          budgetUsed: '0',
          budgetRemaining: '1'
        }
      }).success).toBe(true)
    }
  })
})
