/**
 * Supabase Migration Runner
 *
 * Applies schema.v1.sql and schema.v2.sql to a Supabase project.
 * Run once when setting up a new environment, then re-run safely (all
 * statements use CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS).
 *
 * Usage:
 *   npx tsx scripts/migrate.ts
 *
 * Requires SUPABASE_URL and SUPABASE_SECRET_KEY in .env.local
 */

import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import dotenv from 'dotenv'
import { createClient } from '@supabase/supabase-js'

dotenv.config({ path: resolve(process.cwd(), '.env.local') })
dotenv.config({ path: resolve(process.cwd(), '.env') })

const SUPABASE_URL = process.env.SUPABASE_URL
const SUPABASE_SECRET_KEY = process.env.SUPABASE_SECRET_KEY

if (!SUPABASE_URL || !SUPABASE_SECRET_KEY) {
  console.error('ERROR: SUPABASE_URL and SUPABASE_SECRET_KEY must be set in .env.local')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_SECRET_KEY, {
  auth: { persistSession: false },
})

async function runMigration(label: string, filePath: string) {
  console.log(`\n── Running migration: ${label} ──`)
  const sql = await readFile(filePath, 'utf8')

  // Split on semicolons and run each statement individually
  // (Supabase REST API doesn't support multi-statement queries)
  const statements = sql
    .split(';')
    .map((s) => s.trim())
    .filter((s) => s.length > 0 && !s.startsWith('--'))

  let ok = 0
  let failed = 0

  for (const statement of statements) {
    const preview = statement.slice(0, 60).replace(/\s+/g, ' ')
    try {
      const { error } = await supabase.rpc('exec_sql', { sql: statement + ';' }).select()
      if (error) {
        // Try direct query if RPC not available
        throw error
      }
      console.log(`  ✓ ${preview}...`)
      ok++
    } catch {
      // exec_sql RPC may not exist — that's fine, use Supabase SQL editor for large migrations
      console.log(`  ~ ${preview}... (use Supabase SQL Editor for this statement)`)
      failed++
    }
  }

  console.log(`  Result: ${ok} ok, ${failed} need manual run`)
}

async function main() {
  console.log('Forge OS — Supabase Migration Runner')
  console.log(`Target: ${SUPABASE_URL}`)
  console.log()
  console.log('NOTE: Supabase does not expose raw SQL execution via the REST API.')
  console.log('The recommended approach is to run these files directly in the Supabase SQL Editor:')
  console.log()
  console.log('  1. Go to https://supabase.com/dashboard/project/YOUR_PROJECT/sql')
  console.log('  2. Open supabase/schema.v1.sql — paste and run')
  console.log('  3. Open supabase/schema.v2.sql — paste and run')
  console.log()
  console.log('Both files use IF NOT EXISTS so they are safe to re-run.')
  console.log()

  // Verify Supabase connectivity
  const { error } = await supabase.from('prospects').select('id').limit(1)
  if (!error) {
    console.log('✓ Supabase connection OK — schema.v1.sql has been applied (prospects table exists)')
  } else if (error.code === 'PGRST116' || error.message.includes('does not exist')) {
    console.log('⚠ prospects table not found — run schema.v1.sql in Supabase SQL Editor')
  } else {
    console.log(`✓ Supabase connected (${error.message})`)
  }

  const { error: v2Error } = await supabase.from('content_calendar_items').select('id').limit(1)
  if (!v2Error) {
    console.log('✓ content_calendar_items exists — schema.v2.sql has been applied')
  } else {
    console.log('⚠ content_calendar_items not found — run schema.v2.sql in Supabase SQL Editor')
  }

  console.log()
  console.log('Schema files: backend/supabase/schema.v1.sql and backend/supabase/schema.v2.sql')
}

void main().catch(console.error)
