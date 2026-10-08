import type { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { ReadResourceRequestSchema } from '@modelcontextprotocol/sdk/types.js'

/**
 * Checkpoint resources
 */
export function registerResources (server: Server): void {
  server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    const { uri } = request.params
    
    if (uri === 'agentcore://checkpoints') {
      return {
        contents: [
          {
            uri,
            mimeType: 'application/json',
            text: JSON.stringify({ checkpoints: [] }, null, 2),
          },
        ],
      }
    }
    
    if (uri.startsWith('agentcore://checkpoint/')) {
      const taskId = uri.split('/').pop() || ''
      
      if (uri === `agentcore://checkpoint/${taskId}`) {
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
      
      if (uri === `agentcore://checkpoints/history/${taskId}`) {
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
    }
    
    throw new Error(`Unknown resource: ${uri}`)
  })
}
