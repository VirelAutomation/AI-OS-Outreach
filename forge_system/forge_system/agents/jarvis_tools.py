"""
jarvis_tools.py
Everything Jarvis can see and do — mirrors the full dashboard.

Each function returns a plain string Jarvis can relay back to the user.
All DB calls go direct through supabase.py (no HTTP round-trip needed).
"""

import asyncio
import re
import sys
from datetime import datetime
from pathlib import Path

from database.supabase import db
from config import get_settings


# ── helpers ───────────────────────────────────────────────────────────────────

def _client():
    return db()


def _fmt(rows: list, keys: list) -> str:
    if not rows:
        return "None found."
    lines = []
    for r in rows:
        lines.append("  " + " | ".join(f"{k}: {r.get(k, '—')}" for k in keys))
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# LEADS
# ══════════════════════════════════════════════════════════════════════════════

def list_leads(industry: str = None, status: str = None, limit: int = 20) -> str:
    q = _client().table("outreach.leads").select("id,name,company,email,industry,city,status")
    if industry:
        q = q.ilike("industry", f"%{industry}%")
    if status:
        q = q.eq("status", status)
    rows = q.limit(limit).execute().data
    return f"Leads ({len(rows)}):\n" + _fmt(rows, ["id", "name", "company", "email", "status"])


def add_lead(name: str, company: str, email: str, industry: str = "", city: str = "") -> str:
    res = _client().table("outreach.leads").insert({
        "name": name, "company": company, "email": email,
        "industry": industry, "city": city, "source": "jarvis",
    }).execute()
    return f"Lead added: {name} @ {company} ({email})"


def get_lead_count(industry: str = None) -> str:
    q = _client().table("outreach.leads").select("id", count="exact")
    if industry:
        q = q.ilike("industry", f"%{industry}%")
    total = q.execute().count or 0
    label = f"in '{industry}'" if industry else "total"
    return f"Lead count {label}: {total}"


# ══════════════════════════════════════════════════════════════════════════════
# CAMPAIGNS
# ══════════════════════════════════════════════════════════════════════════════

def list_campaigns(status: str = None) -> str:
    q = _client().table("outreach.campaigns").select(
        "id,name,segment,status,sent_count,replied_count,meeting_count,rating"
    )
    if status:
        q = q.eq("status", status)
    rows = q.order("created_at", desc=True).limit(10).execute().data
    return f"Campaigns ({len(rows)}):\n" + _fmt(
        rows, ["id", "name", "segment", "status", "sent_count", "replied_count", "meeting_count", "rating"]
    )


def get_campaign_stats(campaign_name_or_id: str) -> str:
    c = _client()
    try:
        cid = int(campaign_name_or_id)
        res = c.table("outreach.campaigns").select("*").eq("id", cid).execute()
    except ValueError:
        res = c.table("outreach.campaigns").select("*").ilike("name", f"%{campaign_name_or_id}%").execute()
    if not res.data:
        return f"Campaign '{campaign_name_or_id}' not found."
    camp = res.data[0]
    goals = c.table("outreach.goals").select("*").eq("campaign_id", camp["id"]).eq("status", "active").execute().data
    lines = [
        f"Campaign: {camp['name']} [{camp['status']}]",
        f"  Segment: {camp['segment']}",
        f"  Sent: {camp['sent_count']} | Replied: {camp['replied_count']} | Meetings: {camp['meeting_count']} | Bounced: {camp['bounced_count']}",
        f"  Rating: {camp['rating'] or 'N/A'}",
    ]
    if goals:
        lines.append("  Goals:")
        for g in goals:
            pct = round((g["current_value"] / g["target_value"]) * 100, 1) if g["target_value"] else 0
            lines.append(f"    {g['goal_type']}: {g['current_value']}/{g['target_value']} ({pct}%)")
    return "\n".join(lines)


