import type { FastifyInstance } from 'fastify'
import { z } from 'zod'
import { emitEvent } from '../lib/eventBus.js'
import { recordOutcome } from '../lib/crlLearning.js'
import { MeetingsService } from '../services/meetings.service.js'

const bookingSchema = z.object({
  fullName: z.string().min(1),
  email: z.string().email(),
  companyName: z.string().optional(),
  requestedAt: z.string().min(1),
  source: z.string().optional(),
  notes: z.string().optional(),
})

export async function registerMeetingRoutes(app: FastifyInstance) {
  const meetings = new MeetingsService()

  app.get('/api/meetings', async () => {
    const rows = await meetings.listMeetings()
    return {
      ok: true,
      meetings: rows,
    }
  })

  app.post('/api/public/bookings', async (request, reply) => {
    const parsed = bookingSchema.safeParse(request.body)
    if (!parsed.success) {
      return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    }

    const result = await meetings.createBooking(parsed.data)

    if (result.booked) {
      emitEvent('meeting_booked', {
        prospectName: parsed.data.fullName,
        companyName: parsed.data.companyName,
        requestedAt: parsed.data.requestedAt,
      })
      void recordOutcome('outreach', 'meeting_booked', { channel: 'inbound' })
      emitEvent('pipeline_updated', { source: 'meeting_booked', name: parsed.data.fullName })
    }

    return {
      ok: result.booked,
      ...result,
    }
  })
}
