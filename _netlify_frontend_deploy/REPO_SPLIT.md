# Repo Split

The current codebase is already split along the right boundary for two repositories:

- Frontend repo: `forge-os/`
- Backend repo: `forge-os/backend/`

Recommended repository names:

- `AI-Forge-OS-Frontend`
- `AI-Forge-OS-Backend`

## Push plan

1. Create a new GitHub repository for the frontend and push the contents of `forge-os/`.
2. Create a new GitHub repository for the backend and push the contents of `forge-os/backend/`.
3. Deploy the frontend repo to Vercel.
4. Deploy the backend repo to Railway.
5. Set `VITE_API_BASE_URL` in Vercel to the Railway backend URL.
6. Set `FRONTEND_ORIGIN` and `ALLOWED_ORIGINS` in Railway to the Vercel frontend URL.

## Security boundary

- Frontend repo: public env only, `VITE_*`
- Backend repo: Supabase service role, Gemini keys, Google OAuth, Gmail, Redis, outbound API keys
