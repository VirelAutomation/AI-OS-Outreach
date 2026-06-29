import type { FastifyInstance } from 'fastify'
import { z } from 'zod'
import { LeadManagementService } from '../services/leadManagement.service.js'

const replySchema = z.object({
  leadId: z.string().min(1),
  replyText: z.string().min(1),
})

const meetingSchema = z.object({
  leadId: z.string().min(1),
  value: z.number().min(0).optional(),
})

export async function registerLeadManagementRoutes(app: FastifyInstance) {
  const leadManagement = new LeadManagementService()

  app.get('/api/lead-management/digest', async () => {
    return await leadManagement.digest()
  })

  app.post('/api/lead-management/triage-reply', async (request, reply) => {
    const parsed = replySchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    return await leadManagement.triageReply(parsed.data)
  })

  app.post('/api/lead-management/book-meeting', async (request, reply) => {
    const parsed = meetingSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    return await leadManagement.bookMeeting(parsed.data)
  })
}
