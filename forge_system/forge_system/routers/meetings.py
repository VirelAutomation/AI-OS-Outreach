"""Meetings router."""

import logging
from fastapi import APIRouter
from database.supabase import db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/meetings", tags=["meetings"])


@router.get("", summary="List all booked meetings")
async def list_meetings(limit: int = 50):
    try:
        sdb = db()
        if not sdb:
            return {"ok": True, "meetings": []}

        res = sdb.table("meetings").select(
            "id,prospect_name,company_name,meeting_type,start_at,status,value_estimate"
        ).order("start_at", desc=True).limit(limit).execute()
        return {"ok": True, "meetings": res.data or []}
    except Exception as exc:
        logger.error("Meetings list failed: %s", exc)
        return {"ok": True, "meetings": []}
