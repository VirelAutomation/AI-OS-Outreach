import type { FastifyInstance } from 'fastify'
import { z } from 'zod'
import { writeAudit } from '../lib/auditLog.js'
import { getSystemTopology, getCacheStatus } from '../lib/ceuRuntime.js'
import { getLearningDigest, recordOutcome } from '../lib/crlLearning.js'
import { getSupabaseAdmin } from '../lib/supabaseAdmin.js'
import { type CMOSubAgent, type Platform, CMOService } from '../services/cmo.service.js'

const platformEnum = z.enum(['tiktok', 'instagram_reels', 'youtube_shorts', 'linkedin', 'twitter'])

const researchSchema = z.object({
  niche: z.string().min(1),
  platform: platformEnum,
})

const conceptsSchema = z.object({
  niche: z.string().min(1),
  platform: platformEnum,
  count: z.number().int().min(1).max(8).default(6),
  goal: z.string().optional(),
  researchContext: z
    .object({
      goldHooks: z.array(z.string()).optional(),
      contentAngles: z.array(z.string()).optional(),
      trendingFormats: z.array(z.string()).optional(),
    })
    .optional(),
})

const scriptSchema = z.object({
  concept: z.string().min(1),
  hook: z.string().min(1),
  platform: platformEnum,
  niche: z.string().min(1),
  duration: z.string().optional(),
  goal: z.string().optional(),
})

const hookScoreSchema = z.object({
  hook: z.string().min(1),
  platform: platformEnum,
})

const spawnSchema = z.object({
  subAgent: z.enum([
    'subject_line_lab',
    'message_architect',
    'offer_positioner',
    'landing_cro',
    'content_angle_scout',
  ]),
  goal: z.string().min(1),
})

