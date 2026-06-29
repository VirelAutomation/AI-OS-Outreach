# AI OS Backend Deployment

Backend target: `VirelAutomation/AI-OS-Backend`

This root directory is the backend service. It runs:

- FastAPI backend from `forge_system/forge_system/main.py`
- IG + FB scheduler from `ig_outreach/scheduler.py`
- email scheduler from `email_scheduler.py`
- Jarvis CLI/core, outreach modules, and intelligence engine

## Verified Locally

```powershell
python -m compileall jarvis.py pipeline.py intelligence_engine ig_outreach fb_outreach forge_system\forge_system -q
npm.cmd run build # from forge-os
npm.cmd run build # from forge-os/backend
```

## Railway

Primary path: connect `VirelAutomation/AI-OS-Backend` to Railway and deploy directly from GitHub.

Recommended setup:

1. Railway service source = this GitHub repository
2. Trigger branch = `main`
3. `Wait for CI` = enabled so Railway only deploys when GitHub Actions passes
4. Use `.env.railway.example` as the variable source

CLI fallback still works if needed:

```powershell
npx.cmd @railway/cli login --browserless
npx.cmd @railway/cli init
npx.cmd @railway/cli up
```

Minimum required variables:

```env
PORT=8000
DATA_DIR=/data
GEMINI_API_KEY=...
INSTAGRAM_USERNAME=...
INSTAGRAM_PASSWORD=...
INSTAGRAM_SESSION=...
FACEBOOK_EMAIL=...
FACEBOOK_PASSWORD=...
FACEBOOK_SESSION=...
GMAIL_CLIENT_ID=...
GMAIL_CLIENT_SECRET=...
GMAIL_REFRESH_TOKEN=...
```

## Security Notes

`.dockerignore` excludes local secrets, browser profiles, session files, databases, logs, frontend node modules, and generated archives from the Docker build context.

Do not deploy with local `.env`, `credentials/`, `session_virel.json`, `session_fb.txt`, `*.db`, or `*.log`.
