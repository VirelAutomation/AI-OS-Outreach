import cors from '@fastify/cors'
import Fastify from 'fastify'
import { env } from './config/env.js'
import { initAuditLog } from './lib/auditLog.js'
import { cmoArtifactStore } from './lib/cmoArtifactStore.js'
import { initCrlLearning } from './lib/crlLearning.js'
import { initGoogleTokenStore } from './lib/googleTokenStore.js'
import { jarvisStateStore } from './lib/jarvisStateStore.js'
import { enforceApiKey, enforceRateLimit, redactSensitive } from './lib/security.js'
import { initScheduler } from './lib/scheduler.js'
import { checkSchemaReadiness } from './lib/schemaReadiness.js'
import { runtimeStore } from './lib/runtimeStore.js'
import { registerAnalyticsRoutes } from './routes/analytics.js'
import { registerCrmRoutes } from './routes/crm.js'
import { registerCtoRoutes } from './routes/cto.js'
import { registerHealthRoutes } from './routes/health.js'
import { registerJarvisRoutes } from './routes/jarvis.js'
import { registerLeadManagementRoutes } from './routes/leadManagement.js'
import { registerJarvisSovereignRoutes } from './routes/jarvisSovereign.js'
import { registerMeetingRoutes } from './routes/meetings.js'
import { registerOrchestratorRoutes } from './routes/orchestrator.js'
import { registerOutreachRoutes } from './routes/outreach.js'
import { registerCMORoutes } from './routes/cmo.js'
import { registerCalendarRoutes } from './routes/calendar.js'
import { registerGoogleOAuthRoutes } from './routes/googleOAuth.js'
import { registerGoogleRoutes } from './routes/google.js'
import { registerPublicRoutes } from './routes/public.js'
import { registerSSERoutes } from './routes/sse.js'
import { registerSocialOutreachRoutes } from './routes/socialOutreach.js'

export async function buildApp() {
  await Promise.all([
    runtimeStore.init(),
    cmoArtifactStore.init(),
    jarvisStateStore.init(),
    initAuditLog(),
    initCrlLearning(),
    initGoogleTokenStore(),
  ])

  const app = Fastify({ logger: true })

  app.setErrorHandler((error, request, reply) => {
    request.log.error({ err: error }, 'unhandled_error')
    if (reply.sent) return
    const message = error instanceof Error ? redactSensitive(error.message) : redactSensitive(String(error))
    reply.code(500).send({
      ok: false,
      error: 'internal_server_error',
      message: env.NODE_ENV === 'production' ? 'Unexpected server error.' : message,
    })
  })

  app.addHook('onRequest', async (request, reply) => {
    enforceRateLimit(request, reply)
    if (reply.sent) return
    enforceApiKey(request, reply)
  })

  const origins = env.ALLOWED_ORIGINS
    ? env.ALLOWED_ORIGINS.split(',').map((x) => x.trim()).filter(Boolean)
    : [env.FRONTEND_ORIGIN, 'http://localhost:5173']

  await app.register(cors, {
    origin: origins,
    credentials: true,
  })

  await registerHealthRoutes(app)
  await registerCrmRoutes(app)
  await registerCtoRoutes(app)
  await registerOutreachRoutes(app)
  await registerMeetingRoutes(app)
  await registerAnalyticsRoutes(app)
  await registerJarvisRoutes(app)
  await registerLeadManagementRoutes(app)
  await registerJarvisSovereignRoutes(app)
  await registerCMORoutes(app)
  await registerCalendarRoutes(app)
  await registerGoogleRoutes(app)
  await registerGoogleOAuthRoutes(app)
  await registerPublicRoutes(app)
  await registerOrchestratorRoutes(app)
  await registerSSERoutes(app)
  await registerSocialOutreachRoutes(app)

  // Run schema readiness in the background so local/dev boot and deploy health checks are not blocked
  // on a long chain of remote Supabase table probes.
  void checkSchemaReadiness()
    .then((schema) => {
      if (!schema.ok) {
        app.log.warn({ missingTables: schema.missingTables, status: schema.status }, 'schema_guard_not_ready')
      }
    })
    .catch((error) => {
      app.log.warn({ err: error }, 'schema_guard_check_failed')
    })

  // Start background scheduler (runs in production or when ENABLE_SCHEDULER=true)
  await initScheduler()

  return app
}

