"""CRM router — prospect database."""

import logging
from fastapi import APIRouter
from database.supabase import db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/crm", tags=["crm"])


@router.get("/dashboard", summary="CRM summary: totals, industries, newest")
async def crm_dashboard():
    try:
        sdb = db()
        if not sdb:
            return {"ok": True, "summary": {"totalProspects": 0, "activeProspects": 0, "industries": [], "newest": []}}

        total_res = sdb.table("leads").select("id", count="exact").execute()
        active_res = sdb.table("leads").select("id", count="exact").eq("status", "active").execute()
        ind_res = sdb.table("leads").select("industry").limit(200).execute()
        industries = list({r["industry"] for r in (ind_res.data or []) if r.get("industry")})
        newest_res = sdb.table("leads").select(
            "id,full_name,email,company_name,industry,status,source,created_at"
        ).order("created_at", desc=True).limit(5).execute()

        return {
            "ok": True,
            "summary": {
                "totalProspects": total_res.count or 0,
                "activeProspects": active_res.count or 0,
                "industries": industries[:10],
                "newest": newest_res.data or [],
            },
        }
    except Exception as exc:
        logger.error("CRM dashboard failed: %s", exc)
        return {"ok": True, "summary": {"totalProspects": 0, "activeProspects": 0, "industries": [], "newest": []}}


@router.get("/prospects", summary="List all prospects (paginated)")
async def list_prospects(limit: int = 50, offset: int = 0, status: str | None = None):
    try:
        sdb = db()
        if not sdb:
            return {"ok": True, "prospects": []}

        q = sdb.table("leads").select(
            "id,full_name,email,company_name,industry,city,status,source,created_at"
        ).order("created_at", desc=True).range(offset, offset + limit - 1)
        if status:
            q = q.eq("status", status)
        res = q.execute()
        return {"ok": True, "prospects": res.data or []}
    except Exception as exc:
        logger.error("CRM prospects failed: %s", exc)
        return {"ok": True, "prospects": []}
