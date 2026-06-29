#!/bin/bash
# Virel Automation - cloud startup script (Render / Railway)
# Launches: IG+FB scheduler | email scheduler | FastAPI backend

set -e

export PORT="${PORT:-8000}"
export PYTHONPATH="/app${PYTHONPATH:+:$PYTHONPATH}"

fail=false
missing_envs=()
for name in INSTAGRAM_USERNAME INSTAGRAM_PASSWORD FACEBOOK_EMAIL FACEBOOK_PASSWORD; do
  if [ -z "${!name}" ]; then
    missing_envs+=("$name")
  fi
done
if [ ${#missing_envs[@]} -ne 0 ]; then
  echo "[ERROR] Missing required environment variables: ${missing_envs[*]}"
  echo "Please set them in Render environment settings."
  exit 1
fi

if [ -z "$INSTAGRAM_SESSION" ] && [ -z "$INSTAGRAM_SESSION_ID" ]; then
  echo "[ERROR] INSTAGRAM_SESSION or INSTAGRAM_SESSION_ID is required for cloud deployment."
  echo "Run ig_outreach/ig_session_refresh.py locally and set INSTAGRAM_SESSION or INSTAGRAM_SESSION_ID in Render."
  exit 1
fi

if [ -z "$FACEBOOK_SESSION" ]; then
  echo "[ERROR] FACEBOOK_SESSION is required for cloud deployment."
  echo "Run fb_outreach/fb_login.py locally to refresh and export FACEBOOK_SESSION."
  exit 1
fi

# Validate known session formats before starting
python - <<'PY'
import os, sys, base64, json

for name in ('INSTAGRAM_SESSION', 'FACEBOOK_SESSION'):
    value = os.getenv(name, '')
    if not value:
        continue
    try:
        decoded = base64.b64decode(value)
        json.loads(decoded.decode('utf-8'))
    except Exception as exc:
        print(f'[ERROR] {name} is not valid base64 JSON: {exc}')
        sys.exit(1)
print('[START] Session env validation passed')
PY

echo "========================================"
echo "  Virel Automation - Starting Services"
echo "========================================"

# Start IG + FB outreach scheduler in background
echo "[START] IG/FB outreach scheduler..."
python ig_outreach/scheduler.py &
IG_SCHED_PID=$!

# Start email scheduler in background
echo "[START] Email scheduler..."
python email_scheduler.py &
EMAIL_SCHED_PID=$!

# Allow schedulers a moment to initialize
sleep 2

echo "[START] FastAPI backend on port $PORT..."
cd forge_system/forge_system
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers 1 \
    --log-level info \
    --no-access-log
