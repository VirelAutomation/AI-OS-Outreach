"""SCI operator APIs for Jarvis + Jarvis chat/ops endpoints."""

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Body
import google.generativeai as genai

from models.sci import ApprovalDecisionIn, FounderContextIn, ManualWorldStateUpdateIn
from models.jarvis import MessageIn
from services.sci_service import SciService
from config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jarvis", tags=["jarvis-sci"])
service = SciService()


@router.get("/world-state", summary="Latest SCI world-state snapshot")
async def world_state(founder_id: str = "founder"):
    state = service.latest_world_state(founder_id)
    return {"ok": True, "worldState": state}


@router.post("/world-state", summary="Persist a manual world-state update")
async def update_world_state(payload: ManualWorldStateUpdateIn):
    try:
        state = service.apply_world_state_update(payload)
        return {"ok": True, "worldState": state}
    except Exception as exc:
        logger.error("SCI world-state update failed: %s", exc)
        raise HTTPException(500, str(exc))


@router.post("/objectives", summary="Run the SCI planning cycle and persist the objective graph")
async def run_objectives(payload: FounderContextIn):
    try:
        result = await service.run_cycle(payload)
        return {"ok": True, **result.model_dump(mode="json")}
    except Exception as exc:
        logger.error("SCI objective cycle failed: %s", exc)
        raise HTTPException(500, str(exc))


@router.get("/objectives", summary="Latest objective graphs")
async def objectives(limit: int = 10):
    return {"ok": True, "objectives": service.latest_graphs(limit=limit)}


@router.get("/allocations", summary="Latest founder and subagent allocations")
async def allocations(limit: int = 20, owner: str | None = None):
    return {"ok": True, "allocations": service.latest_allocations(limit=limit, owner=owner)}


@router.get("/approvals", summary="Latest policy decisions and approval queue")
async def approvals(limit: int = 20, status: str | None = None):
    return {"ok": True, "approvals": service.latest_approvals(limit=limit, status=status)}


@router.post("/approvals/{decision_id}", summary="Approve or reject a policy decision")
async def record_approval(decision_id: str, payload: ApprovalDecisionIn):
    updated = service.record_approval(decision_id, payload)
    if not updated:
        raise HTTPException(404, "Decision not found")
    return {"ok": True, "approval": updated}


@router.get("/executions", summary="Recent SCI execution traces")
async def executions(limit: int = 20):
    return {"ok": True, "executions": service.latest_executions(limit=limit)}


@router.get("/evals", summary="Recent model evaluation summaries")
async def evals(limit: int = 20):
    return {"ok": True, "evals": service.latest_evals(limit=limit)}


# ── Jarvis Chat ────────────────────────────────────────────────────────────────

_chat_history: list[dict] = []  # in-memory fallback when Redis is unavailable


@router.post("", summary="Send a message to Jarvis and get a response")
async def jarvis_chat(body: dict = Body(...)):
    prompt = body.get("prompt", "")
    operator = body.get("operator", "founder")
    if not prompt:
        raise HTTPException(400, "prompt is required")
    try:
        from agents.jarvis_agent import respond
        msg = MessageIn(session_id=f"forge-os-{operator}", content=prompt)
        result = await respond(msg)
        return {"ok": True, "response": result.response, "latency_ms": result.latency_ms}
    except Exception as exc:
        logger.error("Jarvis chat failed: %s", exc)
        return {"ok": False, "response": f"Jarvis is offline: {exc}"}


@router.get("/history", summary="Retrieve Jarvis chat history")
async def jarvis_history(session_id: str = "forge-os-founder", limit: int = 20):
    try:
        from database.redis_client import get_messages
        msgs = await get_messages(session_id)
        messages = [
            {
                "id": f"{i}",
                "role": m["role"] if m["role"] == "user" else "jarvis",
                "content": m["content"],
                "createdAt": m.get("created_at", datetime.now(timezone.utc).isoformat()),
            }
            for i, m in enumerate(msgs[-limit:])
        ]
        return {"ok": True, "messages": messages}
    except Exception as exc:
        logger.warning("Jarvis history failed (Redis may not be running): %s", exc)
        return {"ok": True, "messages": []}


# ── Jarvis Ops: Human Tasks ────────────────────────────────────────────────────

_human_tasks: list[dict] = []


@router.get("/human-tasks", summary="List human-in-the-loop tasks")
async def human_tasks(status: str | None = None):
    filtered = [t for t in _human_tasks if not status or t.get("status") == status]
    return {"ok": True, "tasks": filtered}


@router.patch("/human-tasks/{task_id}", summary="Update a human task status")
async def update_human_task(task_id: str, body: dict = Body(...)):
    for t in _human_tasks:
        if t["id"] == task_id:
            t["status"] = body.get("status", t["status"])
    return {"ok": True}


# ── Jarvis Strategy ────────────────────────────────────────────────────────────

_experiments: list[dict] = []
_platform_gaps: list[dict] = []


@router.get("/strategy/experiments", summary="List A/B message experiments")
async def strategy_experiments():
    return {"ok": True, "experiments": _experiments}


