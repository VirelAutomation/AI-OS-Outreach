"""
agents/forge_agent.py — FORGE campaign automation agent (FORGE AEI).

run_campaign_cycle() is the heartbeat of the outreach system. It identifies
which plan step is due today, fetches the next lead batch, generates
personalised drafts via Gemini, and persists them for human review.

Design principles:
- Idempotent: running twice on the same day will not generate duplicate drafts
- Non-destructive: generates draft status only — humans approve and send
- Segment-aware: leads are matched to campaigns by industry segment
- Observable: every run returns a summary dict for monitoring
"""

import logging
from datetime import datetime, timezone

from database.supabase import db
from services.email_generator import generate_drafts_batch

logger = logging.getLogger(__name__)


async def run_campaign_cycle(campaign_id: int) -> dict:
    """
    Execute today's automation step for a campaign.

    Returns a summary dict:
      {campaign_id, step, day, leads_fetched, drafts_created, skipped, reason?}
    """
    client = db()

    # ── Load campaign ────────────────────────────────────────────────────────
    camp_res = client.table("outreach.campaigns").select("*").eq("id", campaign_id).execute()
    if not camp_res.data:
        raise ValueError(f"Campaign {campaign_id} not found")
    campaign = camp_res.data[0]

    if campaign.get("status") != "active":
        return {"campaign_id": campaign_id, "skipped": True, "reason": "campaign_not_active"}

    # ── Load active plan ─────────────────────────────────────────────────────
    plan_res = (
        client.table("outreach.plans")
        .select("*")
        .eq("campaign_id", campaign_id)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    if not plan_res.data:
        logger.info("Campaign %d: no active plan", campaign_id)
        return {"campaign_id": campaign_id, "skipped": True, "reason": "no_active_plan"}

    plan = plan_res.data[0]
    steps = plan.get("steps") or []

    # ── Identify step due today ──────────────────────────────────────────────
    start_raw = plan.get("start_date") or campaign.get("start_date")
    if not start_raw:
        return {"campaign_id": campaign_id, "skipped": True, "reason": "no_start_date"}

    start_date = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00")).date()
    today = datetime.now(timezone.utc).date()
    day_offset = (today - start_date).days + 1

    due = [s for s in steps if s.get("day") == day_offset and s.get("status") == "pending" and s.get("batch_size", 0) > 0]
    if not due:
        logger.info("Campaign %d: no send-steps due on day %d", campaign_id, day_offset)
        return {"campaign_id": campaign_id, "skipped": True, "reason": "no_steps_due", "day": day_offset}

    step = due[0]
    step_number = steps.index(step)
    batch_size = step.get("batch_size", 10)

    # ── Idempotency guard: skip if drafts already generated today ────────────
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    existing = (
        client.table("outreach.email_drafts")
        .select("id", count="exact")
        .eq("campaign_id", campaign_id)
        .gte("created_at", today_start.isoformat())
        .execute()
    )
    if (existing.count or 0) >= batch_size:
        logger.info("Campaign %d: drafts already generated today (step %d) — skipping", campaign_id, step_number)
        return {"campaign_id": campaign_id, "skipped": True, "reason": "already_generated", "step": step_number}

    # ── Fetch next batch of new leads in this segment ────────────────────────
    segment = campaign.get("segment", "ecommerce")
    leads_res = (
        client.table("outreach.leads")
        .select("*")
        .eq("industry", segment)
        .eq("status", "new")
        .limit(batch_size)
        .execute()
    )
    leads = leads_res.data or []
    if not leads:
        logger.info("Campaign %d: no new leads in segment '%s'", campaign_id, segment)
        return {"campaign_id": campaign_id, "skipped": True, "reason": "no_leads_available", "step": step_number}

    # ── Generate personalised drafts ─────────────────────────────────────────
    logger.info("Campaign %d: generating %d drafts for step %d (day %d)", campaign_id, len(leads), step_number, day_offset)
    generated = await generate_drafts_batch(leads, segment)

    # ── Persist drafts and mark leads as contacted ───────────────────────────
    saved = 0
    for draft_result, lead in zip(generated, leads):
        if draft_result.get("status") != "generated":
            logger.warning("Draft gen failed for lead %s: %s", lead.get("id"), draft_result.get("error"))
            continue
        client.table("outreach.email_drafts").insert({
            "campaign_id": campaign_id,
            "lead_id":     lead["id"],
            "subject":     draft_result["subject"],
            "body":        draft_result["body"],
            "status":      "draft",
            "version":     1,
        }).execute()
        saved += 1

    # ── Mark plan step as executed (batch generated, not yet sent) ───────────
    updated_steps = list(steps)
    updated_steps[step_number] = {**step, "status": "executed", "executed_at": datetime.now(timezone.utc).isoformat()}
    client.table("outreach.plans").update({"steps": updated_steps}).eq("id", plan["id"]).execute()

    logger.info("Campaign %d: step %d done — %d/%d drafts saved", campaign_id, step_number, saved, len(leads))
    return {
        "campaign_id": campaign_id,
        "step_index":  step_number,
        "day":         day_offset,
        "segment":     segment,
        "leads_fetched":  len(leads),
        "drafts_created": saved,
        "skipped":        False,
    }


async def get_campaign_summary(campaign_id: int) -> dict:
    """
    Return a rich campaign snapshot for the Analytics and Orchestrator AEIs.
    """
    from services.rating import compute_rating
    client = db()
    camp_res = client.table("outreach.campaigns").select("*").eq("id", campaign_id).execute()
    if not camp_res.data:
        return {"error": "Campaign not found"}
    c = camp_res.data[0]
    leads_count = (
        client.table("outreach.leads")
        .select("id", count="exact")
        .eq("industry", c["segment"])
        .execute().count or 100
    )
    rating = compute_rating(
        c["sent_count"], c["replied_count"],
        c["meeting_count"], c["bounced_count"],
        leads_count,
    )
    return {
        "campaign":    c,
        "total_leads": leads_count,
        "rating":      rating.model_dump(),
    }
