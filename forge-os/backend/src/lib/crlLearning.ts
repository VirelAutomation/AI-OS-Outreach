import { resolve } from 'node:path'
import { getSupabaseAdmin } from './supabaseAdmin.js'
import { writeAudit } from './auditLog.js'
import { loadPersistedState, persistState } from './cloudState.js'

export type OutcomeType =
  | 'email_sent'
  | 'email_failed'
  | 'reply_received'
  | 'meeting_booked'
  | 'unsubscribe'
  | 'objection'
  | 'ai_draft_accepted'
  | 'ai_draft_rejected'
  | 'hook_scored_high'
  | 'hook_scored_low'

export type ReinforcementEvent = {
  id: string
  agentId: string
  outcome: OutcomeType
  context: {
    industry?: string
    channel?: string
    hookStyle?: string
    emailMode?: string
    niche?: string
    platform?: string
  }
  reward: number
  createdAt: string
}

export type PatternWeight = {
  patternKey: string
  successCount: number
  totalCount: number
  avgReward: number
  confidence: number
  updatedAt: string
}

export type LearningState = {
  events: ReinforcementEvent[]
  patterns: Record<string, PatternWeight>
  totalEvents: number
  epochNumber: number
  updatedAt: string
}

const REWARD_MAP: Record<OutcomeType, number> = {
  meeting_booked: 1.0,
  reply_received: 0.6,
  ai_draft_accepted: 0.3,
  email_sent: 0.1,
  hook_scored_high: 0.2,
  hook_scored_low: -0.1,
  ai_draft_rejected: -0.2,
  objection: -0.1,
  unsubscribe: -0.5,
  email_failed: -0.3,
}

const storePath = resolve(process.cwd(), 'data', 'crl-learning.json')
const storeKey = 'crl_learning'
const defaultState: LearningState = {
  events: [],
  patterns: {},
  totalEvents: 0,
  epochNumber: 0,
  updatedAt: new Date().toISOString(),
}
const state = structuredClone(defaultState)
let writeQueue: Promise<unknown> = Promise.resolve()

function normalizeState(value: Partial<LearningState> | null | undefined): LearningState {
  return {
    events: Array.isArray(value?.events) ? value.events : [],
    patterns: value?.patterns && typeof value.patterns === 'object' ? value.patterns : {},
    totalEvents: typeof value?.totalEvents === 'number' ? value.totalEvents : 0,
    epochNumber: typeof value?.epochNumber === 'number' ? value.epochNumber : 0,
    updatedAt: typeof value?.updatedAt === 'string' ? value.updatedAt : new Date().toISOString(),
  }
}

function buildPatternKey(context: ReinforcementEvent['context']): string[] {
  const keys: string[] = []

  if (context.industry) {
    keys.push(`industry:${context.industry}`)
    if (context.channel) keys.push(`industry:${context.industry}:channel:${context.channel}`)
    if (context.hookStyle) keys.push(`industry:${context.industry}:hookStyle:${context.hookStyle}`)
    if (context.emailMode) keys.push(`industry:${context.industry}:emailMode:${context.emailMode}`)
  }

  if (context.channel) keys.push(`channel:${context.channel}`)
  if (context.hookStyle) keys.push(`hookStyle:${context.hookStyle}`)
  if (context.niche && context.platform) keys.push(`niche:${context.niche}:platform:${context.platform}`)

  return keys
}

function computeConfidence(count: number): number {
  return 1 - Math.exp(-count / 30)
}

export async function initCrlLearning() {
  const loaded = await loadPersistedState(storeKey, defaultState, storePath)
  Object.assign(state, normalizeState(loaded.value))
}

async function saveState() {
  await persistState(storeKey, state, storePath)
}

async function mutate<T>(fn: (draft: LearningState) => T): Promise<T> {
  const run = async () => {
    const result = fn(state)
    await saveState()
    return result
  }

  const next = writeQueue.then(run, run)
  writeQueue = next.catch(() => undefined)
  return next
}

