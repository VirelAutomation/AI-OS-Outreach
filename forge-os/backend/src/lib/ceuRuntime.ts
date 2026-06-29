/**
 * CEU Runtime Engine — L99 Adaptive Execution Supervisor
 *
 * Implements the CEU (Civilization-scale Execution Unit) architecture from the L99 framework.
 * Models all agent executions as survivability states across a topology graph.
 * Dynamically scales cognition density, prevents contradiction flooding, and enforces
 * least-contradiction survivability paths across the system.
 *
 * Topology nodes = agent execution slots (jarvis, noah, damien, devan, akhil, zoya, king)
 * Topology edges = dependency pressure between nodes (caller → callee continuity)
 * Contradiction economics = execution failures with cost, density, propagation, and survivability scores
 */

import { writeAudit } from './auditLog.js'

// ── Types ──────────────────────────────────────────────────────────────────────

export type AgentId = 'jarvis' | 'noah' | 'damien' | 'devan' | 'akhil' | 'zoya' | 'king' | string

export type ExecutionState = 'idle' | 'active' | 'queued' | 'circuit_open' | 'degraded'

export type ContradictionEvent = {
  agentId: AgentId
  error: string
  cost: number          // 0–1: how expensive this contradiction is
  density: number       // 0–1: how many similar contradictions occurred recently
  survivability: number // 0–1: probability this agent recovers without intervention
  propagationRisk: number // 0–1: risk this contradiction spreads to dependent agents
  at: string
}

export type AgentTopologyNode = {
  agentId: AgentId
  state: ExecutionState
  activeCount: number
  successCount: number
  failureCount: number
  avgLatencyMs: number
  lastExecutionAt: string | null
  contradictions: ContradictionEvent[]
  survivalScore: number // 0–1: real-time survivability rating
}

export type SystemTopology = {
  nodes: Record<AgentId, AgentTopologyNode>
  globalSurvivalScore: number
  cognitionDensity: 'passive' | 'predictive' | 'contradiction_warfare' | 'catastrophe_reconstruction' | 'judicial_arbitration'
  totalExecutions: number
  totalContradictions: number
  entropyPressure: number // 0–1: system-wide instability pressure
  at: string
}

export type CacheEntry = {
  key: string
  result: string
  agentId: AgentId
  createdAt: number
  hitCount: number
  ttlMs: number
}

// ── Constants ─────────────────────────────────────────────────────────────────

const AGENTS: AgentId[] = ['jarvis', 'noah', 'damien', 'devan', 'akhil', 'zoya', 'king']
const CONTRADICTION_WINDOW_MS = 5 * 60 * 1000 // 5-minute sliding window
const CACHE_TTL_MS = 10 * 60 * 1000 // 10-minute response cache
const MAX_CACHE_ENTRIES = 500
const MAX_CONTRADICTIONS_PER_AGENT = 50
const HIGH_SURVIVABILITY_THRESHOLD = 0.7
const CATASTROPHE_THRESHOLD = 0.3

// ── State ─────────────────────────────────────────────────────────────────────

const nodes = new Map<AgentId, AgentTopologyNode>()
const responseCache = new Map<string, CacheEntry>()
let totalExecutions = 0
let totalContradictions = 0

function initNode(agentId: AgentId): AgentTopologyNode {
  return {
    agentId,
    state: 'idle',
    activeCount: 0,
    successCount: 0,
    failureCount: 0,
    avgLatencyMs: 0,
    lastExecutionAt: null,
    contradictions: [],
    survivalScore: 1.0,
  }
}

function getNode(agentId: AgentId): AgentTopologyNode {
  if (!nodes.has(agentId)) nodes.set(agentId, initNode(agentId))
  return nodes.get(agentId)!
}

// ── Contradiction Economics ───────────────────────────────────────────────────

function computeContradictionCost(error: string): number {
  if (error.includes('circuit_open')) return 0.9
  if (error.includes('timeout') || error.includes('exhausted_retries')) return 0.8
  if (error.includes('rate_limited') || error.includes('429')) return 0.5
  if (error.includes('provider_5xx')) return 0.6
  if (error.includes('missing_key')) return 1.0 // critical — no recovery without config
  if (error.includes('empty_response')) return 0.3
  return 0.4
}

