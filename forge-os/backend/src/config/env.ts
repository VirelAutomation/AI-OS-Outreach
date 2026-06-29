import dotenv from 'dotenv'
import { z } from 'zod'

dotenv.config({ path: '.env.local' })
dotenv.config({ path: '.env' })

const envBoolean = (fallback: boolean) =>
  z.preprocess((value) => {
    if (typeof value !== 'string') return value
    const normalized = value.trim().toLowerCase()
    if (['true', '1', 'yes', 'on'].includes(normalized)) return true
    if (['false', '0', 'no', 'off', ''].includes(normalized)) return false
    return value
  }, z.boolean().default(fallback))

const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  PORT: z.coerce.number().default(8000),
  FRONTEND_ORIGIN: z.string().default('http://localhost:5173'),
  ALLOWED_ORIGINS: z.string().optional(),
  REQUIRE_API_KEY: envBoolean(false),
  BACKEND_API_KEY: z.string().optional(),
  RATE_LIMIT_WINDOW_MS: z.coerce.number().default(60000),
  RATE_LIMIT_MAX_REQUESTS: z.coerce.number().default(120),
  SUPABASE_URL: z.string().url().optional(),
  SUPABASE_PUBLISHABLE_KEY: z.string().optional(),
  SUPABASE_SECRET_KEY: z.string().optional(),
  SUPABASE_JWT_KEY_ID: z.string().optional(),
  SUPABASE_LEGACY_JWT_SECRET: z.string().optional(),
  GEMINI_API_KEY: z.string().optional(),
  GEMINI_API_KEY_JARVIS: z.string().optional(),
  GEMINI_API_KEY_DAMIEN: z.string().optional(),
  GEMINI_API_KEY_NOAH: z.string().optional(),
  GEMINI_API_KEY_ZOYA: z.string().optional(),
  GEMINI_API_KEY_DEVAN: z.string().optional(),
  GEMINI_API_KEY_AKHIL: z.string().optional(),
  GEMINI_API_KEY_KING: z.string().optional(),
  GEMINI_MODEL: z.string().default('gemini-2.5-pro'),
  GEMINI_MAX_RETRIES: z.coerce.number().int().positive().default(4),
  GEMINI_INITIAL_WAIT_MS: z.coerce.number().int().positive().default(60000),
  HF_TOKEN: z.string().optional(),
  HF_MODEL: z.string().default('Qwen/Qwen3-30B-A3B-Instruct-2507'),
  HF_PROVIDER: z.string().default('auto'),
  GOOGLE_CLIENT_ID: z.string().optional(),
  GOOGLE_CLIENT_SECRET: z.string().optional(),
  GOOGLE_REDIRECT_URI: z.string().optional(),
  GOOGLE_CLIENT_ID_BACKUP: z.string().optional(),
  GOOGLE_CLIENT_SECRET_BACKUP: z.string().optional(),
  GOOGLE_REDIRECT_URI_BACKUP: z.string().optional(),
  GOOGLE_ACTIVE_PROFILE: z.enum(['primary', 'backup']).default('primary'),
  GOOGLE_PROFILE_FAILOVER_ENABLED: envBoolean(true),
  GMAIL_REFRESH_TOKEN: z.string().optional(),
  GMAIL_SENDER_EMAIL: z.string().optional(),
  GMAIL_REFRESH_TOKEN_BACKUP: z.string().optional(),
  GMAIL_SENDER_EMAIL_BACKUP: z.string().optional(),
  GMAIL_DAILY_SEND_CAP_PER_ACCOUNT: z.coerce.number().int().positive().default(100),
  REDIS_URL: z.string().optional(),
  APOLLO_API_KEY: z.string().optional(),
  APOLLO_BASE_URL: z.string().default('https://api.apollo.io/api/v1'),
  APIFY_API_TOKEN: z.string().optional(),
  APIFY_ACTOR_ID: z.string().optional(),
  UPSIDE_API_URL: z.string().optional(),
  UPSIDE_API_KEY: z.string().optional(),
  GOOGLE_MAPS_API_KEY: z.string().optional(),
  API_OUTBOUND_TIMEOUT_MS: z.coerce.number().int().positive().default(15000),
  API_OUTBOUND_ALLOWLIST: z.string().default('generativelanguage.googleapis.com,oauth2.googleapis.com,gmail.googleapis.com,www.googleapis.com,api.apify.com,maps.googleapis.com,router.huggingface.co'),
  GOOGLE_SA_PROJECT_ID: z.string().optional(),
  GOOGLE_SA_CLIENT_EMAIL: z.string().optional(),
  GOOGLE_SA_PRIVATE_KEY_ID: z.string().optional(),
  ENABLE_SCHEDULER: envBoolean(false),
})

export const env = envSchema.parse(process.env)

export type GeminiAgentRole =
  | 'jarvis'
  | 'damien'
  | 'noah'
  | 'zoya'
  | 'devan'
  | 'akhil'
  | 'king'

const geminiRoleAliases: Record<string, GeminiAgentRole> = {
  ceo: 'jarvis',
  orchestrator: 'jarvis',
  cto: 'damien',
  ops: 'damien',
  cmo: 'noah',
  cfo: 'zoya',
  analytics: 'zoya',
  lead_generation: 'devan',
  leadgen: 'devan',
  lead_management: 'akhil',
  training: 'king',
  memory: 'king',
}

export function geminiApiKeyFor(role: GeminiAgentRole | string = 'jarvis') {
  const normalized = String(role).trim().toLowerCase().replace(/[\s-]+/g, '_')
  const canonical = geminiRoleAliases[normalized] ?? (normalized as GeminiAgentRole)
  const perRoleKey = {
    jarvis: env.GEMINI_API_KEY_JARVIS,
    damien: env.GEMINI_API_KEY_DAMIEN,
    noah: env.GEMINI_API_KEY_NOAH,
    zoya: env.GEMINI_API_KEY_ZOYA,
    devan: env.GEMINI_API_KEY_DEVAN,
    akhil: env.GEMINI_API_KEY_AKHIL,
    king: env.GEMINI_API_KEY_KING,
  }[canonical]
  return perRoleKey || env.GEMINI_API_KEY
}

if (env.NODE_ENV === 'production') {
  if (env.REQUIRE_API_KEY && !env.BACKEND_API_KEY) {
    throw new Error('BACKEND_API_KEY must be set when REQUIRE_API_KEY=true in production.')
  }
  if (!env.SUPABASE_URL || !env.SUPABASE_SECRET_KEY) {
    throw new Error('SUPABASE_URL and SUPABASE_SECRET_KEY are required in production.')
  }
}
