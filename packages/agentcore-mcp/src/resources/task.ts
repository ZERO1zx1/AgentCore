import type { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { ReadResourceRequestSchema } from '@modelcontextprotocol/sdk/types.js'
import type { TaskManifest } from '@agentcore/types'

/**
 * Task resources
 */
export function registerResources (server: Server): void {
  server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    const { uri } = request.params
    
    if (uri.startsWith('agentcore://task/')) {
      const taskId = uri.split('/').pop() || ''
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
    
    if (uri.startsWith('agentcore://manifest/')) {
      const taskId = uri.split('/').pop() || ''
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
    
    if (uri.startsWith('agentcore://outputs/')) {
      const taskId = uri.split('/').pop() || ''
      return {
        contents: [
          {
            uri,
            mimeType: 'application/json',
            text: JSON.stringify({ taskId, outputs: [] }, null, 2),
          },
        ],
      }
    }
    
    throw new Error(`Unknown resource: ${uri}`)
  })
}
