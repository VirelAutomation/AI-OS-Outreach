"""Outreach pipeline router - drafts, sends, replies, and social runtime activity."""

import logging

from fastapi import APIRouter, Body

from database.supabase import db
from services.social_activity import list_recent_social_activity

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/outreach", tags=["outreach"])


def _safe_query(table_name: str, select_clause: str, limit: int):
    try:
        sdb = db()
        return sdb.table(table_name).select(select_clause).order("created_at", desc=True).limit(limit).execute().data or []
    except Exception as exc:
        logger.debug("Outreach query failed for %s: %s", table_name, exc)
        return []


@router.get("/dashboard", summary="Outreach pipeline activity: drafts, sends, replies, and social runtime")
async def outreach_dashboard(limit: int = 20):
    try:
        social = list_recent_social_activity(limit=limit)
        return {
            "ok": True,
            "drafts": _safe_query(
                "outreach_drafts",
                "id,subject,mode,created_at,prospects(full_name,company_name,email)",
                limit,
            ),
            "sends": _safe_query(
                "outreach_sends",
                "id,recipient_email,status,reason,created_at,prospects(full_name,company_name),outreach_drafts(subject,mode)",
                limit,
            ),
            "replies": _safe_query(
                "outreach_replies",
                "id,intent,raw_text,created_at,prospects(full_name,company_name,email)",
                limit,
            ),
            "social_activity": social["activity"],
            "social_summary": social["summary"],
            "runtime_snapshot": social["runtime_snapshot"],
            "source": social["source"],
        }
    except Exception as exc:
        logger.error("Outreach dashboard failed: %s", exc)
        return {
            "ok": True,
            "drafts": [],
            "sends": [],
            "replies": [],
            "social_activity": [],
            "social_summary": {"total": 0, "by_platform": {}, "by_channel": {}, "failures": 0},
            "runtime_snapshot": None,
            "source": "error",
        }


@router.post("/sync-replies", summary="Pull Gmail replies and import unread ones")
async def sync_replies(body: dict = Body(default={})):
    try:
        from services.gmail import list_recent_replies

        limit = body.get("limit", 20)
        imported, duplicates, unmatched = 0, 0, 0
        replies = await list_recent_replies(limit=limit)
        sdb = db()
        for reply in replies:
            try:
                if not sdb:
                    break
                lead_res = sdb.table("leads").select("id").ilike("email", reply.get("from_email", "")).limit(1).execute()
                lead = (lead_res.data or [{}])[0]
                if not lead.get("id"):
                    unmatched += 1
                    continue
                existing = sdb.table("outreach_replies").select("id").eq("gmail_message_id", reply.get("message_id", "")).limit(1).execute()
                if existing.data:
                    duplicates += 1
                    continue
                sdb.table("outreach_replies").insert({
                    "lead_id": lead["id"],
                    "intent": reply.get("intent", "unknown"),
                    "raw_text": reply.get("body", "")[:500],
                    "gmail_message_id": reply.get("message_id", ""),
                }).execute()
                imported += 1
            except Exception:
                unmatched += 1
        return {"ok": True, "synced": imported, "duplicates": duplicates, "unmatched": unmatched}
    except Exception as exc:
        logger.warning("Reply sync failed (Gmail may not be configured): %s", exc)
        return {"ok": True, "synced": 0, "duplicates": 0, "unmatched": 0, "reason": str(exc)}
