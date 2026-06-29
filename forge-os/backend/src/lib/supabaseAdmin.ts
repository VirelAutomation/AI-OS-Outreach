import { createClient, type SupabaseClient } from '@supabase/supabase-js'
import { env } from '../config/env.js'

let client: SupabaseClient | null = null

export function getSupabaseAdmin() {
  if (client) return client
  if (!env.SUPABASE_URL || !env.SUPABASE_SECRET_KEY) return null

  client = createClient(env.SUPABASE_URL, env.SUPABASE_SECRET_KEY, {
    auth: {
      persistSession: false,
      autoRefreshToken: false,
    },
  })

  return client
}
