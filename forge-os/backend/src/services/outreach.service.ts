import { Buffer } from 'node:buffer'
import { env, geminiApiKeyFor } from '../config/env.js'
import { writeAudit } from '../lib/auditLog.js'
import { callGeminiDetailed } from '../lib/gemini.js'
import { outboundFetch } from '../lib/network.js'
import { GoogleStackService } from './googleStack.service.js'

type PersonalizeInput = {
  fullName: string
  companyName: string
  industry: string
  website?: string
  city?: string
  painPoint?: string
}

type EnrichmentLeadInput = {
  fullName: string
  email: string
  role?: string
  companyName: string
  website?: string
  industry?: string
  city?: string
  painPoint?: string
}

export type DmChannel = 'linkedin' | 'instagram' | 'whatsapp' | 'sms' | 'x'
export type HumorStyle = 'dry' | 'playful' | 'none'

export type CustomDmInput = {
  channel: DmChannel
  fullName: string
  role?: string
  companyName: string
  industry: string
  website?: string
  city?: string
  painPoint?: string
  recentSignal?: string
  hookStyle?: 'pain-first' | 'result-first' | 'signal-first'
  humorStyle?: HumorStyle
  includeCta?: boolean
}

type EnrichedLead = EnrichmentLeadInput & {
  source: 'apify' | 'fallback'
  enrichmentSummary: string
  recentSignal: string
  recommendedAngle: string
}

type ProviderProbe = {
  configured: boolean
  ok: boolean
  status: 'ready' | 'missing_config' | 'error'
  message: string
}

type AiTelemetry = {
  queued: boolean
  queueWaitMs: number
  attemptCount: number
  keyUsed: string
  keyRoleUsed?: string
  fallbackMode: string
  fallbackReason: string | null
}

const companyName = 'Virel Automation'
const primaryOffer = 'Lead Generation'
const targetIndustries = ['HVAC', 'Real Estate Agents', 'Digital Marketing Agencies', 'Interior Designers', 'Clinics', 'Med Spas']

function toBase64Url(input: string) {
  return Buffer.from(input).toString('base64url')
}

function normalizeIndustry(industry = '') {
  const value = industry.toLowerCase()
  if (value.includes('hvac') || value.includes('heating') || value.includes('air conditioning')) return 'HVAC'
  if (value.includes('real estate') || value.includes('realtor') || value.includes('broker')) return 'Real Estate Agents'
  if (value.includes('marketing') || value.includes('agency') || value.includes('seo') || value.includes('ads')) return 'Digital Marketing Agencies'
  if (value.includes('interior')) return 'Interior Designers'
  if (value.includes('med spa') || value.includes('medical spa') || value.includes('aesthetic clinic')) return 'Med Spas'
  if (value.includes('clinic') || value.includes('dental') || value.includes('medical practice')) return 'Clinics'
  if (value.includes('coach') || value.includes('coaching')) return 'Online Coaches'
  if (value.includes('consult') || value.includes('advisor') || value.includes('strategist')) return 'Consultants'
  return industry || 'B2B Services'
}

function hasUsableWebsite(website?: string) {
  const value = (website ?? '').trim().toLowerCase()
  if (!value) return false
  return !['na', 'n/a', 'none', 'no website', 'missing', 'unknown'].includes(value)
}

function defaultPain(industry = '', website?: string) {
  const normalized = normalizeIndustry(industry)
  if (!hasUsableWebsite(website)) return 'weak online trust, lost inbound conversions, and no clear place for prospects to book or enquire'
  if (normalized === 'HVAC') return 'missed service enquiries, slow follow-up, and inconsistent quote pipelines'
  if (normalized === 'Real Estate Agents') return 'cold property leads going stale before an agent follows up'
  if (normalized === 'Digital Marketing Agencies') return 'needing more qualified sales conversations without relying only on referrals'
  if (normalized === 'Interior Designers') return 'strong referrals but inconsistent enquiry volume and too much manual follow-up before a project call'
  if (normalized === 'Clinics') return 'missed patient enquiries, slow response times, and too much admin between enquiry and appointment'
  if (normalized === 'Med Spas') return 'paid traffic leaking because follow-up is slow and consultation bookings are not converted consistently'
  if (normalized === 'Online Coaches') return 'content gets attention but most DM conversations never convert to paid discovery calls'
  if (normalized === 'Consultants') return 'inconsistent pipeline — referrals are unreliable and outbound prospecting is manual and slow'
  return 'turning outbound attention into qualified booked calls'
}

function recommendedAngle(industry = '', website?: string) {
  const normalized = normalizeIndustry(industry)
  if (!hasUsableWebsite(website)) return 'lead with a conversion-focused website plus lead capture and instant follow-up'
  if (normalized === 'HVAC') return 'lead with booked service calls and faster response-to-quote workflows'
  if (normalized === 'Real Estate Agents') return 'lead with buyer/seller lead capture and rapid follow-up'
  if (normalized === 'Digital Marketing Agencies') return 'lead with predictable client acquisition and appointment setting'
  if (normalized === 'Interior Designers') return 'lead with premium enquiry capture and faster qualification before discovery calls'
  if (normalized === 'Clinics') return 'lead with faster patient response, appointment booking, and recall follow-up'
  if (normalized === 'Med Spas') return 'lead with consultation booking, lead nurture, and ad-to-calendar conversion'
  if (normalized === 'Online Coaches') return 'lead with a DM-to-discovery-call system that converts followers into clients without manual chasing'
  if (normalized === 'Consultants') return 'lead with a consistent outbound system that books qualified calls every week without depending on referrals'
  return 'lead with more qualified leads per month'
}

function offerFrame(industry = '', website?: string) {
  if (!hasUsableWebsite(website)) return 'a conversion-focused website, booking flow, and follow-up system'
  const normalized = normalizeIndustry(industry)
  if (normalized === 'Clinics' || normalized === 'Med Spas') return 'a lead-response and booking system that keeps enquiries moving into appointments'
  return 'a lead-generation and follow-up system that keeps new enquiries moving into booked conversations'
}

