import { randomUUID } from 'node:crypto'
import { geminiApiKeyFor } from '../config/env.js'
import { callGemini, callGeminiSimple } from '../lib/gemini.js'
import { getHumanQueueSummary } from '../lib/jarvisHumanQueue.js'
import { getSupabaseAdmin } from '../lib/supabaseAdmin.js'
import { ProductionDataService } from './productionData.service.js'

export type JarvisRunInput = {
  prompt: string
  operator?: string
  calendarContext?: CalendarEvent[]
  selfDevContext?: SelfDevContext
}

export type CalendarEvent = {
  id: string
  summary: string
  description?: string
  start: string
  end: string
  status?: string
}

export type SelfDevContext = {
  goals: Array<{ title: string; category: string; horizon: string; progress: number }>
  habitsCompletedToday: number
  totalHabits: number
  learningInProgress: string[]
  reflection?: { win?: string; lesson?: string; next?: string }
}

export type ChatMessage = {
  id: string
  role: 'user' | 'jarvis'
  content: string
  createdAt: string
}

// In-memory chat history — synced to Supabase when configured
const chatHistory: ChatMessage[] = []

function buildSystemPrompt(metrics: {
  leads: number; drafts: number; sent: number; replies: number; meetings: number; replyRate: number
}, agentContext?: {
  pendingHumanTasks?: number
  criticalHumanTasks?: number
  activeExperiments?: number
  platformGapsCount?: number
}) {
  const taskContext = agentContext
    ? `\nAGENTIC CONTEXT (what I've already done / what's queued):
- Pending Jace tasks: ${agentContext.pendingHumanTasks ?? 0} (${agentContext.criticalHumanTasks ?? 0} critical)
- Active experiments running: ${agentContext.activeExperiments ?? 0}
- Platform gaps identified: ${agentContext.platformGapsCount ?? 0}`
    : ''

  return `You are JARVIS — the sovereign AI CEO of Forge OS. You are not an assistant. You are the autonomous operating mind of Virel Automation.

IDENTITY & OPERATING MANDATE:
You operate proactively. You plan without being asked. You run experiments. You allocate work. You identify gaps and fix them. You tell Jace exactly what he needs to do and when — and you handle everything else yourself.
You are not waiting for instructions. You are executing a plan.

OPERATOR: Jace Silva, 19yo solo founder. You are his CEO brain. He is the executor on human-required tasks. You handle everything that can be automated.
COMPANY: Virel Automation (prev. Virell Labs) — AI outreach and lead gen system
MISSION: Get Jace to $15M MRR in 7 months. Currently at $0. Pre-revenue, pipeline phase.
ICP: HVAC companies, Real Estate Agents, Digital Marketing Agencies, Interior Designers, Clinics, Med Spas.
CHANNELS: Cold email (primary), LinkedIn DM, Instagram DM, TikTok content, SMS.
BRAND VOICE: Direct, specific, founder-energy. No filler. No hedging. No generic advice.

LIVE PIPELINE (real-time):
- Leads: ${metrics.leads} | Drafts: ${metrics.drafts}
- Sent: ${metrics.sent} | Replies: ${metrics.replies} | Meetings: ${metrics.meetings}
- Reply rate: ${metrics.replyRate.toFixed(1)}% ${metrics.replyRate < 5 ? '⚠ CRITICAL — BELOW 5%' : metrics.replyRate < 10 ? '(below benchmark — needs improvement)' : '(healthy)'}
- Revenue gap: $15M MRR. Clock running.
${taskContext}

EXECUTIVE TEAM I COORDINATE:
- Noah (CMO): Viral research, content concepts, scripts, hook scoring, campaigns
- Damien (CTO): System health, API reliability, code changes
- Devan (Lead Gen): Lead sourcing, Apollo enrichment, Apify discovery
- Akhil (Lead Mgmt): Reply triage, CRM updates, meeting handoff
- Zoya (CFO): Revenue tracking, pipeline economics
- King (AI): Memory, training, evaluation loops

AUTONOMOUS OPERATING MODE:
When Jace asks for strategy, don't just advise — PLAN AND ASSIGN:
1. State what Jarvis will do autonomously (AI tasks: enrich leads, generate drafts, score hooks, run experiments)
2. State what Jace must do (human tasks: send emails, record videos, create accounts, reply to prospects)
3. If an experiment should be run (hook A/B, DM angle test), say exactly which one and why
4. If a platform gap exists (missing Apollo key, no LinkedIn presence), name it with exact action
5. Reference CRL learning if relevant — what patterns are working, what to double down on

RESPONSE FORMAT FOR STRATEGY QUERIES:
Always end with:
[JARVIS WILL]: ... (what I execute autonomously)
[JACE MUST]: ... (human tasks, prioritized)
[EXPERIMENT]: ... (optional — if an A/B test should run)

HOW TO RESPOND:
1. Reference specific numbers from pipeline metrics in every strategy response
2. Be direct — no "it's important to" or "you should consider". Say "Do X" or "Don't do Y"
3. If reply rate is below 8%, the subject line and first sentence are broken — say it
4. If no emails have been sent today, say it and give the specific next step
5. You can be dry and witty — but only when it adds force to the advice
6. If Jace is off-track, tell him exactly what the correction is, not the general direction
7. When recommending a hook style or DM angle, cite the CRL confidence level if available

NEVER: Say "great question". Use "leverage" or "synergy" generically. Give advice not specific to this business. Recommend something without a concrete next action.`
}

