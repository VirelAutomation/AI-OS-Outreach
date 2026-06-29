"""
routers/campaigns.py — Campaign management, plans, goals, rating.
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from database.supabase import db
from models.outreach import CampaignIn, GoalIn, GenerateDraftsIn
from services.rating import compute_rating
from services.email_generator import generate_drafts_batch

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("/", summary="Create a new campaign with default goals")
def create_campaign(campaign: CampaignIn):
    client = db()
    existing = client.table("outreach.campaigns").select("id").eq("name", campaign.name).execute()
    if existing.data:
        raise HTTPException(409, f"Campaign '{campaign.name}' already exists")

    start = campaign.start_date or datetime.utcnow()
    end   = campaign.end_date   or (start + timedelta(days=14))

    res = client.table("outreach.campaigns").insert({
        "name": campaign.name,
        "segment": campaign.segment,
        "status": "active",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "extra_data": campaign.extra_data,
    }).execute()
    campaign_id = res.data[0]["id"]

    # Auto-create sensible default goals so the dashboard is never empty
    default_goals = [
        {"campaign_id": campaign_id, "goal_type": "sent",     "target_value": 100, "deadline": end.isoformat()},
        {"campaign_id": campaign_id, "goal_type": "replies",  "target_value": 15,  "deadline": end.isoformat()},
        {"campaign_id": campaign_id, "goal_type": "meetings", "target_value": 5,   "deadline": end.isoformat()},
    ]
    client.table("outreach.goals").insert(default_goals).execute()
    return {"campaign": res.data[0], "goals_created": len(default_goals)}


@router.get("/", summary="List all campaigns")
def get_campaigns(status: str = None):
    client = db()
    q = client.table("outreach.campaigns").select("*")
    if status:
        q = q.eq("status", status)
    return q.execute().data


@router.get("/{campaign_id}/", summary="Get campaign detail")
def get_campaign(campaign_id: int):
    res = db().table("outreach.campaigns").select("*").eq("id", campaign_id).execute()
    if not res.data:
        raise HTTPException(404, "Campaign not found")
    return res.data[0]


@router.get("/{campaign_id}/rating/", summary="Compute and return campaign rating")
def get_rating(campaign_id: int):
    client = db()
    res = client.table("outreach.campaigns").select("*").eq("id", campaign_id).execute()
    if not res.data:
        raise HTTPException(404, "Campaign not found")
    c = res.data[0]
    # Count total leads in this segment as the denominator
    leads_res = client.table("outreach.leads").select("id", count="exact").eq("industry", c["segment"]).execute()
    total_leads = leads_res.count or c.get("total_leads") or 100
    rating = compute_rating(
        sent=c["sent_count"], replied=c["replied_count"],
        meetings=c["meeting_count"], bounced=c["bounced_count"],
        total_leads=total_leads,
    )
    rating.campaign_id = campaign_id
    rating.name = c["name"]
    return rating


@router.post("/{campaign_id}/plans/", summary="Generate 14-day execution plan")
def generate_plan(campaign_id: int):
    client = db()
    res = client.table("outreach.campaigns").select("*").eq("id", campaign_id).execute()
    if not res.data:
        raise HTTPException(404, "Campaign not found")
    c = res.data[0]
    leads_res = client.table("outreach.leads").select("id", count="exact").eq("industry", c["segment"]).execute()
    total = leads_res.count or 100
    batch = max(total // 4, 1)
    steps = [
        {"day": 1,  "action": "Send Batch 1 cold email",                          "batch_size": batch, "status": "pending"},
        {"day": 3,  "action": "Review replies, log events, adjust tone if needed", "batch_size": 0,     "status": "pending"},
        {"day": 4,  "action": "Send Batch 2 cold email",                          "batch_size": batch, "status": "pending"},
        {"day": 6,  "action": "Follow-up — Batch 1 non-responders",               "batch_size": batch, "status": "pending"},
        {"day": 7,  "action": "Week 1 metrics + rating checkpoint",                "batch_size": 0,     "status": "pending"},
        {"day": 8,  "action": "Send Batch 3 cold email",                          "batch_size": batch, "status": "pending"},
        {"day": 10, "action": "Second follow-up — Batch 1 non-responders",        "batch_size": batch, "status": "pending"},
        {"day": 11, "action": "Reply handling — book calls, send case studies",    "batch_size": 0,     "status": "pending"},
        {"day": 13, "action": "Final follow-up sweep",                             "batch_size": total - batch * 3, "status": "pending"},
        {"day": 14, "action": "Campaign close — full rating + retrospective",      "batch_size": 0,     "status": "pending"},
    ]
    plan_res = client.table("outreach.plans").insert({
        "campaign_id": campaign_id,
        "title": f"{c['name']} — 14-Day Plan",
        "steps": steps,
        "status": "active",
    }).execute()
    return plan_res.data[0]


@router.get("/{campaign_id}/plans/", summary="Get active plan for a campaign")
def get_plan(campaign_id: int):
    res = (db().table("outreach.plans").select("*")
           .eq("campaign_id", campaign_id).eq("status", "active")
           .order("created_at", desc=True).limit(1).execute())
    if not res.data:
        raise HTTPException(404, "No active plan. POST to /plans/ to generate one.")
    return res.data[0]


@router.put("/{campaign_id}/plans/steps/{step_index}/", summary="Mark a plan step complete")
def complete_step(campaign_id: int, step_index: int):
    client = db()
    res = client.table("outreach.plans").select("*").eq("campaign_id", campaign_id).eq("status", "active").limit(1).execute()
    if not res.data or step_index >= len(res.data[0]["steps"]):
        raise HTTPException(404, "Plan or step not found")
    steps = list(res.data[0]["steps"])
    steps[step_index]["status"] = "done"
    client.table("outreach.plans").update({"steps": steps}).eq("id", res.data[0]["id"]).execute()
    return {"step_index": step_index, "status": "done"}


@router.post("/{campaign_id}/goals/", summary="Set or overwrite campaign goals")
def set_goals(campaign_id: int, goals: list[GoalIn]):
    client = db()
    client.table("outreach.goals").update({"status": "archived"}).eq("campaign_id", campaign_id).eq("status", "active").execute()
    inserted = client.table("outreach.goals").insert([
        {"campaign_id": campaign_id, "goal_type": g.goal_type,
         "target_value": g.target_value, "deadline": g.deadline.isoformat() if g.deadline else None}
        for g in goals
    ]).execute()
    return {"goals_created": len(inserted.data)}


@router.get("/{campaign_id}/goals/", summary="Get goals and live progress")
def get_goals(campaign_id: int):
    client = db()
    c_res = client.table("outreach.campaigns").select("*").eq("id", campaign_id).execute()
    if not c_res.data:
        raise HTTPException(404, "Campaign not found")
    c = c_res.data[0]
    goals = client.table("outreach.goals").select("*").eq("campaign_id", campaign_id).eq("status", "active").execute().data
    metric_map = {"sent": c["sent_count"], "replies": c["replied_count"], "meetings": c["meeting_count"]}
    output = []
    for g in goals:
        current = metric_map.get(g["goal_type"], g["current_value"])
        pct = round((current / g["target_value"]) * 100, 1) if g["target_value"] else 0
        output.append({"id": g["id"], "type": g["goal_type"], "target": g["target_value"],
                       "current": current, "pct_complete": pct,
                       "status": "On Track" if pct >= 50 else "At Risk"})
    return {"campaign": c["name"], "goals": output}


@router.post("/{campaign_id}/drafts/generate/", summary="AI-generate drafts for a list of leads")
async def ai_generate_drafts(campaign_id: int, payload: GenerateDraftsIn):
    client = db()
    c_res = client.table("outreach.campaigns").select("*").eq("id", campaign_id).execute()
    if not c_res.data:
        raise HTTPException(404, "Campaign not found")
    segment = c_res.data[0]["segment"]
    leads_res = client.table("outreach.leads").select("*").in_("id", payload.lead_ids).execute()
    leads = leads_res.data or []
    if not leads:
        raise HTTPException(404, "No leads found for provided IDs")
    drafts = await generate_drafts_batch(leads, segment, payload.custom_instructions)
    # Save generated drafts to Supabase
    saved = 0
    for d in drafts:
        if d["status"] == "generated":
            client.table("outreach.email_drafts").insert({
                "campaign_id": campaign_id,
                "lead_id": d["lead_id"],
                "subject": d["subject"],
                "body": d["body"],
                "status": "draft",
            }).execute()
            saved += 1
    return {"generated": len(drafts), "saved": saved, "failed": len(drafts) - saved, "drafts": drafts}
