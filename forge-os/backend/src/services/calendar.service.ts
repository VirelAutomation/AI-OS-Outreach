import { env } from '../config/env.js'
import { callGeminiSimple } from '../lib/gemini.js'
import { outboundFetch } from '../lib/network.js'
import { getSupabaseAdmin } from '../lib/supabaseAdmin.js'
import type { CalendarEvent } from './jarvis.service.js'
import { GoogleStackService } from './googleStack.service.js'

type GoogleCalendarEvent = {
  id: string
  summary?: string
  description?: string
  status?: string
  start?: { dateTime?: string; date?: string }
  end?: { dateTime?: string; date?: string }
  attendees?: Array<{ email?: string; displayName?: string; responseStatus?: string }>
  htmlLink?: string
}

type CalendarListResponse = {
  items?: GoogleCalendarEvent[]
  nextPageToken?: string
  error?: { message?: string }
}

type JarvisCalendarAnalysis = {
  events: CalendarEvent[]
  priorities: Array<{ event: CalendarEvent; reason: string; businessRelevance: 'high' | 'medium' | 'low' }>
  todaySummary: string
  suggestedFocus: string
  timeBlocks: Array<{ label: string; time: string; action: string }>
}

const googleStack = new GoogleStackService()

async function getAccessToken(): Promise<string | null> {
  const resolved = await googleStack.resolveActiveProfile()
  return resolved.token.ok ? (resolved.token.accessToken ?? null) : null
}

function normalizeEvent(raw: GoogleCalendarEvent): CalendarEvent {
  return {
    id: raw.id,
    summary: raw.summary ?? '(No title)',
    description: raw.description,
    start: raw.start?.dateTime ?? raw.start?.date ?? '',
    end: raw.end?.dateTime ?? raw.end?.date ?? '',
    status: raw.status,
  }
}

function stripJsonFence(text: string) {
  const t = text.trim()
  if (!t.includes('```')) return t
  const fenced = t.split('```')[1] ?? t
  return fenced.startsWith('json') ? fenced.slice(4).trim() : fenced.trim()
}

export class CalendarService {
  async listEvents(options: { days?: number; calendarId?: string } = {}): Promise<{ ok: boolean; events: CalendarEvent[]; mode: string; error?: string }> {
    const primary = await googleStack.getProfileConfig('primary')
    const backup = await googleStack.getProfileConfig('backup')
    const configured = Boolean(
      (primary.clientId && primary.clientSecret && primary.refreshToken) ||
      (backup.clientId && backup.clientSecret && backup.refreshToken),
    )
    if (!configured) {
      return {
        ok: false,
        mode: 'offline',
        events: this.mockEvents(),
        error: 'Google OAuth credentials not configured. Visit /api/google/oauth/start to set up.',
      }
    }

    const accessToken = await getAccessToken()
    if (!accessToken) {
      return { ok: false, mode: 'offline', events: this.mockEvents(), error: 'Failed to refresh Google access token.' }
    }

    const now = new Date()
    const timeMin = now.toISOString()
    const timeMax = new Date(now.getTime() + (options.days ?? 7) * 24 * 60 * 60 * 1000).toISOString()
    const calendarId = options.calendarId ?? 'primary'

    const params = new URLSearchParams({
      timeMin,
      timeMax,
      singleEvents: 'true',
      orderBy: 'startTime',
      maxResults: '50',
    })

    const response = await outboundFetch(
      `https://www.googleapis.com/calendar/v3/calendars/${encodeURIComponent(calendarId)}/events?${params.toString()}`,
      { headers: { Authorization: `Bearer ${accessToken}` } },
    )

    if (!response.ok) {
      const errText = await response.text()
      const isCalendarScopeError = errText.includes('insufficient authentication scopes') || response.status === 403
      return {
        ok: false,
        mode: 'offline',
        events: this.mockEvents(),
        error: isCalendarScopeError
          ? 'Calendar scope not granted. Re-run OAuth at /api/google/oauth/start — the scope now includes Calendar.'
          : `Calendar API error: ${response.status}`,
      }
    }

    const json = (await response.json()) as CalendarListResponse
    const events = (json.items ?? []).map(normalizeEvent)

    // Cache to Supabase if configured
    const supabase = getSupabaseAdmin()
    if (supabase && events.length > 0) {
      try {
        await supabase.from('calendar_events_cache').upsert(
          events.map((e) => ({
            id: e.id,
            summary: e.summary,
            description: e.description ?? null,
            start_time: e.start,
            end_time: e.end,
            status: e.status ?? 'confirmed',
            synced_at: new Date().toISOString(),
          })),
          { onConflict: 'id' },
        )
      } catch { /* table may not exist yet */ }
    }

    return { ok: true, mode: 'live', events }
  }

