import { resolve } from 'node:path'
import { loadPersistedState, persistState, type PersistenceSource } from './cloudState.js'

type CmoArtifactKind = 'research' | 'concepts' | 'script' | 'hook_score' | 'sub_agent_task'

export type CmoArtifact = {
  id: string
  kind: CmoArtifactKind
  payload: unknown
  createdAt: string
}

type CmoArtifactState = {
  artifacts: CmoArtifact[]
}

const defaultState: CmoArtifactState = { artifacts: [] }
const storePath = resolve(process.cwd(), 'data', 'cmo-artifacts.json')
const storeKey = 'cmo_artifacts'
const state = structuredClone(defaultState)
let storageSource: PersistenceSource = 'memory'
let storagePersisted = false

function normalizeState(value: Partial<CmoArtifactState> | null | undefined): CmoArtifactState {
  return { artifacts: Array.isArray(value?.artifacts) ? value.artifacts : [] }
}

async function persistArtifacts() {
  try {
    storageSource = await persistState(storeKey, state, storePath)
    storagePersisted = storageSource !== 'memory'
  } catch {
    storageSource = 'memory'
    storagePersisted = false
  }
}

export const cmoArtifactStore = {
  async init() {
    const loaded = await loadPersistedState(storeKey, defaultState, storePath)
    storageSource = loaded.source
    storagePersisted = loaded.persisted
    Object.assign(state, normalizeState(loaded.value))
  },
  all: state.artifacts,
  save(kind: CmoArtifactKind, payload: unknown) {
    const artifact: CmoArtifact = {
      id: `${kind}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      kind,
      payload,
      createdAt: new Date().toISOString(),
    }
    state.artifacts.push(artifact)
    void persistArtifacts()
    return artifact
  },
  latest(limit = 50) {
    return state.artifacts.slice(-limit).reverse()
  },
  status() {
    return {
      key: storeKey,
      source: storageSource,
      persisted: storagePersisted,
      fallbackPath: storePath,
      count: state.artifacts.length,
      byKind: state.artifacts.reduce<Record<string, number>>((acc, artifact) => {
        acc[artifact.kind] = (acc[artifact.kind] ?? 0) + 1
        return acc
      }, {}),
    }
  },
}