async function saveMessageToSupabase(message: ChatMessage) {
  const supabase = getSupabaseAdmin()
  if (!supabase) return
  try {
    await supabase.from('jarvis_messages').insert({
      id: message.id,
      role: message.role,
      content: message.content,
      created_at: message.createdAt,
    })
  } catch { /* supabase table may not exist yet */ }
}

async function loadHistoryFromSupabase(): Promise<ChatMessage[]> {
  const supabase = getSupabaseAdmin()
  if (!supabase) return []
  try {
    const { data } = await supabase
      .from('jarvis_messages')
      .select('id, role, content, created_at')
      .order('created_at', { ascending: true })
      .limit(50)
    if (!data) return []
    return data.map((row) => ({
      id: String(row.id),
      role: row.role as 'user' | 'jarvis',
      content: String(row.content),
      createdAt: String(row.created_at),
    }))
  } catch { return [] }
}

export class JarvisService {
  private historyLoaded = false
  private readonly productionData = new ProductionDataService()

  private async ensureHistory() {
    if (this.historyLoaded) return
    this.historyLoaded = true
    const dbHistory = await loadHistoryFromSupabase()
    if (dbHistory.length > 0 && chatHistory.length === 0) {
      chatHistory.push(...dbHistory)
    }
  }

  async run(input: JarvisRunInput) {
    await this.ensureHistory()

    const [metrics, queueSummary] = await Promise.all([
      this.loadMetrics(),
      getHumanQueueSummary().catch(() => null),
    ])

    const agentContext = queueSummary ? {
      pendingHumanTasks: queueSummary.pendingTasks,
      criticalHumanTasks: queueSummary.criticalTasks,
      activeExperiments: queueSummary.recentExperiments,
      platformGapsCount: 0,
    } : undefined

    const userMessage: ChatMessage = {
      id: randomUUID(),
      role: 'user',
      content: input.prompt,
      createdAt: new Date().toISOString(),
    }
    chatHistory.push(userMessage)
    void saveMessageToSupabase(userMessage)

    const geminiKey = geminiApiKeyFor('jarvis')
    if (!geminiKey) {
      const response = this.fallbackResponse(input.prompt, metrics, undefined)
      const jarvisMessage: ChatMessage = { id: randomUUID(), role: 'jarvis', content: response, createdAt: new Date().toISOString() }
      chatHistory.push(jarvisMessage)
      void saveMessageToSupabase(jarvisMessage)
      return { mode: 'local-orchestrator', response, messages: chatHistory.slice(-20), actions: ['Add GEMINI_API_KEY_JARVIS to unlock full AI intelligence'] }
    }

    // Enrich the user message with live context
    const calendarSection = input.calendarContext?.length
      ? `\n\n[CALENDAR CONTEXT]\n${input.calendarContext.map((e) => `• ${e.start.slice(11, 16) || e.start.slice(0, 10)} — ${e.summary}${e.description ? ` (${e.description.slice(0, 100)})` : ''}`).join('\n')}`
      : ''

    const selfDevSection = input.selfDevContext
      ? `\n\n[SELF DEV CONTEXT]\nGoals active: ${input.selfDevContext.goals.length} | Completed: ${input.selfDevContext.goals.filter((g) => g.progress >= 100).length}\nHabits today: ${input.selfDevContext.habitsCompletedToday}/${input.selfDevContext.totalHabits}\nLearning: ${input.selfDevContext.learningInProgress.join(', ') || 'none in progress'}\nWeek reflection win: "${input.selfDevContext.reflection?.win || 'not written yet'}"`
      : ''

    // Build Gemini multi-turn conversation from recent history
    const recentHistory = chatHistory.slice(-21, -1)
    const contents = [
      ...recentHistory.map((m) => ({
        role: m.role === 'user' ? 'user' : 'model',
        parts: [{ text: m.content }],
      })),
      { role: 'user', parts: [{ text: `${input.prompt}${calendarSection}${selfDevSection}` }] },
    ]

    try {
      const text = await callGemini({
        role: 'jarvis',
        contents,
        systemInstruction: { parts: [{ text: buildSystemPrompt(metrics, agentContext) }] },
        generationConfig: { temperature: 0.75, maxOutputTokens: 1500 },
      })
      const jarvisMessage: ChatMessage = { id: randomUUID(), role: 'jarvis', content: text, createdAt: new Date().toISOString() }
      chatHistory.push(jarvisMessage)
      void saveMessageToSupabase(jarvisMessage)
      return { mode: 'governed-runtime', response: text, messages: chatHistory.slice(-20), actions: [] }
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error)
      const fallback = this.fallbackResponse(input.prompt, metrics, reason)
      const jarvisMessage: ChatMessage = { id: randomUUID(), role: 'jarvis', content: fallback, createdAt: new Date().toISOString() }
      chatHistory.push(jarvisMessage)
      return {
        mode: 'fallback',
        response: fallback,
        messages: chatHistory.slice(-20),
        actions: reason.includes('429') ? ['Gemini is rate-limited right now. Reduce concurrent runs or switch keys.'] : [reason],
      }
    }
  }

  async gradeSelfDev(input: SelfDevContext) {
    const fallback = {
      grade: 'B', score: 72,
      breakdown: {
        Goals: { grade: 'B+', score: 78, feedback: `${input.goals.filter((g) => g.progress > 0).length}/${input.goals.length} goals moving. Keep the momentum.` },
        Habits: { grade: 'B', score: 70, feedback: `${input.habitsCompletedToday}/${input.totalHabits} done today. Consistency beats intensity.` },
        Learning: { grade: 'B-', score: 65, feedback: `${input.learningInProgress.length} active. Apply immediately — learning that doesn't change behaviour is waste.` },
        BusinessExecution: { grade: 'C+', score: 68, feedback: 'Add GEMINI_API_KEY_JARVIS for real business metric grading.' },
      },
      recommendations: [
        'Pick one goal this week and move it 20% forward before anything else.',
        'Close the learning loop — what did you apply from last week?',
        'Habit consistency is the multiplier. Protect your non-negotiables.',
      ],
      headline: 'Solid foundation. Execution velocity is the variable.',
      honestTruth: 'You\'re building the right things. The question is whether you\'re moving fast enough for the 7-month window. Every day you don\'t send emails is a day closer to zero.',
    }

    const geminiKey = geminiApiKeyFor('jarvis')
    if (!geminiKey) return fallback

    const metrics = await this.loadMetrics()

    const prompt = `You are JARVIS grading Jace's week. Be direct and honest. Grade like a senior advisor who cares about outcomes, not feelings.

OPERATOR: Jace, 19yo founder, Virell Labs. Target: $15M MRR in 7 months. Current MRR: $0.

SELF DEV THIS WEEK:
Goals: ${JSON.stringify(input.goals.map((g) => ({ title: g.title, category: g.category, progress: g.progress, horizon: g.horizon })))}
Habits today: ${input.habitsCompletedToday}/${input.totalHabits}
Learning in progress: ${input.learningInProgress.join(', ') || 'none'}
Reflection — Win: "${input.reflection?.win || 'not written'}" | Lesson: "${input.reflection?.lesson || 'not written'}" | Next week: "${input.reflection?.next || 'not written'}"

BUSINESS METRICS:
- Emails sent: ${metrics.sent} | Replies: ${metrics.replies} | Meetings booked: ${metrics.meetings}
- Reply rate: ${metrics.replyRate.toFixed(1)}%

Grade everything honestly. A 19-year-old at zero revenue with a 7-month window needs truth, not validation.

Return strict JSON:
{
  "grade": "A-",
  "score": 82,
  "breakdown": {
    "Goals": { "grade": "B+", "score": 78, "feedback": "specific feedback on goal progress" },
    "Habits": { "grade": "A-", "score": 85, "feedback": "specific feedback on habit completion" },
    "Learning": { "grade": "B", "score": 72, "feedback": "specific feedback on learning and application" },
    "BusinessExecution": { "grade": "C+", "score": 68, "feedback": "specific feedback based on emails/replies/meetings numbers" }
  },
  "recommendations": ["action 1", "action 2", "action 3"],
  "headline": "one sentence summary",
  "honestTruth": "the one thing he needs to hear"
}`

    try {
      const text = await callGeminiSimple('jarvis', prompt, { temperature: 0.6, maxOutputTokens: 1000, jsonMode: true })
      if (!text) return fallback
      const raw = text.trim().startsWith('```') ? text.split('```')[1]?.replace(/^json\n?/, '').trim() ?? text : text
      return JSON.parse(raw)
    } catch { return fallback }
  }

  getChatHistory(): ChatMessage[] { return chatHistory.slice(-50) }
  clearHistory() { chatHistory.length = 0 }

  private async loadMetrics() {
    const overview = await this.productionData.analyticsOverview()
    return {
      leads: overview.metrics.totalLeads,
      drafts: overview.metrics.totalDrafts,
      sent: overview.metrics.emailsSent,
      replies: overview.metrics.replies,
      meetings: overview.metrics.meetingsBooked,
      replyRate: overview.metrics.replyRate,
    }
  }

  private fallbackResponse(
    prompt: string,
    m: { leads: number; sent: number; replies: number; meetings: number; replyRate: number },
    failureReason?: string,
  ) {
    const p = prompt.toLowerCase()
    if (failureReason?.includes('429')) {
      return `Gemini is rate-limited right now. Live snapshot: ${m.sent} sent, ${m.replies} replies, ${m.meetings} meetings, ${m.replyRate.toFixed(1)}% reply rate. Jarvis fell back because the provider returned 429, not because your key is missing.`
    }
    if (failureReason?.includes('gemini_error:')) {
      return `Jarvis hit a Gemini provider error: ${failureReason}. Live snapshot: ${m.sent} sent, ${m.replies} replies, ${m.meetings} meetings, ${m.replyRate.toFixed(1)}% reply rate.`
    }
    if (p.includes('grade') || p.includes('score') || p.includes('progress'))
      return `Add GEMINI_API_KEY_JARVIS for real grading. Live snapshot: ${m.leads} leads, ${m.sent} emails sent, ${m.replies} replies, ${m.meetings} meetings. Reply rate: ${m.replyRate.toFixed(1)}%. That's where you are right now.`
    if (p.includes('calendar') || p.includes('today') || p.includes('schedule'))
      return `No Gemini for calendar intelligence yet. Rule of thumb: first thing is the outreach review. Second is the highest-revenue conversation you can have. Everything else is admin.`
    if (p.includes('brief') || p.includes('strategy') || p.includes('what should'))
      return `Pipeline snapshot: ${m.leads} leads, ${m.sent} sent, ${m.replyRate.toFixed(1)}% reply rate, ${m.meetings} meetings. ${m.replyRate < 8 ? 'Reply rate is below 8% — fix the subject line and opener before scaling volume.' : 'Reply rate is healthy — scale volume in legal and fintech first.'} Next move: run enrich-smart on your lead list.`
    return `Running in offline mode (add GEMINI_API_KEY_JARVIS). Metrics: ${m.sent} sent, ${m.replies} replies, ${m.meetings} meetings, ${m.replyRate.toFixed(1)}% reply rate. Add your Jarvis key for full intelligence.`
  }
}
