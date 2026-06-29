/**
 * Forge OS Event Bus
 *
 * In-process event emitter shared across all services.
 * Routes, services, and the scheduler emit events here.
 * The SSE endpoint subscribes and pushes them to connected browser clients.
 * Nothing blocks on this — all listeners are fire-and-forget.
 */

import { EventEmitter } from 'node:events'

export type ForgeEventType =
  | 'email_sent'
  | 'email_failed'
  | 'reply_received'
  | 'meeting_booked'
  | 'lead_enriched'
  | 'lead_added'
  | 'draft_created'
  | 'scheduler_tick'
  | 'brief_generated'
  | 'experiment_complete'
  | 'hook_experiment_complete'
  | 'dm_experiment_complete'
  | 'human_task_added'
  | 'crl_outcome'
  | 'pipeline_updated'

export type ForgeEvent = {
  type: ForgeEventType
  payload?: unknown
  at: string
}

class ForgeEventBus extends EventEmitter {
  constructor() {
    super()
    // Prevent Node warning for many SSE subscribers
    this.setMaxListeners(200)
  }
}

export const eventBus = new ForgeEventBus()

export function emitEvent(type: ForgeEventType, payload?: unknown) {
  const event: ForgeEvent = { type, payload, at: new Date().toISOString() }
  eventBus.emit('forge_event', event)
}
