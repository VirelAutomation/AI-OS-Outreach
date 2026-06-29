import type { FastifyInstance } from 'fastify'
import { z } from 'zod'
import { runtimeStore } from '../lib/runtimeStore.js'
import { OutreachService } from '../services/outreach.service.js'

const strategySchema = z.object({
  objective: z.string().min(1).default('increase meetings booked'),
})

const executeSchema = z.object({
  leads: z.array(
    z.object({
      fullName: z.string().min(1),
      email: z.string().email(),
      role: z.string().optional(),
      companyName: z.string().min(1),
      website: z.string().optional(),
      industry: z.string().optional(),
      city: z.string().optional(),
      painPoint: z.string().optional(),
    }),
  ).min(1),
  sendImmediately: z.boolean().default(false),
})

export async function registerOrchestratorRoutes(app: FastifyInstance) {
  const outreach = new OutreachService()

  app.get('/api/orchestrator/status', async () => {
    const sent = runtimeStore.all.sends.filter((s) => s.status === 'sent').length
    const replies = runtimeStore.all.replies.length
    const meetings = runtimeStore.all.meetings.length
    return {
      ok: true,
      agents: {
        jarvis: 'online',
        outreach: 'online',
        cmo: 'online',
        cto: 'online',
      },
      kpi: { sent, replies, meetings },
    }
  })

  app.post('/api/orchestrator/strategy', async (request, reply) => {
    const parsed = strategySchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })

    const sent = runtimeStore.all.sends.filter((s) => s.status === 'sent').length
    const replies = runtimeStore.all.replies.length
    const meetings = runtimeStore.all.meetings.length
    const replyRate = sent > 0 ? (replies / sent) * 100 : 0

    return {
      ok: true,
      objective: parsed.data.objective,
      strategy: [
        replyRate < 8 ? 'Refine subject + opener by segment before scaling volume.' : 'Keep winning sequence and increase volume in top segments.',
        'Enrich all new leads before first touch to improve personalization relevance.',
        'Trigger follow-up automation on neutral and objection replies within 24h.',
      ],
      nextActions: [
        'Run enrich-and-draft on pending leads',
        'Send approved drafts in controlled batch',
        'Monitor reply intent and route meeting-intent to meetings queue',
      ],
      snapshot: { sent, replies, meetings, replyRate: Number(replyRate.toFixed(2)) },
    }
  })

  app.post('/api/orchestrator/execute-cycle', async (request, reply) => {
    const parsed = executeSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })

    const run = await outreach.enrichAndDraft(parsed.data.leads)
    const persisted = run.items.map((item) => {
      const lead = runtimeStore.upsertLead({
        fullName: item.lead.fullName,
        email: item.lead.email,
        companyName: item.lead.companyName,
        industry: item.lead.industry,
        city: item.lead.city,
        enrichedAt: new Date().toISOString(),
      })
      const draft = runtimeStore.createDraft({
        leadId: lead.id,
        subject: item.draft.subject,
        body: item.draft.body,
        mode: item.draft.mode,
      })
      return { lead, draft }
    })

    const sendResults = []
    if (parsed.data.sendImmediately) {
      for (const item of persisted) {
        const send = await outreach.sendEmailDraft({
          to: item.lead.email,
          subject: item.draft.subject,
          body: item.draft.body,
        })
        runtimeStore.createSendEvent({
          leadId: item.lead.id,
          draftId: item.draft.id,
          to: item.lead.email,
          status: send.sent ? 'sent' : 'failed',
          reason: send.reason,
        })
        sendResults.push({ leadId: item.lead.id, sent: send.sent, reason: send.reason ?? null })
      }
    }

    return {
      ok: true,
      enrichedAndDrafted: persisted.length,
      sendAttempted: parsed.data.sendImmediately,
      sendResults,
    }
  })
}