  async analyzeWithJarvis(events: CalendarEvent[]): Promise<JarvisCalendarAnalysis> {
    const fallback: JarvisCalendarAnalysis = {
      events,
      priorities: events.slice(0, 3).map((e) => ({
        event: e,
        reason: 'Scheduled event — confirm preparation is complete.',
        businessRelevance: 'medium',
      })),
      todaySummary: `You have ${events.length} events. Focus on the meetings first, admin second.`,
      suggestedFocus: 'Run your morning outreach review before any meetings. Protect your deep work block.',
      timeBlocks: [
        { label: 'Morning', time: '7:00–9:00 AM', action: 'Morning review: check overnight replies, approve outreach batch' },
        { label: 'Deep Work', time: '9:00 AM–1:00 PM', action: 'Priority work — highest-leverage business task' },
        { label: 'Meetings', time: '1:00–5:00 PM', action: 'All calls and meetings — batch them here' },
        { label: 'Evening', time: '6:00–8:00 PM', action: 'Review day metrics, update pipeline, plan tomorrow' },
      ],
    }

    if (!env.GEMINI_API_KEY && !env.GEMINI_API_KEY_DAMIEN) return fallback

    const prompt = `You are JARVIS analyzing Jace's calendar for today and this week.

OPERATOR: Jace, 19yo founder, Virell Labs. Mission: AI ops for B2B companies. Target: $15M MRR in 7 months. MRR now: $0.

CALENDAR EVENTS:
${events.map((e) => `- ${e.start.slice(0, 16).replace('T', ' ')} | ${e.summary}${e.description ? ` — ${e.description.slice(0, 100)}` : ''}`).join('\n') || 'No events found.'}

Analyze each event from a business-building perspective. What matters most for the 7-month path? What can be cut or delegated? What needs prep?

Return strict JSON:
{
  "priorities": [
    { "eventId": "id", "reason": "why this is high priority", "businessRelevance": "high|medium|low" }
  ],
  "todaySummary": "1-2 sentence honest summary of today's agenda",
  "suggestedFocus": "the single most important thing to accomplish today outside of these events",
  "timeBlocks": [
    { "label": "Morning", "time": "7:00–9:00 AM", "action": "specific action for this block" },
    { "label": "Deep Work", "time": "9:00 AM–1:00 PM", "action": "specific action" },
    { "label": "Meetings", "time": "1:00–5:00 PM", "action": "specific action" },
    { "label": "Evening", "time": "6:00–8:00 PM", "action": "specific action" }
  ]
}`

    try {
      const text = await callGeminiSimple('damien', prompt, { temperature: 0.6, maxOutputTokens: 1200, jsonMode: true })
      if (!text) return fallback

      const parsed = JSON.parse(stripJsonFence(text)) as {
        priorities?: Array<{ eventId: string; reason: string; businessRelevance: string }>
        todaySummary?: string; suggestedFocus?: string
        timeBlocks?: Array<{ label: string; time: string; action: string }>
      }

      const priorities = (parsed.priorities ?? []).map((p) => ({
        event: events.find((e) => e.id === p.eventId) ?? events[0] ?? { id: '', summary: '', start: '', end: '' },
        reason: p.reason,
        businessRelevance: (p.businessRelevance ?? 'medium') as 'high' | 'medium' | 'low',
      })).filter((p) => p.event.id)

      return {
        events,
        priorities: priorities.length ? priorities : fallback.priorities,
        todaySummary: parsed.todaySummary ?? fallback.todaySummary,
        suggestedFocus: parsed.suggestedFocus ?? fallback.suggestedFocus,
        timeBlocks: parsed.timeBlocks ?? fallback.timeBlocks,
      }
    } catch { return fallback }
  }

  async createEvent(input: {
    summary: string; description?: string; startTime: string; endTime: string; calendarId?: string
  }): Promise<{ ok: boolean; event?: CalendarEvent; error?: string }> {
    const accessToken = await getAccessToken()
    if (!accessToken) return { ok: false, error: 'Cannot get Google access token. Check OAuth credentials.' }

    const calendarId = input.calendarId ?? 'primary'
    const body = {
      summary: input.summary,
      description: input.description,
      start: { dateTime: input.startTime, timeZone: 'Asia/Kolkata' },
      end: { dateTime: input.endTime, timeZone: 'Asia/Kolkata' },
    }

    const response = await outboundFetch(
      `https://www.googleapis.com/calendar/v3/calendars/${encodeURIComponent(calendarId)}/events`,
      { method: 'POST', headers: { Authorization: `Bearer ${accessToken}`, 'Content-Type': 'application/json' }, body: JSON.stringify(body) },
    )

    if (!response.ok) {
      return { ok: false, error: `Calendar create failed: ${response.status} ${await response.text()}` }
    }

    const raw = (await response.json()) as GoogleCalendarEvent
    return { ok: true, event: normalizeEvent(raw) }
  }

  async addPriorityBlock(title: string, dateIso: string, startHour: number, durationHours = 2): Promise<{ ok: boolean; event?: CalendarEvent; error?: string }> {
    const start = new Date(`${dateIso}T${String(startHour).padStart(2, '0')}:00:00`)
    const end = new Date(start.getTime() + durationHours * 60 * 60 * 1000)
    return this.createEvent({
      summary: `[JARVIS] ${title}`,
      description: 'Priority block added by Jarvis based on business analysis.',
      startTime: start.toISOString(),
      endTime: end.toISOString(),
    })
  }

  private mockEvents(): CalendarEvent[] {
    const now = new Date()
    const fmt = (offsetHours: number) => {
      const d = new Date(now.getTime() + offsetHours * 3600000)
      return d.toISOString()
    }
    return [
      { id: 'mock-1', summary: 'Outreach Strategy Review', description: 'Review campaign performance and pipeline metrics', start: fmt(1), end: fmt(2) },
      { id: 'mock-2', summary: 'Investor / Mentor Call', description: 'Update on Forge OS progress and revenue path', start: fmt(3), end: fmt(4) },
      { id: 'mock-3', summary: 'Content Creation Block', description: 'Record 2 reels for this week\'s content cycle', start: fmt(25), end: fmt(27) },
      { id: 'mock-4', summary: 'Lead Generation Review', description: 'Review enriched leads and approve next send batch', start: fmt(48), end: fmt(49) },
    ]
  }
}
