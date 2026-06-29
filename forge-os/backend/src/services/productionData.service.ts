import { getSupabaseAdmin } from '../lib/supabaseAdmin.js'
import { runtimeStore } from '../lib/runtimeStore.js'

type PersistLeadInput = {
  fullName: string
  email: string
  companyName: string
  industry?: string
  city?: string
  roleTitle?: string
  source?: string
  status?: string
}

type PersistDraftInput = {
  leadId: string
  subject: string
  body: string
  mode: string
}

type PersistSendEventInput = {
  leadId?: string
  draftId?: string
  to: string
  status: 'queued' | 'sent' | 'failed' | 'blocked'
  reason?: string
  providerMessageId?: string | null
  metadata?: Record<string, unknown>
}

type PersistReplyEventInput = {
  leadId: string
  sendEventId?: string
  intent: 'interested' | 'neutral' | 'unsubscribe' | 'objection' | 'meeting_intent'
  rawText?: string
  metadata?: Record<string, unknown>
}

type PersistMeetingInput = {
  leadId: string
  value?: number
}

function asString(value: unknown, fallback = '') {
  return typeof value === 'string' ? value : fallback
}

function asNumber(value: unknown, fallback = 0) {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

export class ProductionDataService {
  async upsertProspect(input: PersistLeadInput) {
    const supabase = getSupabaseAdmin()
    if (!supabase) {
      return runtimeStore.upsertLead({
        fullName: input.fullName,
        email: input.email,
        companyName: input.companyName,
        industry: input.industry,
        city: input.city,
        enrichedAt: new Date().toISOString(),
      })
    }

    const { data: existing } = await supabase
      .from('prospects')
      .select('id, status')
      .eq('email', input.email)
      .order('created_at', { ascending: false })
      .limit(1)
      .maybeSingle()

    if (existing?.id) {
      const { data: updated } = await supabase
        .from('prospects')
        .update({
          full_name: input.fullName,
          company_name: input.companyName,
          industry: input.industry ?? 'Unknown',
          city: input.city ?? null,
          role_title: input.roleTitle ?? null,
          source: input.source ?? 'manual',
          status: input.status ?? existing.status ?? 'new',
        })
        .eq('id', existing.id)
        .select('id, full_name, email, company_name, industry, city, status, source, created_at')
        .single()

      if (updated) return updated
    }

    const { data: created, error } = await supabase
      .from('prospects')
      .insert({
        full_name: input.fullName,
        email: input.email,
        company_name: input.companyName,
        industry: input.industry ?? 'Unknown',
        city: input.city ?? null,
        role_title: input.roleTitle ?? null,
        source: input.source ?? 'manual',
        status: input.status ?? 'new',
      })
      .select('id, full_name, email, company_name, industry, city, status, source, created_at')
      .single()

    if (error || !created) {
      return runtimeStore.upsertLead({
        fullName: input.fullName,
        email: input.email,
        companyName: input.companyName,
        industry: input.industry,
        city: input.city,
        enrichedAt: new Date().toISOString(),
      })
    }

    return created
  }

  async createDraft(input: PersistDraftInput) {
    const supabase = getSupabaseAdmin()
    if (!supabase) {
      return runtimeStore.createDraft({
        leadId: input.leadId,
        subject: input.subject,
        body: input.body,
        mode: input.mode,
      })
    }

    const { data, error } = await supabase
      .from('outreach_drafts')
      .insert({
        lead_id: input.leadId,
        subject: input.subject,
        body: input.body,
        mode: input.mode,
      })
      .select('id, lead_id, subject, body, mode, created_at')
      .single()

    if (error || !data) {
      return runtimeStore.createDraft({
        leadId: input.leadId,
        subject: input.subject,
        body: input.body,
        mode: input.mode,
      })
    }

    return data
  }

  async createSendEvent(input: PersistSendEventInput) {
    const supabase = getSupabaseAdmin()
    if (!supabase || !input.leadId || !input.draftId) {
      if (input.leadId && input.draftId) {
        return runtimeStore.createSendEvent({
          leadId: input.leadId,
          draftId: input.draftId,
          to: input.to,
          status: input.status === 'sent' ? 'sent' : 'failed',
          reason: input.reason,
        })
      }
      return null
    }

    const { data, error } = await supabase
      .from('outreach_send_events')
      .insert({
        lead_id: input.leadId,
        draft_id: input.draftId,
        recipient_email: input.to,
        status: input.status,
        provider_message_id: input.providerMessageId ?? null,
        reason: input.reason ?? null,
        metadata: input.metadata ?? {},
      })
      .select('id, lead_id, draft_id, recipient_email, status, reason, created_at')
      .single()

    if (error || !data) {
      return runtimeStore.createSendEvent({
        leadId: input.leadId,
        draftId: input.draftId,
        to: input.to,
        status: input.status === 'sent' ? 'sent' : 'failed',
        reason: input.reason,
      })
    }

    return data
  }

  async createReplyEvent(input: PersistReplyEventInput) {
    const supabase = getSupabaseAdmin()
    if (!supabase) {
      return runtimeStore.createReplyEvent({
        leadId: input.leadId,
        intent: input.intent,
      })
    }

    const { data, error } = await supabase
      .from('outreach_reply_events')
      .insert({
        lead_id: input.leadId,
        send_event_id: input.sendEventId ?? null,
        intent: input.intent,
        raw_text: input.rawText ?? null,
        metadata: input.metadata ?? {},
      })
      .select('id, lead_id, intent, raw_text, created_at')
      .single()

    if (error || !data) {
      return runtimeStore.createReplyEvent({
        leadId: input.leadId,
        intent: input.intent,
      })
    }

    return data
  }

  async createMeeting(input: PersistMeetingInput) {
    const supabase = getSupabaseAdmin()
    if (!supabase) {
      return runtimeStore.createMeeting({ leadId: input.leadId, value: input.value ?? 0 })
    }

    const { data: prospect } = await supabase
      .from('prospects')
      .select('id, full_name, company_name')
      .eq('id', input.leadId)
      .maybeSingle()

    const { data, error } = await supabase
      .from('meetings')
      .insert({
        prospect_id: input.leadId,
        prospect_name: asString(prospect?.full_name, 'Unknown Prospect'),
        company_name: asString(prospect?.company_name, ''),
        meeting_type: 'Discovery',
        start_at: new Date().toISOString(),
        status: 'booked_pending_schedule',
        value_estimate: input.value ?? 0,
      })
      .select('id, prospect_id, prospect_name, company_name, meeting_type, start_at, status, value_estimate, created_at')
      .single()

    if (error || !data) {
      return runtimeStore.createMeeting({ leadId: input.leadId, value: input.value ?? 0 })
    }

    return data
  }

  async latestReplyIntent(leadId: string) {
    const supabase = getSupabaseAdmin()
    if (!supabase) {
      return runtimeStore.all.replies.find((item) => item.leadId === leadId)?.intent
    }

    const { data } = await supabase
      .from('outreach_reply_events')
      .select('intent')
      .eq('lead_id', leadId)
      .order('created_at', { ascending: false })
      .limit(1)
      .maybeSingle()

    return data?.intent
  }

  async analyticsOverview() {
    const supabase = getSupabaseAdmin()
    if (!supabase) {
      const sent = runtimeStore.all.sends.filter((s) => s.status === 'sent').length
      const failed = runtimeStore.all.sends.filter((s) => s.status === 'failed').length
      const replies = runtimeStore.all.replies.length
      const meetings = runtimeStore.all.meetings.length
      const replyRate = sent > 0 ? (replies / sent) * 100 : 0
      const meetingRate = replies > 0 ? (meetings / replies) * 100 : 0
      return {
        metrics: {
          totalLeads: runtimeStore.all.leads.length,
          totalDrafts: runtimeStore.all.drafts.length,
          emailsSent: sent,
          sendFailures: failed,
          replies,
          meetingsBooked: meetings,
          replyRate: Number(replyRate.toFixed(2)),
          meetingRate: Number(meetingRate.toFixed(2)),
          pipelineValue: runtimeStore.all.meetings.reduce((sum, item) => sum + item.value, 0),
        },
        campaignLeaderboard: [],
        recentReplies: [],
        statsSource: 'runtime_events',
      }
    }

    const [
      prospectsCount,
      draftsCount,
      sentCount,
      failedCount,
      repliesCount,
      meetingsCount,
      meetingsValueRows,
      campaignsRows,
      recentReplyRows,
    ] = await Promise.all([
      supabase.from('prospects').select('*', { count: 'exact', head: true }),
      supabase.from('outreach_drafts').select('*', { count: 'exact', head: true }),
      supabase.from('outreach_send_events').select('*', { count: 'exact', head: true }).eq('status', 'sent'),
      supabase.from('outreach_send_events').select('*', { count: 'exact', head: true }).eq('status', 'failed'),
      supabase.from('outreach_reply_events').select('*', { count: 'exact', head: true }),
      supabase.from('meetings').select('*', { count: 'exact', head: true }),
      supabase.from('meetings').select('value_estimate').limit(500),
      supabase
        .from('campaigns')
        .select('id, name, target_vertical, total_sent, reply_rate, meetings_booked')
        .order('meetings_booked', { ascending: false })
        .limit(5),
      supabase
        .from('outreach_reply_events')
        .select('id, intent, raw_text, created_at, lead_id, prospects(full_name, company_name)')
        .order('created_at', { ascending: false })
        .limit(5),
    ])

    const totalLeads = prospectsCount.count ?? 0
    const totalDrafts = draftsCount.count ?? 0
    const emailsSent = sentCount.count ?? 0
    const sendFailures = failedCount.count ?? 0
    const replies = repliesCount.count ?? 0
    const meetingsBooked = meetingsCount.count ?? 0
    const replyRate = emailsSent > 0 ? (replies / emailsSent) * 100 : 0
    const meetingRate = replies > 0 ? (meetingsBooked / replies) * 100 : 0
    const pipelineValue = (meetingsValueRows.data ?? []).reduce((sum, row) => sum + asNumber(row.value_estimate), 0)

    return {
      metrics: {
        totalLeads,
        totalDrafts,
        emailsSent,
        sendFailures,
        replies,
        meetingsBooked,
        replyRate: Number(replyRate.toFixed(2)),
        meetingRate: Number(meetingRate.toFixed(2)),
        pipelineValue,
      },
      campaignLeaderboard: (campaignsRows.data ?? []).map((row) => ({
        id: row.id,
        name: row.name,
        vertical: row.target_vertical,
        sent: row.total_sent,
        replyRate: Number(row.reply_rate ?? 0),
        meetingsBooked: row.meetings_booked ?? 0,
      })),
      recentReplies: (recentReplyRows.data ?? []).map((row) => ({
        id: row.id,
        intent: row.intent,
        rawText: row.raw_text,
        createdAt: row.created_at,
        leadId: row.lead_id,
        fullName: asString((row.prospects as { full_name?: string } | null)?.full_name, 'Unknown'),
        companyName: asString((row.prospects as { company_name?: string } | null)?.company_name, ''),
      })),
      statsSource: 'supabase',
    }
  }

  async outreachActivity(limit = 20) {
    const supabase = getSupabaseAdmin()
    if (!supabase) {
      return {
        drafts: runtimeStore.all.drafts.slice(-limit).reverse(),
        sends: runtimeStore.all.sends.slice(-limit).reverse(),
        replies: runtimeStore.all.replies.slice(-limit).reverse(),
        source: 'runtime_events',
      }
    }

    const [drafts, sends, replies] = await Promise.all([
      supabase
        .from('outreach_drafts')
        .select('id, subject, body, mode, created_at, lead_id, prospects(full_name, company_name, email)')
        .order('created_at', { ascending: false })
        .limit(limit),
      supabase
        .from('outreach_send_events')
        .select('id, recipient_email, status, reason, created_at, lead_id, draft_id, prospects(full_name, company_name), outreach_drafts(subject, mode)')
        .order('created_at', { ascending: false })
        .limit(limit),
      supabase
        .from('outreach_reply_events')
        .select('id, intent, raw_text, created_at, lead_id, prospects(full_name, company_name, email)')
        .order('created_at', { ascending: false })
        .limit(limit),
    ])

    return {
      drafts: drafts.data ?? [],
      sends: sends.data ?? [],
      replies: replies.data ?? [],
      source: 'supabase',
    }
  }

  async leadManagementDigest() {
    const supabase = getSupabaseAdmin()
    if (!supabase) {
      const replies = runtimeStore.all.replies
      const meetings = runtimeStore.all.meetings
      const byIntent = replies.reduce<Record<string, number>>((acc, reply) => {
        acc[reply.intent] = (acc[reply.intent] ?? 0) + 1
        return acc
      }, {})
      return {
        ok: true,
        owner: 'Akhil',
        role: 'Lead Management Head',
        totalReplies: replies.length,
        meetingsBooked: meetings.length,
        byIntent,
        source: 'runtime_events',
        storage: runtimeStore.storage,
      }
    }

    const [replyRows, meetingsCount] = await Promise.all([
      supabase.from('outreach_reply_events').select('intent'),
      supabase.from('meetings').select('*', { count: 'exact', head: true }),
    ])

    const byIntent = (replyRows.data ?? []).reduce<Record<string, number>>((acc, reply) => {
      acc[reply.intent] = (acc[reply.intent] ?? 0) + 1
      return acc
    }, {})

    return {
      ok: true,
      owner: 'Akhil',
      role: 'Lead Management Head',
      totalReplies: replyRows.data?.length ?? 0,
      meetingsBooked: meetingsCount.count ?? 0,
      byIntent,
      source: 'supabase',
    }
  }
}
