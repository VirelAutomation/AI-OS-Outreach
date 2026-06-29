import { supabase } from './supabase'

const STATE_ID = 'forge-os-default'

export type StoredForgeState = {
  calls?: unknown[]
  campaigns?: unknown[]
  meetings?: unknown[]
  deals?: unknown[]
  products?: unknown[]
  settings?: Record<string, unknown>
  savedAt?: string
}

export async function loadForgeState() {
  if (!supabase) return { state: null, error: 'Supabase is not configured.' }

  const { data, error } = await supabase
    .from('forge_settings')
    .select('state')
    .eq('id', STATE_ID)
    .maybeSingle()

  if (error) return { state: null, error: error.message }

  return {
    state: (data?.state as StoredForgeState | null) ?? null,
    error: null,
  }
}

export async function saveForgeState(state: StoredForgeState) {
  if (!supabase) return { ok: false, error: 'Supabase is not configured.' }

  const { error } = await supabase.from('forge_settings').upsert({
    id: STATE_ID,
    state: {
      ...state,
      savedAt: new Date().toISOString(),
    },
    updated_at: new Date().toISOString(),
  })

  if (error) return { ok: false, error: error.message }
  return { ok: true, error: null }
}
