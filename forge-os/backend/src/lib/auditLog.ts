import { resolve } from 'node:path'
import { loadPersistedState, persistState, type PersistenceSource } from './cloudState.js'

type AuditResult = 'ok' | 'error' | 'blocked'

type AuditEvent = {
  actor: string
  action: string
  purpose: string
  result: AuditResult
  detail?: string
  metadata?: Record<string, unknown>
}

type AuditRow = AuditEvent & { ts: string }
type AuditLogState = { entries: AuditRow[] }

const storePath = resolve(process.cwd(), 'data', 'audit-log.json')
const storeKey = 'audit_log'
const maxEntries = 1000
const state: AuditLogState = { entries: [] }
let storageSource: PersistenceSource = 'memory'
let storagePersisted = false

function safeDetail(value?: string) {
  if (!value) return null
  return value
    .replace(/[A-Za-z0-9_-]{24,}/g, '[redacted]')
    .slice(0, 400)
}

export async function initAuditLog() {
  const loaded = await loadPersistedState(storeKey, state, storePath)
  storageSource = loaded.source
  storagePersisted = loaded.persisted
  state.entries = Array.isArray(loaded.value.entries) ? loaded.value.entries : []
}

export function writeAudit(event: AuditEvent) {
  const row: AuditRow = {
    ts: new Date().toISOString(),
    actor: event.actor,
    action: event.action,
    purpose: event.purpose,
    result: event.result,
    detail: safeDetail(event.detail) ?? undefined,
    metadata: event.metadata ?? {},
  }

  state.entries.push(row)
  if (state.entries.length > maxEntries) {
    state.entries = state.entries.slice(-maxEntries)
  }

  void persistState(storeKey, state, storePath)
    .then((source) => {
      storageSource = source
      storagePersisted = source !== 'memory'
    })
    .catch(() => {
      storageSource = 'memory'
      storagePersisted = false
    })
}

export function auditStatus() {
  return {
    key: storeKey,
    source: storageSource,
    persisted: storagePersisted,
    count: state.entries.length,
    fallbackPath: storePath,
  }
}
