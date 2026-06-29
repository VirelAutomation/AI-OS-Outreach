"""
Virel Automation — Sales Pipeline & Task Manager

Tracks every lead from first touch → closed client.
Stores tasks Jarvis assigns to Jace.
JSON-backed, syncs to Supabase when available.
"""

import os, json, sqlite3, logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

log  = logging.getLogger("virel.pipeline")
_IST = timezone(timedelta(hours=5, minutes=30))
_ROOT = Path(__file__).parent

DATA_DIR = Path(os.getenv("DATA_DIR", str(_ROOT)))
DATA_DIR.mkdir(exist_ok=True)

PIPELINE_FILE = DATA_DIR / "pipeline.json"
TASKS_FILE    = DATA_DIR / "tasks.json"

# ── Pipeline stages ────────────────────────────────────────────────────────────

STAGES = {
    1: "dm_sent",          # First DM or comment sent
    2: "replied",          # They replied to us
    3: "call_booked",      # Discovery call scheduled
    4: "call_done",        # Call completed
    5: "proposal_sent",    # Proposal/price sent
    6: "closed",           # Closed — paying client
    7: "lost",             # Not interested
}

STAGE_NAMES = {v: k for k, v in STAGES.items()}

OFFERS = {
    "ai_voice_receptionist": "AI Voice Receptionist (HVAC/Med Spa) — $1,500-3,000/mo",
    "ai_outreach_system":    "AI Outreach + Sales System — $2,000/mo",
    "ai_ads":                "AI Ads System — $1,500/mo",
    "full_stack":            "Full Stack AI Employee — $3,500/mo",
}


def _now() -> str:
    return datetime.now(_IST).isoformat()


# ── Pipeline ───────────────────────────────────────────────────────────────────

def _load_pipeline() -> dict:
    try:
        return json.loads(PIPELINE_FILE.read_text()) if PIPELINE_FILE.exists() else {"leads": [], "meta": {}}
    except Exception:
        return {"leads": [], "meta": {}}


def _save_pipeline(data: dict):
    PIPELINE_FILE.write_text(json.dumps(data, indent=2, default=str))


def add_lead(name: str, business: str, niche: str, platform: str,
             profile_url: str = "", offer: str = "ai_outreach_system",
             region: str = "us", notes: str = "") -> dict:
    """Add a new lead to stage 1 (dm_sent)."""
    data   = _load_pipeline()
    lead_id = f"L{len(data['leads']) + 1:04d}"
    lead   = {
        "id":          lead_id,
        "name":        name,
        "business":    business,
        "niche":       niche,
        "platform":    platform,
        "profile_url": profile_url,
        "offer":       offer,
        "region":      region,
        "stage":       1,
        "stage_name":  STAGES[1],
        "notes":       notes,
        "created_at":  _now(),
        "updated_at":  _now(),
        "history":     [{"stage": 1, "name": STAGES[1], "at": _now()}],
    }
    data["leads"].append(lead)
    _save_pipeline(data)
    log.info(f"[PIPELINE] Added {lead_id}: {name} @ {business} ({niche})")
    return lead


def move_lead(lead_id: str, new_stage: int, notes: str = "") -> dict:
    """Move a lead to a new pipeline stage."""
    data = _load_pipeline()
    for lead in data["leads"]:
        if lead["id"] == lead_id:
            old = lead["stage"]
            lead["stage"]      = new_stage
            lead["stage_name"] = STAGES.get(new_stage, "unknown")
            lead["updated_at"] = _now()
            if notes:
                lead["notes"] = notes
            lead["history"].append({
                "stage": new_stage, "name": STAGES.get(new_stage), "at": _now(), "notes": notes
            })
            _save_pipeline(data)
            log.info(f"[PIPELINE] {lead_id} moved stage {old} → {new_stage}")
            return lead
    return {"error": f"Lead {lead_id} not found"}