function computeContradictionDensity(node: AgentTopologyNode): number {
  const now = Date.now()
  const recent = node.contradictions.filter(
    (c) => now - new Date(c.at).getTime() < CONTRADICTION_WINDOW_MS
  )
  return Math.min(1, recent.length / 10)
}

function computePropagationRisk(agentId: AgentId, density: number): number {
  // Agents with many dependents spread contradictions further
  const highRiskAgents = ['jarvis', 'noah', 'king']
  const baseRisk = highRiskAgents.includes(agentId) ? 0.6 : 0.3
  return Math.min(1, baseRisk + density * 0.4)
}

function computeSurvivalScore(node: AgentTopologyNode): number {
  const total = node.successCount + node.failureCount
  if (total === 0) return 1.0
  const successRate = node.successCount / total
  const densityPenalty = computeContradictionDensity(node) * 0.3
  return Math.max(0, Math.min(1, successRate - densityPenalty))
}

function computeEntropyPressure(): number {
  const allNodes = Array.from(nodes.values())
  if (!allNodes.length) return 0
  const avgSurvival = allNodes.reduce((sum, n) => sum + n.survivalScore, 0) / allNodes.length
  return 1 - avgSurvival
}

function computeCognitionDensity(entropyPressure: number): SystemTopology['cognitionDensity'] {
  if (entropyPressure < 0.1) return 'passive'
  if (entropyPressure < 0.3) return 'predictive'
  if (entropyPressure < 0.5) return 'contradiction_warfare'
  if (entropyPressure < 0.7) return 'catastrophe_reconstruction'
  return 'judicial_arbitration'
}

// ── Response Cache ────────────────────────────────────────────────────────────

function makeCacheKey(agentId: AgentId, prompt: string): string {
  // Use first 512 chars of prompt as cache key — prevents memory explosion
  const normalized = prompt.trim().slice(0, 512).toLowerCase().replace(/\s+/g, ' ')
  return `${agentId}:${normalized}`
}

export function getCachedResponse(agentId: AgentId, prompt: string): string | null {
  const key = makeCacheKey(agentId, prompt)
  const entry = responseCache.get(key)
  if (!entry) return null

  const age = Date.now() - entry.createdAt
  if (age > entry.ttlMs) {
    responseCache.delete(key)
    return null
  }

  entry.hitCount += 1
  return entry.result
}

export function setCachedResponse(agentId: AgentId, prompt: string, result: string, ttlMs = CACHE_TTL_MS): void {
  // Evict oldest entry if at capacity (LRU approximation)
  if (responseCache.size >= MAX_CACHE_ENTRIES) {
    const oldest = Array.from(responseCache.entries())
      .sort(([, a], [, b]) => a.createdAt - b.createdAt)[0]
    if (oldest) responseCache.delete(oldest[0])
  }

  const key = makeCacheKey(agentId, prompt)
  responseCache.set(key, {
    key,
    result,
    agentId,
    createdAt: Date.now(),
    hitCount: 0,
    ttlMs,
  })
}

export function invalidateCache(agentId?: AgentId): number {
  let removed = 0
  for (const [key, entry] of responseCache.entries()) {
    if (!agentId || entry.agentId === agentId) {
      responseCache.delete(key)
      removed++
    }
  }
  return removed
}

// ── Execution Tracking ───────────────────────────────────────────────────────

export function trackExecutionStart(agentId: AgentId): { startedAt: number; release: () => void } {
  const node = getNode(agentId)
  node.activeCount++
  node.state = 'active'

  const startedAt = Date.now()

  const release = () => {
    node.activeCount = Math.max(0, node.activeCount - 1)
    node.state = node.activeCount > 0 ? 'active' : 'idle'
  }

  return { startedAt, release }
}

export function recordSuccess(agentId: AgentId, latencyMs: number): void {
  const node = getNode(agentId)
  node.successCount++
  totalExecutions++

  // Rolling average latency
  const total = node.successCount + node.failureCount
  node.avgLatencyMs = node.avgLatencyMs + (latencyMs - node.avgLatencyMs) / Math.max(1, total)
  node.lastExecutionAt = new Date().toISOString()
  node.survivalScore = computeSurvivalScore(node)
}

