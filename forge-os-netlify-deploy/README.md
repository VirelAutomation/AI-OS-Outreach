# FORGE OS

Single-page AI business operating system for a solo AI agency founder.

## Run

```bash
npm install
npm run dev
```

Vite will print the local URL, usually `http://localhost:5173/`.

## Verify

```bash
npm run lint
npm run build
```

Both commands currently pass.

## API Safety

The frontend now expects a split deploy with a server-side backend. Browser code only uses public `VITE_*` values; provider credentials, Gmail OAuth refresh tokens, Gemini keys, and Hugging Face tokens stay on the backend.

When you add the backend, keep these server-side only:

```bash
GEMINI_API_KEY=replace_on_server
GOOGLE_CLIENT_ID=replace_on_server
GOOGLE_CLIENT_SECRET=replace_on_server
GMAIL_REFRESH_TOKEN=replace_on_server
SUPABASE_SERVICE_ROLE_KEY=replace_on_server
REDIS_URL=replace_on_server
```

Frontend should call backend endpoints such as `POST /api/jarvis` and `POST /api/outreach/send`. If you enable backend API key enforcement, the frontend sends the optional weak gate in the `x-api-key` header from `VITE_BACKEND_API_KEY`.

Backend env placeholders are in [backend/.env.example](./backend/.env.example).

## Supabase

The frontend is wired to Supabase through:

```bash
VITE_SUPABASE_URL
VITE_SUPABASE_PUBLISHABLE_KEY
```

Run [supabase/schema.v1.sql](./supabase/schema.v1.sql) and then [supabase/schema.v2.sql](./supabase/schema.v2.sql) in the Supabase SQL Editor. `forge_settings` now also backs cloud-persisted runtime state, audit logs, CRL learning state, CMO artifacts, and Gmail OAuth token storage when the backend is deployed on Railway.
