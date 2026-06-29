import { createHash } from 'node:crypto'
import { env, geminiApiKeyFor, type GeminiAgentRole } from '../config/env.js'
import { outboundFetch } from './network.js'
import { writeAudit } from './auditLog.js'

export type GeminiRequest = {
  role: GeminiAgentRole | string
  contents: Array<{ role?: string; parts: Array<{ text: string }> }>
  systemInstruction?: { parts: Array<{ text: string }> }
  generationConfig?: {
    temperature?: number
    maxOutputTokens?: number
    responseMimeType?: string
  }
}

export type GeminiCallMeta = {
  queued: boolean
  queueWaitMs: number
  attemptCount: number
  keyRoleUsed: string
  keyFingerprint: string
  fallbackMode: 'none' | 'role_fallback' | 'global_fallback' | 'hf_fallback'
  fallbackReason: string | null
}

type GeminiRawResponse = {
  candidates?: Array<{ content?: { parts?: Array<{ text?: string }> } }>
  error?: { code?: number; message?: string; details?: Array<{ retryDelay?: string }> }
}

type HuggingFaceChatResponse = {
  choices?: Array<{ message?: { content?: string } }>
  error?: { message?: string } | string
}

type CircuitState = {
  openUntil: number
  consecutive429: number
}

const roleFallback: Record<string, GeminiAgentRole> = {
  jarvis: 'king',
  noah: 'jarvis',
  devan: 'noah',
  damien: 'jarvis',
  zoya: 'king',
  akhil: 'jarvis',
  king: 'jarvis',
}

const laneChains = new Map<string, Promise<void>>()
const lanePending = new Map<string, number>()
const keyCircuit = new Map<string, CircuitState>()
const deadLetters: Array<{ at: string; role: string; reason: string; requestHash: string }> = []

function sleep(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms))
}

function retryDelayMs(raw?: string) {
  if (!raw) return env.GEMINI_INITIAL_WAIT_MS
  const value = Number.parseFloat(raw.replace('s', '').trim())
  if (!Number.isFinite(value)) return env.GEMINI_INITIAL_WAIT_MS
  return Math.max(env.GEMINI_INITIAL_WAIT_MS, Math.ceil(value * 1000))
}

function normalizeRole(role: GeminiAgentRole | string) {
  return String(role).trim().toLowerCase().replace(/[\s-]+/g, '_')
}

function keyFingerprint(key: string) {
  return createHash('sha256').update(key).digest('hex').slice(0, 12)
}

function requestHash(payload: unknown) {
  return createHash('sha256').update(JSON.stringify(payload)).digest('hex').slice(0, 16)
}

function candidateKeys(role: string) {
  const primary = geminiApiKeyFor(role)
  const secondaryRole = roleFallback[role]
  const secondary = secondaryRole ? geminiApiKeyFor(secondaryRole) : undefined
  const global = env.GEMINI_API_KEY

  const list = [primary, secondary, global].filter((value, idx, arr): value is string => Boolean(value) && arr.indexOf(value) === idx)

  return list.map((key) => ({
    key,
    mode:
      key === primary
        ? ('none' as const)
        : key === secondary
          ? ('role_fallback' as const)
          : ('global_fallback' as const),
    keyRoleUsed: key === primary ? role : key === secondary ? (secondaryRole ?? 'unknown') : 'global',
  }))
}

function huggingFaceEnabled() {
  return Boolean(env.HF_TOKEN?.trim())
}

function huggingFaceModel() {
  const model = env.HF_MODEL.trim()
  const provider = env.HF_PROVIDER.trim()
  if (!provider || provider === 'auto') return `${model}:fastest`
  return `${model}:${provider}`
}

function toChatMessages(request: GeminiRequest) {
  const messages: Array<{ role: 'system' | 'user' | 'assistant'; content: string }> = []
  if (request.systemInstruction?.parts?.length) {
    messages.push({
      role: 'system',
      content: request.systemInstruction.parts.map((part) => part.text).join('\n\n'),
    })
  }
  for (const message of request.contents) {
    messages.push({
      role: message.role === 'model' ? 'assistant' : 'user',
      content: message.parts.map((part) => part.text).join('\n\n'),
    })
  }
  return messages
}

async function sendGeminiRequest(key: string, request: GeminiRequest) {
  const body = {
    contents: request.contents,
    ...(request.systemInstruction ? { system_instruction: request.systemInstruction } : {}),
    generationConfig: request.generationConfig ?? { temperature: 0.7, maxOutputTokens: 1200 },
  }

  const response = await outboundFetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${env.GEMINI_MODEL}:generateContent?key=${key}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  )

  const json = (await response.json()) as GeminiRawResponse
  return { response, json }
}

