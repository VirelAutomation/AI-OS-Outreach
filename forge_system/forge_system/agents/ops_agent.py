"""
agents/ops_agent.py â€” OPS AEI (Operations & Automation).

Handles system health monitoring, campaign automation scheduling,
workflow status checks, and resource allocation decisions.
The OPS AEI is the "engine room" â€” it keeps everything running and
surfaces operational issues before they become problems.
"""

import logging
from datetime import datetime, timezone

import google.generativeai as genai

from config import get_settings
from database.supabase import db
from database.redis_client import r

logger = logging.getLogger(__name__)


async def check_system_health() -> dict:
    """
    Run a comprehensive health check across all system components.
    Returns a status dict that the Orchestrator uses to determine if
    any AEIs are degraded or offline.
    """
    health = {
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "components": {},
        "overall":    "healthy",
    }
    issues = []

    # â”€â”€ Supabase connection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        client = db()
        result = client.table("outreach.campaigns").select("id").limit(1).execute()
        health["components"]["supabase"] = {"status": "ok", "latency_hint": "< 500ms"}
    except Exception as e:
        health["components"]["supabase"] = {"status": "error", "detail": str(e)[:100]}
        issues.append("Supabase connection failed")

    # â”€â”€ Redis connection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        redis_client = r()
        pong = await redis_client.ping()
        health["components"]["redis"] = {"status": "ok" if pong else "degraded"}
    except Exception as e:
        health["components"]["redis"] = {"status": "error", "detail": str(e)[:100]}
        issues.append("Redis connection failed")

    # â”€â”€ Active campaigns count â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        client = db()
        res = client.table("outreach.campaigns").select("id", count="exact").eq("status", "active").execute()
        health["components"]["campaigns"] = {"status": "ok", "active": res.count or 0}
    except Exception as e:
        health["components"]["campaigns"] = {"status": "error", "detail": str(e)[:80]}

    # â”€â”€ Training pipeline health â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        client = db()
        runs = client.table("jarvis.training_runs").select("*").order("created_at", desc=True).limit(1).execute()
        if runs.data:
            last_run = runs.data[0]
            health["components"]["training_pipeline"] = {
                "status": "ok",
                "last_run_status": last_run.get("status"),
                "last_run_at": last_run.get("created_at"),
            }
        else:
            health["components"]["training_pipeline"] = {"status": "no_runs_yet"}
    except Exception as e:
        health["components"]["training_pipeline"] = {"status": "error", "detail": str(e)[:80]}

    # â”€â”€ Overall health determination â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if issues:
        health["overall"] = "degraded" if len(issues) < 2 else "critical"
        health["issues"] = issues

    return health


async def get_campaign_schedule() -> dict:
    """
    Return today's campaign automation schedule â€” which campaigns have
    steps due today and what their batch sizes are.
    Used by the Orchestrator to decide whether to trigger run_campaign_cycle.
    """
    client = db()
    today = datetime.now(timezone.utc).date()

    campaigns = client.table("outreach.campaigns").select("*").eq("status", "active").execute().data
    schedule = []

    for c in campaigns:
        plan_res = (
            client.table("outreach.plans")
            .select("*")
            .eq("campaign_id", c["id"])
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        if not plan_res.data:
            continue

        plan = plan_res.data[0]
        start_raw = plan.get("start_date") or c.get("start_date")
        if not start_raw:
            continue

        start_date = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00")).date()
        day_offset = (today - start_date).days + 1

        due_steps = [
            s for s in (plan.get("steps") or [])
            if s.get("day") == day_offset
            and s.get("status") == "pending"
            and s.get("batch_size", 0) > 0
        ]

        if due_steps:
            schedule.append({
                "campaign_id":   c["id"],
                "campaign_name": c["name"],
                "segment":       c["segment"],
                "day_in_plan":   day_offset,
                "steps_due":     due_steps,
            })

    return {
        "date":     today.isoformat(),
        "campaigns_with_steps_due": len(schedule),
        "schedule": schedule,
    }


async def monitor_draft_queue() -> dict:
    """
    Check the draft review queue â€” how many AI-generated drafts are
    waiting for human approval. High queue depth = team needs to review.
    """
    client = db()

    pending = (
        client.table("outreach.email_drafts")
        .select("id", count="exact")
        .eq("status", "draft")
        .execute().count or 0
    )
    approved = (
        client.table("outreach.email_drafts")
        .select("id", count="exact")
        .eq("status", "approved")
        .execute().count or 0
    )
    sent = (
        client.table("outreach.email_drafts")
        .select("id", count="exact")
        .eq("status", "sent")
        .execute().count or 0
    )

    urgency = "low"
    if pending >= 50:
        urgency = "high"
    elif pending >= 20:
        urgency = "medium"

    return {
        "draft_queue_depth":   pending,
        "approved_unsent":     approved,
        "total_sent":          sent,
        "review_urgency":      urgency,
        "action_required":     pending > 0,
        "recommendation":      f"Review {pending} pending drafts in the Draft Review Queue." if pending > 0 else "Queue is clear.",
    }


async def generate_ops_digest() -> dict:
    """
    Generate a daily operations digest combining health, schedule, and queue status.
    Called by the Orchestrator as a morning briefing for the team.
    """
    health = await check_system_health()
    schedule = await get_campaign_schedule()
    queue = await monitor_draft_queue()

    s = get_settings()
    genai.configure(api_key=s.gemini_key_for("damien"))
    model = genai.GenerativeModel("gemini-1.5-flash")

    summary_prompt = f"""You are an operations AI. Write a 3-bullet daily ops digest for a B2B sales team.

System health: {health['overall']}
Campaigns with automation steps due today: {schedule['campaigns_with_steps_due']}
Draft review queue depth: {queue['draft_queue_depth']} pending
Approved drafts waiting to send: {queue['approved_unsent']}

Write 3 brief, specific bullets the team needs to act on today. Each bullet: 1 sentence, action-oriented."""

    try:
        result = model.generate_content(summary_prompt)
        bullets = [line.strip().lstrip("â€¢-").strip() for line in result.text.strip().split("\n") if line.strip()][:3]
    except Exception:
        bullets = [
            f"System health: {health['overall']}",
            f"{schedule['campaigns_with_steps_due']} campaign(s) have automation steps due today",
            f"{queue['draft_queue_depth']} draft(s) awaiting review",
        ]

    return {
        "date":     datetime.now(timezone.utc).date().isoformat(),
        "health":   health["overall"],
        "schedule": schedule,
        "queue":    queue,
        "digest_bullets": bullets,
    }

