"""Calendar router — Google Calendar sync and priority blocks."""

import logging
from fastapi import APIRouter, Body
from services.google_calendar import list_events
from config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/sync", summary="Sync Google Calendar events and prioritise them")
async def sync_calendar(days: int = 3):
    try:
        result = await list_events(days=days)
        events = result.get("events", [])
        priorities = _prioritise(events)
        today_count = len([e for e in events if _is_today(e.get("start", ""))])
        return {
            "ok": True,
            "mode": "live" if events else "offline",
            "analysis": {
                "events": events,
                "priorities": priorities,
                "todaySummary": f"{today_count} events today",
                "suggestedFocus": _suggest_focus(events),
            },
        }
    except Exception as exc:
        logger.warning("Calendar sync failed (likely not configured): %s", exc)
        return {
            "ok": True,
            "mode": "offline",
            "analysis": {
                "events": [],
                "priorities": [],
                "todaySummary": "Calendar not connected",
                "suggestedFocus": "Connect Google Calendar at /api/google/oauth/start",
            },
        }


@router.post("/priority-block", summary="Create a priority block on Google Calendar")
async def priority_block(body: dict = Body(...)):
    return {"ok": False, "error": "Calendar write requires Google Calendar API write scope. Re-run OAuth at /api/google/oauth/start"}


def _is_today(start_str: str) -> bool:
    try:
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date().isoformat()
        return start_str.startswith(today)
    except Exception:
        return False


def _prioritise(events: list) -> list:
    BUSINESS_KEYWORDS = ["meeting", "call", "client", "demo", "pitch", "investor", "review", "interview"]
    result = []
    for e in events:
        summary = e.get("summary", "").lower()
        is_biz = any(k in summary for k in BUSINESS_KEYWORDS)
        result.append({
            "event": e,
            "reason": "Business-critical event" if is_biz else "Standard event",
            "businessRelevance": "high" if is_biz else "low",
        })
    return result


def _suggest_focus(events: list) -> str:
    if not events:
        return "No events found — deep work window open"
    high = [e for e in events if any(k in e.get("summary", "").lower() for k in ["meeting", "call", "demo"])]
    if high:
        return f"Prepare for: {high[0].get('summary', 'meeting')}"
    return "Clear schedule — focus on outreach and pipeline"
