import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'
import { env } from '../config/env.js'
import { getSupabaseAdmin } from './supabaseAdmin.js'

export type PersistenceSource = 'supabase' | 'local-file' | 'memory'

export type PersistedRecord<T> = {
  value: T
  source: PersistenceSource
  persisted: boolean
}

function cloneValue<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function canUseLocalFileFallback() {
  return env.NODE_ENV !== 'production'
}

export async function loadPersistedState<T>(key: string, fallback: T, localFilePath?: string): Promise<PersistedRecord<T>> {
  const supabase = getSupabaseAdmin()
  if (supabase) {
    try {
      const { data, error } = await supabase
        .from('forge_settings')
        .select('state')
        .eq('id', key)
        .maybeSingle()

      if (!error && data?.state !== undefined) {
        return {
          value: (data.state as T) ?? cloneValue(fallback),
          source: 'supabase',
          persisted: true,
        }
      }
    } catch {
      // Fall through to local or memory fallback.
    }
  }

  if (localFilePath && canUseLocalFileFallback()) {
    try {
      if (existsSync(localFilePath)) {
        return {
          value: JSON.parse(readFileSync(localFilePath, 'utf8')) as T,
          source: 'local-file',
          persisted: true,
        }
      }
    } catch {
      // Fall through to in-memory fallback.
    }
  }

  return {
    value: cloneValue(fallback),
    source: supabase ? 'supabase' : localFilePath && canUseLocalFileFallback() ? 'local-file' : 'memory',
    persisted: Boolean(supabase || (localFilePath && canUseLocalFileFallback())),
  }
}

export async function persistState<T>(key: string, value: T, localFilePath?: string): Promise<PersistenceSource> {
  const supabase = getSupabaseAdmin()
  if (supabase) {
    await supabase.from('forge_settings').upsert({
      id: key,
      state: value,
      updated_at: new Date().toISOString(),
    })
    return 'supabase'
  }

  if (localFilePath && canUseLocalFileFallback()) {
    mkdirSync(dirname(localFilePath), { recursive: true })
    writeFileSync(localFilePath, JSON.stringify(value, null, 2), 'utf8')
    return 'local-file'
  }

  return 'memory'
}