def create_campaign(name: str, segment: str) -> str:
    c = _client()
    res = c.table("outreach.campaigns").insert({
        "name": name, "segment": segment, "status": "active",
    }).execute()
    if not res.data:
        return "Failed to create campaign."
    cid = res.data[0]["id"]
    from datetime import timedelta
    end = (datetime.utcnow() + timedelta(days=14)).isoformat()
    c.table("outreach.goals").insert([
        {"campaign_id": cid, "goal_type": "sent",     "target_value": 100, "deadline": end},
        {"campaign_id": cid, "goal_type": "replies",  "target_value": 15,  "deadline": end},
        {"campaign_id": cid, "goal_type": "meetings", "target_value": 5,   "deadline": end},
    ]).execute()
    return f"Campaign '{name}' created (ID {cid}) for segment '{segment}' with default goals."


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL DRAFTS (Gmail)
# ══════════════════════════════════════════════════════════════════════════════

async def generate_email_drafts(campaign_name_or_id: str, lead_limit: int = 10) -> str:
    c = _client()
    try:
        cid = int(campaign_name_or_id)
        res = c.table("outreach.campaigns").select("*").eq("id", cid).execute()
    except ValueError:
        res = c.table("outreach.campaigns").select("*").ilike("name", f"%{campaign_name_or_id}%").execute()
    if not res.data:
        return f"Campaign '{campaign_name_or_id}' not found."
    camp = res.data[0]
    leads = c.table("outreach.leads").select("*").ilike("industry", f"%{camp['segment']}%").limit(lead_limit).execute().data
    if not leads:
        return f"No leads found for segment '{camp['segment']}'."

    from services.email_generator import generate_drafts_batch
    drafts = await generate_drafts_batch(leads, camp["segment"])
    saved = 0
    for d in drafts:
        if d["status"] == "generated":
            c.table("outreach.email_drafts").insert({
                "campaign_id": camp["id"],
                "lead_id": d["lead_id"],
                "subject": d["subject"],
                "body": d["body"],
                "status": "draft",
            }).execute()
            saved += 1
    return f"Generated {saved} email drafts for campaign '{camp['name']}' (segment: {camp['segment']})."


async def send_email_drafts(campaign_name_or_id: str, limit: int = 10) -> str:
    from services.gmail import send_draft as gmail_send, create_draft as gmail_create
    c = _client()
    try:
        cid = int(campaign_name_or_id)
        res = c.table("outreach.campaigns").select("*").eq("id", cid).execute()
    except ValueError:
        res = c.table("outreach.campaigns").select("*").ilike("name", f"%{campaign_name_or_id}%").execute()
    if not res.data:
        return f"Campaign '{campaign_name_or_id}' not found."
    camp = res.data[0]

    drafts = (c.table("outreach.email_drafts").select("*")
              .eq("campaign_id", camp["id"]).eq("status", "draft").limit(limit).execute().data)
    if not drafts:
        return f"No unsent drafts for campaign '{camp['name']}'. Generate drafts first."

    sent = failed = 0
    for draft in drafts:
        lead = c.table("outreach.leads").select("email,name").eq("id", draft["lead_id"]).execute().data
        if not lead:
            continue
        to_email = lead[0]["email"]
        gmail_draft_id = await gmail_create(to_email, draft["subject"], draft["body"])
        if gmail_draft_id:
            result = await gmail_send(gmail_draft_id)
            if "error" not in result:
                c.table("outreach.email_drafts").update({"status": "sent"}).eq("id", draft["id"]).execute()
                sent += 1
            else:
                failed += 1
        else:
            failed += 1

    return f"Email send complete — sent: {sent}, failed: {failed} (campaign: {camp['name']})"


