# GitHub Cron Autonomy

This is the free-tier fallback when you do not have a true always-on host.

## What it does

GitHub Actions runs [social-cron.yml](C:/Users/Marilyn/Downloads/AI OS/.github/workflows/social-cron.yml) every hour.
Each run:

- restores runtime state from the previous run
- executes the current or recently missed outreach slot in IST
- runs Instagram reply checks
- runs scheduled follow-ups at 11:00 and 22:00 IST
- rebuilds CRL reply-learning artifacts from the latest IG/FB outcome logs
- optionally runs the optimizer dry-run if reply count is still zero
- saves runtime state back into the workflow cache and uploads reports as artifacts

The tick logic lives in [cloud_autonomy_tick.py](C:/Users/Marilyn/Downloads/AI OS/cloud_autonomy_tick.py).

## What this is good for

- no local PC required
- no credit card required
- GitHub-only backend scheduling
- recovery if one scheduled run fails and the next run needs to catch up

## What this is not

- not a true always-on daemon
- not ideal for long-lived browser sessions
- not a guaranteed replacement for a persistent backend host

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
GEMINI_API_KEY=
GEMINI_API_KEY_JARVIS=
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
```

`INSTAGRAM_SESSION_ID` / `INSTAGRAM_SESSION` and `FACEBOOK_SESSION` are the most important.

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
