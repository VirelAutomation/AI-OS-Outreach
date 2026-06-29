import type { FastifyInstance } from 'fastify'
import { env } from '../config/env.js'
import { geminiQueueStatus } from '../lib/gemini.js'
import { outboundPolicy } from '../lib/network.js'
import { runtimeStore } from '../lib/runtimeStore.js'
import { checkSchemaReadiness, migrationChecklist } from '../lib/schemaReadiness.js'
import { getSystemTopology, getCacheStatus } from '../lib/ceuRuntime.js'
import { getLearningDigest } from '../lib/crlLearning.js'
import { getSchedulerStatus } from '../lib/scheduler.js'
import { OutreachService } from '../services/outreach.service.js'
import { GoogleStackService } from '../services/googleStack.service.js'

async function checkSupabase() {
  const schema = await checkSchemaReadiness()
  return {
    configured: schema.configured,
    ok: schema.ok,
    status: schema.status,
    message: schema.message,
    missingTables: schema.missingTables,
  }
}

export async function registerHealthRoutes(app: FastifyInstance) {
  const outreach = new OutreachService()
  const google = new GoogleStackService()

  app.get('/api/health', async () => {
    return {
      ok: true,
      service: 'forge-os-backend',
      env: env.NODE_ENV,
      timestamp: new Date().toISOString(),
      storage: runtimeStore.storage,
      scheduler: getSchedulerStatus(),
    }
  })

  app.get('/api/supabase/health', async () => {
    return checkSupabase()
  })

  app.get('/api/readiness', async () => {
    const [readiness, supabase] = await Promise.all([outreach.readiness(), checkSupabase()])
    const providers = {
      ...readiness.providers,
      supabase,
    }
    const ok = Object.values(providers).every((provider) => provider.ok)

    return {
      ok,
      service: 'forge-os-backend',
      env: env.NODE_ENV,
      timestamp: new Date().toISOString(),
      storage: runtimeStore.storage,
      providers,
    }
  })

  app.get('/api/system/readiness/details', async () => {
    const [providerReadiness, googleReadiness, schema] = await Promise.all([
      outreach.readiness(),
      google.readiness(),
      checkSchemaReadiness(),
    ])

    const queue = geminiQueueStatus()
    const blockedReasons: string[] = []
    for (const [name, status] of Object.entries(providerReadiness.providers)) {
      if (!status.ok) blockedReasons.push(`${name}:${status.status}`)
    }
    if (!googleReadiness.ok) blockedReasons.push('google_stack:not_ready')
    if (!schema.ok) blockedReasons.push(`schema:${schema.missingTables.join(',')}`)
    if (queue.deadLetters.length) blockedReasons.push('gemini_dead_letters_present')

    return {
      ok: blockedReasons.length === 0,
      providerReadiness: {
        ...providerReadiness.providers,
        google: googleReadiness,
      },
      schemaReadiness: schema,
      queueStatus: queue,
      outboundPolicy: outboundPolicy(),
      blockedReasons,
    }
  })

  app.get('/api/system/migrations/checklist', async () => {
    const [schema, checklist] = await Promise.all([checkSchemaReadiness(), Promise.resolve(migrationChecklist())])
    return {
      ok: schema.ok,
      schemaStatus: schema.status,
      missingTables: schema.missingTables,
      ...checklist,
    }
  })

  // CEU Runtime topology — full system survivability snapshot
  app.get('/api/system/ceu', async () => {
    const [topology, cache, learning] = await Promise.all([
      Promise.resolve(getSystemTopology()),
      Promise.resolve(getCacheStatus()),
      getLearningDigest(),
    ])

    return {
      ok: true,
      ceuRuntime: {
        cognitionDensity: topology.cognitionDensity,
        globalSurvivalScore: topology.globalSurvivalScore,
        entropyPressure: topology.entropyPressure,
        totalExecutions: topology.totalExecutions,
        totalContradictions: topology.totalContradictions,
        nodes: Object.entries(topology.nodes).map(([id, node]) => ({
          agentId: id,
          state: node.state,
          activeCount: node.activeCount,
          successCount: node.successCount,
          failureCount: node.failureCount,
          avgLatencyMs: Math.round(node.avgLatencyMs),
          survivalScore: Number(node.survivalScore.toFixed(2)),
          lastExecutionAt: node.lastExecutionAt,
        })),
        at: topology.at,
      },
      responseCache: cache,
      crlLearning: learning,
    }
  })
}
