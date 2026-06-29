/**
 * SSE Live Feed — GET /api/events
 *
 * Server-Sent Events endpoint. The frontend connects once and receives
 * real-time events whenever pipeline state changes: email sent, reply
 * received, experiment complete, scheduler tick, etc.
 *
 * Each connected client is a subscriber on the in-process eventBus.
 * When the connection closes, the subscriber is removed immediately.
 * No memory leak, no database, no Redis needed.
 */

import type { FastifyInstance } from 'fastify'
import { type ForgeEvent, eventBus } from '../lib/eventBus.js'

export async function registerSSERoutes(app: FastifyInstance) {
  app.get('/api/events', async (request, reply) => {
    // Tell Fastify not to serialize or end this response
    reply.raw.setHeader('Content-Type', 'text/event-stream')
    reply.raw.setHeader('Cache-Control', 'no-cache, no-transform')
    reply.raw.setHeader('Connection', 'keep-alive')
    reply.raw.setHeader('X-Accel-Buffering', 'no') // Nginx: disable buffering
    reply.raw.flushHeaders()

    // Send initial connection confirmation
    reply.raw.write(`data: ${JSON.stringify({ type: 'connected', at: new Date().toISOString() })}\n\n`)

    const onEvent = (event: ForgeEvent) => {
      try {
        reply.raw.write(`data: ${JSON.stringify(event)}\n\n`)
      } catch {
        // Client disconnected mid-write — will be cleaned up below
      }
    }

    eventBus.on('forge_event', onEvent)

    // Heartbeat every 25s to keep connection alive through proxies
    const heartbeat = setInterval(() => {
      try {
        reply.raw.write(': heartbeat\n\n')
      } catch {
        clearInterval(heartbeat)
      }
    }, 25000)

    request.raw.on('close', () => {
      clearInterval(heartbeat)
      eventBus.off('forge_event', onEvent)
      app.log.info({ path: '/api/events' }, 'sse_client_disconnected')
    })

    // Keep the handler alive — Fastify must not end the response
    await new Promise<void>((resolve) => {
      request.raw.on('close', resolve)
    })
  })

  // Quick status: how many SSE clients are currently connected
  app.get('/api/events/status', async () => {
    const listenerCount = eventBus.listenerCount('forge_event')
    return { ok: true, connectedClients: listenerCount }
  })
}