def get_pipeline(stage: int = None, niche: str = None) -> dict:
    """Get pipeline overview with counts per stage."""
    data  = _load_pipeline()
    leads = data["leads"]

    if stage:
        leads = [l for l in leads if l["stage"] == stage]
    if niche:
        leads = [l for l in leads if niche.lower() in l.get("niche", "").lower()]

    by_stage = {v: [] for v in STAGES.values()}
    for l in leads:
        sname = STAGES.get(l["stage"], "unknown")
        by_stage[sname].append(l)

    active   = [l for l in leads if l["stage"] not in (6, 7)]
    closed   = [l for l in leads if l["stage"] == 6]
    lost     = [l for l in leads if l["stage"] == 7]
    mrr      = len(closed) * 2000  # default $2,000/mo estimate

    return {
        "total_leads":    len(leads),
        "active_leads":   len(active),
        "closed":         len(closed),
        "lost":           len(lost),
        "estimated_mrr":  f"${mrr:,}/mo",
        "by_stage":       {k: len(v) for k, v in by_stage.items()},
        "active_list":    [{"id": l["id"], "name": l["name"], "biz": l["business"],
                            "stage": l["stage_name"], "niche": l["niche"]} for l in active],
        "closed_list":    [{"id": l["id"], "name": l["name"], "biz": l["business"]} for l in closed],
    }


def update_lead_notes(lead_id: str, notes: str) -> dict:
    data = _load_pipeline()
    for lead in data["leads"]:
        if lead["id"] == lead_id:
            lead["notes"]      = notes
            lead["updated_at"] = _now()
            _save_pipeline(data)
            return lead
    return {"error": f"Lead {lead_id} not found"}


# ── Task manager ───────────────────────────────────────────────────────────────

def _load_tasks() -> dict:
    try:
        return json.loads(TASKS_FILE.read_text()) if TASKS_FILE.exists() else {"tasks": []}
    except Exception:
        return {"tasks": []}


def _save_tasks(data: dict):
    TASKS_FILE.write_text(json.dumps(data, indent=2, default=str))


def assign_task(title: str, description: str, priority: str = "medium",
                due_by: str = "today", lead_id: str = None,
                task_type: str = "call") -> dict:
    """
    Assign a task to Jace. task_type: 'call', 'reply', 'demo', 'close', 'other'
    """
    data    = _load_tasks()
    task_id = f"T{len(data['tasks']) + 1:03d}"
    task    = {
        "id":          task_id,
        "title":       title,
        "description": description,
        "priority":    priority,     # high / medium / low
        "due_by":      due_by,
        "type":        task_type,
        "lead_id":     lead_id,
        "status":      "pending",
        "created_at":  _now(),
        "completed_at": None,
    }
    data["tasks"].append(task)
    _save_tasks(data)
    log.info(f"[TASK] Assigned {task_id} [{priority}]: {title}")
    return task


def get_pending_tasks(priority: str = None) -> list:
    data  = _load_tasks()
    tasks = [t for t in data["tasks"] if t["status"] == "pending"]
    if priority:
        tasks = [t for t in tasks if t["priority"] == priority]
    # Sort by priority: high first
    order = {"high": 0, "medium": 1, "low": 2}
    tasks.sort(key=lambda t: order.get(t["priority"], 1))
    return tasks


def complete_task(task_id: str) -> dict:
    data = _load_tasks()
    for task in data["tasks"]:
        if task["id"] == task_id:
            task["status"]       = "completed"
            task["completed_at"] = _now()
            _save_tasks(data)
            log.info(f"[TASK] {task_id} completed: {task['title']}")
            return task
    return {"error": f"Task {task_id} not found"}


def get_task_summary() -> dict:
    data   = _load_tasks()
    tasks  = data["tasks"]
    pend   = [t for t in tasks if t["status"] == "pending"]
    high   = [t for t in pend  if t["priority"] == "high"]
    due_today = [t for t in pend if "today" in str(t.get("due_by", "")).lower()]
    return {
        "total_pending": len(pend),
        "high_priority": len(high),
        "due_today":     len(due_today),
        "tasks":         pend[:10],   # top 10
    }


# ── Daily brief ────────────────────────────────────────────────────────────────

def generate_brief() -> dict:
    """Full briefing for Jarvis's daily report to Jace."""
    pipeline = get_pipeline()
    tasks    = get_task_summary()
    return {
        "date":     datetime.now(_IST).strftime("%A %d %B %Y — %H:%M IST"),
        "pipeline": pipeline,
        "tasks":    tasks,
        "alert_if": {
            "calls_not_booked": pipeline["by_stage"].get("replied", 0),
            "proposals_open":   pipeline["by_stage"].get("proposal_sent", 0),
            "calls_to_do":      tasks["total_pending"],
        },
    }
