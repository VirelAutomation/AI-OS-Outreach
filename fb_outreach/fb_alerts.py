"""
Production alerting — Slack webhook + Telegram.
Fire and forget: never raises, never blocks the outreach run.
Configure via env vars — silently no-ops if neither is set.

SLACK_WEBHOOK_URL  = https://hooks.slack.com/services/...
TELEGRAM_BOT_TOKEN = 123456:ABC...
TELEGRAM_CHAT_ID   = -100123456789
"""

import os, logging, requests
from datetime import datetime, timezone, timedelta

log  = logging.getLogger("virel.fb.alerts")
_IST = timezone(timedelta(hours=5, minutes=30))

_SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")
_TG_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN", "")
_TG_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID", "")

_ICONS = {"info": "ℹ️", "warn": "⚠️", "error": "🚨", "ok": "✅"}


def alert(title: str, body: str = "", level: str = "error"):
    """Send alert to all configured channels. Safe to call from anywhere."""
    now  = datetime.now(_IST).strftime("%d %b %H:%M IST")
    icon = _ICONS.get(level, "🔔")
    text = f"{icon} *{title}*\n{body}\n_{now}_" if body else f"{icon} *{title}*\n_{now}_"

    _try_slack(text)
    _try_telegram(text)
    log.warning(f"[ALERT:{level.upper()}] {title}" + (f" — {body[:120]}" if body else ""))


def _try_slack(text: str):
    if not _SLACK_WEBHOOK:
        return
    try:
        requests.post(_SLACK_WEBHOOK, json={"text": text}, timeout=5)
    except Exception:
        pass


def _try_telegram(text: str):
    if not _TG_TOKEN or not _TG_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{_TG_TOKEN}/sendMessage",
            json={"chat_id": _TG_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=5,
        )
    except Exception:
        pass
