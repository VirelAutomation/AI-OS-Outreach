"""Google Calendar integration for SCI founder scheduling."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from config import get_settings

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def _is_configured() -> bool:
    s = get_settings()
    return bool(s.gmail_client_id and s.gmail_client_secret and s.gmail_refresh_token)


def _service():
    s = get_settings()
    creds = Credentials(
        token=None,
        refresh_token=s.gmail_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=s.gmail_client_id,
        client_secret=s.gmail_client_secret,
        scopes=_SCOPES,
    )
    creds.refresh(Request())
    return build("calendar", "v3", credentials=creds)


def _list_events_sync(days: int, calendar_id: str) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)
    result = (
        _service()
        .events()
        .list(
            calendarId=calendar_id,
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=100,
        )
        .execute()
    )
    events: list[dict[str, Any]] = []
    for item in result.get("items", []):
        start = (item.get("start") or {}).get("dateTime") or (item.get("start") or {}).get("date")
        end_at = (item.get("end") or {}).get("dateTime") or (item.get("end") or {}).get("date")
        if not start or not end_at:
            continue
        events.append(
            {
                "id": item.get("id"),
                "summary": item.get("summary") or "Untitled event",
                "description": item.get("description") or "",
                "start": start,
                "end": end_at,
                "status": item.get("status") or "confirmed",
            }
        )
    return events


async def list_events(days: int = 7, calendar_id: str | None = None) -> dict[str, Any]:
    if not _is_configured():
        return {"configured": False, "events": [], "source": "unconfigured"}
    try:
        events = await asyncio.to_thread(_list_events_sync, days, calendar_id or get_settings().google_calendar_id)
        return {"configured": True, "events": events, "source": "google_calendar"}
    except Exception as exc:
        logger.error("Calendar sync failed: %s", exc)
        return {"configured": True, "events": [], "source": "error", "error": str(exc)}
