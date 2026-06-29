# FORGE OS Backend Contract

The frontend is ready to call a backend, but secrets must stay here, not in React.

## Required Endpoints

```txt
POST /api/jarvis
POST /api/outreach/send
POST /api/outreach/personalize
POST /api/public/chat
POST /api/public/bookings
GET  /api/crm/prospects
GET  /api/crm/dashboard
GET  /api/meetings
GET  /api/analytics/roots
GET  /api/content/queue
GET  /api/supabase/health
GET  /api/google/oauth/start
GET  /api/google/oauth/callback
```

## Data System

The frontend now builds a local prefix index plus sparse-Merkle-style roots for:

```txt
calls
campaigns
meetings
deals
products
settings
```

Backend should store canonical data in Supabase. For large datasets, keep the same concept server-side:

```txt
collection table -> incremental index table -> collection root -> global root
```

Use the global root as the fast version/checkpoint value. If a root has not changed, the frontend can skip a heavy refetch.

## Security Rules

Use `SUPABASE_SECRET_KEY`, Gemini API key, Gmail OAuth secret, and legacy JWT secret only inside backend runtime.

Do not add these to `VITE_*`.

See also [ARCHITECTURE.md](./ARCHITECTURE.md) and [schema.v1.sql](./supabase/schema.v1.sql).
