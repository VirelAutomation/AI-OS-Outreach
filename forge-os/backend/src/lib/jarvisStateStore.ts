import { resolve } from 'node:path'
import { loadPersistedState, persistState } from './cloudState.js'

export type JarvisTaskStatus = 'pending' | 'running' | 'done' | 'failed' | 'blocked' | 'approval_required'
export type JarvisAgentType = 'orchestrator' | 'outreach' | 'research' | 'ops' | 'crm' | 'content' | 'analyst' | 'cto' | 'cmo' | 'cfo' | 'lead_generation' | 'lead_management' | 'human'

export type JarvisTask = {
  id: string
  runId: string
  goal: string
  agentType: JarvisAgentType
  depth: number
  parentId: string | null
  status: JarvisTaskStatus
  result?: string
  causalNode?: string
  priority: number
  dependsOn: string[]
  createdAt: string
  updatedAt: string
}

export type JarvisLog = {
  id: string
  runId: string
  agentId: string
  taskId: string
  event: string
  payload: unknown
  ts: string
}

export type JarvisRun = {
  id: string
  goal: string
  status: JarvisTaskStatus
  mode: 'advisory' | 'approval' | 'autonomous'
  synthesis?: string
  createdAt: string
  updatedAt: string
}

export type JarvisState = {
  runs: JarvisRun[]
  tasks: JarvisTask[]
  logs: JarvisLog[]
  companyState: Record<string, { value: unknown; updatedAt: string }>
}

const defaultState: JarvisState = {
  runs: [],
  tasks: [],
  logs: [],
  companyState: {},
}

const storePath = resolve(process.cwd(), 'data', 'jarvis-state.json')
const storeKey = 'jarvis_state'
const state = structuredClone(defaultState)
let writeQueue: Promise<unknown> = Promise.resolve()

function normalizeState(value: Partial<JarvisState> | null | undefined): JarvisState {
  return {
    runs: Array.isArray(value?.runs) ? value.runs : [],
    tasks: Array.isArray(value?.tasks) ? value.tasks : [],
    logs: Array.isArray(value?.logs) ? value.logs : [],
    companyState: value?.companyState && typeof value.companyState === 'object' ? value.companyState : {},
  }
}

async function saveState() {
  await persistState(storeKey, state, storePath)
}

async function mutateState<T>(operation: (draft: JarvisState) => T | Promise<T>): Promise<T> {
  const run = async () => {
    const result = await operation(state)
    await saveState()
    return result
  }

  const next = writeQueue.then(run, run)
  writeQueue = next.catch(() => undefined)
  return next
}

export const jarvisStateStore = {
  async init() {
    const loaded = await loadPersistedState(storeKey, defaultState, storePath)
    Object.assign(state, normalizeState(loaded.value))
  },

  async getState() {
    return structuredClone(state)
  },

  async saveRun(run: JarvisRun) {
    return mutateState(() => {
      const idx = state.runs.findIndex((item) => item.id === run.id)
      if (idx >= 0) state.runs[idx] = run
      else state.runs.push(run)
      return run
    })
  },

  async saveTask(task: JarvisTask) {
    return mutateState(() => {
      const idx = state.tasks.findIndex((item) => item.id === task.id)
      if (idx >= 0) state.tasks[idx] = task
      else state.tasks.push(task)
      return task
    })
  },

  async updateTask(taskId: string, patch: Partial<JarvisTask>) {
    return mutateState(() => {
      const task = state.tasks.find((item) => item.id === taskId)
      if (!task) return null
      Object.assign(task, patch, { updatedAt: new Date().toISOString() })
      return task
    })
  },

  async updateRun(runId: string, patch: Partial<JarvisRun>) {
    return mutateState(() => {
      const run = state.runs.find((item) => item.id === runId)
      if (!run) return null
      Object.assign(run, patch, { updatedAt: new Date().toISOString() })
      return run
    })
  },

  async log(log: JarvisLog) {
    return mutateState(() => {
      state.logs.push(log)
      return log
    })
  },

  async setCompanyState(key: string, value: unknown) {
    return mutateState(() => {
      state.companyState[key] = { value, updatedAt: new Date().toISOString() }
      return state.companyState[key]
    })
  },

  async getCompanySnapshot() {
    return Object.fromEntries(Object.entries(state.companyState).map(([key, item]) => [key, item.value]))
  },
}
