# AI OS Backend — Render Deployment

Backend target: [VirelAutomation/AI-OS-Backend](https://github.com/VirelAutomation/AI-OS-Backend)

This root directory is the always-on backend. On Render it runs:

- FastAPI from `forge_system/forge_system/main.py`
- IG + FB outreach scheduler (`ig_outreach/scheduler.py`) — DMs, comments, group posts, follow-ups
- Email scheduler (`email_scheduler.py`)
- Jarvis / intelligence engine

## One-click deploy (recommended)

1. Open [Render Dashboard](https://dashboard.render.com/)
2. **New → Blueprint**
3. Connect GitHub → select `VirelAutomation/AI-OS-Backend`
4. Render reads `render.yaml` and creates the web service + 1 GB persistent disk at `/data`
5. In the service **Environment** tab, paste secrets from `.env.render.example`
6. Click **Manual Deploy → Deploy latest commit**
7. When live, open `https://<your-service>.onrender.com/health/`

## What makes it autonomous (no PC required)

Once deployed, `start.sh` keeps three processes alive on Render:

| Process | Role |
|---------|------|
| `ig_outreach/scheduler.py` | IG DMs, comments, follow-ups, reply checks |
| `email_scheduler.py` | Gmail campaigns |
| `uvicorn main:app` | API + Jarvis |

`DATA_DIR=/data` (Render disk) stores outreach SQLite DBs and refreshed IG/FB sessions across restarts.

**Free-tier fallback:** GitHub Actions [social-cron.yml](.github/workflows/social-cron.yml) runs hourly if Render is down. Enable repo secrets listed in [GITHUB_CRON_AUTONOMY.md](GITHUB_CRON_AUTONOMY.md).

## Required environment variables

Copy `.env.render.example` into Render **Environment**. Minimum for a healthy deploy:

```env
PORT=8000
DATA_DIR=/data
APP_ENV=production
API_SECRET_KEY=<random-32+-chars>
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=
DATABASE_URL=
REDIS_URL=
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
INSTAGRAM_USERNAME=
INSTAGRAM_PASSWORD=
INSTAGRAM_SESSION=
FACEBOOK_EMAIL=
FACEBOOK_PASSWORD=
FACEBOOK_SESSION=
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
GMAIL_REFRESH_TOKEN=
GMAIL_SENDER_EMAIL=
```

**Critical for social automation:** `INSTAGRAM_SESSION` (or `INSTAGRAM_SESSION_ID`) and `FACEBOOK_SESSION` must be valid browser-exported sessions. Local session files are **not** baked into the Docker image.

## Pre-deploy verification

```powershell
python test_audit.py --no-drafts
python -m compileall jarvis.py pipeline.py intelligence_engine ig_outreach fb_outreach forge_system\forge_system -q
docker build . -t ai-os-backend:local
```

## Post-deploy health check

```powershell
curl https://<your-service>.onrender.com/health/
curl https://<your-service>.onrender.com/
```

Check Render logs for:

```
[SCHED] IG/FB outreach scheduler...
[SCHED] Email scheduler...
[START] FastAPI backend on port 8000...
```

## Outreach stress test (after deploy)

Run from Render **Shell** (or locally with production env):

```bash
python test_audit.py --no-drafts
python fb_outreach/main.py --status
python ig_outreach/scheduler.py --status
python ig_outreach/scheduler.py --test    # schedule dry-run only
```

To fire one live slot immediately (uses real accounts):

```bash
python ig_outreach/scheduler.py --now
```

## Render vs Railway

This repo also supports Railway (`railway.json`, `DEPLOY_BACKEND_RAILWAY.md`). Use **one** always-on host — Render **or** Railway — plus GitHub cron as backup. Do not run two schedulers against the same IG/FB accounts.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Build fails on import | Set all Supabase + Redis + Gemini env vars before deploy |
| `/health/` 502 | Check logs; often missing `API_SECRET_KEY` when `APP_ENV=production` |
| IG login fails | Refresh `INSTAGRAM_SESSION` via `python ig_outreach/ig_session_refresh.py` locally, copy to Render env |
| FB posts fail | Confirm Chromium in Docker logs; refresh `FACEBOOK_SESSION` |
| Redis errors | Use `rediss://` URL for Upstash; plain `redis://` for local/non-TLS |
| Gmail not sending | Set `GMAIL_REFRESH_TOKEN` (audit flags this) |
