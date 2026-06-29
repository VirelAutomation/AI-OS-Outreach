import { resolve } from 'node:path'
import { loadPersistedState, persistState } from './cloudState.js'
import type { GoogleProfile } from '../services/googleStack.service.js'

type GoogleTokenState = {
  primary?: { refreshToken?: string; updatedAt?: string }
  backup?: { refreshToken?: string; updatedAt?: string }
}

const storeKey = 'google_oauth_tokens'
const storePath = resolve(process.cwd(), 'data', 'google-oauth-tokens.json')
const defaultState: GoogleTokenState = {}
const state: GoogleTokenState = {}

export async function initGoogleTokenStore() {
  const loaded = await loadPersistedState(storeKey, defaultState, storePath)
  Object.assign(state, loaded.value ?? {})
}

export async function saveGoogleRefreshToken(profile: GoogleProfile, refreshToken: string) {
  state[profile] = {
    refreshToken,
    updatedAt: new Date().toISOString(),
  }
  await persistState(storeKey, state, storePath)
}

export function getGoogleRefreshToken(profile: GoogleProfile) {
  return state[profile]?.refreshToken
}

export function googleTokenStoreStatus() {
  return {
    key: storeKey,
    configuredProfiles: (['primary', 'backup'] as GoogleProfile[]).filter((profile) => Boolean(state[profile]?.refreshToken)),
  }
}