function recentSignalFallback(industry = '', website?: string) {
  const normalized = normalizeIndustry(industry)
  if (!hasUsableWebsite(website)) return 'prospects are likely checking the business online first and dropping when there is no strong website or booking path'
  if (normalized === 'Digital Marketing Agencies') return 'more agencies are competing on speed-to-lead while referrals alone are getting less reliable'
  if (normalized === 'Interior Designers') return 'higher-ticket buyers are researching online longer before they ever ask for a consultation'
  if (normalized === 'Clinics') return 'patient acquisition pressure is rising while front-desk teams are already overloaded'
  if (normalized === 'Med Spas') return 'ad costs stay high unless enquiry-to-consultation speed is tight'
  if (normalized === 'Online Coaches') return 'coaches with large audiences are leaving money on the table because DM follow-up is manual and inconsistent'
  if (normalized === 'Consultants') return 'senior consultants are too busy delivering to build pipeline — which creates feast-or-famine revenue cycles'
  return 'demand is up but follow-up speed is usually the bottleneck'
}

function firstName(value: string) {
  return (value ?? '').trim().split(/\s+/)[0] || value || 'there'
}

function shortRole(role?: string) {
  if (!role) return 'team'
  const normalized = role.trim()
  return normalized.length > 28 ? `${normalized.slice(0, 28)}...` : normalized
}

function channelCharLimit(channel: DmChannel) {
  if (channel === 'sms') return 420
  if (channel === 'x') return 260
  return 550
}

function channelTemplate(channel: DmChannel) {
  if (channel === 'linkedin') return 'Professional, concise, and context-aware.'
  if (channel === 'instagram') return 'Conversational and lightweight, with natural language.'
  if (channel === 'whatsapp') return 'Friendly but direct. Short lines and clear action.'
  if (channel === 'sms') return 'Ultra-short and direct. One message, one CTA.'
  return 'Fast-moving and punchy with high clarity.'
}

function normalizeWhitespace(text: string) {
  return text.replace(/\s+/g, ' ').trim()
}

const bannedDmPhrases = ['synergy', 'leverage our ai', 'game-changer', 'circle back', 'quick question']

function qualityChecks(message: string, company: string, industry: string) {
  const normalized = message.toLowerCase()
  const banned = bannedDmPhrases.filter((phrase) => normalized.includes(phrase))
  const hasCompany = normalized.includes(company.toLowerCase())
  const hasIndustry = normalized.includes(industry.toLowerCase())
  const hasCta = /\b(call|chat|reply|meet|minutes)\b/i.test(message)
  const specificityScore = [hasCompany, hasIndustry, hasCta].filter(Boolean).length / 3
  const genericPenalty = /\bwe help businesses\b/i.test(message) ? 0.2 : 0
  const score = Math.max(0, Math.min(1, specificityScore - genericPenalty - banned.length * 0.1))
  return { banned, score, hasCta }
}

export class OutreachService {
  private googleStack = new GoogleStackService()

  personalizeColdEmail(input: PersonalizeInput) {
    const city = input.city ? ` in ${input.city}` : ''
    const industry = normalizeIndustry(input.industry)
    const pain = input.painPoint ?? defaultPain(industry, input.website)
    const angle = recommendedAngle(industry, input.website)
    const offer = offerFrame(industry, input.website)
    return {
      subject: hasUsableWebsite(input.website) ? `${input.companyName} lead flow` : `${input.companyName} website + lead flow`,
      body: [
        `${input.fullName},`,
        '',
        `I looked at ${input.companyName}${city}; for ${industry}, the usual leak is ${pain}.`,
        `Virel Automation builds ${offer} so businesses can turn more attention into actual booked conversations.`,
        `The practical angle for ${industry} is ${angle}.`,
        'The point is not more software. It is more booked conversations from the same market you already serve.',
        'Worth a 15-minute look this week?',
        '',
        'Jace',
        companyName,
      ].join('\n'),
    }
  }

  private buildPersonalizedHook(input: {
    fullName: string
    companyName: string
    industry: string
    website?: string
    city?: string
    painPoint?: string
    recentSignal?: string
    role?: string
  }) {
    const name = firstName(input.fullName)
    const industry = normalizeIndustry(input.industry)
    const role = shortRole(input.role)
    const pain = input.painPoint ?? defaultPain(industry, input.website)
    const signal = input.recentSignal ?? recentSignalFallback(industry, input.website)
    const location = input.city ? ` in ${input.city}` : ''
    const angle = recommendedAngle(industry, input.website)
    const offer = offerFrame(industry, input.website)
    const websiteMissing = !hasUsableWebsite(input.website)
    const jokes: Record<HumorStyle, string[]> = {
      dry: [
        'This is a cold message, but at least it has a pulse.',
        'Another outreach note, yes. This one is actually useful.',
        'I know your inbox is chaos, so I will keep this surgical.',
      ],
      playful: [
        'I promise this is less painful than most cold DMs.',
        'This is a cold message, but we can still keep it human.',
        'I will skip the buzzwords and keep the useful part.',
      ],
      none: [''],
    }
    return { name, industry, role, pain, signal, location, angle, offer, websiteMissing, jokes }
  }

