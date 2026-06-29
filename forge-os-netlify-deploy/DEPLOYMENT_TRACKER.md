# Forge OS — Deployment Checklist

## Step 1 — Create two GitHub repos

Go to github.com → New Repository:

1. `AI-Forge-OS-Frontend` — push the `forge-os/` directory (excluding `backend/`)
2. `AI-Forge-OS-Backend` — push the `forge-os/backend/` directory

```bash
# From forge-os/ directory
git init
git add .
git commit -m "Initial commit — Forge OS frontend"
git remote add origin https://github.com/YOUR_USERNAME/AI-Forge-OS-Frontend.git
git push -u origin main
```

```bash
# From forge-os/backend/ directory
cd backend
git init
git add .
git commit -m "Initial commit — Forge OS backend"
git remote add origin https://github.com/YOUR_USERNAME/AI-Forge-OS-Backend.git
git push -u origin main
```

---

## Step 2 — Deploy backend to Railway

1. Go to railway.app → New Project → Deploy from GitHub repo → `AI-Forge-OS-Backend`
2. Railway will detect the `Dockerfile` and `railway.toml` automatically
3. Add environment variables from `.env.railway.example`:
   - MINIMUM: `NODE_ENV=production`, `PORT=8000`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `GEMINI_API_KEY`
   - Copy your Railway URL (e.g. `https://forge-os-backend.up.railway.app`)

---

## Step 3 — Apply Supabase schema

1. Go to supabase.com/dashboard → your project → SQL Editor
2. Paste and run `backend/supabase/schema.v1.sql`
3. Paste and run `backend/supabase/schema.v2.sql`
4. Both files use `IF NOT EXISTS` — safe to re-run

OR verify with:
```bash
cd backend && npx tsx scripts/migrate.ts
```

---

## Step 4 — Deploy frontend to Vercel

1. Go to vercel.com → Add New Project → Import `AI-Forge-OS-Frontend`
2. Framework: Vite (auto-detected)
3. Add environment variables:
   ```
   VITE_API_BASE_URL=https://your-railway-url.up.railway.app
   VITE_SCI_API_BASE_URL=https://your-railway-url.up.railway.app
   VITE_BACKEND_API_KEY=same_as_BACKEND_API_KEY_in_railway
   VITE_SUPABASE_URL=https://your-project.supabase.co
   VITE_SUPABASE_PUBLISHABLE_KEY=your_anon_key
   ```
4. Deploy → copy your Vercel URL (e.g. `https://forge-os.vercel.app`)

---

## Step 5 — Update Railway CORS

In Railway variables, set:
```
FRONTEND_ORIGIN=https://forge-os.vercel.app
ALLOWED_ORIGINS=https://forge-os.vercel.app
```

Then redeploy Railway (it auto-redeploys on variable change).

---

## Step 6 — Connect Gmail

1. Go to your deployed Vercel frontend
2. Navigate to Settings → Google OAuth
3. Click "Connect Gmail" → authorize access
4. This stores refresh tokens in Railway (encrypted in Supabase)

---

## Step 7 — Validate

Open your Vercel URL and check:
- [ ] `/api/health` returns `ok: true` with scheduler status
- [ ] Jarvis chat responds
- [ ] Outreach pipeline shows live data
- [ ] SSE events tab at `/api/events` streams heartbeats

---

## CI (GitHub Actions)

`.github/workflows/ci.yml` runs on every push:
- TypeScript check on frontend
- TypeScript check + build on backend
- Docker build check on `main`

Vercel and Railway auto-deploy on push to `main` when repos are connected.

---

## Security checklist

- [ ] `REQUIRE_API_KEY=true` in Railway + matching `VITE_BACKEND_API_KEY` in Vercel
- [ ] `ALLOWED_ORIGINS` set to Vercel URL only (no localhost in production)
- [ ] Supabase Row Level Security enabled (already in schema)
- [ ] Gmail OAuth tokens stored in Supabase, not in env (for multi-account support)

---

## Status

### Done
- [x] Frontend Vite app production-ready (`npm run build`)
- [x] Backend Fastify production-ready (`npm run build && npm start`)
- [x] Dockerfile multi-stage with healthcheck + non-root user
- [x] `railway.toml` deployment config
- [x] `vercel.json` deployment config
- [x] GitHub Actions CI workflow
- [x] Supabase schema files + migration guide
- [x] SSE live events endpoint
- [x] Background scheduler (reply sync, daily brief, lead enrichment, hook experiments)
- [x] All env vars documented in `.env.railway.example`

### Pending (you need to do these)
- [ ] Create GitHub repos and push code
- [ ] Deploy to Railway
- [ ] Run Supabase migrations
- [ ] Deploy to Vercel
- [ ] Set CORS env vars
- [ ] Connect Gmail via OAuth
