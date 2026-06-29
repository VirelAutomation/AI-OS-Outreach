import type { FastifyInstance } from 'fastify'
import { z } from 'zod'
import { runtimeStore } from '../lib/runtimeStore.js'
import { recordOutcome } from '../lib/crlLearning.js'
import { emitEvent } from '../lib/eventBus.js'
import { ProductionDataService } from '../services/productionData.service.js'
import { ReplySyncService } from '../services/replySync.service.js'
import { OutreachService } from '../services/outreach.service.js'

const personalizeSchema = z.object({
  fullName: z.string().min(1),
  companyName: z.string().min(1),
  industry: z.string().min(1),
  website: z.string().optional(),
  city: z.string().optional(),
  painPoint: z.string().optional(),
})

const sendSchema = z.object({
  to: z.string().email(),
  subject: z.string().min(1),
  body: z.string().min(1),
  leadId: z.string().optional(),
  draftId: z.string().optional(),
})

const enrichLeadSchema = z.object({
  fullName: z.string().min(1),
  email: z.string().email(),
  role: z.string().optional(),
  companyName: z.string().min(1),
  website: z.string().optional(),
  industry: z.string().optional(),
  city: z.string().optional(),
  painPoint: z.string().optional(),
})

const enrichAndDraftSchema = z.object({
  leads: z.array(enrichLeadSchema).min(1),
})

const discoverAndDraftSchema = z.object({
  actorInput: z.record(z.string(), z.unknown()).default({}),
  limit: z.number().int().min(3).max(10).default(3),
})

const customDmSchema = z.object({
  channel: z.enum(['linkedin', 'instagram', 'whatsapp', 'sms', 'x']),
  fullName: z.string().min(1),
  role: z.string().optional(),
  companyName: z.string().min(1),
  industry: z.string().min(1),
  website: z.string().optional(),
  city: z.string().optional(),
  painPoint: z.string().optional(),
  recentSignal: z.string().optional(),
  hookStyle: z.enum(['pain-first', 'result-first', 'signal-first']).optional(),
  humorStyle: z.enum(['dry', 'playful', 'none']).optional(),
  includeCta: z.boolean().optional(),
})

const customDmBatchSchema = z.object({
  items: z.array(customDmSchema).min(1).max(30),
})

