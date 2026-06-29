import { env } from '../config/env.js'
import { getGoogleRefreshToken } from '../lib/googleTokenStore.js'
import { outboundFetch } from '../lib/network.js'

export type GoogleProfile = 'primary' | 'backup'

type GoogleProfileConfig = {
  clientId?: string
  clientSecret?: string
  redirectUri?: string
  refreshToken?: string
  senderEmail?: string
}

type TokenHealth = {
  profile: GoogleProfile
  configured: boolean
  ok: boolean
  reason: string
  expiresInSeconds?: number
}

async function profileConfig(profile: GoogleProfile): Promise<GoogleProfileConfig> {
  if (profile === 'backup') {
    return {
      clientId: env.GOOGLE_CLIENT_ID_BACKUP ?? env.GOOGLE_CLIENT_ID,
      clientSecret: env.GOOGLE_CLIENT_SECRET_BACKUP ?? env.GOOGLE_CLIENT_SECRET,
      redirectUri: env.GOOGLE_REDIRECT_URI_BACKUP ?? env.GOOGLE_REDIRECT_URI,
      refreshToken: getGoogleRefreshToken('backup') ?? env.GMAIL_REFRESH_TOKEN_BACKUP ?? env.GMAIL_REFRESH_TOKEN,
      senderEmail: env.GMAIL_SENDER_EMAIL_BACKUP ?? env.GMAIL_SENDER_EMAIL,
    }
  }

  return {
    clientId: env.GOOGLE_CLIENT_ID,
    clientSecret: env.GOOGLE_CLIENT_SECRET,
    redirectUri: env.GOOGLE_REDIRECT_URI,
    refreshToken: getGoogleRefreshToken('primary') ?? env.GMAIL_REFRESH_TOKEN,
    senderEmail: env.GMAIL_SENDER_EMAIL,
  }
}

export class GoogleStackService {
  async refreshAccessToken(profile: GoogleProfile): Promise<{ ok: boolean; accessToken?: string; expiresIn?: number; reason?: string }> {
    const cfg = await profileConfig(profile)
    if (!cfg.clientId || !cfg.clientSecret || !cfg.refreshToken) {
      return { ok: false, reason: 'missing_config' }
    }

    const body = new URLSearchParams({
      client_id: cfg.clientId,
      client_secret: cfg.clientSecret,
      refresh_token: cfg.refreshToken,
      grant_type: 'refresh_token',
    })

    const response = await outboundFetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    })

    if (!response.ok) {
      const error = await response.text()
      return { ok: false, reason: `token_refresh_failed:${response.status}:${error.slice(0, 160)}` }
    }

    const payload = (await response.json()) as { access_token?: string; expires_in?: number }
    if (!payload.access_token) return { ok: false, reason: 'token_missing' }
    return { ok: true, accessToken: payload.access_token, expiresIn: payload.expires_in ?? 0 }
  }

  async resolveActiveProfile() {
    const preferred = env.GOOGLE_ACTIVE_PROFILE
    const profiles: GoogleProfile[] = preferred === 'backup' ? ['backup', 'primary'] : ['primary', 'backup']

    for (const profile of profiles) {
      const token = await this.refreshAccessToken(profile)
      if (token.ok) return { profile, token }
      if (!env.GOOGLE_PROFILE_FAILOVER_ENABLED) return { profile, token }
    }

    return { profile: preferred, token: await this.refreshAccessToken(preferred) }
  }

  async getTokenHealth(): Promise<{ activeProfile: GoogleProfile; tokenHealth: TokenHealth[] }> {
    const checks = await Promise.all((['primary', 'backup'] as GoogleProfile[]).map(async (profile) => {
      const cfg = await profileConfig(profile)
      const token = await this.refreshAccessToken(profile)
      return {
        profile,
        configured: Boolean(cfg.clientId && cfg.clientSecret && cfg.refreshToken),
        ok: token.ok,
        reason: token.ok ? 'ready' : (token.reason ?? 'unknown'),
        expiresInSeconds: token.expiresIn,
      } satisfies TokenHealth
    }))

    const active = await this.resolveActiveProfile()
    return { activeProfile: active.profile, tokenHealth: checks }
  }

  async readiness() {
    const profile = await this.resolveActiveProfile()
    const accessToken = profile.token.ok ? profile.token.accessToken : undefined
    const activeCfg = await profileConfig(profile.profile)

    const gmail = await this.gmailProbe(accessToken)
    const calendar = await this.calendarProbe(accessToken)
    const maps = await this.mapsProbe()
    const tokenHealth = await this.getTokenHealth()

    return {
      ok: gmail.ok && calendar.ok && maps.ok,
      activeProfile: profile.profile,
      senderEmail: activeCfg.senderEmail ?? null,
      gmail,
      calendar,
      maps,
      tokenHealth,
    }
  }

  async getProfileConfig(profile: GoogleProfile) {
    const cfg = await profileConfig(profile)
    return {
      clientId: Boolean(cfg.clientId),
      clientSecret: Boolean(cfg.clientSecret),
      redirectUri: cfg.redirectUri ?? null,
      refreshToken: Boolean(cfg.refreshToken),
      senderEmail: cfg.senderEmail ?? null,
    }
  }

  private async gmailProbe(accessToken?: string) {
    if (!accessToken) return { configured: false, ok: false, status: 'missing_token', message: 'No valid Gmail token.' }
    const response = await outboundFetch('https://gmail.googleapis.com/gmail/v1/users/me/profile', {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    return response.ok
      ? { configured: true, ok: true, status: 'ready', message: 'Gmail reachable.' }
      : { configured: true, ok: false, status: `http_${response.status}`, message: await response.text() }
  }

  private async calendarProbe(accessToken?: string) {
    if (!accessToken) return { configured: false, ok: false, status: 'missing_token', message: 'No valid Calendar token.' }
    const response = await outboundFetch('https://www.googleapis.com/calendar/v3/users/me/calendarList?maxResults=1', {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    return response.ok
      ? { configured: true, ok: true, status: 'ready', message: 'Calendar reachable.' }
      : { configured: true, ok: false, status: `http_${response.status}`, message: await response.text() }
  }

  private async mapsProbe() {
    if (!env.GOOGLE_MAPS_API_KEY) {
      return { configured: false, ok: false, status: 'missing_config', message: 'GOOGLE_MAPS_API_KEY is not set.' }
    }

    const url = `https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent('Bangalore India')}&key=${env.GOOGLE_MAPS_API_KEY}`
    const response = await outboundFetch(url)
    if (!response.ok) {
      return { configured: true, ok: false, status: `http_${response.status}`, message: await response.text() }
    }

    const payload = (await response.json()) as { status?: string; error_message?: string }
    if (payload.status !== 'OK' && payload.status !== 'ZERO_RESULTS') {
      return {
        configured: true,
        ok: false,
        status: payload.status ?? 'error',
        message: payload.error_message ?? 'Maps probe failed.',
      }
    }
    return { configured: true, ok: true, status: 'ready', message: 'Maps key is valid.' }
  }
}