async def gmail_status() -> str:
    from services.gmail import provider_status
    status = await provider_status(live=True)
    if not status.get("configured"):
        return "Gmail not configured — GMAIL_REFRESH_TOKEN is missing. Run: python forge_system/get_gmail_token.py"
    return (
        f"Gmail: {status['status']}\n"
        f"  Sender: {status.get('sender')}\n"
        f"  Sent today: {status.get('sent_today', 0)} / {status.get('daily_cap', 100)}\n"
        f"  Remaining today: {status.get('remaining_today', 0)}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════

def get_analytics_summary() -> str:
    c = _client()
    camps = c.table("outreach.campaigns").select("sent_count,replied_count,meeting_count,bounced_count,rating").execute().data
    leads_total = c.table("outreach.leads").select("id", count="exact").execute().count or 0
    ig = c.table("ig_messaged").select("id", count="exact").execute().count or 0

    total_sent    = sum(r["sent_count"] or 0    for r in camps)
    total_replied = sum(r["replied_count"] or 0 for r in camps)
    total_meetings= sum(r["meeting_count"] or 0 for r in camps)
    reply_rate    = round((total_replied / total_sent * 100), 1) if total_sent else 0
    avg_rating    = round(sum(r["rating"] or 0 for r in camps) / len(camps), 1) if camps else 0

    return (
        f"Dashboard Analytics:\n"
        f"  Total leads in CRM: {leads_total}\n"
        f"  Active campaigns: {len(camps)}\n"
        f"  Emails sent (all time): {total_sent}\n"
        f"  Replies: {total_replied} ({reply_rate}% reply rate)\n"
        f"  Meetings booked: {total_meetings}\n"
        f"  Average campaign rating: {avg_rating}/100\n"
        f"  Instagram accounts DMed: {ig}"
    )


def get_recent_events(limit: int = 10) -> str:
    rows = (db().table("outreach.events").select("event_type,created_at,campaign_id,lead_id")
            .order("created_at", desc=True).limit(limit).execute().data)
    return f"Recent events ({len(rows)}):\n" + _fmt(rows, ["event_type", "campaign_id", "lead_id", "created_at"])


# ══════════════════════════════════════════════════════════════════════════════
# AUTOMATIONS
# ══════════════════════════════════════════════════════════════════════════════

def list_automations(status: str = "active") -> str:
    rows = (db().table("outreach.automation_tasks").select("id,name,owner_system,task_type,status,trigger_type")
            .eq("status", status).order("created_at", desc=True).limit(15).execute().data)
    return f"Automations ({status}, {len(rows)}):\n" + _fmt(rows, ["id", "name", "owner_system", "status"])


def get_automation_runs(limit: int = 10) -> str:
    rows = (db().table("outreach.automation_runs").select("task_id,status,summary,created_at")
            .order("created_at", desc=True).limit(limit).execute().data)
    return f"Recent automation runs:\n" + _fmt(rows, ["task_id", "status", "summary", "created_at"])


# ══════════════════════════════════════════════════════════════════════════════
# INSTAGRAM
# ══════════════════════════════════════════════════════════════════════════════

async def run_ig_outreach_async(limit: int = 10) -> str:
    ig_path = Path(__file__).parent.parent.parent / "ig_outreach"
    if str(ig_path) not in sys.path:
        sys.path.insert(0, str(ig_path))
    from jarvis_tool import run_ig_outreach
    return await asyncio.to_thread(run_ig_outreach, limit)


def ig_stats() -> str:
    try:
        rows = db().table("ig_messaged").select("username,business_type,sent_at").order("sent_at", desc=True).limit(10).execute().data
        total = db().table("ig_messaged").select("id", count="exact").execute().count or 0
        today = datetime.now().strftime("%Y-%m-%d")
        today_count = db().table("ig_messaged").select("id", count="exact").gte("sent_at", f"{today}T00:00:00").execute().count or 0
        lines = [f"Instagram outreach — total: {total} | today: {today_count}", "Recent:"]
        for r in rows:
            lines.append(f"  @{r['username']} ({r['business_type']}) — {str(r['sent_at'])[:10]}")
        return "\n".join(lines)
    except Exception as e:
        return f"IG stats error: {e}"
