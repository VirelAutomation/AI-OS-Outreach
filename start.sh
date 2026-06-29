#!/bin/bash
# Virel Automation cloud startup script.
# Runtime roles are controlled by env flags so Render can stay API-only while
# GitHub Actions owns the live outreach schedule.

set -e

export PORT="${PORT:-8000}"
export PYTHONPATH="/app${PYTHONPATH:+:$PYTHONPATH}"

RUN_API="${RUN_API:-1}"
RUN_SOCIAL_SCHEDULER="${RUN_SOCIAL_SCHEDULER:-1}"
RUN_EMAIL_SCHEDULER="${RUN_EMAIL_SCHEDULER:-1}"
RUN_JARVIS_SUPERVISOR="${RUN_JARVIS_SUPERVISOR:-0}"

is_enabled() {
  [ "$1" = "1" ] || [ "$1" = "true" ] || [ "$1" = "TRUE" ]
}

require_social_env() {
  local missing_envs=()
  for name in INSTAGRAM_USERNAME INSTAGRAM_PASSWORD FACEBOOK_EMAIL FACEBOOK_PASSWORD; do
    if [ -z "${!name}" ]; then
      missing_envs+=("$name")
    fi
  done

  if [ ${#missing_envs[@]} -ne 0 ]; then
    echo "[ERROR] Missing required social environment variables: ${missing_envs[*]}"
    exit 1
  fi

  if [ -z "$INSTAGRAM_SESSION" ] && [ -z "$INSTAGRAM_SESSION_ID" ]; then
    echo "[ERROR] INSTAGRAM_SESSION or INSTAGRAM_SESSION_ID is required when RUN_SOCIAL_SCHEDULER=1."
    exit 1
  fi

  if [ -z "$FACEBOOK_SESSION" ]; then
    echo "[ERROR] FACEBOOK_SESSION is required when RUN_SOCIAL_SCHEDULER=1."
    exit 1
  fi
}

validate_sessions() {
  python - <<'PY'
import base64
import json
import os
import sys

for name in ("INSTAGRAM_SESSION", "FACEBOOK_SESSION"):
    value = os.getenv(name, "")
    if not value:
        continue
    try:
        decoded = base64.b64decode(value)
        json.loads(decoded.decode("utf-8"))
    except Exception as exc:
        print(f"[ERROR] {name} is not valid base64 JSON: {exc}")
        sys.exit(1)
print("[START] Session env validation passed")
PY
}

if ! is_enabled "$RUN_API" && ! is_enabled "$RUN_SOCIAL_SCHEDULER" && ! is_enabled "$RUN_EMAIL_SCHEDULER" && ! is_enabled "$RUN_JARVIS_SUPERVISOR"; then
  echo "[ERROR] Nothing to run. Enable at least one of RUN_API, RUN_SOCIAL_SCHEDULER, RUN_EMAIL_SCHEDULER, RUN_JARVIS_SUPERVISOR."
  exit 1
fi

if is_enabled "$RUN_SOCIAL_SCHEDULER"; then
  require_social_env
  validate_sessions
fi

echo "========================================"
echo "  Virel Automation - Starting Services"
echo "========================================"
echo "[START] RUN_API=$RUN_API RUN_SOCIAL_SCHEDULER=$RUN_SOCIAL_SCHEDULER RUN_EMAIL_SCHEDULER=$RUN_EMAIL_SCHEDULER RUN_JARVIS_SUPERVISOR=$RUN_JARVIS_SUPERVISOR"

if is_enabled "$RUN_SOCIAL_SCHEDULER"; then
  echo "[START] IG/FB outreach scheduler..."
  python ig_outreach/scheduler.py &
fi

if is_enabled "$RUN_EMAIL_SCHEDULER"; then
  echo "[START] Email scheduler..."
  python email_scheduler.py &
fi

if is_enabled "$RUN_JARVIS_SUPERVISOR"; then
  if [ -f "outreach_agent.py" ]; then
    echo "[START] Jarvis supervisor..."
    python outreach_agent.py &
  else
    echo "[WARN] RUN_JARVIS_SUPERVISOR=1 but outreach_agent.py was not found; skipping."
  fi
fi

if is_enabled "$RUN_API"; then
  sleep 2
  echo "[START] FastAPI backend on port $PORT..."
  cd forge_system/forge_system
  exec uvicorn main:app \
      --host 0.0.0.0 \
      --port "$PORT" \
      --workers 1 \
      --log-level info \
      --no-access-log
fi

echo "[START] Background-only role set running. Waiting on child processes..."
wait
