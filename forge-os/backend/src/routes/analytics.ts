import type { FastifyInstance } from 'fastify'
import { ProductionDataService } from '../services/productionData.service.js'

export async function registerAnalyticsRoutes(app: FastifyInstance) {
  const productionData = new ProductionDataService()

  app.get('/api/analytics/overview', async () => {
    const overview = await productionData.analyticsOverview()

    return {
      ok: true,
      metrics: overview.metrics,
      campaignLeaderboard: overview.campaignLeaderboard,
      recentReplies: overview.recentReplies,
      integrity: {
        statsSource: overview.statsSource,
        noHardcodedDashboardNumbers: true,
      },
    }
  })
}