async function sendHuggingFaceRequest(request: GeminiRequest) {
  const response = await outboundFetch('https://router.huggingface.co/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${env.HF_TOKEN}`,
    },
    body: JSON.stringify({
      model: huggingFaceModel(),
      messages: toChatMessages(request),
      temperature: request.generationConfig?.temperature ?? 0.7,
      max_tokens: request.generationConfig?.maxOutputTokens ?? 1200,
      ...(request.generationConfig?.responseMimeType === 'application/json'
        ? { response_format: { type: 'json_object' } }
        : {}),
    }),
  })

  const json = (await response.json()) as HuggingFaceChatResponse
  return { response, json }
}

async function executeWithHuggingFace(request: GeminiRequest, fallbackReason: string | null): Promise<{ text: string; meta: GeminiCallMeta }> {
  if (!huggingFaceEnabled()) {
    throw new Error('hf_missing_token')
  }

  const hfResult = await sendHuggingFaceRequest(request)
  if (!hfResult.response.ok) {
    const hfMessage = typeof hfResult.json.error === 'string'
      ? hfResult.json.error
      : hfResult.json.error?.message ?? 'unknown'
    throw new Error(`hf_error:${hfResult.response.status}:${hfMessage}`)
  }

  const text = hfResult.json.choices?.[0]?.message?.content?.trim()
  if (!text) {
    throw new Error('hf_empty_response')
  }

  return {
    text,
    meta: {
      queued: false,
      queueWaitMs: 0,
      attemptCount: 1,
      keyRoleUsed: 'huggingface',
      keyFingerprint: keyFingerprint(env.HF_TOKEN ?? ''),
      fallbackMode: 'hf_fallback',
      fallbackReason,
    },
  }
}

async function executeWithRetry(role: string, request: GeminiRequest): Promise<{ text: string; meta: GeminiCallMeta }> {
  const keys = candidateKeys(role)
  if (!keys.length) {
    throw new Error(`gemini_missing_key:${role}`)
  }

  let attempt = 0
  let fallbackReason: string | null = null
  let lastError = 'unknown'
  const maxAttempts = Math.max(env.GEMINI_MAX_RETRIES, 1)
  const startedAt = Date.now()
  const maxTotalWaitMs = 120000
  let waitedFor429 = false

  for (let cycle = 0; cycle < maxAttempts; cycle += 1) {
    for (const candidate of keys) {
      const fingerprint = keyFingerprint(candidate.key)
      const circuit = keyCircuit.get(fingerprint) ?? { openUntil: 0, consecutive429: 0 }
      if (circuit.openUntil > Date.now()) {
        fallbackReason = `circuit_open:${candidate.keyRoleUsed}`
        continue
      }

      attempt += 1
      const { response, json } = await sendGeminiRequest(candidate.key, request)

      if (response.ok) {
        const text = json.candidates?.[0]?.content?.parts?.[0]?.text
        if (!text) {
          lastError = 'gemini_empty_response'
          continue
        }

        keyCircuit.set(fingerprint, { openUntil: 0, consecutive429: 0 })
        return {
          text,
          meta: {
            queued: false,
            queueWaitMs: 0,
            attemptCount: attempt,
            keyRoleUsed: candidate.keyRoleUsed,
            keyFingerprint: fingerprint,
            fallbackMode: candidate.mode,
            fallbackReason,
          },
        }
      }

      if (response.status === 429) {
        const retryAfter = retryDelayMs(json.error?.details?.[0]?.retryDelay)
        const next429 = (circuit.consecutive429 ?? 0) + 1
        const backoff = Math.min(
          Math.ceil(retryAfter * Math.pow(2, Math.max(0, next429 - 1)) + Math.random() * 1000),
          120000,
        )
        keyCircuit.set(fingerprint, {
          consecutive429: next429,
          openUntil: Date.now() + backoff,
        })
        fallbackReason = `rate_limited:${candidate.keyRoleUsed}`
        lastError = `429_${candidate.keyRoleUsed}`
        if (Date.now() - startedAt > maxTotalWaitMs) {
          throw new Error(`gemini_timeout_budget_exceeded:${lastError}`)
        }
        if (!waitedFor429) {
          waitedFor429 = true
          await sleep(backoff)
        }
        continue
      }

      if (response.status >= 500) {
        fallbackReason = `provider_5xx:${candidate.keyRoleUsed}`
        lastError = `http_${response.status}`
        await sleep(800 + Math.floor(Math.random() * 400))
        continue
      }

      throw new Error(`gemini_error:${response.status}:${json.error?.message ?? 'unknown'}`)
    }
  }

  const hash = requestHash({ role, contents: request.contents })
  deadLetters.push({ at: new Date().toISOString(), role, reason: lastError, requestHash: hash })
  if (deadLetters.length > 100) deadLetters.shift()
  throw new Error(`gemini_exhausted_retries:${lastError}`)
}