export async function registerOutreachRoutes(app: FastifyInstance) {
  const outreach = new OutreachService()
  const productionData = new ProductionDataService()
  const replySync = new ReplySyncService()

  app.get('/api/outreach/dashboard', async (request) => {
    const limitRaw = Number((request.query as { limit?: string | number }).limit ?? 20)
    const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.min(50, Math.trunc(limitRaw))) : 20
    const activity = await productionData.outreachActivity(limit)
    return { ok: true, ...activity }
  })

  app.get('/api/outreach/readiness', async () => {
    const result = await outreach.readiness()
    return {
      ok: result.ok,
      providers: result.providers,
    }
  })

  app.post('/api/outreach/personalize', async (request, reply) => {
    const parsed = personalizeSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    return { ok: true, draft: outreach.personalizeColdEmail(parsed.data) }
  })

  app.post('/api/outreach/custom-dm', async (request, reply) => {
    const parsed = customDmSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    const dm = await outreach.generateCustomDm(parsed.data)
    return {
      ok: true,
      dm,
      queued: Boolean((dm as { telemetry?: { queued?: boolean } }).telemetry?.queued),
      queueWaitMs: (dm as { telemetry?: { queueWaitMs?: number } }).telemetry?.queueWaitMs ?? 0,
      attemptCount: (dm as { telemetry?: { attemptCount?: number } }).telemetry?.attemptCount ?? 0,
      keyRoleUsed: (dm as { telemetry?: { keyRoleUsed?: string } }).telemetry?.keyRoleUsed ?? null,
      fallbackMode: (dm as { telemetry?: { fallbackMode?: string } }).telemetry?.fallbackMode ?? null,
    }
  })

  app.post('/api/outreach/custom-dm/batch', async (request, reply) => {
    const parsed = customDmBatchSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    const dms = await Promise.all(parsed.data.items.map((item) => outreach.generateCustomDm(item)))
    return {
      ok: true,
      total: dms.length,
      items: dms,
      queuedCount: dms.filter((dm) => Boolean((dm as { telemetry?: { queued?: boolean } }).telemetry?.queued)).length,
    }
  })

  app.post('/api/outreach/send', async (request, reply) => {
    const parsed = sendSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })

    const leadState = parsed.data.leadId
      ? await productionData.latestReplyIntent(parsed.data.leadId)
      : undefined
    const precheck = await outreach.sendPrecheckGate({ to: parsed.data.to, leadState })
    if (!precheck.ok) {
      return reply.code(409).send({ ok: false, error: 'send_blocked', reason: precheck.reason })
    }

    const result = await outreach.sendEmailDraft({
      to: parsed.data.to,
      subject: parsed.data.subject,
      body: parsed.data.body,
    })

    if (parsed.data.leadId && parsed.data.draftId) {
      await productionData.createSendEvent({
        leadId: parsed.data.leadId,
        draftId: parsed.data.draftId,
        to: parsed.data.to,
        status: result.sent ? 'sent' : 'failed',
        reason: result.reason,
        providerMessageId: (result as { gmailMessageId?: string | null }).gmailMessageId ?? null,
        metadata: {
          gmailThreadId: (result as { gmailThreadId?: string | null }).gmailThreadId ?? null,
          mode: result.mode,
        },
      })
    }

    // CRL: record outcome so the learning engine can reinforce successful patterns
    void recordOutcome('outreach', result.sent ? 'email_sent' : 'email_failed', {
      channel: 'email',
      emailMode: result.mode,
    })

    // SSE: push live event to connected dashboard clients
    if (result.sent) {
      emitEvent('email_sent', { to: parsed.data.to, mode: result.mode })
    }

    return { ok: result.sent, ...result }
  })

  app.post('/api/outreach/sync-replies', async (request) => {
    const limitRaw = Number((request.body as { limit?: number } | undefined)?.limit ?? 20)
    const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.min(50, Math.trunc(limitRaw))) : 20
    const result = await replySync.syncRecentReplies(limit)

    // CRL: record each reply intent as a reinforcement event
    if (result.ok && Array.isArray(result.items)) {
      let positiveReplies = 0
      for (const item of result.items as Array<{ intent?: string }>) {
        const intent = item.intent as string | undefined
        if (intent === 'interested' || intent === 'meeting_intent') {
          void recordOutcome('outreach', 'reply_received', { channel: 'email' })
          positiveReplies++
        } else if (intent === 'unsubscribe') {
          void recordOutcome('outreach', 'unsubscribe', { channel: 'email' })
        } else if (intent === 'objection') {
          void recordOutcome('outreach', 'objection', { channel: 'email' })
        }
      }
      if (positiveReplies > 0) {
        emitEvent('reply_received', { count: positiveReplies })
        emitEvent('pipeline_updated', { source: 'reply_sync', newReplies: positiveReplies })
      }
    }

    return result
  })

  app.get('/api/outreach/apollo/search', async (request) => {
    const { segment, limit: limitRaw } = request.query as { segment?: string; limit?: string }
    const seg = String(segment ?? 'all')
    const limit = Math.min(Math.max(Number(limitRaw ?? 10), 1), 25)
    const result = await outreach.apolloSearch(seg, limit)
    return { ok: true, ...result }
  })

  app.post('/api/outreach/enrich-and-draft', async (request, reply) => {
    const parsed = enrichAndDraftSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })

    const result = await outreach.enrichAndDraft(parsed.data.leads)
    const items = await Promise.all(result.items.map(async (item) => {
      const lead = await productionData.upsertProspect({
        fullName: item.lead.fullName,
        email: item.lead.email,
        companyName: item.lead.companyName,
        industry: item.lead.industry,
        city: item.lead.city,
        roleTitle: item.lead.role,
        source: item.lead.source,
      })
      const draft = await productionData.createDraft({
        leadId: String(lead.id),
        subject: item.draft.subject,
        body: item.draft.body,
        mode: item.draft.mode,
      })
      return { lead, draft, source: item.lead.source, enrichmentSummary: item.lead.enrichmentSummary }
    }))

    return { ok: true, provider: result.provider, mode: result.mode, enrichmentMessage: result.enrichmentMessage, total: items.length, items }
  })

  app.post('/api/outreach/apify/discover-and-draft', async (request, reply) => {
    const parsed = discoverAndDraftSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })

    const result = await outreach.discoverAndDraft(parsed.data)
    const items = await Promise.all(result.items.map(async (item) => {
      const lead = await productionData.upsertProspect({
        fullName: item.lead.fullName,
        email: item.lead.email,
        companyName: item.lead.companyName,
        industry: item.lead.industry,
        city: item.lead.city,
        roleTitle: item.lead.role,
        source: item.lead.source,
      })
      const draft = await productionData.createDraft({
        leadId: String(lead.id),
        subject: item.draft.subject,
        body: item.draft.body,
        mode: item.draft.mode,
      })
      return { lead, draft, source: item.lead.source, enrichmentSummary: item.lead.enrichmentSummary }
    }))

    return { ok: result.mode === 'live', provider: result.provider, mode: result.mode, enrichmentMessage: result.enrichmentMessage, total: items.length, items }
  })

  // Smart enrichment: Gemini research → funny email → optional typo subject hook
  const enrichSmartSchema = z.object({
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
    ).min(1).max(20),
    typoHook: z.boolean().default(true),
  })

  app.post('/api/outreach/enrich-smart', async (request, reply) => {
    const parsed = enrichSmartSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })

    const result = await outreach.enrichSmartAndDraft(parsed.data.leads, { typoHook: parsed.data.typoHook })

    const items = await Promise.all(result.items.map(async (item) => {
      const lead = await productionData.upsertProspect({
        fullName: item.lead.fullName,
        email: item.lead.email,
        companyName: item.lead.companyName,
        industry: item.lead.industry,
        city: item.lead.city,
        roleTitle: item.lead.role,
        source: item.lead.source,
      })
      const draft = await productionData.createDraft({
        leadId: String(lead.id),
        subject: item.draft.subject,
        body: item.draft.body,
        mode: item.draft.mode,
      })
      return {
        lead,
        draft,
        enrichmentSummary: item.lead.enrichmentSummary,
        funFact: (item.lead as { funFact?: string }).funFact,
        openingJoke: (item.lead as { openingJoke?: string }).openingJoke,
        typoHookApplied: result.typoHookActive,
        queued: Boolean((item.draft as { telemetry?: { queued?: boolean } }).telemetry?.queued),
        queueWaitMs: (item.draft as { telemetry?: { queueWaitMs?: number } }).telemetry?.queueWaitMs ?? 0,
        attemptCount: (item.draft as { telemetry?: { attemptCount?: number } }).telemetry?.attemptCount ?? 0,
        keyRoleUsed: (item.draft as { telemetry?: { keyRoleUsed?: string } }).telemetry?.keyRoleUsed ?? null,
        fallbackMode: (item.draft as { telemetry?: { fallbackMode?: string } }).telemetry?.fallbackMode ?? null,
      }
    }))

    return { ok: true, mode: result.mode, typoHookActive: result.typoHookActive, total: items.length, items }
  })

  // Batch-send all pending drafts — matches each draft to its lead and fires
  const batchSendSchema = z.object({
    limit: z.number().int().min(1).max(100).default(10),
    dryRun: z.boolean().default(false),
  })

  app.post('/api/outreach/batch-send', async (request, reply) => {
    const parsed = batchSendSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })

    const { limit, dryRun } = parsed.data
    const leads = runtimeStore.all.leads
    const drafts = runtimeStore.all.drafts.slice(0, limit)
    const alreadySent = new Set(runtimeStore.all.sends.map((s) => s.leadId))

    const pending = drafts.filter((d) => !alreadySent.has(d.leadId))

    if (dryRun) {
      return {
        ok: true,
        dryRun: true,
        pendingCount: pending.length,
        preview: pending.map((d) => {
          const lead = leads.find((l) => l.id === d.leadId)
          return { to: lead?.email ?? 'unknown', subject: d.subject, leadName: lead?.fullName ?? 'unknown' }
        }),
      }
    }

    const results = []
    for (const draft of pending) {
      const lead = leads.find((l) => l.id === draft.leadId)
      if (!lead?.email) continue

      const result = await outreach.sendEmailDraft({ to: lead.email, subject: draft.subject, body: draft.body })

      runtimeStore.createSendEvent({
        leadId: draft.leadId,
        draftId: draft.id,
        to: lead.email,
        status: result.sent ? 'sent' : 'failed',
        reason: result.reason,
      })

      results.push({
        lead: lead.fullName,
        to: lead.email,
        subject: draft.subject,
        sent: result.sent,
        mode: result.mode,
        reason: result.reason ?? null,
      })
    }

    const sent = results.filter((r) => r.sent).length
    const failed = results.filter((r) => !r.sent).length

    return { ok: sent > 0, sent, failed, total: results.length, results }
  })
}
