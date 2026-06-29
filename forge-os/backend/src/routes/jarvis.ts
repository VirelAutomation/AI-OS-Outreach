import type { FastifyInstance } from 'fastify'
import { z } from 'zod'
import {
  getExperiments,
  getHumanTasks,
  pushHumanTask,
  updateHumanTask,
} from '../lib/jarvisHumanQueue.js'
import { type SelfDevContext, JarvisService } from '../services/jarvis.service.js'
import {
  analyzePlatformGaps,
  generateDailyBrief,
  generateWeeklyPlan,
  getStrategyRecommendation,
  runDmExperiment,
  runHookExperiment,
} from '../services/jarvisStrategy.service.js'

const calendarEventSchema = z.object({
  id: z.string(),
  summary: z.string(),
  description: z.string().optional(),
  start: z.string(),
  end: z.string(),
  status: z.string().optional(),
})

const selfDevGoalSchema = z.object({
  title: z.string(),
  category: z.string(),
  horizon: z.string(),
  progress: z.number(),
})

const selfDevContextSchema = z.object({
  goals: z.array(selfDevGoalSchema),
  habitsCompletedToday: z.number(),
  totalHabits: z.number(),
  learningInProgress: z.array(z.string()),
  reflection: z.object({
    win: z.string().optional(),
    lesson: z.string().optional(),
    next: z.string().optional(),
  }).optional(),
})

const chatSchema = z.object({
  prompt: z.string().min(1),
  operator: z.string().optional(),
  calendarContext: z.array(calendarEventSchema).optional(),
  selfDevContext: selfDevContextSchema.optional(),
})

const gradeSchema = selfDevContextSchema

export async function registerJarvisRoutes(app: FastifyInstance) {
  const jarvis = new JarvisService()

  // Main chat endpoint — full context-aware Gemini response
  app.post('/api/jarvis', async (request, reply) => {
    const parsed = chatSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    const result = await jarvis.run(parsed.data)
    return { ok: true, ...result }
  })

  // Get chat history
  app.get('/api/jarvis/history', async () => {
    return { ok: true, messages: jarvis.getChatHistory() }
  })

  // Clear chat history
  app.delete('/api/jarvis/history', async () => {
    jarvis.clearHistory()
    return { ok: true, cleared: true }
  })

  // Grade self-development progress
  app.post('/api/jarvis/grade', async (request, reply) => {
    const parsed = gradeSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    const grade = await jarvis.gradeSelfDev(parsed.data as SelfDevContext)
    return { ok: true, grade }
  })

  // ── Autonomous Strategy Engine ───────────────────────────────────────────────

  // Daily brief — Jarvis autonomously analyzes everything and produces an ops brief
  app.post('/api/jarvis/brief', async () => {
    const brief = await generateDailyBrief()
    return { ok: true, brief }
  })

  app.get('/api/jarvis/brief', async () => {
    const brief = await generateDailyBrief()
    return { ok: true, brief }
  })

  // Weekly plan — Jarvis generates split ownership plan (jarvis vs jace)
  app.post('/api/jarvis/strategy/weekly-plan', async () => {
    const plan = await generateWeeklyPlan()
    return { ok: true, plan }
  })

  // Platform gap analysis
  const platformGapSchema = z.object({
    configuredCredentials: z.array(z.string()).optional(),
  })

  app.post('/api/jarvis/strategy/platform-gaps', async (request, reply) => {
    const parsed = platformGapSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    const gaps = await analyzePlatformGaps(parsed.data.configuredCredentials)
    return { ok: true, gaps, total: gaps.length }
  })

  app.get('/api/jarvis/strategy/platform-gaps', async () => {
    const gaps = await analyzePlatformGaps()
    return { ok: true, gaps, total: gaps.length }
  })

  // CRL-powered approach recommendation
  app.get('/api/jarvis/strategy/recommendation', async (request) => {
    const { industry, channel } = request.query as { industry?: string; channel?: string }
    const recommendation = await getStrategyRecommendation(industry, channel)
    return { ok: true, ...recommendation }
  })

  // Hook A/B experiment
  const hookExpSchema = z.object({
    niche: z.string().min(1),
    platform: z.enum(['tiktok', 'instagram_reels', 'youtube_shorts', 'linkedin', 'twitter']),
    count: z.number().int().min(2).max(8).optional(),
  })

  app.post('/api/jarvis/strategy/experiment/hook', async (request, reply) => {
    const parsed = hookExpSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    const experiment = await runHookExperiment(parsed.data)
    return { ok: true, experiment }
  })

  // DM angle experiment
  const dmExpSchema = z.object({
    industry: z.string().min(1),
    channel: z.enum(['linkedin', 'instagram', 'sms', 'x']),
    hookStyles: z.array(z.enum(['pain-first', 'result-first', 'signal-first'])).optional(),
  })

  app.post('/api/jarvis/strategy/experiment/dm', async (request, reply) => {
    const parsed = dmExpSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    const experiment = await runDmExperiment(parsed.data)
    return { ok: true, experiment }
  })

  // List all experiments
  app.get('/api/jarvis/strategy/experiments', async (request) => {
    const { type } = request.query as { type?: string }
    const experiments = await getExperiments(type as 'hook' | 'dm' | undefined)
    return { ok: true, experiments, total: experiments.length }
  })

  // ── Human Task Queue ─────────────────────────────────────────────────────────

  const humanTaskSchema = z.object({
    title: z.string().min(1),
    description: z.string().min(1),
    category: z.enum(['account_setup', 'content_record', 'credential_setup', 'strategy_approval', 'outreach_manual', 'feedback', 'review']),
    priority: z.union([z.literal(1), z.literal(2), z.literal(3)]),
    createdBy: z.string().optional(),
    payload: z.unknown().optional(),
  })

  app.get('/api/jarvis/human-tasks', async (request) => {
    const { status } = request.query as { status?: string }
    const tasks = await getHumanTasks(status as 'pending' | 'done' | 'dismissed' | undefined)
    return { ok: true, tasks, total: tasks.length }
  })

  app.post('/api/jarvis/human-tasks', async (request, reply) => {
    const parsed = humanTaskSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    const task = await pushHumanTask({
      ...parsed.data,
      createdBy: parsed.data.createdBy ?? 'jace',
    })
    return { ok: true, task }
  })

  app.patch('/api/jarvis/human-tasks/:id', async (request, reply) => {
    const { id } = request.params as { id: string }
    const body = request.body as { status?: 'pending' | 'done' | 'dismissed' }
    if (!body.status) return reply.code(400).send({ ok: false, error: 'status required' })
    const task = await updateHumanTask(id, { status: body.status })
    if (!task) return reply.code(404).send({ ok: false, error: 'task not found' })
    return { ok: true, task }
  })
}
