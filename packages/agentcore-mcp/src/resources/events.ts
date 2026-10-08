import type { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { ReadResourceRequestSchema } from '@modelcontextprotocol/sdk/types.js'

/**
 * Event stream resources
 */
export function registerResources (server: Server): void {
  server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    const { uri } = request.params
    
    if (uri.startsWith('agentcore://events/')) {
      const parts = uri.split('/')
      const taskId = parts.pop() || ''
      const subPath = parts.pop() || ''
      
      if (subPath === 'events' && taskId) {
        return {
          contents: [
            {
              uri,
              mimeType: 'text/event-stream',
              text: `data: {"type":"task.started","taskId":"${taskId}"}\n\n`,
            },
          ],
        }
      }
      
      if (subPath === 'history' && taskId) {
        return {
          contents: [
            {
              uri,
              mimeType: 'application/json',
              text: JSON.stringify({ taskId, events: [], limit: 100 }, null, 2),
            },
          ],
        }
      }
    }
    
    throw new Error(`Unknown resource: ${uri}`)
  })
}
