import { getSupabaseAdmin } from './supabaseAdmin.js'

export const coreRequiredTables = [
  'prospects',
  'campaigns',
  'campaign_events',
  'call_logs',
  'meetings',
  'deals',
  'booking_requests',
  'agent_runs',
] as const

export const extendedForgeTables = [
  'products',
  'content_items',
  'analytics_roots',
  'analytics_global_roots',
  'forge_settings',
  'jarvis_messages',
  'calendar_events_cache',
  'self_dev_state',
  'jarvis_grades',
  'outreach_drafts',
  'outreach_send_events',
  'outreach_reply_events',
  'outbound_suppressions',
  'prospect_enrichment_runs',
  'campaign_goals',
  'campaign_execution_plans',
  'page_visits',
  'chat_signals',
  'booking_signals',
  'automation_tasks',
  'automation_runs',
  'content_calendar_items',
  'agent_run_steps',
] as const

export const backendMigrationFiles = ['schema.v1.sql', 'schema.v2.sql'] as const

const allRequiredTables = [...coreRequiredTables, ...extendedForgeTables] as const

function isMissingTableError(message?: string, code?: string) {
  const lower = message?.toLowerCase() ?? ''
  return code === '42P01' || lower.includes("doesn't exist") || lower.includes('schema cache')
}

export async function checkSchemaReadiness() {
  const supabase = getSupabaseAdmin()
  if (!supabase) {
    return {
      configured: false,
      ok: false,
      fullForgeOk: false,
      status: 'missing_config' as const,
      missingTables: [...coreRequiredTables],
      extendedMissingTables: [...extendedForgeTables],
      checkedTables: [],
      message: 'Supabase is not configured.',
    }
  }

  const coreMissingTables: string[] = []
  const extendedMissingTables: string[] = []
  const checkedTables: Array<{ table: string; ok: boolean; reason: string | null }> = []

  for (const table of allRequiredTables) {
    const { error } = await supabase.from(table).select('*', { count: 'exact', head: true }).limit(1)
    if (error) {
      checkedTables.push({ table, ok: false, reason: error.message })
      if (isMissingTableError(error.message, error.code)) {
        if (coreRequiredTables.includes(table as (typeof coreRequiredTables)[number])) {
          coreMissingTables.push(table)
        } else {
          extendedMissingTables.push(table)
        }
      }
    } else {
      checkedTables.push({ table, ok: true, reason: null })
    }
  }

  const ok = coreMissingTables.length === 0
  const fullForgeOk = ok && extendedMissingTables.length === 0
  return {
    configured: true,
    ok,
    fullForgeOk,
    status: fullForgeOk
      ? ('full_forge_ready' as const)
      : ok
        ? ('core_ready_extended_pending' as const)
        : ('schema_not_ready' as const),
    missingTables: coreMissingTables,
    extendedMissingTables,
    checkedTables,
    message: fullForgeOk
      ? 'Core and extended Forge OS tables are present.'
      : ok
        ? 'Core production tables are present, but full Forge OS expansion tables are still missing.'
        : 'One or more core production tables are missing.',
  }
}

export function migrationChecklist() {
  return {
    sqlFiles: [...backendMigrationFiles],
    instruction: 'Apply the canonical Supabase SQL files in lexical order before routing production traffic.',
  }
}
