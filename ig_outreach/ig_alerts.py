"""
IG production alerting — Slack webhook + Telegram.
Same env vars as fb_alerts: SLACK_WEBHOOK_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""
import os, logging, requests
from datetime import datetime, timezone, timedelta

log  = logging.getLogger("virel.ig.alerts")
_IST = timezone(timedelta(hours=5, minutes=30))

_SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")
_TG_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN", "")
_TG_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID", "")

_ICONS = {"info": "ℹ️", "warn": "⚠️", "error": "🚨", "ok": "✅"}


def alert(title: str, body: str = "", level: str = "error"):
    now  = datetime.now(_IST).strftime("%d %b %H:%M IST")
    icon = _ICONS.get(level, "🔔")
    text = f"{icon} *[IG] {title}*\n{body}\n_{now}_" if body else f"{icon} *[IG] {title}*\n_{now}_"

    _slack(text)
    _telegram(text)
    log.warning(f"[IG ALERT:{level.upper()}] {title}" + (f" — {body[:120]}" if body else ""))


def _slack(text: str):
    if not _SLACK_WEBHOOK:
        return
    try:
        requests.post(_SLACK_WEBHOOK, json={"text": text}, timeout=5)
    except Exception:
        pass


def _telegram(text: str):
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
