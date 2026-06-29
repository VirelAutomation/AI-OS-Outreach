# AI OS Backend - Render Deployment

Backend target: [VirelAutomation/AI-OS-Outreach](https://github.com/VirelAutomation/AI-OS-Outreach)

This root directory is the outreach backend/runtime. On Render it is now intended to run in API-first mode while GitHub Actions owns the live social schedule.

## One-click deploy

1. Open [Render Dashboard](https://dashboard.render.com/)
2. `New -> Blueprint`
3. Connect GitHub and select `VirelAutomation/AI-OS-Outreach`
4. Render reads `render.yaml` from branch `clean-main`
5. In the service `Environment` tab, paste values from `.env.render.example`
6. Keep the default role flags unless you explicitly want a background worker host:
   - `RUN_API=1`
   - `RUN_SOCIAL_SCHEDULER=0`
   - `RUN_EMAIL_SCHEDULER=0`
   - `RUN_JARVIS_SUPERVISOR=0`
7. Deploy and verify `https://<your-service>.onrender.com/health/`

## What runs on Render

Default Render role:

| Process | Role |
|---------|------|
| `uvicorn main:app` | API + Jarvis-facing backend |

Optional roles, only if you explicitly enable them:

| Env flag | Process |
|----------|---------|
| `RUN_SOCIAL_SCHEDULER=1` | `ig_outreach/scheduler.py` |
| `RUN_EMAIL_SCHEDULER=1` | `email_scheduler.py` |
| `RUN_JARVIS_SUPERVISOR=1` | `outreach_agent.py` |

`DATA_DIR=/data` stores SQLite DBs, session files, screenshots, and runtime state on the Render disk.

## GitHub vs Render ownership

- GitHub Actions `social-cron.yml` is the live outreach scheduler.
- Render is the API/health/runtime inspection surface.
- Do not enable both GitHub cron and Render social schedulers against the same accounts unless you intentionally want duplicate sends.

## Required environment variables

Copy `.env.render.example` into Render `Environment`. Minimum for a healthy API deploy:

```env
PORT=8000
DATA_DIR=/data
APP_ENV=production
API_SECRET_KEY=<random-32+-chars>
RUN_API=1
RUN_SOCIAL_SCHEDULER=0
RUN_EMAIL_SCHEDULER=0
RUN_JARVIS_SUPERVISOR=0
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=
DATABASE_URL=
REDIS_URL=
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
CORS_ALLOW_ORIGINS=
```

If you ever enable the social scheduler on Render, these become mandatory:

```env
INSTAGRAM_USERNAME=
INSTAGRAM_PASSWORD=
INSTAGRAM_SESSION=
INSTAGRAM_SESSION_ID=
FACEBOOK_EMAIL=
FACEBOOK_PASSWORD=
FACEBOOK_SESSION=
```

## Pre-deploy verification

```powershell
python -m compileall jarvis.py pipeline.py intelligence_engine ig_outreach fb_outreach forge_system\forge_system -q
python ig_outreach/scheduler.py --test
python cloud_autonomy_tick.py --plan
```

## Post-deploy health check

```powershell
curl https://<your-service>.onrender.com/health/
curl https://<your-service>.onrender.com/
```

Check Render logs for API-first mode:

```text
[START] RUN_API=1 RUN_SOCIAL_SCHEDULER=0 RUN_EMAIL_SCHEDULER=0 RUN_JARVIS_SUPERVISOR=0
[START] FastAPI backend on port 8000...
```

If you see the social scheduler or email scheduler starting on Render while GitHub cron is live, your role flags are wrong.
