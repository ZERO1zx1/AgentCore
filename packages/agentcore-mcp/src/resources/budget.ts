import type { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { ReadResourceRequestSchema } from '@modelcontextprotocol/sdk/types.js'

/**
 * Budget resources
 */
export function registerResources (server: Server): void {
  // Budget status resource template
  server.registerCapabilities({
    resources: {
      listChanged: true,
    },
  })

  // Handle read resource requests
  server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    const { uri } = request.params
    
    if (uri.startsWith('agentcore://budget/')) {
      const taskId = uri.split('/').pop() || ''
      
      if (uri === `agentcore://budget/${taskId}`) {
        return {
          contents: [
            {
              uri,
              mimeType: 'application/json',
              text: JSON.stringify({ taskId, status: 'not_implemented' }, null, 2),
            },
          ],
        }
      }
      
      if (uri === `agentcore://budget/history/${taskId}`) {
        return {
          contents: [
            {
              uri,
              mimeType: 'application/json',
              text: JSON.stringify({ taskId, history: [] }, null, 2),
            },
          ],
        }
      }
      
      if (uri === `agentcore://budget/breakdown/${taskId}`) {
        return {
          contents: [
            {
              uri,
              mimeType: 'application/json',
              text: JSON.stringify({ taskId, breakdown: {} }, null, 2),
            },
          ],
        }
      }
    }
    
    throw new Error(`Unknown resource: ${uri}`)
  })
}
