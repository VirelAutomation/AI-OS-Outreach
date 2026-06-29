import type { FastifyInstance } from 'fastify'
import { CrmService } from '../services/crm.service.js'

export async function registerCrmRoutes(app: FastifyInstance) {
  const crm = new CrmService()

  app.get('/api/crm/prospects', async () => {
    const prospects = await crm.listProspects()
    return {
      ok: true,
      prospects,
    }
  })

  app.get('/api/crm/dashboard', async () => {
    const summary = await crm.dashboardSummary()
    return {
      ok: true,
      summary,
    }
  })
}
