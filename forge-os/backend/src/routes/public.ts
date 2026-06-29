import type { FastifyInstance } from 'fastify'
import { z } from 'zod'
import { writeAudit } from '../lib/auditLog.js'
import { recordOutcome } from '../lib/crlLearning.js'
import { getSupabaseAdmin } from '../lib/supabaseAdmin.js'
import { JarvisService } from '../services/jarvis.service.js'
import { ProductionDataService } from '../services/productionData.service.js'

const chatSchema = z.object({
  message: z.string().min(1),
  visitorName: z.string().optional(),
  companyName: z.string().optional(),
  sessionId: z.string().optional(),
  campaignId: z.string().uuid().optional(),
})

const bookingSchema = z.object({
  fullName: z.string().min(1),
  email: z.string().email(),
  companyName: z.string().optional(),
  notes: z.string().optional(),
  source: z.string().optional(),
  campaignId: z.string().uuid().optional(),
})

const visitSchema = z.object({
  pageUrl: z.string().optional(),
  referrer: z.string().optional(),
  visitorEmail: z.string().email().optional(),
  visitorName: z.string().optional(),
  companyName: z.string().optional(),
  utmSource: z.string().optional(),
  utmCampaign: z.string().optional(),
  campaignId: z.string().uuid().optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
})

export async function registerPublicRoutes(app: FastifyInstance) {
  const jarvis = new JarvisService()
  const productionData = new ProductionDataService()

  // ── Chat (existing) ──────────────────────────────────────────────────────────

  app.post('/api/public/chat', async (request, reply) => {
    const parsed = chatSchema.safeParse(request.body)
    if (!parsed.success) {
      return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    }

    const result = await jarvis.run({
      prompt: `Inbound landing page visitor: ${parsed.data.message}`,
      operator: parsed.data.visitorName ?? 'Inbound visitor',
    })

    // Track chat signal in Supabase
    const supabase = getSupabaseAdmin()
    if (supabase) {
      void supabase.from('chat_signals').insert({
        session_id: parsed.data.sessionId ?? null,
        campaign_id: parsed.data.campaignId ?? null,
        message: parsed.data.message,
        sentiment: null,
        qualified: result.actions?.some((a: string) => a.toLowerCase().includes('book') || a.toLowerCase().includes('call')) ?? false,
        metadata: {
          visitorName: parsed.data.visitorName,
          companyName: parsed.data.companyName,
          responseLength: result.response?.length ?? 0,
        },
      })
    }

    return {
      ok: true,
      reply: result.response,
      nextActions: result.actions,
    }
  })

  // ── Booking Request ──────────────────────────────────────────────────────────

  app.post('/api/public/booking', async (request, reply) => {
    const parsed = bookingSchema.safeParse(request.body)
    if (!parsed.success) {
      return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    }

    const { fullName, email, companyName, notes, source, campaignId } = parsed.data
    const supabase = getSupabaseAdmin()

    let bookingId: string | null = null

    if (supabase) {
      const { data, error } = await supabase
        .from('booking_requests')
        .insert({
          full_name: fullName,
          email,
          company_name: companyName ?? null,
          requested_at: new Date().toISOString(),
          source: source ?? 'landing_page',
          notes: notes ?? null,
          status: 'requested',
        })
        .select('id')
        .single()

      if (!error && data) {
        bookingId = data.id

        // Auto-upsert as prospect for CRM
        const prospect = await productionData.upsertProspect({
          fullName,
          email,
          companyName: companyName ?? 'Unknown',
          source: 'inbound_landing_page',
        })

        // Wire booking signal
        if (prospect?.id) {
          void supabase.from('booking_signals').insert({
            campaign_id: campaignId ?? null,
            prospect_id: String(prospect.id),
            booking_request_id: bookingId,
            name: fullName,
            email,
            company: companyName ?? null,
            source: source ?? 'landing_page',
            metadata: { notes },
          })
        }
      }
    } else {
      // Offline: still upsert to JSON store
      await productionData.upsertProspect({
        fullName,
        email,
        companyName: companyName ?? 'Unknown',
        source: 'inbound_landing_page',
      })
    }

    // CRL: record high-intent inbound
    void recordOutcome('outreach', 'reply_received', {
      channel: 'email',
      industry: companyName ?? 'unknown',
    })

    writeAudit({
      actor: 'public',
      action: 'booking_request',
      purpose: `${fullName} <${email}>`,
      result: 'ok',
      metadata: { companyName, source: source ?? 'landing_page', bookingId },
    })

    return {
      ok: true,
      bookingId,
      message: 'Booking request received. The team will be in touch within 24 hours.',
    }
  })

  // ── Page Visit Tracking ──────────────────────────────────────────────────────

  app.post('/api/public/visit', async (request, reply) => {
    const parsed = visitSchema.safeParse(request.body)
    if (!parsed.success) {
      return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    }

    const supabase = getSupabaseAdmin()
    if (!supabase) {
      return { ok: true, tracked: false, reason: 'offline_mode' }
    }

    await supabase.from('page_visits').insert({
      campaign_id: parsed.data.campaignId ?? null,
      prospect_id: null,
      draft_id: null,
      visitor_email: parsed.data.visitorEmail ?? null,
      visitor_name: parsed.data.visitorName ?? null,
      company_name: parsed.data.companyName ?? null,
      page_url: parsed.data.pageUrl ?? null,
      referrer: parsed.data.referrer ?? null,
      utm_source: parsed.data.utmSource ?? null,
      utm_campaign: parsed.data.utmCampaign ?? null,
      metadata: parsed.data.metadata ?? {},
    })

    return { ok: true, tracked: true }
  })

  // ── Inbound Analytics (dashboard readable) ───────────────────────────────────

  app.get('/api/public/inbound/summary', async () => {
    const supabase = getSupabaseAdmin()
    if (!supabase) {
      return { ok: true, source: 'offline', bookings: 0, visits: 0, chatSignals: 0 }
    }

    const [bookings, visits, chatSignals] = await Promise.all([
      supabase.from('booking_requests').select('id', { count: 'exact', head: true }),
      supabase.from('page_visits').select('id', { count: 'exact', head: true }),
      supabase.from('chat_signals').select('id', { count: 'exact', head: true }),
    ])

    return {
      ok: true,
      source: 'supabase',
      bookings: bookings.count ?? 0,
      visits: visits.count ?? 0,
      chatSignals: chatSignals.count ?? 0,
    }
  })

  app.get('/api/public/bookings', async (request) => {
    const limitRaw = Number((request.query as { limit?: string }).limit ?? 20)
    const limit = Math.min(Math.max(limitRaw, 1), 100)

    const supabase = getSupabaseAdmin()
    if (!supabase) {
      return { ok: true, source: 'offline', items: [] }
    }

    const { data, error } = await supabase
      .from('booking_requests')
      .select('id, full_name, email, company_name, status, source, notes, requested_at, created_at')
      .order('created_at', { ascending: false })
      .limit(limit)

    if (error) return { ok: false, error: error.message, items: [] }
    return { ok: true, source: 'supabase', total: data?.length ?? 0, items: data ?? [] }
  })
}
