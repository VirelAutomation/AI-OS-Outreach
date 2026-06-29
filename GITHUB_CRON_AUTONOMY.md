# GitHub Cron Autonomy

This is the GitHub-driven outreach runtime when you do not want a 24/7 social worker host.

## What it does

GitHub Actions runs [social-cron.yml](C:/Users/Marilyn/Downloads/AI OS/.github/workflows/social-cron.yml) every 30 minutes.
Each run:

- restores runtime state from the previous run
- executes the current or recently missed outreach slots in IST
- runs Instagram reply checks on the `:30` cadence
- runs scheduled follow-ups at `11:00` and `22:30` IST
- runs Gmail morning/evening draft campaigns when due
- rebuilds CRL reply-learning artifacts from the latest IG/FB outcome logs
- optionally runs the optimizer dry-run if reply count is still zero
- mirrors social runtime activity and tick summaries into Supabase when the outreach tables exist
- saves runtime state back into the workflow cache and uploads reports as artifacts

The tick logic lives in [cloud_autonomy_tick.py](C:/Users/Marilyn/Downloads/AI OS/cloud_autonomy_tick.py).

## What this is good for

- no local PC required
- no credit card required
- GitHub-owned outreach scheduling
- catch-up behavior if one scheduled run fails and the next run needs to recover

## What this is not

- not a true always-on daemon
- not ideal for fragile long-lived browser sessions
- not a guaranteed replacement for a persistent social browser host

## Required GitHub secrets

Set these in the GitHub repo before enabling the workflow:

```env
INSTAGRAM_USERNAME=
INSTAGRAM_PASSWORD=
INSTAGRAM_SESSION_ID=
INSTAGRAM_SESSION=
FACEBOOK_EMAIL=
FACEBOOK_PASSWORD=
FACEBOOK_SESSION=
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
GMAIL_REFRESH_TOKEN=
GMAIL_SENDER_EMAIL=
GEMINI_API_KEY=
GEMINI_API_KEY_JARVIS=
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
```

`INSTAGRAM_SESSION_ID` / `INSTAGRAM_SESSION` and `FACEBOOK_SESSION` are the authoritative auth source.
The workflow also caches safe text session artifacts under `.runtime/github-social/ig_outreach/` and `.runtime/github-social/fb_outreach/`, but secrets remain the source of truth.

## Frontend

Keep the frontend on Netlify or Vercel.
Do not try to run the social browser workers there.

Current frontend-ready app:

- [forge-os](C:/Users/Marilyn/Downloads/AI OS/forge-os)

## Reports produced

The workflow uploads:

- `github_social_last_report.json`
- `github_social_state.json`
- `github_social_optimizer.json` when available
- `reply_crl_state.json`
- `reply_crl_dataset.jsonl`
- `reply_crl_graph.json`
- `reply_crl_graph.mmd`
