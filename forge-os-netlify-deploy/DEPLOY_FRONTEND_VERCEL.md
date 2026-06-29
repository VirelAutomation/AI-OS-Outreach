# AI Forge OS Frontend

This directory is the frontend repo boundary.

Recommended repository name:

`AI-Forge-OS-Frontend`

## What belongs in this repo

- React/Vite frontend from this directory root
- `src/`
- `public/`
- `package.json`
- `vercel.json`
- frontend-only environment variables

## Vercel settings

- Framework preset: `Vite`
- Root directory: project root
- Build command: `npm run build`
- Output directory: `dist`

## Required environment variables

```env
VITE_API_BASE_URL=https://your-backend-domain.up.railway.app
VITE_BACKEND_API_KEY=
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=your_supabase_publishable_key
VITE_GOOGLE_CLIENT_ID=your_google_client_id
```

## Local development

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Notes

- The frontend already uses `VITE_API_BASE_URL` for all API calls.
- If you decide to enforce `BACKEND_API_KEY` at the backend, the frontend can send `VITE_BACKEND_API_KEY`, but that value is browser-visible and should be treated as a weak gate only.
- Stronger production posture: put the Railway API behind Cloudflare and enforce edge controls there instead of relying on a browser-exposed shared key.
- Keep secrets out of this repo. Only `VITE_*` public values belong here.
