import { env } from '../config/env.js'

const allowlist = env.API_OUTBOUND_ALLOWLIST.split(',')
  .map((value) => value.trim().toLowerCase())
  .filter(Boolean)

function isHostAllowed(hostname: string) {
  const normalized = hostname.toLowerCase()
  return allowlist.some((allowed) => normalized === allowed || normalized.endsWith(`.${allowed}`))
}

function timeoutSignal(timeoutMs: number) {
  if (typeof AbortSignal !== 'undefined' && 'timeout' in AbortSignal) {
    return AbortSignal.timeout(timeoutMs)
  }

  const controller = new AbortController()
  setTimeout(() => controller.abort(new Error(`timeout_${timeoutMs}ms`)), timeoutMs)
  return controller.signal
}

export async function outboundFetch(input: string, init?: RequestInit) {
  const url = new URL(input)
  if (!isHostAllowed(url.hostname)) {
    throw new Error(`outbound_host_blocked:${url.hostname}`)
  }

  return fetch(input, {
    ...init,
    signal: init?.signal ?? timeoutSignal(env.API_OUTBOUND_TIMEOUT_MS),
  })
}

export function outboundPolicy() {
  return {
    timeoutMs: env.API_OUTBOUND_TIMEOUT_MS,
    allowlist,
  }
}
