"""CMO router — Noah content engine powered by Gemini."""

import json
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Body, HTTPException
import google.generativeai as genai
from config import get_settings
from database.supabase import db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cmo", tags=["cmo"])


def _model():
    s = get_settings()
    genai.configure(api_key=s.gemini_key_for("noah"))
    return genai.GenerativeModel("gemini-2.5-flash")


def _json_from_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())


# ── Viral Research ─────────────────────────────────────────────────────────────

@router.post("/research", summary="Research viral patterns for a niche + platform")
async def research(body: dict = Body(...)):
    niche = body.get("niche", "B2B")
    platform = body.get("platform", "instagram_reels")
    try:
        model = _model()
        prompt = f"""You are Noah, a CMO AI for Virel Automation (B2B AI sales agency).
Analyse what goes viral in "{niche}" on {platform.replace("_", " ")}.

Return ONLY valid JSON (no markdown, no commentary):
{{
  "niche": "{niche}",
  "platform": "{platform}",
  "topPatterns": [
    {{"hookFormula": "...", "angle": "...", "structure": ["...","..."], "retentionTechnique": "...", "exampleOpener": "...", "whyItWorks": "..."}}
  ],
  "goldHooks": ["hook1","hook2","hook3","hook4","hook5"],
  "contentAngles": ["angle1","angle2","angle3"],
  "avoidThese": ["avoid1","avoid2"],
  "trendingFormats": ["format1","format2","format3"],
  "researchSummary": "2-3 sentence summary of what works and why."
}}

Return exactly 3 topPatterns, 5 goldHooks, 3 contentAngles, 2 avoidThese, 3 trendingFormats."""
        r = model.generate_content(prompt)
        data = _json_from_response(r.text)
        return {"ok": True, "research": data}
    except Exception as exc:
        logger.error("CMO research failed: %s", exc)
        raise HTTPException(500, f"Research failed: {exc}")


# ── Concept Generator ──────────────────────────────────────────────────────────

@router.post("/concepts", summary="Generate video concepts")
async def concepts(body: dict = Body(...)):
    niche = body.get("niche", "B2B")
    platform = body.get("platform", "instagram_reels")
    count = min(body.get("count", 6), 8)
    goal = body.get("goal", "")
    research_ctx = body.get("researchContext", {})
    try:
        model = _model()
        ctx_str = ""
        if research_ctx:
            ctx_str = f"\nResearch context: gold hooks: {research_ctx.get('goldHooks', [][:3])}, trending formats: {research_ctx.get('trendingFormats', [])}"
        prompt = f"""Generate {count} video concepts for "{niche}" on {platform.replace("_", " ")}.
{f"Creator goal: {goal}" if goal else ""}{ctx_str}

Return ONLY valid JSON array (no markdown):
[
  {{
    "id": "uuid-here",
    "title": "...",
    "hook": "first 1.5 seconds exactly",
    "angle": "...",
    "format": "talking_head|voiceover_b_roll|text_on_screen|hook_reveal|storytime|list_format|day_in_life",
    "platforms": ["{platform}"],
    "viralScore": 0-100,
    "whyItWorks": "...",
    "openingLine": "...",
    "keyPoints": ["...", "...", "..."],
    "cta": "..."
  }}
]"""
        r = model.generate_content(prompt)
        items = _json_from_response(r.text)
        if not isinstance(items, list):
            items = items.get("concepts", [])
        for item in items:
            if not item.get("id"):
                item["id"] = str(uuid.uuid4())
        return {"ok": True, "concepts": items}
    except Exception as exc:
        logger.error("CMO concepts failed: %s", exc)
        raise HTTPException(500, f"Concepts failed: {exc}")


# ── Script Builder ─────────────────────────────────────────────────────────────

@router.post("/script", summary="Generate full video script")
async def script(body: dict = Body(...)):
    concept = body.get("concept", "")
    hook = body.get("hook", "")
    platform = body.get("platform", "instagram_reels")
    niche = body.get("niche", "B2B")
    goal = body.get("goal", "")
    if not concept or not hook:
        raise HTTPException(400, "concept and hook are required")
    try:
        model = _model()
        prompt = f"""Write a full video script for {platform.replace("_", " ")}.
Concept: {concept}
Hook: {hook}
Niche: {niche}
{f"Goal: {goal}" if goal else ""}

Return ONLY valid JSON (no markdown):
{{
  "title": "...",
  "platform": "{platform}",
  "duration": "e.g. 45-60s",
  "hook": "{hook}",
  "segments": [
    {{"label": "HOOK", "timing": "0-3s", "content": "exact words", "visualNote": "..."}}
  ],
  "cta": "...",
  "captionHook": "...",
  "hashtags": ["hashtag1","hashtag2"],
  "viralScore": 0-100,
  "scoreReason": "...",
  "productionNotes": ["note1","note2"]
}}

Include 4-6 segments: HOOK, PROBLEM, REVEAL/SOLUTION, PROOF, CTA."""
        r = model.generate_content(prompt)
        data = _json_from_response(r.text)
        return {"ok": True, "script": data}
    except Exception as exc:
        logger.error("CMO script failed: %s", exc)
        raise HTTPException(500, f"Script failed: {exc}")


# ── Hook Scorer ────────────────────────────────────────────────────────────────