export async function recordOutcome(
  agentId: string,
  outcome: OutcomeType,
  context: ReinforcementEvent['context'] = {},
): Promise<ReinforcementEvent> {
  const reward = REWARD_MAP[outcome] ?? 0
  const event: ReinforcementEvent = {
    id: `crl_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    agentId,
    outcome,
    context,
    reward,
    createdAt: new Date().toISOString(),
  }

  await mutate((draft) => {
    draft.events.push(event)
    draft.totalEvents += 1

    for (const key of buildPatternKey(context)) {
      const existing = draft.patterns[key] ?? {
        patternKey: key,
        successCount: 0,
        totalCount: 0,
        avgReward: 0,
        confidence: 0,
        updatedAt: new Date().toISOString(),
      }

      existing.totalCount += 1
      if (reward > 0) existing.successCount += 1
      existing.avgReward = existing.avgReward + (reward - existing.avgReward) / existing.totalCount
      existing.confidence = computeConfidence(existing.totalCount)
      existing.updatedAt = new Date().toISOString()
      draft.patterns[key] = existing
    }

    if (draft.events.length > 2000) {
      draft.events = draft.events.slice(-2000)
    }

    draft.updatedAt = new Date().toISOString()
  })

  try {
    const supabase = getSupabaseAdmin()
    if (supabase) {
      await supabase.from('agent_runs').insert({
        agent_name: agentId,
        prompt: `crl_outcome:${outcome}`,
        response: JSON.stringify({ reward, context }),
        tools_used: [],
        guardrails: [],
      })
    }
  } catch {
    // Best-effort analytics mirror only.
  }

  writeAudit({
    actor: agentId,
    action: 'crl_outcome',
    purpose: 'reinforcement_learning',
    result: reward > 0 ? 'ok' : 'error',
    metadata: { outcome, reward, context },
  })

  return event
}

export async function getBestApproach(
  context: ReinforcementEvent['context'],
  options: string[],
  contextKey: keyof ReinforcementEvent['context'],
): Promise<{ best: string | null; confidence: number; reason: string }> {
  let bestOption: string | null = null
  let bestScore = -Infinity
  let bestConfidence = 0
  const scores: Array<{ option: string; avgReward: number; confidence: number; count: number }> = []

  for (const option of options) {
    const testContext = { ...context, [contextKey]: option }
    const keys = buildPatternKey(testContext)
    let totalReward = 0
    let totalWeight = 0

    for (const key of keys) {
      const pattern = state.patterns[key]
      if (pattern && pattern.confidence > 0.1) {
        totalReward += pattern.avgReward * pattern.confidence
        totalWeight += pattern.confidence
      }
    }

    const score = totalWeight > 0 ? totalReward / totalWeight : 0
    const pattern = keys
      .map((key) => state.patterns[key])
      .filter(Boolean)
      .sort((left, right) => right!.confidence - left!.confidence)[0]

    scores.push({
      option,
      avgReward: score,
      confidence: pattern?.confidence ?? 0,
      count: pattern?.totalCount ?? 0,
    })

    if (score > bestScore) {
      bestScore = score
      bestOption = option
      bestConfidence = pattern?.confidence ?? 0
    }
  }

  if (bestOption === null || bestConfidence < 0.1) {
    return {
      best: null,
      confidence: 0,
      reason: 'insufficient_data - not enough reinforcement events to recommend an approach',
    }
  }

  return {
    best: bestOption,
    confidence: bestConfidence,
    reason: `Recommended based on ${scores.find((item) => item.option === bestOption)?.count ?? 0} events with avg reward ${bestScore.toFixed(2)}`,
  }
}

export async function getLearningDigest() {
  const recentEvents = state.events.slice(-100)
  const outcomeBreakdown = recentEvents.reduce<Record<string, number>>((acc, event) => {
    acc[event.outcome] = (acc[event.outcome] ?? 0) + 1
    return acc
  }, {})

  const avgReward = recentEvents.length > 0
    ? recentEvents.reduce((sum, event) => sum + event.reward, 0) / recentEvents.length
    : 0

  const topPatterns = Object.values(state.patterns)
    .filter((pattern) => pattern.confidence > 0.2 && pattern.totalCount >= 3)
    .sort((left, right) => right.avgReward - left.avgReward)
    .slice(0, 10)

  const worstPatterns = Object.values(state.patterns)
    .filter((pattern) => pattern.confidence > 0.2 && pattern.avgReward < -0.1)
    .sort((left, right) => left.avgReward - right.avgReward)
    .slice(0, 5)

  return {
    totalEvents: state.totalEvents,
    epochNumber: state.epochNumber,
    recentAvgReward: Number(avgReward.toFixed(3)),
    outcomeBreakdown,
    topPatterns: topPatterns.map((pattern) => ({
      key: pattern.patternKey,
      avgReward: Number(pattern.avgReward.toFixed(3)),
      confidence: Number(pattern.confidence.toFixed(2)),
      count: pattern.totalCount,
    })),
    worstPatterns: worstPatterns.map((pattern) => ({
      key: pattern.patternKey,
      avgReward: Number(pattern.avgReward.toFixed(3)),
      confidence: Number(pattern.confidence.toFixed(2)),
      count: pattern.totalCount,
    })),
    updatedAt: state.updatedAt,
  }
}