export async function registerCMORoutes(app: FastifyInstance) {
  const cmo = new CMOService()

  // Research viral patterns for niche + platform
  app.post('/api/cmo/research', async (request, reply) => {
    const parsed = researchSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    const research = await cmo.researchViralTrends(parsed.data.niche, parsed.data.platform as Platform)
    return { ok: true, research }
  })

  // Generate video concepts
  app.post('/api/cmo/concepts', async (request, reply) => {
    const parsed = conceptsSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    const concepts = await cmo.generateConcepts({
      niche: parsed.data.niche,
      platform: parsed.data.platform as Platform,
      count: parsed.data.count,
      goal: parsed.data.goal,
      researchContext: parsed.data.researchContext,
    })
    return { ok: true, concepts }
  })

  // Generate a full production script
  app.post('/api/cmo/script', async (request, reply) => {
    const parsed = scriptSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    const script = await cmo.generateScript({
      concept: parsed.data.concept,
      hook: parsed.data.hook,
      platform: parsed.data.platform as Platform,
      niche: parsed.data.niche,
      duration: parsed.data.duration,
      goal: parsed.data.goal,
    })
    return { ok: true, script }
  })

  // Score a hook for virality
  app.post('/api/cmo/hook/score', async (request, reply) => {
    const parsed = hookScoreSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    const score = await cmo.scoreHook(parsed.data.hook, parsed.data.platform as Platform)
    return { ok: true, score }
  })

  // Spawn a CMO sub-agent (called by Jarvis orchestrator or directly)
  app.post('/api/cmo/spawn', async (request, reply) => {
    const parsed = spawnSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    const task = await cmo.spawnSubAgent(parsed.data.subAgent as CMOSubAgent, parsed.data.goal)
    writeAudit({
      actor: 'cmo',
      action: 'spawn_sub_agent',
      purpose: parsed.data.goal,
      result: task.status === 'done' ? 'ok' : 'error',
      metadata: { subAgent: parsed.data.subAgent, status: task.status },
    })
    return { ok: task.status === 'done', task }
  })

  // List active CMO sub-agent tasks
  app.get('/api/cmo/tasks', async () => {
    return { ok: true, tasks: cmo.getActiveTasks() }
  })

  app.get('/api/cmo/artifacts', async (request) => {
    const limit = Number((request.query as { limit?: string }).limit ?? 50)
    return { ok: true, artifacts: cmo.getArtifacts(Math.min(Math.max(limit, 1), 200)) }
  })

  // CMO status — used by Jarvis for cross-system delegation
  app.get('/api/cmo/status', async () => {
    return {
      ok: true,
      agent: 'noah',
      title: 'CMO',
      mission: 'Messaging, campaign architecture, subject lines, hooks, and content strategy.',
      subAgents: ['subject_line_lab', 'message_architect', 'offer_positioner', 'landing_cro', 'content_angle_scout'],
      capabilities: ['viral_research', 'concept_generation', 'script_writing', 'hook_scoring', 'sub_agent_spawn', 'artifact_persistence', 'content_calendar'],
      reportsTo: 'jarvis',
      storage: cmo.getArtifactStatus(),
    }
  })

  // ── Content Calendar ─────────────────────────────────────────────────────────

  const calendarScheduleSchema = z.object({
    title: z.string().min(1),
    platform: z.string().min(1),
    contentType: z.string().optional(),
    publishAt: z.string().datetime().optional(),
    notes: z.string().optional(),
    sourceItemId: z.string().uuid().optional(),
    metadata: z.record(z.string(), z.unknown()).optional(),
  })

  app.get('/api/cmo/calendar', async (request) => {
    const { status, limit: limitRaw } = request.query as { status?: string; limit?: string }
    const limit = Math.min(Math.max(Number(limitRaw ?? 50), 1), 200)

    const supabase = getSupabaseAdmin()
    if (!supabase) {
      return { ok: true, items: [], source: 'offline', message: 'Supabase not configured — calendar requires database connection.' }
    }

    let query = supabase
      .from('content_calendar_items')
      .select('id, title, platform, content_type, status, publish_at, owner_system, notes, metadata, created_at')
      .order('publish_at', { ascending: true })
      .limit(limit)

    if (status) query = query.eq('status', status)

    const { data, error } = await query

    if (error) {
      return { ok: false, error: error.message, items: [] }
    }

    return { ok: true, items: data ?? [], total: data?.length ?? 0, source: 'supabase' }
  })

  app.post('/api/cmo/calendar/schedule', async (request, reply) => {
    const parsed = calendarScheduleSchema.safeParse(request.body)
    if (!parsed.success) return reply.code(400).send({ ok: false, error: parsed.error.flatten() })

    const supabase = getSupabaseAdmin()
    if (!supabase) {
      return reply.code(503).send({ ok: false, error: 'Supabase not configured. Set SUPABASE_URL and SUPABASE_SECRET_KEY in backend environment variables.' })
    }

    const { data, error } = await supabase
      .from('content_calendar_items')
      .insert({
        title: parsed.data.title,
        platform: parsed.data.platform,
        content_type: parsed.data.contentType ?? 'video',
        status: 'planned',
        publish_at: parsed.data.publishAt ?? null,
        owner_system: 'noah',
        notes: parsed.data.notes ?? null,
        source_item_id: parsed.data.sourceItemId ?? null,
        metadata: parsed.data.metadata ?? {},
      })
      .select('id, title, platform, content_type, status, publish_at, notes, created_at')
      .single()

    if (error || !data) {
      return reply.code(500).send({ ok: false, error: error?.message ?? 'insert_failed' })
    }

    writeAudit({
      actor: 'noah',
      action: 'calendar_schedule',
      purpose: parsed.data.title,
      result: 'ok',
      metadata: { platform: parsed.data.platform, publishAt: parsed.data.publishAt },
    })

    await recordOutcome('noah', 'ai_draft_accepted', {
      niche: parsed.data.title,
      platform: parsed.data.platform,
    })

    return { ok: true, item: data }
  })

  app.patch('/api/cmo/calendar/:id', async (request, reply) => {
    const { id } = request.params as { id: string }
    const body = request.body as { status?: string; publishAt?: string; notes?: string }

    const supabase = getSupabaseAdmin()
    if (!supabase) return reply.code(503).send({ ok: false, error: 'Supabase not configured.' })

    const patch: Record<string, unknown> = {}
    if (body.status) patch.status = body.status
    if (body.publishAt) patch.publish_at = body.publishAt
    if (body.notes !== undefined) patch.notes = body.notes

    const { data, error } = await supabase
      .from('content_calendar_items')
      .update(patch)
      .eq('id', id)
      .select('id, title, platform, status, publish_at, notes, created_at')
      .single()

    if (error || !data) return reply.code(404).send({ ok: false, error: error?.message ?? 'not_found' })
    return { ok: true, item: data }
  })

  app.delete('/api/cmo/calendar/:id', async (request, reply) => {
    const { id } = request.params as { id: string }

    const supabase = getSupabaseAdmin()
    if (!supabase) return reply.code(503).send({ ok: false, error: 'Supabase not configured.' })

    const { error } = await supabase.from('content_calendar_items').delete().eq('id', id)
    if (error) return reply.code(404).send({ ok: false, error: error.message })

    return { ok: true, deleted: id }
  })

  // ── CEU Runtime + CRL Intelligence ──────────────────────────────────────────

  app.get('/api/cmo/runtime', async () => {
    const [topology, cache, learning] = await Promise.all([
      Promise.resolve(getSystemTopology()),
      Promise.resolve(getCacheStatus()),
      getLearningDigest(),
    ])

    return {
      ok: true,
      ceuRuntime: {
        topology,
        cache,
      },
      crlLearning: learning,
    }
  })
}