  async generateCustomDm(input: CustomDmInput) {
    const hook = this.buildPersonalizedHook(input)
    const channel = input.channel
    const includeCta = input.includeCta ?? true
    const humorStyle = input.humorStyle ?? 'dry'
    const hookStyle = input.hookStyle ?? 'signal-first'
    let telemetry: AiTelemetry = {
      queued: false,
      queueWaitMs: 0,
      attemptCount: 0,
      keyUsed: 'none',
      keyRoleUsed: 'none',
      fallbackMode: 'fallback',
      fallbackReason: null,
    }

    if (geminiApiKeyFor('noah')) {
      const prompt = [
        `You are Noah, CMO for ${companyName}.`,
        `Write one ${channel.toUpperCase()} DM for B2B outreach.`,
        `Channel style template: ${channelTemplate(channel)}`,
        `Offer: ${primaryOffer}. Industry targets: ${targetIndustries.join(', ')}.`,
        `Recipient: ${input.fullName}, role=${hook.role}, company=${input.companyName}, industry=${hook.industry}, city=${input.city ?? 'unknown'}, website=${input.website ?? 'unknown'}.`,
        `Pain: ${hook.pain}`,
        `Signal: ${hook.signal}`,
        `Angle: ${hook.angle}`,
        `Offer frame: ${hook.offer}`,
        `Hook style: ${hookStyle}. Humor style: ${humorStyle}.`,
        `Rules: ${channelCharLimit(channel)} chars max, plain text, specific not generic, one clear CTA max, no "AI automation" jargon spam.`,
        hook.websiteMissing ? 'If the website looks missing or weak, pivot the outreach toward a website-plus-follow-up system instead of only appointment setting.' : 'Assume the business already has a working website and focus on follow-up, booking, and lead conversion.',
        'Return strict JSON: {"opener":"...","message":"...","cta":"...","full":"..."}',
      ].join('\n')

      try {
        const ai = await callGeminiDetailed({
          role: 'noah',
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0.8, maxOutputTokens: 450, responseMimeType: 'application/json' },
        })
        telemetry = {
          queued: ai.meta.queued,
          queueWaitMs: ai.meta.queueWaitMs,
          attemptCount: ai.meta.attemptCount,
          keyUsed: ai.meta.keyFingerprint,
          keyRoleUsed: ai.meta.keyRoleUsed,
          fallbackMode: ai.meta.fallbackMode,
          fallbackReason: ai.meta.fallbackReason,
        }
        const text = ai.text
        if (text) {
          const raw = text.trim().startsWith('```') ? text.split('```')[1]?.replace(/^json\n?/, '').trim() ?? text : text
          const parsed = JSON.parse(raw) as { opener?: string; message?: string; cta?: string; full?: string }
          const opener = parsed.opener?.trim() || `${hook.name} - quick one for ${input.companyName}${hook.location}.`
          const cta = includeCta ? (parsed.cta?.trim() || 'Open to a quick 15-minute chat this week?') : ''
          const middle = parsed.message?.trim() || parsed.full?.trim() || `${hook.signal}. We solve ${hook.pain} with ${hook.offer} built for ${hook.industry}.`
          const full = [opener, middle, cta].filter(Boolean).join('\n')
          const clipped = normalizeWhitespace(full).slice(0, channelCharLimit(channel))
          const checks = qualityChecks(clipped, input.companyName, hook.industry)
          if (!checks.hasCta || checks.banned.length > 0 || checks.score < 0.5) {
            telemetry.fallbackReason = `quality_guardrail:${checks.score.toFixed(2)}`
          } else {
            return { mode: 'ai', channel, opener, message: middle, cta, full: clipped, telemetry, quality: checks }
          }
        }
      } catch {
        telemetry.fallbackReason = 'ai_generation_failed'
      }
    }

