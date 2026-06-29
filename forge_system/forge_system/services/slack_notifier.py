"""
services/slack_notifier.py — Slack notification service.

Posts formatted notifications to the configured channel on significant events:
meeting booked, campaign rating checkpoint, Jarvis training complete.
All functions are async but Slack SDK is synchronous — the calls are lightweight
enough that they don't need to_thread wrapping (sub-100ms network round-trip).
Silently skips (returns {"skipped": True}) if Slack is not configured.
"""

import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from config import get_settings

logger = logging.getLogger(__name__)

_GRADE_EMOJI = {
    "S": ":star2:",
    "A": ":white_check_mark:",
    "B": ":large_blue_circle:",
    "C": ":warning:",
    "F": ":red_circle:",
}


def _client() -> WebClient:
    return WebClient(token=get_settings().slack_bot_token)


def _is_configured() -> bool:
    s = get_settings()
    return bool(s.slack_bot_token and s.slack_channel_id)


def _post(text: str) -> dict:
    s = get_settings()
    try:
        result = _client().chat_postMessage(
            channel=s.slack_channel_id,
            text=text,
            mrkdwn=True,
        )
        return {"ts": result["ts"], "channel": result["channel"]}
    except SlackApiError as e:
        logger.error("Slack API error: %s", e.response["error"])
        return {"error": e.response["error"]}


async def notify_meeting_booked(lead_name: str, company: str, campaign_name: str) -> dict:
    """
    Fire when event_type == "meeting_booked" in routers/events.py.
    Tells the team a call is booked so they can prep immediately.
    """
    if not _is_configured():
        logger.debug("Slack not configured — skipping meeting_booked")
        return {"skipped": True}

    text = (
        f":calendar: *Meeting Booked — FORGE*\n"
        f"*Lead:* {lead_name} @ {company}\n"
        f"*Campaign:* {campaign_name}\n"
        f"Next: add to CRM and prep discovery questions."
    )
    logger.info("Slack: meeting_booked → %s @ %s", lead_name, company)
    return _post(text)


async def notify_campaign_rating(
    campaign_name: str, score: float, grade: str, weakest_axis: str
) -> dict:
    """
    Fire on Day-7 and Day-14 rating checkpoints from the campaign plan.
    Gives the team a heads-up before the next sending batch.
    """
    if not _is_configured():
        return {"skipped": True}

    emoji = _GRADE_EMOJI.get(grade, ":white_circle:")
    text = (
        f"{emoji} *Campaign Rating — {campaign_name}*\n"
        f"*Score:* {score}/100   *Grade:* {grade}\n"
        f"*Weakest Axis:* {weakest_axis}\n"
        f"Check the FORGE dashboard for the recommended action."
    )
    logger.info("Slack: rating checkpoint → %s %s %s", campaign_name, score, grade)
    return _post(text)


async def notify_training_complete(
    model_version: str, examples: int, validation_loss: float
) -> dict:
    """Fire when Jarvis training pipeline completes a run."""
    if not _is_configured():
        return {"skipped": True}

    text = (
        f":robot_face: *Jarvis Training Complete*\n"
        f"*Model:* {model_version}\n"
        f"*Examples Used:* {examples}\n"
        f"*Val Loss:* {validation_loss:.4f}"
    )
    logger.info("Slack: training_complete → %s examples=%d", model_version, examples)
    return _post(text)


async def notify_asi_insight(insight: str, aeis_involved: list) -> dict:
    """
    Fire when the ASI Orchestrator surfaces a high-priority strategic insight.
    """
    if not _is_configured():
        return {"skipped": True}

    aei_list = ", ".join(a.upper() for a in aeis_involved) if aeis_involved else "ORCHESTRATOR"
    text = (
        f":brain: *ASI Insight — {aei_list}*\n"
        f"{insight}"
    )
    return _post(text)