@router.get("/strategy/platform-gaps", summary="Platform gap analysis")
async def platform_gaps():
    return {"ok": True, "gaps": _platform_gaps}


@router.post("/strategy/experiment/hook", summary="Run hook A/B experiment via Gemini")
async def hook_experiment(body: dict = Body(...)):
    niche = body.get("niche", "B2B")
    platform = body.get("platform", "instagram")
    count = min(body.get("count", 5), 8)
    try:
        s = get_settings()
        genai.configure(api_key=s.gemini_key_for("noah"))
        model = genai.GenerativeModel("gemini-2.5-flash")
        r = model.generate_content(
            f"Generate {count} different opening hooks for cold outreach to {niche} businesses on {platform}. "
            f"Score each hook 0-100 for likely response rate. "
            f"Return JSON: {{\"hooks\": [{{\"text\": \"...\", \"score\": 0-100, \"angle\": \"...\"}}], \"winner\": \"best hook text\", \"winnerScore\": 0-100}}"
        )
        text = r.text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())
        exp = {
            "id": str(uuid.uuid4()),
            "type": "hook",
            "niche": niche,
            "platform": platform,
            "variants": data.get("hooks", []),
            "winner": data.get("winner", ""),
            "winnerScore": data.get("winnerScore", 0),
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "status": "complete",
        }
        _experiments.insert(0, exp)
        return {"ok": True, "experiment": exp}
    except Exception as exc:
        logger.error("Hook experiment failed: %s", exc)
        raise HTTPException(500, f"Experiment failed: {exc}")


@router.post("/strategy/experiment/dm", summary="Run DM template experiment via Gemini")
async def dm_experiment(body: dict = Body(...)):
    industry = body.get("industry", "HVAC")
    channel = body.get("channel", "instagram")
    try:
        s = get_settings()
        genai.configure(api_key=s.gemini_key_for("noah"))
        model = genai.GenerativeModel("gemini-2.5-flash")
        r = model.generate_content(
            f"Write 3 different cold DM templates for {industry} businesses on {channel}. "
            f"Focus on outcome-driven messaging (revenue, leads, automation). No 'AI employee' phrasing. "
            f"Score each 0-100. Return JSON: "
            f"{{\"variants\": [{{\"text\": \"...\", \"score\": 0-100, \"angle\": \"...\"}}], \"winner\": \"best text\", \"winnerScore\": 0-100}}"
        )
        text = r.text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())
        exp = {
            "id": str(uuid.uuid4()),
            "type": "dm",
            "industry": industry,
            "channel": channel,
            "variants": data.get("variants", []),
            "winner": data.get("winner", ""),
            "winnerScore": data.get("winnerScore", 0),
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "status": "complete",
        }
        _experiments.insert(0, exp)
        return {"ok": True, "experiment": exp}
    except Exception as exc:
        logger.error("DM experiment failed: %s", exc)
        raise HTTPException(500, f"DM experiment failed: {exc}")


@router.post("/brief", summary="Generate daily CEO brief via Gemini")
async def generate_brief(body: dict = Body(default={})):
    try:
        from database.supabase import db
        sdb = db()
        context = ""
        if sdb:
            try:
                leads_count = (sdb.table("leads").select("id", count="exact").execute()).count or 0
                context = f"Current leads in DB: {leads_count}."
            except Exception:
                pass

        s = get_settings()
        genai.configure(api_key=s.gemini_key_for("jarvis"))
        model = genai.GenerativeModel("gemini-2.5-flash")
        r = model.generate_content(
            f"You are Jarvis for Virel Automation (AI outreach agency). "
            f"Generate a concise daily CEO brief. {context} "
            f"Return JSON: {{\"headline\": \"...\", \"priorities\": [\"...\",\"...\",\"...\"], "
            f"\"risks\": [\"...\"], \"opportunities\": [\"...\"], \"metrics\": {{\"leads\": 0, \"sent\": 0, \"replies\": 0}}}}"
        )
        text = r.text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        brief = json.loads(text.strip())
        return {"ok": True, "brief": brief}
    except Exception as exc:
        logger.error("Brief generation failed: %s", exc)
        raise HTTPException(500, f"Brief failed: {exc}")


@router.post("/grade", summary="Grade a message or strategy with Gemini")
async def grade(body: dict = Body(...)):
    content = body.get("content", "")
    content_type = body.get("type", "message")
    if not content:
        raise HTTPException(400, "content is required")
    try:
        s = get_settings()
        genai.configure(api_key=s.gemini_key_for("noah"))
        model = genai.GenerativeModel("gemini-2.5-flash")
        r = model.generate_content(
            f"Grade this {content_type} for cold outreach effectiveness (0-100). "
            f"Content: \"{content}\"\n"
            f"Return JSON: {{\"score\": 0-100, \"strengths\": [\"...\"], \"weaknesses\": [\"...\"], \"rewrite\": \"improved version\"}}"
        )
        text = r.text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text.strip())
        return {"ok": True, "grade": result}
    except Exception as exc:
        logger.error("Grade failed: %s", exc)
        raise HTTPException(500, f"Grade failed: {exc}")
