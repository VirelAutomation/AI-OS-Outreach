# AI OS Backend

This repository is the GitHub source of truth for the Virel Automation backend.

It ships:

- the FastAPI backend in `forge_system/forge_system`
- Instagram and Facebook outreach workers in `ig_outreach/` and `fb_outreach/`
- schedulers, Jarvis orchestration, and the intelligence engine
- a Hugging Face Space stub in `forge_system/hf_space`

## GitHub-first deploy flow

1. Push to `main`.
2. GitHub Actions runs `Backend CI`.
3. Deploy from GitHub using **Render** (recommended) or **Railway**:
   - **Render:** [DEPLOY_BACKEND_RENDER.md](DEPLOY_BACKEND_RENDER.md) + `render.yaml` Blueprint
   - **Railway:** connect repo, enable `Wait for CI`, use [DEPLOY_BACKEND_RAILWAY.md](DEPLOY_BACKEND_RAILWAY.md)
4. Set environment variables from `.env.render.example` (Render) or `.env.railway.example` (Railway).

This keeps deploy control in the repository and runs outreach schedulers on an always-on host (no local PC required).

## Required Render / Railway configuration

Use the values in `.env.render.example` or `.env.railway.example`.

Minimum runtime secrets:

- `GEMINI_API_KEY`
- `INSTAGRAM_USERNAME`
- `INSTAGRAM_PASSWORD`
- `INSTAGRAM_SESSION`
- `FACEBOOK_EMAIL`
- `FACEBOOK_PASSWORD`
- `FACEBOOK_SESSION`
- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`

## Local verification

```powershell
python -m compileall jarvis.py pipeline.py intelligence_engine ig_outreach fb_outreach forge_system\forge_system -q
docker build . -t ai-os-backend:local
```