class GeminiExecutionService {
  async execute(request: GeminiRequest): Promise<{ text: string; meta: GeminiCallMeta }> {
    const role = normalizeRole(request.role)
    const lane = role
    const chain = laneChains.get(lane) ?? Promise.resolve()
    const pendingNow = lanePending.get(lane) ?? 0
    lanePending.set(lane, pendingNow + 1)

    const startedAt = Date.now()
    let release: () => void = () => {}
    const gate = new Promise<void>((resolve) => { release = resolve })
    laneChains.set(lane, chain.then(() => gate))

    await chain
    const queueWaitMs = Date.now() - startedAt
    const queued = pendingNow > 0

    try {
      let result: { text: string; meta: GeminiCallMeta }
      if (huggingFaceEnabled()) {
        try {
          result = await executeWithHuggingFace(request, null)
        } catch (hfError) {
          const hfReason = hfError instanceof Error ? hfError.message : String(hfError)
          result = await executeWithRetry(role, request).catch(async (geminiError) => {
            const geminiReason = geminiError instanceof Error ? geminiError.message : String(geminiError)
            throw new Error(`llm_dual_failure:hf=${hfReason};gemini=${geminiReason}`)
          })
          result.meta = {
            ...result.meta,
            fallbackReason: hfReason,
          }
        }
      } else {
        try {
          result = await executeWithRetry(role, request)
        } catch (error) {
          if (!huggingFaceEnabled()) throw error
          const reason = error instanceof Error ? error.message : String(error)
          result = await executeWithHuggingFace(request, reason)
        }
      }

      const meta = {
        ...result.meta,
        queued,
        queueWaitMs,
      }
      writeAudit({
        actor: role,
        action: 'llm_execute',
        purpose: 'llm_generation',
        result: 'ok',
        metadata: {
          attemptCount: meta.attemptCount,
          fallbackMode: meta.fallbackMode,
          queueWaitMs: meta.queueWaitMs,
          keyRoleUsed: meta.keyRoleUsed,
          fallbackReason: meta.fallbackReason,
        },
      })
      return { text: result.text, meta }
    } catch (error) {
      writeAudit({
        actor: role,
        action: 'llm_execute',
        purpose: 'llm_generation',
        result: 'error',
        detail: error instanceof Error ? error.message : String(error),
      })
      throw error
    } finally {
      const current = lanePending.get(lane) ?? 1
      lanePending.set(lane, Math.max(0, current - 1))
      release()
    }
  }

  status() {
    const queue = Array.from(lanePending.entries()).map(([lane, pending]) => ({ lane, pending }))
    return {
      queue,
      deadLetters: deadLetters.slice(-20),
      circuitBreakers: Array.from(keyCircuit.entries()).map(([fingerprint, state]) => ({
        keyFingerprint: fingerprint,
        openUntil: state.openUntil,
        remainingMs: Math.max(0, state.openUntil - Date.now()),
        consecutive429: state.consecutive429,
      })),
    }
  }
}

const geminiService = new GeminiExecutionService()

export function geminiQueueStatus() {
  return geminiService.status()
}

export async function callGeminiDetailed(request: GeminiRequest) {
  return geminiService.execute(request)
}

export async function callGemini(request: GeminiRequest): Promise<string> {
  const result = await geminiService.execute(request)
  return result.text
}

export async function callGeminiSimple(
  role: GeminiAgentRole | string,
  prompt: string,
  options: { temperature?: number; maxOutputTokens?: number; jsonMode?: boolean } = {},
): Promise<string | null> {
  try {
    const result = await geminiService.execute({
      role,
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: {
        temperature: options.temperature ?? 0.7,
        maxOutputTokens: options.maxOutputTokens ?? 1200,
        ...(options.jsonMode ? { responseMimeType: 'application/json' } : {}),
      },
    })
    return result.text
  } catch {
    return null
  }
}
