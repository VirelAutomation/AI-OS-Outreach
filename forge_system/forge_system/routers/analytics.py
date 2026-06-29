"""Analytics router — live pipeline metrics from Supabase."""

import logging
from fastapi import APIRouter
from database.supabase import db
from intelligence_engine.crl_learning import build_learning_report

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview", summary="Live pipeline metrics + campaign leaderboard")
async def analytics_overview():
    try:
        sdb = db()
        if not sdb:
            return _empty_overview("no_db")

        # Leads
        leads_res = sdb.table("leads").select("id", count="exact").execute()
        total_leads = leads_res.count or 0

        # Drafts
        drafts_res = sdb.table("outreach_drafts").select("id", count="exact").execute()
        total_drafts = drafts_res.count or 0

        # Sends
        sends_res = sdb.table("outreach_sends").select("id,status,created_at").execute()
        sends = sends_res.data or []
        emails_sent = len([s for s in sends if s.get("status") == "sent"])
        send_failures = len([s for s in sends if s.get("status") in ("failed", "bounced")])

        # Replies
        replies_res = sdb.table("outreach_replies").select("id,intent,raw_text,created_at,lead_id").execute()
        replies_data = replies_res.data or []
        total_replies = len(replies_data)

        # Meetings
        meetings_res = sdb.table("meetings").select("id,value_estimate").execute()
        meetings = meetings_res.data or []
        meetings_booked = len(meetings)
        pipeline_value = sum(m.get("value_estimate") or 0 for m in meetings)

        reply_rate = round((total_replies / emails_sent * 100) if emails_sent else 0, 2)
        meeting_rate = round((meetings_booked / total_replies * 100) if total_replies else 0, 2)

        # Campaign leaderboard
        campaigns_res = sdb.table("campaigns").select("id,name,vertical").limit(10).execute()
        leaderboard = []
        for c in (campaigns_res.data or []):
            cid = c["id"]
            c_sends = [s for s in sends if s.get("campaign_id") == cid]
            c_sent = len([s for s in c_sends if s.get("status") == "sent"])
            c_replies = [r for r in replies_data if r.get("campaign_id") == cid]
            c_rate = round((len(c_replies) / c_sent * 100) if c_sent else 0, 1)
            leaderboard.append({
                "id": cid,
                "name": c.get("name", ""),
                "vertical": c.get("vertical", ""),
                "sent": c_sent,
                "replyRate": c_rate,
                "meetingsBooked": 0,
            })

        # Recent replies with lead info
        recent = []
        for r in replies_data[-5:]:
            lead_id = r.get("lead_id", "")
            lead = {}
            if lead_id:
                try:
                    lr = sdb.table("leads").select("full_name,company_name").eq("id", lead_id).limit(1).execute()
                    lead = (lr.data or [{}])[0]
                except Exception:
                    pass
            recent.append({
                "id": r.get("id", ""),
                "intent": r.get("intent", "unknown"),
                "rawText": r.get("raw_text", ""),
                "createdAt": r.get("created_at", ""),
                "leadId": lead_id,
                "fullName": lead.get("full_name", "Unknown"),
                "companyName": lead.get("company_name", ""),
            })

        return {
            "ok": True,
            "metrics": {
                "totalLeads": total_leads,
                "totalDrafts": total_drafts,
                "emailsSent": emails_sent,
                "sendFailures": send_failures,
                "replies": total_replies,
                "meetingsBooked": meetings_booked,
                "replyRate": reply_rate,
                "meetingRate": meeting_rate,
                "pipelineValue": pipeline_value,
            },
            "campaignLeaderboard": leaderboard,
            "recentReplies": recent,
            "integrity": {"statsSource": "supabase_live"},
        }
    except Exception as exc:
        logger.error("Analytics overview failed: %s", exc)
        return _empty_overview("error")


def _empty_overview(source: str):
    return {
        "ok": True,
        "metrics": {
            "totalLeads": 0, "totalDrafts": 0, "emailsSent": 0,
            "sendFailures": 0, "replies": 0, "meetingsBooked": 0,
            "replyRate": 0.0, "meetingRate": 0.0, "pipelineValue": 0,
        },
        "campaignLeaderboard": [],
        "recentReplies": [],
        "integrity": {"statsSource": source},
    }


@router.get("/crl-learning", summary="CRL reply-learning graph and mechanisms from live outreach DBs")
async def crl_learning():
    try:
        report = build_learning_report(export=True)
        return {"ok": True, **report}
    except Exception as exc:
        logger.error("CRL learning report failed: %s", exc)
        return {"ok": False, "error": str(exc)}
