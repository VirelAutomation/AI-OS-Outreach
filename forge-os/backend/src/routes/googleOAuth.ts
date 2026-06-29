import type { FastifyInstance } from 'fastify'
import { z } from 'zod'
import { env } from '../config/env.js'
import { saveGoogleRefreshToken } from '../lib/googleTokenStore.js'
import { outboundFetch } from '../lib/network.js'
import { redactSensitive } from '../lib/security.js'
import { GoogleStackService, type GoogleProfile } from '../services/googleStack.service.js'

const profileSchema = z.enum(['primary', 'backup']).catch('primary')

function resolveProfile(query: unknown): GoogleProfile {
  const value = (query as { profile?: string } | undefined)?.profile
  return profileSchema.parse(value ?? 'primary')
}

function profileCredentials(profile: GoogleProfile) {
  if (profile === 'backup') {
    return {
      clientId: env.GOOGLE_CLIENT_ID_BACKUP ?? env.GOOGLE_CLIENT_ID,
      clientSecret: env.GOOGLE_CLIENT_SECRET_BACKUP ?? env.GOOGLE_CLIENT_SECRET,
      redirectUri: env.GOOGLE_REDIRECT_URI_BACKUP ?? env.GOOGLE_REDIRECT_URI,
    }
  }

  return {
    clientId: env.GOOGLE_CLIENT_ID,
    clientSecret: env.GOOGLE_CLIENT_SECRET,
    redirectUri: env.GOOGLE_REDIRECT_URI,
  }
}

function tokenEnvVar(profile: GoogleProfile) {
  return profile === 'backup' ? 'GMAIL_REFRESH_TOKEN_BACKUP' : 'GMAIL_REFRESH_TOKEN'
}

export async function registerGoogleOAuthRoutes(app: FastifyInstance) {
  const google = new GoogleStackService()

  app.get('/api/google/oauth/start', async (request, reply) => {
    const profile = resolveProfile(request.query)
    const creds = profileCredentials(profile)
    if (!creds.clientId || !creds.redirectUri) {
      return reply.code(503).send({
        ok: false,
        error: 'missing_config',
        message: `Set GOOGLE_CLIENT_ID${profile === 'backup' ? '_BACKUP' : ''} and GOOGLE_REDIRECT_URI${profile === 'backup' ? '_BACKUP' : ''}.`,
      })
    }

    const params = new URLSearchParams({
      client_id: creds.clientId,
      redirect_uri: creds.redirectUri,
      response_type: 'code',
      scope: 'https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/calendar',
      access_type: 'offline',
      prompt: 'consent',
      state: profile,
    })

    return reply.redirect(`https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`)
  })

  app.get('/api/google/oauth/callback', async (request, reply) => {
    const { code, error, state } = request.query as { code?: string; error?: string; state?: string }
    const profile = profileSchema.parse(state ?? 'primary')
    const creds = profileCredentials(profile)

    if (error) {
      return reply.code(400).send({ ok: false, error, message: 'Google OAuth denied or failed.' })
    }
    if (!code) {
      return reply.code(400).send({ ok: false, error: 'missing_code', message: 'No code returned from Google.' })
    }
    if (!creds.clientId || !creds.clientSecret || !creds.redirectUri) {
      return reply.code(503).send({
        ok: false,
        error: 'missing_config',
        message: `Missing profile credentials for ${profile}.`,
      })
    }

    const body = new URLSearchParams({
      code,
      client_id: creds.clientId,
      client_secret: creds.clientSecret,
      redirect_uri: creds.redirectUri,
      grant_type: 'authorization_code',
    })

    const response = await outboundFetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    })

    const json = (await response.json()) as {
      access_token?: string
      refresh_token?: string
      error?: string
      error_description?: string
    }

    if (!response.ok || json.error) {
      return reply.code(400).send({
        ok: false,
        error: json.error ?? 'token_exchange_failed',
        message: redactSensitive(json.error_description ?? 'Could not exchange code for tokens.'),
      })
    }

    const hasRefresh = Boolean(json.refresh_token)
    const masked = hasRefresh ? `${json.refresh_token!.slice(0, 6)}...${json.refresh_token!.slice(-4)}` : null
    if (json.refresh_token) {
      await saveGoogleRefreshToken(profile, json.refresh_token)
      ;((env as unknown) as Record<string, string | undefined>)[tokenEnvVar(profile)] = json.refresh_token
    }

    return reply.type('text/html').send(`
      <!DOCTYPE html>
      <html>
        <head><title>Google OAuth Complete</title></head>
        <body style="font-family: Arial, sans-serif; background: #090909; color: #f3f3f3; padding: 32px;">
          <div style="max-width:700px;border:1px solid #2a2a2a;background:#111;padding:24px;border-radius:10px;">
            <h2 style="margin-top:0;color:#10b981;">Google OAuth Completed (${profile})</h2>
            <p>Token exchange succeeded. Sensitive token values are intentionally hidden.</p>
            <p>${hasRefresh ? `Saved <code>${tokenEnvVar(profile)}</code> into the cloud runtime store.` : `No refresh token was returned, so <code>${tokenEnvVar(profile)}</code> could not be saved.`}</p>
            <p>Refresh token detected: <strong>${masked ?? 'No (re-consent required)'}</strong></p>
            <p>Verify <code>/api/google/readiness</code> and then run <code>/api/outreach/sync-replies</code>.</p>
          </div>
        </body>
      </html>
    `)
  })

  app.get('/api/google/oauth/status', async (request) => {
    const profile = resolveProfile(request.query)
    const tokenHealth = await google.getTokenHealth()
    return {
      ok: true,
      profile,
      activeProfile: tokenHealth.activeProfile,
      configured: {
        primary: await google.getProfileConfig('primary'),
        backup: await google.getProfileConfig('backup'),
      },
      tokenHealth: tokenHealth.tokenHealth,
      startUrl: `/api/google/oauth/start?profile=${profile}`,
      instruction: 'Use profile-specific OAuth start URL and then check /api/google/readiness.',
    }
  })
}
