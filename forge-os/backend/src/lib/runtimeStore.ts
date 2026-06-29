import { createHash } from 'node:crypto'
import { resolve } from 'node:path'
import { loadPersistedState, persistState, type PersistenceSource } from './cloudState.js'

export type RuntimeLead = {
  id: string
  fullName: string
  email: string
  companyName: string
  industry?: string
  city?: string
  enrichedAt?: string
}

export type RuntimeDraft = {
  id: string
  leadId: string
  subject: string
  body: string
  mode: string
  createdAt: string
}

export type RuntimeSendEvent = {
  id: string
  leadId: string
  draftId: string
  to: string
  status: 'sent' | 'failed'
  reason?: string
  createdAt: string
}

export type RuntimeReplyEvent = {
  id: string
  leadId: string
  intent: 'interested' | 'neutral' | 'unsubscribe' | 'objection' | 'meeting_intent'
  createdAt: string
}

export type RuntimeMeeting = {
  id: string
  leadId: string
  value: number
  createdAt: string
}

type RuntimeState = {
  leads: RuntimeLead[]
  drafts: RuntimeDraft[]
  sends: RuntimeSendEvent[]
  replies: RuntimeReplyEvent[]
  meetings: RuntimeMeeting[]
}

const defaultRuntime: RuntimeState = {
  leads: [],
  drafts: [],
  sends: [],
  replies: [],
  meetings: [],
}

const storePath = resolve(process.cwd(), 'data', 'runtime-store.json')
const storeKey = 'runtime_store'
const runtime = structuredClone(defaultRuntime)
let storageSource: PersistenceSource = 'memory'
let storagePersisted = false

function normalizeRuntime(parsed: Partial<RuntimeState> | null | undefined): RuntimeState {
  return {
    leads: Array.isArray(parsed?.leads) ? parsed.leads : [],
    drafts: Array.isArray(parsed?.drafts) ? parsed.drafts : [],
    sends: Array.isArray(parsed?.sends) ? parsed.sends : [],
    replies: Array.isArray(parsed?.replies) ? parsed.replies : [],
    meetings: Array.isArray(parsed?.meetings) ? parsed.meetings : [],
  }
}

async function persistRuntime() {
  try {
    storageSource = await persistState(storeKey, runtime, storePath)
    storagePersisted = storageSource !== 'memory'
  } catch {
    storageSource = 'memory'
    storagePersisted = false
  }
}

const uid = (prefix: string) => `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
const now = () => new Date().toISOString()
const persist = () => {
  void persistRuntime()
}

function hashValue(value: unknown) {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex')
}

function collectionRoot<T extends { id: string }>(items: T[]) {
  const leaves = [...items].sort((a, b) => a.id.localeCompare(b.id)).map((item) => hashValue(item))
  if (!leaves.length) return hashValue([])
  let layer = leaves
  while (layer.length > 1) {
    const next: string[] = []
    for (let i = 0; i < layer.length; i += 2) {
      next.push(hashValue([layer[i], layer[i + 1] ?? layer[i]]))
    }
    layer = next
  }
  return layer[0]
}

function dataRoots() {
  const roots = {
    leads: collectionRoot(runtime.leads),
    drafts: collectionRoot(runtime.drafts),
    sends: collectionRoot(runtime.sends),
    replies: collectionRoot(runtime.replies),
    meetings: collectionRoot(runtime.meetings),
  }
  return { ...roots, global: hashValue(roots) }
}

export const runtimeStore = {
  async init() {
    const state = await loadPersistedState(storeKey, defaultRuntime, storePath)
    storageSource = state.source
    storagePersisted = state.persisted
    Object.assign(runtime, normalizeRuntime(state.value))
  },
  all: runtime,
  get storage() {
    return {
      key: storeKey,
      source: storageSource,
      persisted: storagePersisted,
      fallbackPath: storePath,
      counts: {
        leads: runtime.leads.length,
        drafts: runtime.drafts.length,
        sends: runtime.sends.length,
        replies: runtime.replies.length,
        meetings: runtime.meetings.length,
      },
      roots: dataRoots(),
    }
  },
  upsertLead(input: Omit<RuntimeLead, 'id'> & { id?: string }) {
    const existing = runtime.leads.find((l) => l.email.toLowerCase() === input.email.toLowerCase())
    if (existing) {
      Object.assign(existing, input)
      persist()
      return existing
    }
    const lead: RuntimeLead = { id: input.id ?? uid('lead'), ...input }
    runtime.leads.push(lead)
    persist()
    return lead
  },
  createDraft(input: Omit<RuntimeDraft, 'id' | 'createdAt'>) {
    const draft: RuntimeDraft = { id: uid('draft'), createdAt: now(), ...input }
    runtime.drafts.push(draft)
    persist()
    return draft
  },
  createSendEvent(input: Omit<RuntimeSendEvent, 'id' | 'createdAt'>) {
    const event: RuntimeSendEvent = { id: uid('send'), createdAt: now(), ...input }
    runtime.sends.push(event)
    persist()
    return event
  },
  createReplyEvent(input: Omit<RuntimeReplyEvent, 'id' | 'createdAt'>) {
    const event: RuntimeReplyEvent = { id: uid('reply'), createdAt: now(), ...input }
    runtime.replies.push(event)
    persist()
    return event
  },
  createMeeting(input: Omit<RuntimeMeeting, 'id' | 'createdAt'>) {
    const event: RuntimeMeeting = { id: uid('meeting'), createdAt: now(), ...input }
    runtime.meetings.push(event)
    persist()
    return event
  },
}
