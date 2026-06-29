# Cloudflare Edge Checklist

Use Cloudflare in front of the Railway backend after Railway is live.

## Recommended setup

- Put the backend on a custom subdomain such as `api.yourdomain.com`
- Proxy that DNS record through Cloudflare
- Use SSL mode `Full (strict)`
- Enable WAF managed rules
- Add rate limiting for sensitive routes

## High-priority rate-limited routes

- `POST /api/jarvis`
- `POST /api/jarvis/sovereign/goal`
- `POST /api/outreach/send`
- `POST /api/outreach/enrich-and-draft`
- `GET /api/google/oauth/start`
- `GET /api/google/oauth/callback`

## App-side requirements

- Keep `REQUIRE_API_KEY=true`
- Set a strong `BACKEND_API_KEY`
- Restrict `ALLOWED_ORIGINS` to the real frontend URL plus localhost for development
- Keep all secrets in Railway, not in Vercel

## Important note

Cloudflare protects the backend edge. It does not replace Supabase auth, backend auth, or provider secret management.
