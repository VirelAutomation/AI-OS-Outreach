"""Outreach pipeline router — drafts, sends, replies dashboard."""

import logging
from fastapi import APIRouter, Body
from database.supabase import db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/outreach", tags=["outreach"])


@router.get("/dashboard", summary="Outreach pipeline activity: drafts, sends, replies")
async def outreach_dashboard(limit: int = 20):
    try:
        sdb = db()
        if not sdb:
            return {"ok": True, "drafts": [], "sends": [], "replies": [], "source": "no_db"}

        drafts_res = sdb.table("outreach_drafts").select(
            "id,subject,mode,created_at,prospects(full_name,company_name,email)"
        ).order("created_at", desc=True).limit(limit).execute()

        sends_res = sdb.table("outreach_sends").select(
            "id,recipient_email,status,reason,created_at,prospects(full_name,company_name),outreach_drafts(subject,mode)"
        ).order("created_at", desc=True).limit(limit).execute()

        replies_res = sdb.table("outreach_replies").select(
            "id,intent,raw_text,created_at,prospects(full_name,company_name,email)"
        ).order("created_at", desc=True).limit(limit).execute()

        return {
            "ok": True,
            "drafts": drafts_res.data or [],
            "sends": sends_res.data or [],
            "replies": replies_res.data or [],
            "source": "supabase_live",
        }
    except Exception as exc:
        logger.error("Outreach dashboard failed: %s", exc)
        return {"ok": True, "drafts": [], "sends": [], "replies": [], "source": "error"}


@router.post("/sync-replies", summary="Pull Gmail replies and import unread ones")
async def sync_replies(body: dict = Body(default={})):
    try:
        from services.gmail import list_recent_replies
        limit = body.get("limit", 20)
        imported, duplicates, unmatched = 0, 0, 0
        replies = await list_recent_replies(limit=limit)
        sdb = db()
        for r in replies:
            try:
                if not sdb:
                    break
                lead_res = sdb.table("leads").select("id").ilike("email", r.get("from_email", "")).limit(1).execute()
                lead = (lead_res.data or [{}])[0]
                if not lead.get("id"):
                    unmatched += 1
                    continue
                existing = sdb.table("outreach_replies").select("id").eq("gmail_message_id", r.get("message_id", "")).limit(1).execute()
                if existing.data:
                    duplicates += 1
                    continue
                sdb.table("outreach_replies").insert({
                    "lead_id": lead["id"],
                    "intent": r.get("intent", "unknown"),
                    "raw_text": r.get("body", "")[:500],
                    "gmail_message_id": r.get("message_id", ""),
                }).execute()
                imported += 1
            except Exception:
                unmatched += 1
        return {"ok": True, "synced": imported, "duplicates": duplicates, "unmatched": unmatched}
    except Exception as exc:
        logger.warning("Reply sync failed (Gmail may not be configured): %s", exc)
        return {"ok": True, "synced": 0, "duplicates": 0, "unmatched": 0, "reason": str(exc)}
