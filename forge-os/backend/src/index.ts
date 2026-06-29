import { buildApp } from './app.js'
import { env } from './config/env.js'

const app = await buildApp()
let shuttingDown = false

async function shutdown(signal: string) {
  if (shuttingDown) return
  shuttingDown = true
  app.log.info({ signal }, 'shutdown_requested')
  try {
    await app.close()
    process.exit(0)
  } catch (error) {
    app.log.error({ err: error, signal }, 'shutdown_failed')
    process.exit(1)
  }
}

process.on('SIGINT', () => {
  void shutdown('SIGINT')
})

process.on('SIGTERM', () => {
  void shutdown('SIGTERM')
})

app
  .listen({
    port: env.PORT,
    host: '0.0.0.0',
  })
  .then(() => {
    app.log.info(`FORGE OS backend listening on ${env.PORT}`)
  })
  .catch((error) => {
    app.log.error(error)
    process.exit(1)
  })
