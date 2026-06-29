import type { FastifyInstance } from 'fastify'
import { z } from 'zod'
import { JarvisSovereignService } from '../services/jarvisSovereign.service.js'

const goalSchema = z.object({
  goal: z.string().min(5),
  mode: z.enum(['advisory', 'approval', 'autonomous']).default('approval'),
  maxDepth: z.number().int().min(1).max(5).optional(),
  maxAgents: z.number().int().min(1).max(50).optional(),
})

const companyStateSchema = z.object({
  key: z.string().min(1),
  value: z.unknown(),
})

const approvalSchema = z.object({
  taskId: z.string().min(1),
  approved: z.boolean(),
  note: z.string().optional(),
})

export async function registerJarvisSovereignRoutes(app: FastifyInstance) {
  const jarvis = new JarvisSovereignService()

  app.post('/api/jarvis/sovereign/goal', async (request, reply) => {
    const parsed = goalSchema.safeParse(request.body)
    if (!parsed.success) {
      return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    }

    const result = await jarvis.receiveGoal(parsed.data)
    return result
  })

  app.get('/api/jarvis/sovereign/status', async () => {
    const status = await jarvis.getStatus()
    return { ok: true, ...status }
  })

  app.post('/api/jarvis/sovereign/state', async (request, reply) => {
    const parsed = companyStateSchema.safeParse(request.body)
    if (!parsed.success) {
      return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    }

    const state = await jarvis.setCompanyState(parsed.data.key, parsed.data.value)
    return { ok: true, state }
  })

  app.post('/api/jarvis/sovereign/approval', async (request, reply) => {
    const parsed = approvalSchema.safeParse(request.body)
    if (!parsed.success) {
      return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    }

    const result = await jarvis.recordApproval(parsed.data.taskId, parsed.data.approved, parsed.data.note)
    return { ok: Boolean(result), task: result }
  })
}
