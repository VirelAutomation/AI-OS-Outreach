import type { FastifyInstance } from 'fastify'
import { z } from 'zod'
import { CalendarService } from '../services/calendar.service.js'

const createEventSchema = z.object({
  summary: z.string().min(1),
  description: z.string().optional(),
  startTime: z.string().min(1),
  endTime: z.string().min(1),
  calendarId: z.string().optional(),
})

const addPriorityBlockSchema = z.object({
  title: z.string().min(1),
  dateIso: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  startHour: z.number().int().min(0).max(23),
  durationHours: z.number().min(0.5).max(8).default(2),
})

export async function registerCalendarRoutes(app: FastifyInstance) {
  const calendar = new CalendarService()

  // List upcoming events (live from Google Calendar)
  app.get('/api/calendar/events', async (request) => {
    const days = Number((request.query as { days?: string }).days ?? 7)
    return calendar.listEvents({ days: Math.min(Math.max(days, 1), 30) })
  })

  // List events AND run Jarvis priority analysis in one call
  app.get('/api/calendar/sync', async (request) => {
    const days = Number((request.query as { days?: string }).days ?? 3)
    const { events, mode, error } = await calendar.listEvents({ days })
    const analysis = await calendar.analyzeWithJarvis(events)
    return { ok: true, mode, error, analysis }
  })

  // Create a calendar event
  app.post('/api/calendar/events', async (request, reply) => {
    const parsed = createEventSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    return calendar.createEvent(parsed.data)
  })

  // Jarvis adds a priority block to the calendar
  app.post('/api/calendar/priority-block', async (request, reply) => {
    const parsed = addPriorityBlockSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    return calendar.addPriorityBlock(parsed.data.title, parsed.data.dateIso, parsed.data.startHour, parsed.data.durationHours)
  })

  // Calendar status
  app.get('/api/calendar/status', async () => {
    const result = await calendar.listEvents({ days: 1 })
    return {
      ok: result.ok,
      mode: result.mode,
      eventCount: result.events.length,
      error: result.error ?? null,
      instruction: result.ok ? 'Google Calendar is live.' : 'Visit /api/google/oauth/start to connect Google Calendar.',
    }
  })
}
