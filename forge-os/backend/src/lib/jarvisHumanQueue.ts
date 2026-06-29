/**
 * Jarvis Human Task Queue
 *
 * When Jarvis cannot execute something itself (create an account, record a video,
 * add an API key, manually follow 50 LinkedIn profiles), it pushes a structured task
 * here so Jace sees exactly what action is required, why, and how urgent it is.
 *
 * This is the primary handoff mechanism between Jarvis's autonomous planning and
 * human execution. All agents can push tasks; only Jace (or a route handler) marks them done.
 */

import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { randomUUID } from 'node:crypto'

// ── Types ──────────────────────────────────────────────────────────────────────

export type HumanTaskCategory =
  | 'account_setup'      // Create an account on a platform (LinkedIn, Apollo, TikTok…)
  | 'content_record'     // Record a video, audio clip, or screenshot
  | 'credential_setup'   // Add API key / OAuth credential to .env.local
  | 'strategy_approval'  // Review and approve a Jarvis strategy before it executes
  | 'outreach_manual'    // Manual action: follow, connect, DM, reply
  | 'feedback'           // Tell Jarvis what happened so CRL can learn
  | 'review'             // Review something Jarvis generated (hook, script, sequence)

export type HumanTask = {
  id: string
  title: string
  description: string
  category: HumanTaskCategory
  priority: 1 | 2 | 3  // 1=critical blocks Jarvis, 2=important this week, 3=when possible
  status: 'pending' | 'done' | 'dismissed'
  createdBy: string    // agent that created it (e.g. 'jarvis', 'noah', 'strategy_engine')
  payload?: unknown    // structured data (e.g. the hook text to test, the script to record)
  createdAt: string
  updatedAt: string
  doneAt?: string
}

export type StrategyExperiment = {
  id: string
  type: 'hook' | 'dm' | 'subject_line' | 'sequence'
  niche: string
  platform: string
  status: 'running' | 'complete' | 'failed'
  variants: Array<{
    text: string
    score: number
    viralityScore?: number
    clarity?: number
    hookStrength?: number
  }>
  winner: string | null
  winnerScore: number
  insight: string
  createdAt: string
  completedAt?: string
}

type HumanQueueState = {
  tasks: HumanTask[]
  experiments: StrategyExperiment[]
  updatedAt: string
}

// ── Persistence ───────────────────────────────────────────────────────────────

const storePath = resolve(process.cwd(), 'data', 'jarvis-human-queue.json')
let writeQueue: Promise<unknown> = Promise.resolve()

const defaultState: HumanQueueState = {
  tasks: [],
  experiments: [],
  updatedAt: new Date().toISOString(),
}

async function readState(): Promise<HumanQueueState> {
  try {
    const raw = await readFile(storePath, 'utf8')
    const parsed = JSON.parse(raw) as Partial<HumanQueueState>
    return {
      tasks: Array.isArray(parsed.tasks) ? parsed.tasks : [],
      experiments: Array.isArray(parsed.experiments) ? parsed.experiments : [],
      updatedAt: parsed.updatedAt ?? new Date().toISOString(),
    }
  } catch {
    return structuredClone(defaultState)
  }
}

async function persistState(state: HumanQueueState): Promise<void> {
  await mkdir(dirname(storePath), { recursive: true })
  await writeFile(storePath, JSON.stringify(state, null, 2), 'utf8')
}

async function mutate<T>(fn: (state: HumanQueueState) => T): Promise<T> {
  const run = async () => {
    const state = await readState()
    const result = fn(state)
    state.updatedAt = new Date().toISOString()
    await persistState(state)
    return result
  }
  const next = writeQueue.then(run, run)
  writeQueue = next.catch(() => undefined)
  return next
}

// ── Human Task API ────────────────────────────────────────────────────────────

export async function pushHumanTask(
  task: Omit<HumanTask, 'id' | 'status' | 'createdAt' | 'updatedAt'>,
): Promise<HumanTask> {
  const now = new Date().toISOString()
  const full: HumanTask = {
    id: `ht_${randomUUID().slice(0, 8)}`,
    status: 'pending',
    createdAt: now,
    updatedAt: now,
    ...task,
  }
  await mutate((state) => {
    state.tasks.push(full)
  })
  return full
}

export async function getHumanTasks(statusFilter?: HumanTask['status']): Promise<HumanTask[]> {
  const state = await readState()
  const tasks = statusFilter ? state.tasks.filter((t) => t.status === statusFilter) : state.tasks
  return tasks.sort((a, b) => {
    if (a.priority !== b.priority) return a.priority - b.priority
    return b.createdAt.localeCompare(a.createdAt)
  })
}

export async function updateHumanTask(
  id: string,
  patch: { status?: HumanTask['status']; doneAt?: string },
): Promise<HumanTask | null> {
  return mutate((state) => {
    const task = state.tasks.find((t) => t.id === id)
    if (!task) return null
    Object.assign(task, patch, { updatedAt: new Date().toISOString() })
    if (patch.status === 'done' && !task.doneAt) {
      task.doneAt = new Date().toISOString()
    }
    return task
  })
}

// ── Strategy Experiment API ───────────────────────────────────────────────────

export async function saveExperiment(experiment: StrategyExperiment): Promise<void> {
  await mutate((state) => {
    const idx = state.experiments.findIndex((e) => e.id === experiment.id)
    if (idx >= 0) state.experiments[idx] = experiment
    else state.experiments.push(experiment)
    // Keep only last 100 experiments
    if (state.experiments.length > 100) {
      state.experiments = state.experiments.slice(-100)
    }
  })
}

export async function getExperiments(type?: StrategyExperiment['type']): Promise<StrategyExperiment[]> {
  const state = await readState()
  const exps = type ? state.experiments.filter((e) => e.type === type) : state.experiments
  return exps.sort((a, b) => b.createdAt.localeCompare(a.createdAt))
}

export async function getHumanQueueSummary() {
  const state = await readState()
  const pending = state.tasks.filter((t) => t.status === 'pending')
  const critical = pending.filter((t) => t.priority === 1)
  const recentExps = state.experiments.slice(-10).reverse()
  return {
    pendingTasks: pending.length,
    criticalTasks: critical.length,
    totalTasks: state.tasks.length,
    recentExperiments: recentExps.length,
    lastUpdated: state.updatedAt,
  }
}
