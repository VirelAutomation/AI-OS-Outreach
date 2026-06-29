import type { FastifyInstance } from 'fastify'
import { z } from 'zod'
import { writeAudit } from '../lib/auditLog.js'
import { CtoService } from '../services/cto.service.js'

const spawnPlanSchema = z.object({
  businessArea: z.enum(['ceo', 'cto', 'cmo', 'cfo', 'lead_generation', 'lead_management', 'content', 'analytics']),
  objective: z.string().min(3),
  maxAgents: z.number().int().min(1).max(50).optional(),
})

export async function registerCtoRoutes(app: FastifyInstance) {
  const cto = new CtoService()

  app.get('/api/cto/readiness', async () => {
    return cto.systemReadiness()
  })

  app.get('/api/cto/sci', async () => {
    return cto.sciArchitecture()
  })

  app.post('/api/cto/spawn-plan', async (request, reply) => {
    const parsed = spawnPlanSchema.safeParse(request.body)
    if (!parsed.success) {
      return reply.code(400).send({ ok: false, error: parsed.error.flatten() })
    }

    const plan = cto.spawnPlan(parsed.data)
    writeAudit({
      actor: 'cto',
      action: 'spawn_plan',
      purpose: parsed.data.objective,
      result: 'ok',
      metadata: { businessArea: parsed.data.businessArea, agentCount: plan.agents.length },
    })
    return plan
  })
}
