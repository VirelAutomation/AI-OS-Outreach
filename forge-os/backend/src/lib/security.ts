import type { FastifyReply, FastifyRequest } from 'fastify'
import { env } from '../config/env.js'
import { createHmac, timingSafeEqual } from 'node:crypto'

const buckets = new Map<string, { count: number; resetAt: number }>()

function readProvidedApiKey(request: FastifyRequest) {
  return String(request.headers['x-api-key'] ?? request.headers['x-backend-api-key'] ?? '')
}

function getClientKey(request: FastifyRequest) {
  const ip = request.ip ?? 'unknown'
  const apiKey = readProvidedApiKey(request)
  return `${ip}:${apiKey}`
}

export function enforceApiKey(request: FastifyRequest, reply: FastifyReply) {
  const requireStrict = env.NODE_ENV === 'production' || env.REQUIRE_API_KEY
  if (!requireStrict) return
  const provided = readProvidedApiKey(request)
  if (provided && env.BACKEND_API_KEY && safeEquals(provided, env.BACKEND_API_KEY)) {
    return
  }

  const signature = String(request.headers['x-service-signature'] ?? '')
  const timestamp = String(request.headers['x-service-timestamp'] ?? '')
  if (env.BACKEND_API_KEY && verifyServiceSignature(request.method, request.url, timestamp, signature, env.BACKEND_API_KEY)) {
    return
  }

  if (request.url.startsWith('/api/public/')) return

  if (!provided || provided !== env.BACKEND_API_KEY) {
    reply.code(401).send({ ok: false, error: 'unauthorized' })
  }
}

export function enforceRateLimit(request: FastifyRequest, reply: FastifyReply) {
  const now = Date.now()
  const key = getClientKey(request)
  const current = buckets.get(key)
  if (!current || now > current.resetAt) {
    buckets.set(key, { count: 1, resetAt: now + env.RATE_LIMIT_WINDOW_MS })
    return
  }
  current.count += 1
  if (current.count > env.RATE_LIMIT_MAX_REQUESTS) {
    const retryAfter = Math.ceil((current.resetAt - now) / 1000)
    reply
      .code(429)
      .header('Retry-After', retryAfter)
      .send({ ok: false, error: 'rate_limit_exceeded', retryAfterSeconds: retryAfter })
  }
}

function verifyServiceSignature(method: string, url: string, timestamp: string, signature: string, secret: string) {
  if (!timestamp || !signature) return false
  const age = Math.abs(Date.now() - Number(timestamp))
  if (!Number.isFinite(age) || age > 5 * 60 * 1000) return false
  const payload = `${method.toUpperCase()}:${url}:${timestamp}`
  const digest = createHmac('sha256', secret).update(payload).digest('hex')
  return safeEquals(digest, signature)
}

function safeEquals(left: string, right: string) {
  if (left.length !== right.length) return false
  return timingSafeEqual(Buffer.from(left), Buffer.from(right))
}

export function redactSensitive(input: string) {
  return input
    .replace(/(Bearer\s+)[A-Za-z0-9._-]+/gi, '$1[redacted]')
    .replace(/(token|secret|key)=([^&\s]+)/gi, '$1=[redacted]')
    .replace(/[A-Za-z0-9_-]{32,}/g, '[redacted]')
}