export function recordContradiction(agentId: AgentId, error: string): ContradictionEvent {
  const node = getNode(agentId)
  node.failureCount++
  totalContradictions++

  const density = computeContradictionDensity(node)
  const cost = computeContradictionCost(error)
  const propagationRisk = computePropagationRisk(agentId, density)

  const event: ContradictionEvent = {
    agentId,
    error,
    cost,
    density,
    survivability: Math.max(0, 1 - cost - density * 0.5),
    propagationRisk,
    at: new Date().toISOString(),
  }

  node.contradictions.push(event)

  // Trim sliding window
  if (node.contradictions.length > MAX_CONTRADICTIONS_PER_AGENT) {
    node.contradictions = node.contradictions.slice(-MAX_CONTRADICTIONS_PER_AGENT)
  }

  node.survivalScore = computeSurvivalScore(node)
  node.lastExecutionAt = new Date().toISOString()

  // Flag degraded state for high-cost contradictions
  if (cost >= HIGH_SURVIVABILITY_THRESHOLD || density >= HIGH_SURVIVABILITY_THRESHOLD) {
    node.state = 'degraded'
    writeAudit({
      actor: 'ceu_runtime',
      action: 'contradiction_warfare',
      purpose: 'survivability_reconstruction',
      result: 'error',
      detail: `Agent ${agentId} entered degraded state. cost=${cost.toFixed(2)} density=${density.toFixed(2)} propagation=${propagationRisk.toFixed(2)}`,
    })
  }

  // Catastrophe detection — low survival score triggers reconstruction mode
  if (node.survivalScore < CATASTROPHE_THRESHOLD) {
    writeAudit({
      actor: 'ceu_runtime',
      action: 'catastrophe_reconstruction',
      purpose: 'survivability_reconstruction',
      result: 'error',
      detail: `Agent ${agentId} survival score collapsed to ${node.survivalScore.toFixed(2)}. Reconstruction triggered.`,
    })
  }

  return event
}

// ── Topology Snapshot ─────────────────────────────────────────────────────────

export function getSystemTopology(): SystemTopology {
  const allAgents = [...AGENTS, ...Array.from(nodes.keys()).filter((id) => !AGENTS.includes(id))]
  const nodeMap: Record<AgentId, AgentTopologyNode> = {}

  for (const agentId of allAgents) {
    nodeMap[agentId] = getNode(agentId)
  }

  const entropyPressure = computeEntropyPressure()
  const globalSurvivalScore = 1 - entropyPressure
  const cognitionDensity = computeCognitionDensity(entropyPressure)

  return {
    nodes: nodeMap,
    globalSurvivalScore,
    cognitionDensity,
    totalExecutions,
    totalContradictions,
    entropyPressure,
    at: new Date().toISOString(),
  }
}

// ── Cache Status ──────────────────────────────────────────────────────────────

export function getCacheStatus() {
  const entries = Array.from(responseCache.values())
  const now = Date.now()
  const live = entries.filter((e) => now - e.createdAt < e.ttlMs)
  const totalHits = live.reduce((sum, e) => sum + e.hitCount, 0)

  const byAgent = live.reduce<Record<string, number>>((acc, e) => {
    acc[e.agentId] = (acc[e.agentId] ?? 0) + 1
    return acc
  }, {})

  return {
    total: responseCache.size,
    live: live.length,
    stale: responseCache.size - live.length,
    totalHits,
    byAgent,
    maxCapacity: MAX_CACHE_ENTRIES,
    utilizationPct: Number(((responseCache.size / MAX_CACHE_ENTRIES) * 100).toFixed(1)),
  }
}

// ── Adaptive Execution Wrapper ────────────────────────────────────────────────

export async function withCEU<T>(
  agentId: AgentId,
  label: string,
  fn: () => Promise<T>,
): Promise<{ result: T; latencyMs: number; fromCache: false }> {
  const { startedAt, release } = trackExecutionStart(agentId)

  try {
    const result = await fn()
    const latencyMs = Date.now() - startedAt
    recordSuccess(agentId, latencyMs)
    return { result, latencyMs, fromCache: false }
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error)
    recordContradiction(agentId, errorMsg)
    release()
    throw error
  } finally {
    release()
  }
}