    const jokePool = hook.jokes[humorStyle]
    const openerByStyle: Record<NonNullable<CustomDmInput['hookStyle']>, string> = {
      'signal-first': `${hook.name} - I noticed something in ${input.companyName}${hook.location}.`,
      'pain-first': `${hook.name} - quick one on ${hook.pain}.`,
      'result-first': `${hook.name} - we help ${hook.industry} teams book more qualified leads monthly.`,
    }
    const opener = openerByStyle[hookStyle]
    const joke = jokePool.length ? jokePool[Math.floor(Math.random() * jokePool.length)] : ''
    const message = [
      joke,
      `${hook.signal}.`,
      `Most ${hook.industry} teams lose pipeline when ${hook.pain}.`,
      `We run ${hook.offer} focused on ${hook.angle}.`,
    ].filter(Boolean).join(' ')
    const cta = includeCta ? 'If useful, I can show you a 15-minute walkthrough.' : ''
    const full = normalizeWhitespace([opener, message, cta].filter(Boolean).join('\n')).slice(0, channelCharLimit(channel))
    const checks = qualityChecks(full, input.companyName, hook.industry)
    return { mode: 'fallback', channel, opener, message, cta, full, telemetry, quality: checks }
  }

  async readiness() {
    const [gmail, gemini, apify] = await Promise.all([
      this.gmailReadiness(),
      this.geminiReadiness(),
      this.apifyReadiness(),
    ])

    return {
      ok: gmail.ok && gemini.ok && apify.ok,
      providers: {
        gmail,
        gemini,
        apify,
      },
    }
  }

  private geminiKeyRing(primary: 'noah' | 'devan') {
    const rolePrimary = geminiApiKeyFor(primary)
    const roleSecondary = geminiApiKeyFor(primary === 'noah' ? 'jarvis' : 'king')
    const global = env.GEMINI_API_KEY
    return [rolePrimary, roleSecondary, global].filter((value, idx, arr): value is string => Boolean(value) && arr.indexOf(value) === idx)
  }

  private async geminiGenerate(options: {
    primaryRole: 'noah' | 'devan'
    prompt: string
    maxOutputTokens: number
    temperature: number
    responseMimeType?: 'application/json'
  }) {
    if (!this.geminiKeyRing(options.primaryRole).length) {
      return { ok: false as const, reason: `missing_key:${options.primaryRole}` }
    }

    try {
      const ai = await callGeminiDetailed({
        role: options.primaryRole,
        contents: [{ parts: [{ text: options.prompt }] }],
        generationConfig: {
          temperature: options.temperature,
          maxOutputTokens: options.maxOutputTokens,
          ...(options.responseMimeType ? { responseMimeType: options.responseMimeType } : {}),
        },
      })
      return {
        ok: true as const,
        text: ai.text,
        telemetry: {
          keyUsed: ai.meta.keyFingerprint,
          attemptCount: ai.meta.attemptCount,
          fallbackReason: ai.meta.fallbackReason,
          queueWaitMs: ai.meta.queueWaitMs,
          queued: ai.meta.queued,
          keyRoleUsed: ai.meta.keyRoleUsed,
          fallbackMode: ai.meta.fallbackMode,
        },
      }
    } catch (error) {
      return { ok: false as const, reason: error instanceof Error ? error.message : String(error) }
    }
  }

  async gmailReadiness(): Promise<ProviderProbe & { sender: string | null; dailyCap: number; sentToday?: number; remainingToday?: number }> {
    const primary = await this.googleStack.getProfileConfig('primary')
    const backup = await this.googleStack.getProfileConfig('backup')
    const configured = Boolean(
      (primary.senderEmail && primary.clientId && primary.clientSecret && primary.refreshToken) ||
      (backup.senderEmail && backup.clientId && backup.clientSecret && backup.refreshToken),
    )
    if (!configured) {
      return {
        configured,
        ok: false,
        status: 'missing_config',
        sender: env.GMAIL_SENDER_EMAIL ?? env.GMAIL_SENDER_EMAIL_BACKUP ?? null,
        dailyCap: env.GMAIL_DAILY_SEND_CAP_PER_ACCOUNT,
        message: 'Missing one or more Gmail OAuth settings or a persisted refresh token.',
      }
    }

    try {
      const token = await this.getGoogleAccessToken()
      const sentToday = token ? await this.countSentToday(token) : 0
      return {
        configured,
        ok: Boolean(token),
        status: token ? 'ready' : 'error',
        sender: env.GMAIL_SENDER_EMAIL ?? env.GMAIL_SENDER_EMAIL_BACKUP ?? null,
        dailyCap: env.GMAIL_DAILY_SEND_CAP_PER_ACCOUNT,
        sentToday,
        remainingToday: Math.max(0, env.GMAIL_DAILY_SEND_CAP_PER_ACCOUNT - sentToday),
        message: token ? 'Gmail OAuth refresh succeeded.' : 'Gmail OAuth refresh returned no access token.',
      }
    } catch (error) {
      return {
        configured,
        ok: false,
        status: 'error',
        sender: env.GMAIL_SENDER_EMAIL ?? env.GMAIL_SENDER_EMAIL_BACKUP ?? null,
        dailyCap: env.GMAIL_DAILY_SEND_CAP_PER_ACCOUNT,
        message: error instanceof Error ? error.message : String(error),
      }
    }
  }

  async geminiReadiness(): Promise<ProviderProbe & { model: string; keysConfigured: number }> {
    // Intentionally no live API call here — Gemini has per-minute quota limits and a probe
    // call would burn quota every time /api/readiness is hit. Key presence is enough to gate
    // the system; actual Gemini errors surface through real request failures.
    const keys = this.geminiKeyRing('noah')
    const configured = keys.length > 0
    return {
      configured,
      ok: configured,
      status: configured ? 'ready' : 'missing_config',
      model: env.GEMINI_MODEL,
      keysConfigured: [
        env.GEMINI_API_KEY,
        env.GEMINI_API_KEY_JARVIS,
        env.GEMINI_API_KEY_DAMIEN,
        env.GEMINI_API_KEY_NOAH,
        env.GEMINI_API_KEY_ZOYA,
        env.GEMINI_API_KEY_DEVAN,
        env.GEMINI_API_KEY_AKHIL,
        env.GEMINI_API_KEY_KING,
      ].filter(Boolean).length,
      message: configured
        ? `Gemini keys configured. Model: ${env.GEMINI_MODEL}.`
        : 'No Gemini API keys found. Add GEMINI_API_KEY or per-agent keys.',
    }
  }

  async apifyReadiness(): Promise<ProviderProbe & { actorId: string | null }> {
    const configured = Boolean(env.APIFY_API_TOKEN && env.APIFY_ACTOR_ID)
    if (!configured) {
      return {
        configured,
        ok: false,
        status: 'missing_config',
        actorId: env.APIFY_ACTOR_ID ?? null,
        message: 'APIFY_API_TOKEN or APIFY_ACTOR_ID is not configured.',
      }
    }

    try {
      const response = await outboundFetch(`https://api.apify.com/v2/acts/${env.APIFY_ACTOR_ID}?token=${env.APIFY_API_TOKEN}`)
      return {
        configured,
        ok: response.ok,
        status: response.ok ? 'ready' : 'error',
        actorId: env.APIFY_ACTOR_ID ?? null,
        message: response.ok ? 'Apify actor is reachable.' : `Apify actor check failed: ${response.status}`,
      }
    } catch (error) {
      return {
        configured,
        ok: false,
        status: 'error',
        actorId: env.APIFY_ACTOR_ID ?? null,
        message: error instanceof Error ? error.message : String(error),
      }
    }
  }

  private async getGoogleAccessToken() {
    const resolved = await this.googleStack.resolveActiveProfile()
    if (!resolved.token.ok) return null
    return resolved.token.accessToken ?? null
  }

  private async countSentToday(accessToken: string) {
    const sender = env.GMAIL_SENDER_EMAIL ?? env.GMAIL_SENDER_EMAIL_BACKUP ?? ''
    const start = new Date()
    start.setHours(0, 0, 0, 0)
    const after = `${start.getFullYear()}/${String(start.getMonth() + 1).padStart(2, '0')}/${String(start.getDate()).padStart(2, '0')}`
    const query = encodeURIComponent(`in:sent from:${sender} after:${after}`)
    const response = await outboundFetch(`https://gmail.googleapis.com/gmail/v1/users/me/messages?q=${query}&maxResults=1`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    if (!response.ok) return 0
    const json = (await response.json()) as { resultSizeEstimate?: number }
    return json.resultSizeEstimate ?? 0
  }

  async sendPrecheckGate(payload: { to: string; leadState?: string }) {
    const gmail = await this.gmailReadiness()
    if (!gmail.ok) {
      return {
        ok: false,
        reason: `gmail_unavailable:${gmail.status}`,
      }
    }

    if (payload.leadState && ['unsubscribe', 'do_not_contact', 'converted'].includes(payload.leadState)) {
      return {
        ok: false,
        reason: `lead_state_blocked:${payload.leadState}`,
      }
    }

    return { ok: true, reason: 'ready' }
  }

  async sendEmailDraft(payload: { to: string; subject: string; body: string }) {
    const sender = env.GMAIL_SENDER_EMAIL ?? env.GMAIL_SENDER_EMAIL_BACKUP ?? null
    if (!env.GMAIL_SENDER_EMAIL && !env.GMAIL_SENDER_EMAIL_BACKUP) {
      return { mode: 'offline', sent: false, reason: 'GMAIL_SENDER_EMAIL is not configured.', draft: payload }
    }
    const accessToken = await this.getGoogleAccessToken()
    if (!accessToken) {
      return {
        mode: 'offline',
        sent: false,
        reason: 'Gmail OAuth credentials are not configured yet.',
        draft: payload,
      }
    }

    const sentToday = await this.countSentToday(accessToken)
    if (sentToday >= env.GMAIL_DAILY_SEND_CAP_PER_ACCOUNT) {
      return {
        mode: 'ready',
        sent: false,
        reason: `gmail_daily_cap_reached:${sentToday}/${env.GMAIL_DAILY_SEND_CAP_PER_ACCOUNT}`,
        draft: payload,
      }
    }

    const mime = [
      `From: ${sender}`,
      `To: ${payload.to}`,
      `Subject: ${payload.subject}`,
      'Content-Type: text/plain; charset="UTF-8"',
      '',
      payload.body,
    ].join('\r\n')

    const response = await outboundFetch('https://gmail.googleapis.com/gmail/v1/users/me/messages/send', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ raw: toBase64Url(mime) }),
    })
    if (!response.ok) {
      const text = await response.text()
      return { mode: 'ready', sent: false, reason: `gmail_send_failed:${text}`, draft: payload }
    }

    const sent = (await response.json()) as { id?: string; threadId?: string }
    writeAudit({
      actor: 'outreach',
      action: 'gmail_send',
      purpose: 'outbound_email',
      result: 'ok',
      metadata: { to: payload.to, subject: payload.subject.slice(0, 80), sentToday },
    })
    return {
      mode: 'live',
      sent: true,
      reason: 'Message sent through Gmail API.',
      gmailMessageId: sent.id ?? null,
      gmailThreadId: sent.threadId ?? null,
      draft: payload,
    }
  }

  async apolloSearch(segment: string, limit = 10) {
    if (!env.APOLLO_API_KEY) {
      return { provider: 'apollo', mode: 'offline', message: 'APOLLO_API_KEY is not configured.', results: [] }
    }

    // Map segments to Apollo person-title and industry filters
    const segmentMap: Record<string, { titles: string[]; keywords: string[] }> = {
      hvac: {
        titles: ['Owner', 'Founder', 'President', 'General Manager', 'Operations Manager'],
        keywords: ['HVAC', 'Heating Cooling', 'Air Conditioning', 'Plumbing HVAC'],
      },
      realestate: {
        titles: ['Real Estate Agent', 'Realtor', 'Broker', 'Real Estate Broker', 'Property Consultant'],
        keywords: ['Real Estate', 'Realty'],
      },
      agency: {
        titles: ['Founder', 'CEO', 'Managing Director', 'Director of Marketing', 'Head of Growth'],
        keywords: ['Digital Marketing', 'Marketing Agency', 'SEO Agency', 'Paid Ads', 'PPC Agency'],
      },
      interior: {
        titles: ['Interior Designer', 'Principal Designer', 'Design Director', 'Founder', 'Owner'],
        keywords: ['Interior Design', 'Interior Decorating', 'Home Staging'],
      },
      clinic: {
        titles: ['Practice Owner', 'Clinic Director', 'Office Manager', 'Medical Director', 'Principal'],
        keywords: ['Medical Practice', 'Dental Clinic', 'Health Clinic', 'GP Practice'],
      },
      medspa: {
        titles: ['Owner', 'Founder', 'Medical Director', 'Clinic Manager', 'Aesthetic Director'],
        keywords: ['Med Spa', 'Medical Spa', 'Aesthetic Clinic', 'Aesthetics', 'Medspa'],
      },
      coach: {
        titles: ['Coach', 'Life Coach', 'Business Coach', 'Executive Coach', 'Sales Coach', 'Mindset Coach', 'Health Coach', 'Founder'],
        keywords: ['Business Coaching', 'Life Coaching', 'Executive Coaching', 'Online Coach', 'Coaching Programs'],
      },
      consultant: {
        titles: ['Consultant', 'Principal Consultant', 'Managing Consultant', 'Strategy Consultant', 'Business Advisor', 'Fractional CMO', 'Fractional CFO'],
        keywords: ['Management Consulting', 'Business Consulting', 'Strategy Consulting', 'Advisory', 'Fractional Executive'],
      },
      'online coaches': {
        titles: ['Coach', 'Life Coach', 'Business Coach', 'Online Coach', 'Founder'],
        keywords: ['Business Coaching', 'Life Coaching', 'Online Coach', 'Coaching Programs'],
      },
      consultants: {
        titles: ['Consultant', 'Principal Consultant', 'Business Advisor', 'Fractional CMO'],
        keywords: ['Management Consulting', 'Business Consulting', 'Advisory'],
      },
      all: {
        titles: ['Owner', 'Founder', 'CEO', 'Managing Director', 'Principal'],
        keywords: ['HVAC', 'Real Estate', 'Digital Marketing Agency', 'Interior Design', 'Medical Spa', 'Dental Clinic'],
      },
    }

    const filters = segmentMap[segment] ?? segmentMap.all

    try {
      const res = await outboundFetch('https://api.apollo.io/api/v1/mixed_people/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache',
          'X-Api-Key': env.APOLLO_API_KEY,
        },
        body: JSON.stringify({
          per_page: Math.min(limit, 25),
          page: 1,
          person_titles: filters.titles,
          q_keywords: filters.keywords.join(' OR '),
          contact_email_status: ['verified', 'guessed'],
          prospected_by_current_team: ['no'],
        }),
      })

      if (!res.ok) {
        const text = await res.text()
        return { provider: 'apollo', mode: 'error', message: `Apollo API error: ${res.status} ${text}`, results: [] }
      }

      const json = await res.json() as {
        people?: Array<{
          first_name?: string
          last_name?: string
          name?: string
          email?: string
          title?: string
          organization?: { name?: string; website_url?: string; industry?: string; primary_phone?: { number?: string } }
          city?: string
          state?: string
          country?: string
        }>
        total_entries?: number
      }

      const people = json.people ?? []
      const results = people.map((p) => {
        const company = p.organization?.name ?? 'Unknown Company'
        const industry = normalizeIndustry(p.organization?.industry ?? segment)
        const city = [p.city, p.state, p.country].filter(Boolean).join(', ')
        return {
          fullName: (p.name ?? `${p.first_name ?? ''} ${p.last_name ?? ''}`.trim()) || 'Unknown',
          email: p.email ?? '',
          role: p.title ?? '',
          companyName: company,
          website: p.organization?.website_url ?? '',
          industry,
          city,
          painPoint: defaultPain(industry, p.organization?.website_url),
          source: 'apollo' as const,
          enrichmentSummary: `${p.title ?? 'Contact'} at ${company} — ${industry} sector.`,
          recentSignal: 'Sourced via Apollo.io people search.',
          recommendedAngle: recommendedAngle(industry, p.organization?.website_url),
        }
      }).filter((r) => r.email && !r.email.includes('example.com'))

      writeAudit({
        actor: 'outreach',
        action: 'apollo_search',
        purpose: `segment:${segment}`,
        result: 'ok',
        metadata: { found: results.length, totalEntries: json.total_entries ?? 0 },
      })

      return {
        provider: 'apollo',
        mode: 'live',
        segment,
        total: json.total_entries ?? people.length,
        results,
      }
    } catch (err) {
      return {
        provider: 'apollo',
        mode: 'error',
        message: `Apollo fetch failed: ${String(err)}`,
        results: [],
      }
    }
  }

  private normalizeApifyItem(item: Record<string, unknown>): EnrichedLead {
    const companyName = String(item.companyName ?? item.company ?? item.organization ?? 'Unknown Company')
    const fullName = String(item.fullName ?? item.name ?? 'Unknown Contact')
    const email = String(item.email ?? item.workEmail ?? 'unknown@example.com')
    const industry = normalizeIndustry(String(item.industry ?? item.categoryName ?? 'B2B Services'))
    const website = String(item.website ?? item.url ?? '')
    const city = String(item.city ?? item.location ?? '')
    const role = String(item.role ?? item.title ?? '')
    const summary = String(item.summary ?? item.description ?? `Lead captured for ${companyName}.`)
    const signal = String(item.recentSignal ?? item.latestUpdate ?? 'Source did not provide a recent buying signal.')
    const angle = String(item.recommendedAngle ?? recommendedAngle(industry, website))

    return {
      fullName,
      email,
      role,
      companyName,
      website,
      industry,
      city,
      painPoint: defaultPain(industry, website),
      source: 'apify',
      enrichmentSummary: summary,
      recentSignal: signal,
      recommendedAngle: angle,
    }
  }

  async runApifyEnrichment(leads: EnrichmentLeadInput[]) {
    if (!env.APIFY_API_TOKEN || !env.APIFY_ACTOR_ID) {
      const fallback = leads.map((lead) => {
        const industry = normalizeIndustry(lead.industry)
        return {
          ...lead,
          industry,
          painPoint: lead.painPoint ?? defaultPain(industry, lead.website),
          source: 'fallback' as const,
          enrichmentSummary: `${lead.companyName} is a fit for ${offerFrame(industry, lead.website)} if they need more qualified enquiries converting into booked conversations.`,
          recentSignal: recentSignalFallback(industry, lead.website),
          recommendedAngle: recommendedAngle(industry, lead.website),
        }
      })
      return {
        provider: 'apify',
        mode: 'offline',
        message: 'APIFY_API_TOKEN or APIFY_ACTOR_ID is not configured.',
        leads: fallback,
      }
    }

    const response = await outboundFetch(
      `https://api.apify.com/v2/acts/${env.APIFY_ACTOR_ID}/run-sync-get-dataset-items?token=${env.APIFY_API_TOKEN}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ leads }),
      },
    )
    if (!response.ok) {
      const text = await response.text()
      writeAudit({ actor: 'outreach', action: 'apify_enrichment', purpose: 'lead_enrichment', result: 'error', detail: text })
      return {
        provider: 'apify',
        mode: 'error',
        message: `Apify actor call failed: ${text}`,
        leads: [],
      }
    }

    const items = (await response.json()) as Record<string, unknown>[]
    writeAudit({
      actor: 'outreach',
      action: 'apify_enrichment',
      purpose: 'lead_enrichment',
      result: 'ok',
      metadata: { records: items.length },
    })
    return {
      provider: 'apify',
      mode: 'live',
      message: `Apify returned ${items.length} enriched records.`,
      leads: items.map((item) => this.normalizeApifyItem(item)),
    }
  }

  async runKnownApifyActor(input: { actorInput: Record<string, unknown>; limit: number }) {
    if (!env.APIFY_API_TOKEN || !env.APIFY_ACTOR_ID) {
      return {
        provider: 'apify',
        mode: 'offline',
        message: 'APIFY_API_TOKEN or APIFY_ACTOR_ID is not configured.',
        leads: [] as EnrichedLead[],
      }
    }

    const response = await outboundFetch(
      `https://api.apify.com/v2/acts/${env.APIFY_ACTOR_ID}/run-sync-get-dataset-items?token=${env.APIFY_API_TOKEN}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input.actorInput),
      },
    )
    if (!response.ok) {
      const detail = `${response.status} ${await response.text()}`
      writeAudit({ actor: 'outreach', action: 'apify_discovery', purpose: 'lead_discovery', result: 'error', detail })
      return {
        provider: 'apify',
        mode: 'error',
        message: `Apify actor call failed: ${detail}`,
        leads: [] as EnrichedLead[],
      }
    }

    const items = (await response.json()) as Record<string, unknown>[]
    writeAudit({
      actor: 'outreach',
      action: 'apify_discovery',
      purpose: 'lead_discovery',
      result: 'ok',
      metadata: { records: items.length },
    })
    return {
      provider: 'apify',
      mode: 'live',
      message: `Apify returned ${items.length} raw records.`,
      leads: items.slice(0, input.limit).map((item) => this.normalizeApifyItem(item)),
    }
  }

  async generateAiDraftFromEnrichment(lead: EnrichedLead) {
    if (!geminiApiKeyFor('noah')) {
      const draft = this.personalizeColdEmail({
        fullName: lead.fullName,
        companyName: lead.companyName,
        industry: lead.industry ?? 'B2B Services',
        website: lead.website,
        city: lead.city,
        painPoint: lead.painPoint,
      })
      return { mode: 'fallback', telemetry: null, ...draft }
    }

    const prompt = [
      `You are Noah, CMO system for ${companyName}.`,
      `Offer: ${primaryOffer}. Help ${targetIndustries.join(', ')} get more qualified leads per month.`,
      'Write one cold email that sounds human, specific, and low-friction.',
      'Constraints: 75-115 words, plain text, one CTA, no hype, no AI buzzwords, no generic opener.',
      `Contact: ${lead.fullName} (${lead.role ?? 'unknown role'})`,
      `Company: ${lead.companyName}`,
      `Industry: ${lead.industry ?? 'B2B Services'}`,
      `Website: ${lead.website ?? 'unknown'}`,
      `City: ${lead.city ?? 'unknown'}`,
      `Pain Point: ${lead.painPoint ?? defaultPain(lead.industry, lead.website)}`,
      `Enrichment Summary: ${lead.enrichmentSummary}`,
      `Recent Signal: ${lead.recentSignal}`,
      `Recommended Angle: ${lead.recommendedAngle}`,
      `Offer Frame: ${offerFrame(lead.industry, lead.website)}`,
      !hasUsableWebsite(lead.website)
        ? 'If the website is absent or weak, anchor the draft around a website-plus-booking system rather than only lead nurture.'
        : 'Assume the website exists and anchor the draft around faster follow-up, qualification, and booking.',
      'Return strict JSON with keys: subject, body',
    ].join('\n')

    const ai = await this.geminiGenerate({
      primaryRole: 'noah',
      prompt,
      temperature: 0.55,
      maxOutputTokens: 650,
      responseMimeType: 'application/json',
    })

    if (!ai.ok) {
      const draft = this.personalizeColdEmail({
        fullName: lead.fullName,
        companyName: lead.companyName,
        industry: lead.industry ?? 'B2B Services',
        website: lead.website,
        city: lead.city,
        painPoint: lead.painPoint,
      })
      return { mode: 'fallback', reason: ai.reason, telemetry: null, ...draft }
    }

    try {
      const parsed = JSON.parse(ai.text) as { subject: string; body: string }
      return { mode: 'ai', subject: parsed.subject, body: parsed.body, telemetry: ai.telemetry }
    } catch {
      const draft = this.personalizeColdEmail({
        fullName: lead.fullName,
        companyName: lead.companyName,
        industry: lead.industry ?? 'B2B Services',
        website: lead.website,
        city: lead.city,
        painPoint: lead.painPoint,
      })
      return { mode: 'fallback', reason: 'gemini_invalid_json', telemetry: ai.telemetry, ...draft }
    }
  }

  async enrichAndDraft(leads: EnrichmentLeadInput[]) {
    const enrichment = await this.runApifyEnrichment(leads)
    const enriched = enrichment.leads as EnrichedLead[]
    const drafted = await Promise.all(
      enriched.map(async (lead) => ({
        lead,
        draft: await this.generateAiDraftFromEnrichment(lead),
      })),
    )

    return {
      provider: enrichment.provider,
      mode: enrichment.mode,
      enrichmentMessage: enrichment.message,
      total: drafted.length,
      items: drafted,
    }
  }

  async discoverAndDraft(input: { actorInput: Record<string, unknown>; limit: number }) {
    const discovery = await this.runKnownApifyActor(input)
    const drafted = await Promise.all(
      discovery.leads.map(async (lead) => ({
        lead,
        draft: await this.generateAiDraftFromEnrichment(lead),
      })),
    )

    return {
      provider: discovery.provider,
      mode: discovery.mode,
      enrichmentMessage: discovery.message,
      total: drafted.length,
      items: drafted,
    }
  }

  // ── Typo Hook ──────────────────────────────────────────────────────────────
  // Deliberate single misspelling in the subject line — makes the email look
  // like it was typed by a real human in a hurry, not blasted by a tool.
  injectTypoHook(subject: string): string {
    const typos: [RegExp, string][] = [
      [/\bquick\b/i, 'quik'],
      [/\bquestion\b/i, 'questoin'],
      [/\bfollow[ -]?up\b/i, 'folowup'],
      [/\bstrategy\b/i, 'stragtegy'],
      [/\binteresting\b/i, 'intresting'],
      [/\bthought\b/i, 'thot'],
      [/\bregarding\b/i, 're:'],
      [/\bimportant\b/i, 'importnt'],
      [/\bclient\b/i, 'cleint'],
      [/\bsystem\b/i, 'sytem'],
      [/\boutreach\b/i, 'outreachh'],
      [/\bmeeting\b/i, 'meetng'],
      [/\bsales\b/i, 'saless'],
      [/\bgrowth\b/i, 'growht'],
    ]

    for (const [pattern, replacement] of typos) {
      if (pattern.test(subject)) {
        return subject.replace(pattern, replacement)
      }
    }

    // No match — append a fat-finger double space before a word
    const words = subject.split(' ')
    if (words.length >= 3) {
      const idx = Math.floor(words.length / 2)
      words[idx] = words[idx] ? `${words[idx]![0]}${words[idx]}` : 'quick'
      return words.join(' ')
    }

    return subject + ' ?'
  }

  // ── Gemini-powered smart enrichment ────────────────────────────────────────
  async enrichLeadWithGemini(lead: EnrichmentLeadInput): Promise<EnrichedLead & { funFact: string; openingJoke: string }> {
    const fallback = {
      ...lead,
      industry: normalizeIndustry(lead.industry),
      source: 'fallback' as const,
      enrichmentSummary: `${lead.companyName} operates in ${normalizeIndustry(lead.industry)} and likely faces typical challenges around ${defaultPain(lead.industry, lead.website)}.`,
      recentSignal: recentSignalFallback(lead.industry, lead.website),
      recommendedAngle: recommendedAngle(lead.industry, lead.website),
      painPoint: lead.painPoint ?? defaultPain(lead.industry, lead.website),
      funFact: !hasUsableWebsite(lead.website)
        ? 'Businesses without a credible website often lose high-intent buyers before the first conversation even starts.'
        : `${normalizeIndustry(lead.industry)} companies typically lose 30–40% of inbound leads to slow follow-up — that is usually the angle.`,
      openingJoke: `I promise this isn't another templated cold email. (It is. But the template is really good.)`,
    }

    if (!geminiApiKeyFor('devan')) return fallback

    const prompt = `You are a sharp B2B sales researcher. Enrich this lead with specific intelligence.

Lead:
- Name: ${lead.fullName}
- Company: ${lead.companyName}
- Industry: ${lead.industry ?? 'Unknown'}
- City: ${lead.city ?? 'Unknown'}
- Role: ${lead.role ?? 'Unknown'}
- Website: ${lead.website ?? 'Unknown'}

Return strict JSON (no markdown):
{
  "enrichmentSummary": "2-3 sentence specific description of what this company actually does and their market position",
  "recentSignal": "One specific buying signal or business moment this type of company is likely experiencing RIGHT NOW in ${new Date().getFullYear()}",
  "recommendedAngle": "The single most compelling conversation angle for THIS specific company — specific to their industry and city",
  "painPoint": "The specific operational pain that a lead generation AI system would solve for them — be specific to their industry",
  "funFact": "One genuinely interesting industry-specific statistic or insight relevant to their business — something they'd find surprising",
  "openingJoke": "A short, dry, self-aware one-liner about cold emailing someone in the ${lead.industry ?? 'B2B'} space — funny but not cheesy, max 15 words"
}

Be specific. No generic answers. Make the enrichment feel like you actually researched this company.`

    try {
      const ai = await this.geminiGenerate({
        primaryRole: 'devan',
        prompt,
        temperature: 0.7,
        maxOutputTokens: 800,
        responseMimeType: 'application/json',
      })
      if (!ai.ok) return fallback
      const raw = ai.text.trim().startsWith('```') ? ai.text.split('```')[1]?.replace(/^json\n?/, '').trim() ?? ai.text : ai.text
      const parsed = JSON.parse(raw) as {
        enrichmentSummary?: string
        recentSignal?: string
        recommendedAngle?: string
        painPoint?: string
        funFact?: string
        openingJoke?: string
      }

      return {
        ...lead,
        industry: normalizeIndustry(lead.industry),
        source: 'fallback' as const,
        enrichmentSummary: parsed.enrichmentSummary ?? fallback.enrichmentSummary,
        recentSignal: parsed.recentSignal ?? fallback.recentSignal,
        recommendedAngle: parsed.recommendedAngle ?? fallback.recommendedAngle,
        painPoint: parsed.painPoint ?? fallback.painPoint,
        funFact: parsed.funFact ?? fallback.funFact,
        openingJoke: parsed.openingJoke ?? fallback.openingJoke,
      }
    } catch {
      return fallback
    }
  }

  // ── Funny + personal email with typo subject hook ─────────────────────────
  async generateSmartFunnyDraft(
    lead: EnrichedLead & { funFact?: string; openingJoke?: string },
    options: { typoHook?: boolean } = {},
  ) {
    const { typoHook = true } = options
    const industry = normalizeIndustry(lead.industry)
    const pain = lead.painPoint ?? defaultPain(industry, lead.website)
    const angle = lead.recommendedAngle ?? recommendedAngle(industry, lead.website)
    const offer = offerFrame(industry, lead.website)
    const funFact = lead.funFact ?? `${industry} companies lose 30–40% of leads to slow follow-up.`
    const joke = lead.openingJoke ?? `I know. Another cold email. Bear with me — this one has a point.`

    if (geminiApiKeyFor('noah')) {
      const prompt = `Write a short, punchy cold email for a B2B sales outreach.
It must feel like it was written by a real person — not a template tool.
Include exactly ONE dry, self-aware joke early in the email.
The joke should acknowledge that this is a cold email without apologising for it.

Lead details:
- Name: ${lead.fullName} (use first name only)
- Company: ${lead.companyName}
- Industry: ${industry}
- Website: ${lead.website ?? 'unknown'}
- City: ${lead.city ?? 'their city'}
- Pain: ${pain}
- Conversation angle: ${angle}
- Offer frame: ${offer}
- Fun fact to open with or reference: ${funFact}
- Suggested opening joke: "${joke}"

Rules:
- 80–120 words MAX. If it goes over, cut it.
- Plain text only. No bullet points, no headers.
- One clear CTA: propose a 15-minute call.
- Signed from "Jace" at "Virell Labs"
- The email must feel personal — reference the company or industry specifically.
- Do not use the word "synergy", "leverage", "game-changer", or "circle back".
- The joke should land in the FIRST 2 sentences.

Also generate a subject line (6 words max, conversational, NOT promotional).

Return strict JSON: { "subject": "...", "body": "..." }`

      try {
        const ai = await this.geminiGenerate({
          primaryRole: 'noah',
          prompt,
          temperature: 0.85,
          maxOutputTokens: 600,
          responseMimeType: 'application/json',
        })
        if (ai.ok) {
          const raw = ai.text.trim().startsWith('```') ? ai.text.split('```')[1]?.replace(/^json\n?/, '').trim() ?? ai.text : ai.text
          const parsed = JSON.parse(raw) as { subject?: string; body?: string }
          const subject = parsed.subject ?? `${lead.companyName} — quick one`
          return {
            mode: 'ai',
            subject: typoHook ? this.injectTypoHook(subject) : subject,
            body: parsed.body ?? '',
            enrichmentUsed: true,
            telemetry: ai.telemetry,
          }
        }
      } catch {
        // fall through to deterministic version
      }
    }

    // Deterministic fallback — still funny, still personal
    const firstName = lead.fullName.split(' ')[0] ?? lead.fullName
    const cityNote = lead.city ? ` in ${lead.city}` : ''
    const rawSubject = `${lead.companyName} — quick questoin`
    const subject = typoHook ? this.injectTypoHook(rawSubject) : `${lead.companyName} — quick question`

    const body = [
      `${firstName},`,
      '',
      joke,
      '',
      `I looked at ${lead.companyName}${cityNote}. The gap I keep seeing in ${industry} is ${pain}.`,
      `${funFact}`,
      '',
      `${angle} — that's why we build ${offer} at Virell Labs. Not a SaaS tool you set up and forget. A system that actually runs.`,
      '',
      '15 minutes to show you what it looks like for a business your size?',
      '',
      'Jace',
      'Virell Labs',
    ].join('\n')

    return { mode: 'fallback', subject, body, enrichmentUsed: false, telemetry: null }
  }

  // ── Main smart pipeline: enrich with Gemini → funny email → typo hook ─────
  async enrichSmartAndDraft(leads: EnrichmentLeadInput[], options: { typoHook?: boolean } = {}) {
    const enriched = await Promise.all(leads.map((lead) => this.enrichLeadWithGemini(lead)))
    const drafted = await Promise.all(
      enriched.map(async (lead) => ({
        lead,
        draft: await this.generateSmartFunnyDraft(lead, options),
      })),
    )

    return {
      mode: geminiApiKeyFor('noah') ? 'ai' : 'fallback',
      typoHookActive: options.typoHook ?? true,
      total: drafted.length,
      items: drafted,
    }
  }
}
