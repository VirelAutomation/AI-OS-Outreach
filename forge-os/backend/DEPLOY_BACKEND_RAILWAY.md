# AI Forge OS Backend

This directory is the backend repo boundary.

Recommended repository name:

`AI-Forge-OS-Backend`

## What belongs in this repo

- Fastify backend from this directory root
- `src/`
- `supabase/`
- `package.json`
- `Dockerfile`
- backend env templates

## Railway deploy target

- Service type: Dockerfile or Node service
- Start port: `8000`
- Health check: use the backend health endpoints already exposed by the app

## Required production variables

Use `.env.railway.example` as the source of truth.

Minimum critical values:

```env
NODE_ENV=production
PORT=8000
FRONTEND_ORIGIN=https://your-frontend.vercel.app
ALLOWED_ORIGINS=https://your-frontend.vercel.app,http://localhost:5173
REQUIRE_API_KEY=true
BACKEND_API_KEY=replace_with_a_long_random_secret
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SECRET_KEY=your_supabase_service_role_key
```

Recommended open-model fallback for production:

```env
HF_TOKEN=your_huggingface_user_access_token
HF_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507
HF_PROVIDER=auto
```

## Notes

- Keep all provider secrets here, not in the frontend.
- Railway is the right host for this backend shape because it runs as a long-lived Node process.
- Hugging Face is now wired as the open-model fallback path behind the existing LLM abstraction. If Gemini rate-limits or is unavailable, the backend can route to the configured Hugging Face model through `router.huggingface.co`.
- Netlify is not the right primary target for this backend because this codebase is not structured as Netlify Functions and it expects a persistent server process.
- If you keep `REQUIRE_API_KEY=true` for browser traffic, the frontend must send a matching header. That works mechanically, but the key is visible to browser users, so treat it as a light gate only.
- The stronger setup is Cloudflare in front of Railway plus strict CORS and route-level rate limits.