@router.post("/digest", summary="Generate a short-form content pack and optionally draft it to Gmail")
async def digest(body: dict = Body(default={})):
    niche = body.get("niche", "B2B")
    platform = body.get("platform", "instagram_reels")
    goal = body.get("goal", "Build trust before outbound touches hit.")
    recipient_email = body.get("recipientEmail", "")
    duration_seconds = max(15, min(int(body.get("durationSeconds", 20)), 45))
    try:
        model = _model()
        prompt = f"""You are Noah, the CMO AI for Virel Automation.
Build one operator-ready short-form content pack for {platform.replace("_", " ")} in the "{niche}" niche.
Goal: {goal}
Target duration: about {duration_seconds} seconds.

Return ONLY valid JSON (no markdown, no commentary):
{{
  "title": "...",
  "platform": "{platform}",
  "durationSeconds": {duration_seconds},
  "hook": "...",
  "caption": "...",
  "hashtags": ["hashtag1", "hashtag2", "hashtag3"],
  "talkingPoints": ["point1", "point2", "point3"],
  "scriptSegments": [
    {{"label": "HOOK", "seconds": "0-4", "content": "..."}},
    {{"label": "PROBLEM", "seconds": "4-9", "content": "..."}},
    {{"label": "PROOF", "seconds": "9-15", "content": "..."}},
    {{"label": "CTA", "seconds": "15-20", "content": "..."}}
  ],
  "imagePrompt": "Prompt for a still image or carousel cover using a premium red/black/grey visual system.",
  "videoPrompt": "Prompt for a premium short-form video reel using the same red/black/grey visual system.",
  "emailSubject": "Subject line for the operator digest email.",
  "emailBody": "Plain-text operator digest with title, hook, script, caption, hashtags, image prompt, and video prompt."
}}"""
        r = model.generate_content(prompt)
        pack = _json_from_response(r.text)

        gmail_payload = {"configured": False, "draftCreated": False, "draftId": ""}
        if recipient_email:
            from services.gmail import create_draft as gmail_create_draft, provider_status as gmail_provider_status

            gmail_status = await gmail_provider_status(live=False)
            gmail_payload = {
                "configured": gmail_status.get("configured", False),
                "status": gmail_status.get("status"),
                "sender": gmail_status.get("sender"),
                "draftCreated": False,
                "draftId": "",
            }
            if gmail_status.get("configured"):
                draft_id = await gmail_create_draft(
                    recipient_email,
                    pack.get("emailSubject", f"Virel content pack - {pack.get('title', 'untitled')}"),
                    pack.get("emailBody", ""),
                )
                gmail_payload["draftId"] = draft_id
                gmail_payload["draftCreated"] = bool(draft_id)

        return {"ok": True, "pack": pack, "gmail": gmail_payload}
    except Exception as exc:
        logger.error("CMO digest failed: %s", exc)
        raise HTTPException(500, f"Digest failed: {exc}")


@router.post("/hook/score", summary="Score a hook across 5 virality dimensions")
async def hook_score(body: dict = Body(...)):
    hook = body.get("hook", "")
    platform = body.get("platform", "instagram_reels")
    if not hook:
        raise HTTPException(400, "hook is required")
    try:
        model = _model()
        prompt = f"""Score this hook for {platform.replace("_", " ")}: "{hook}"

Return ONLY valid JSON:
{{
  "hook": "{hook}",
  "platform": "{platform}",
  "overallScore": 0-100,
  "breakdown": {{
    "patternInterrupt": 0-100,
    "curiosityGap": 0-100,
    "specificity": 0-100,
    "emotionalPull": 0-100,
    "clarity": 0-100
  }},
  "strengths": ["strength1","strength2"],
  "improvements": ["improvement1","improvement2"],
  "rewriteSuggestions": ["rewrite1","rewrite2","rewrite3"]
}}"""
        r = model.generate_content(prompt)
        data = _json_from_response(r.text)
        return {"ok": True, "score": data}
    except Exception as exc:
        logger.error("CMO hook score failed: %s", exc)
        raise HTTPException(500, f"Hook score failed: {exc}")


# ── Content Calendar ───────────────────────────────────────────────────────────

@router.get("/calendar", summary="List content calendar items")
async def calendar_list():
    try:
        sdb = db()
        if not sdb:
            return {"ok": True, "items": []}
        res = sdb.table("content_calendar").select("*").order("publish_at", desc=False).limit(50).execute()
        return {"ok": True, "items": res.data or []}
    except Exception as exc:
        logger.warning("CMO calendar list failed: %s", exc)
        return {"ok": True, "items": []}


@router.post("/calendar/schedule", summary="Schedule a content item")
async def calendar_schedule(body: dict = Body(...)):
    title = body.get("title", "")
    if not title:
        raise HTTPException(400, "title is required")
    try:
        sdb = db()
        if not sdb:
            return {"ok": False, "error": "Database not configured"}
        row = {
            "id": str(uuid.uuid4()),
            "title": title,
            "platform": body.get("platform", "instagram_reels"),
            "content_type": body.get("contentType", "video"),
            "status": "scheduled",
            "publish_at": body.get("publishAt") or None,
            "notes": body.get("notes") or None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        sdb.table("content_calendar").insert(row).execute()
        return {"ok": True, "item": row}
    except Exception as exc:
        logger.error("CMO calendar schedule failed: %s", exc)
        return {"ok": False, "error": str(exc)}


@router.delete("/calendar/{item_id}", summary="Delete a content calendar item")
async def calendar_delete(item_id: str):
    try:
        sdb = db()
        if sdb:
            sdb.table("content_calendar").delete().eq("id", item_id).execute()
        return {"ok": True}
    except Exception as exc:
        logger.warning("CMO calendar delete failed: %s", exc)
        return {"ok": True}
