import { env } from '../config/env.js'
import { outboundFetch } from '../lib/network.js'
import { getSupabaseAdmin } from '../lib/supabaseAdmin.js'
import { runtimeStore } from '../lib/runtimeStore.js'
import { GoogleStackService } from './googleStack.service.js'
import { ProductionDataService } from './productionData.service.js'

type GmailMessageRef = {
  id?: string
  threadId?: string
}

type GmailPayloadPart = {
  mimeType?: string
  body?: { data?: string }
  parts?: GmailPayloadPart[]
  headers?: Array<{ name?: string; value?: string }>
}

type GmailMessage = {
  id?: string
  threadId?: string
  snippet?: string
  payload?: GmailPayloadPart
}

function decodeBase64Url(value?: string) {
  if (!value) return ''
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/')
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
  return Buffer.from(padded, 'base64').toString('utf8')
}

function extractHeader(payload: GmailPayloadPart | undefined, name: string) {
  const header = payload?.headers?.find((item) => item.name?.toLowerCase() === name.toLowerCase())
  return header?.value ?? ''
}

function extractEmail(value: string) {
  const match = value.match(/<([^>]+)>/)
  return (match?.[1] ?? value).trim().toLowerCase()
}

function stripHtml(html: string) {
  return html.replace(/<style[\s\S]*?<\/style>/gi, ' ').replace(/<script[\s\S]*?<\/script>/gi, ' ').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
}

function extractBody(part?: GmailPayloadPart): string {
  if (!part) return ''

  if (part.mimeType === 'text/plain') {
    return decodeBase64Url(part.body?.data).trim()
  }

  if (part.mimeType === 'text/html') {
    return stripHtml(decodeBase64Url(part.body?.data))
  }

  for (const child of part.parts ?? []) {
    const text = extractBody(child)
    if (text) return text
  }

  return decodeBase64Url(part.body?.data).trim()
}

function classifyIntent(text: string) {
  const value = text.toLowerCase()
  if (/(unsubscribe|remove me|stop emailing|opt out)/.test(value)) return 'unsubscribe' as const
  if (/(book|schedule|calendar|call|demo|meet|tomorrow|next week)/.test(value)) return 'meeting_intent' as const
  if (/(interested|send more|sounds good|tell me more|pricing)/.test(value)) return 'interested' as const
  if (/(not interested|already have|too expensive|no budget|later)/.test(value)) return 'objection' as const
  return 'neutral' as const
}

export class ReplySyncService {
  private readonly googleStack = new GoogleStackService()
  private readonly productionData = new ProductionDataService()

  async syncRecentReplies(limit = 20) {
    const sender = (env.GMAIL_SENDER_EMAIL ?? env.GMAIL_SENDER_EMAIL_BACKUP ?? '').trim().toLowerCase()
    const resolved = await this.googleStack.resolveActiveProfile()
    const accessToken = resolved.token.ok ? resolved.token.accessToken : null

    if (!accessToken) {
      return {
        ok: false,
        mode: 'offline',
        reason: resolved.token.reason ?? 'missing_gmail_token',
        synced: 0,
        duplicates: 0,
        unmatched: 0,
        items: [],
      }
    }

    const query = encodeURIComponent(`in:inbox newer_than:30d -from:${sender}`)
    const listResponse = await outboundFetch(`https://gmail.googleapis.com/gmail/v1/users/me/messages?q=${query}&maxResults=${limit}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })

    if (!listResponse.ok) {
      return {
        ok: false,
        mode: 'error',
        reason: `gmail_list_failed:${listResponse.status}:${await listResponse.text()}`,
        synced: 0,
        duplicates: 0,
        unmatched: 0,
        items: [],
      }
    }

    const listJson = (await listResponse.json()) as { messages?: GmailMessageRef[] }
    const refs = listJson.messages ?? []
    const items: Array<Record<string, unknown>> = []
    let synced = 0
    let duplicates = 0
    let unmatched = 0

    for (const ref of refs) {
      if (!ref.id) continue
      if (await this.replyExists(ref.id)) {
        duplicates += 1
        continue
      }

      const messageResponse = await outboundFetch(`https://gmail.googleapis.com/gmail/v1/users/me/messages/${ref.id}?format=full`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      })
      if (!messageResponse.ok) continue

      const message = (await messageResponse.json()) as GmailMessage
      const fromHeader = extractHeader(message.payload, 'From')
      const subject = extractHeader(message.payload, 'Subject')
      const replyAt = extractHeader(message.payload, 'Date')
      const fromEmail = extractEmail(fromHeader)

      if (!fromEmail || fromEmail === sender) continue

      const prospect = await this.findProspectByEmail(fromEmail)
      if (!prospect?.id) {
        unmatched += 1
        continue
      }

      const sendEvent = await this.findLatestSendEvent(fromEmail)
      const rawText = extractBody(message.payload) || message.snippet || subject || 'Reply detected'
      const intent = classifyIntent(`${subject}\n${rawText}`)
      const event = await this.productionData.createReplyEvent({
        leadId: String(prospect.id),
        sendEventId: sendEvent?.id ? String(sendEvent.id) : undefined,
        intent,
        rawText,
        metadata: {
          gmailMessageId: ref.id,
          gmailThreadId: message.threadId ?? ref.threadId ?? null,
          fromEmail,
          subject,
          repliedAt: replyAt,
        },
      })

      synced += 1
      const fullName = 'full_name' in prospect ? prospect.full_name : prospect.fullName
      const companyName = 'company_name' in prospect ? prospect.company_name : prospect.companyName
      items.push({
        replyEventId: (event as { id?: string })?.id ?? null,
        leadId: prospect.id,
        fullName: fullName ?? 'Unknown',
        companyName: companyName ?? '',
        fromEmail,
        subject,
        intent,
        gmailMessageId: ref.id,
      })
    }

    return {
      ok: true,
      mode: 'live',
      synced,
      duplicates,
      unmatched,
      items,
    }
  }

  private async replyExists(gmailMessageId: string) {
    const supabase = getSupabaseAdmin()
    if (!supabase) return false

    const { data } = await supabase
      .from('outreach_reply_events')
      .select('id')
      .contains('metadata', { gmailMessageId })
      .limit(1)

    return Boolean(data?.length)
  }

  private async findProspectByEmail(email: string) {
    const supabase = getSupabaseAdmin()
    if (!supabase) {
      return runtimeStore.all.leads.find((lead) => lead.email.toLowerCase() === email)
    }

    const { data } = await supabase
      .from('prospects')
      .select('id, full_name, company_name, email')
      .eq('email', email)
      .order('created_at', { ascending: false })
      .limit(1)
      .maybeSingle()

    return data
  }

  private async findLatestSendEvent(email: string) {
    const supabase = getSupabaseAdmin()
    if (!supabase) {
      const runtimeLead = runtimeStore.all.leads.find((lead) => lead.email.toLowerCase() === email)
      if (!runtimeLead) return null
      return runtimeStore.all.sends.find((send) => send.leadId === runtimeLead.id) ?? null
    }

    const { data } = await supabase
      .from('outreach_send_events')
      .select('id, lead_id, recipient_email, created_at')
      .eq('recipient_email', email)
      .order('created_at', { ascending: false })
      .limit(1)
      .maybeSingle()

    return data
  }
}
