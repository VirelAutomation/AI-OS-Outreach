"""
agents/analytics_agent.py â€” Analytics AEI (Business Intelligence).

Provides AI-powered campaign analysis, pipeline forecasting, KPI tracking,
and trend identification. The Analytics AEI is called by the Orchestrator
when it needs data-backed insights to inform strategic decisions.

It layers Gemini reasoning on top of raw FORGE metrics to surface the
non-obvious: why is reply rate declining? Which segment has the best LTV?
What's the projected end-of-campaign pipeline if current rates hold?
"""

import logging
import json

import google.generativeai as genai

from database.supabase import db
from services.rating import compute_rating
from config import get_settings

logger = logging.getLogger(__name__)


async def analyze_campaign_performance(campaign_id: int | None = None) -> dict:
    """
    Analyze campaign performance with AI-generated recommendations.

    If campaign_id is None, analyzes all active campaigns and ranks them
    worst-first so the team's attention goes where it's needed most.
    """
    client = db()
    s = get_settings()
    genai.configure(api_key=s.gemini_key_for("zoya"))

    if campaign_id is not None:
        campaigns = client.table("outreach.campaigns").select("*").eq("id", campaign_id).execute().data
    else:
        campaigns = client.table("outreach.campaigns").select("*").eq("status", "active").execute().data

    if not campaigns:
        return {"campaigns_analyzed": 0, "analysis": [], "summary": "No active campaigns."}

    model = genai.GenerativeModel("gemini-1.5-flash")
    analysis = []

    for c in campaigns:
        total_leads = (
            client.table("outreach.leads")
            .select("id", count="exact")
            .eq("industry", c["segment"])
            .execute().count or c.get("total_leads") or 100
        )
        rating = compute_rating(
            c["sent_count"], c["replied_count"],
            c["meeting_count"], c["bounced_count"],
            total_leads,
        )

        insight_prompt = (
            f"You are a B2B sales analytics expert. Analyze this campaign and give ONE specific, "
            f"immediately actionable recommendation. Max 2 sentences.\n\n"
            f"Campaign: {c['name']} (Segment: {c['segment']})\n"
            f"Sent: {c['sent_count']} | Replied: {c['replied_count']} | "
            f"Meetings: {c['meeting_count']} | Bounced: {c['bounced_count']}\n"
            f"Rating: {rating.total}/100 (Grade {rating.grade})\n"
            f"Weakest axis: {rating.weakest_axis}\n"
            f"System diagnosis: {rating.diagnosis}\n\n"
            f"Give ONE specific action the team should take today."
        )

        ai_recommendation = rating.recommended_action  # fallback
        try:
            res = model.generate_content(insight_prompt)
            ai_recommendation = res.text.strip()
        except Exception as e:
            logger.warning("Analytics AI recommendation failed for campaign %d: %s", c["id"], e)

        analysis.append({
            "campaign_id":      c["id"],
            "name":             c["name"],
            "segment":          c["segment"],
            "rating":           rating.total,
            "grade":            rating.grade,
            "weakest_axis":     rating.weakest_axis,
            "diagnosis":        rating.diagnosis,
            "ai_recommendation": ai_recommendation,
            "raw_metrics": {
                "sent": c["sent_count"], "replied": c["replied_count"],
                "meetings": c["meeting_count"], "bounced": c["bounced_count"],
                "total_leads": total_leads,
            },
        })

    # Sort worst-first â€” the campaigns that need the most attention come first
    analysis.sort(key=lambda x: x["rating"])

    worst = analysis[0] if analysis else None
    summary = (
        f"Analyzed {len(analysis)} campaign(s). "
        + (f"Most urgent: '{worst['name']}' at {worst['rating']}/100 â€” {worst['weakest_axis']} is the bottleneck." if worst else "")
    )

    return {
        "campaigns_analyzed": len(analysis),
        "analysis":           analysis,
        "summary":            summary,
    }


async def forecast_pipeline(campaign_id: int) -> dict:
    """
    Project end-of-campaign meetings based on current conversion trajectory.
    Uses linear extrapolation from current reply and conversion rates.
    """
    client = db()
    res = client.table("outreach.campaigns").select("*").eq("id", campaign_id).execute()
    if not res.data:
        return {"error": "Campaign not found"}
    c = res.data[0]

    total_leads = (
        client.table("outreach.leads")
        .select("id", count="exact")
        .eq("industry", c["segment"])
        .execute().count or c.get("total_leads") or 100
    )

    remaining = max(total_leads - c["sent_count"], 0)
    reply_rate = c["replied_count"] / max(c["sent_count"], 1)
    conversion_rate = c["meeting_count"] / max(c["replied_count"], 1)

    projected_replies = round(remaining * reply_rate)
    projected_meetings = round(projected_replies * conversion_rate)

    return {
        "campaign_id":                    campaign_id,
        "name":                           c["name"],
        "sent_so_far":                    c["sent_count"],
        "remaining_to_send":              remaining,
        "current_reply_rate_pct":         round(reply_rate * 100, 1),
        "current_conversion_rate_pct":    round(conversion_rate * 100, 1),
        "projected_additional_replies":   projected_replies,
        "projected_additional_meetings":  projected_meetings,
        "total_projected_meetings":       c["meeting_count"] + projected_meetings,
        "total_leads":                    total_leads,
    }


async def generate_kpi_report() -> dict:
    """
    Generate a cross-campaign KPI snapshot for the dashboard and Slack digest.
    """
    client = db()
    campaigns = client.table("outreach.campaigns").select("*").eq("status", "active").execute().data
    if not campaigns:
        return {"total_sent": 0, "total_replies": 0, "total_meetings": 0, "campaigns": []}

    total_sent = sum(c["sent_count"] for c in campaigns)
    total_replies = sum(c["replied_count"] for c in campaigns)
    total_meetings = sum(c["meeting_count"] for c in campaigns)

    return {
        "active_campaigns":     len(campaigns),
        "total_sent":           total_sent,
        "total_replies":        total_replies,
        "total_meetings":       total_meetings,
        "overall_reply_rate":   round(total_replies / max(total_sent, 1) * 100, 1),
        "overall_conversion":   round(total_meetings / max(total_replies, 1) * 100, 1),
        "campaigns": [
            {"id": c["id"], "name": c["name"], "sent": c["sent_count"],
             "replies": c["replied_count"], "meetings": c["meeting_count"]}
            for c in campaigns
        ],
    }

