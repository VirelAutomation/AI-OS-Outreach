"""
routers/automations.py

Company-wide automation definitions.
These are the backend objects that power the Automations section in the dashboard.
"""

from datetime import datetime
import logging

from fastapi import APIRouter, HTTPException

from database.supabase import db
from models.automation import AutomationTaskIn, AutomationTaskUpdate

router = APIRouter(prefix="/automations", tags=["automations"])
log = logging.getLogger("forge.automations")


@router.post("/", summary="Create an automation task for Jarvis or a specialist system")
def create_automation(task: AutomationTaskIn):
    client = db()
    res = client.table("outreach.automation_tasks").insert({
        "name": task.name,
        "owner_system": task.owner_system,
        "task_type": task.task_type,
        "trigger_type": task.trigger_type,
        "trigger_value": task.trigger_value,
        "priority": task.priority,
        "status": "active",
        "requires_approval": task.requires_approval,
        "payload": task.payload,
    }).execute()
    log.info("Automation created: %s (%s)", task.name, task.owner_system)
    return res.data[0]


@router.get("/", summary="List automation tasks")
def list_automations(status: str | None = None, owner_system: str | None = None):
    client = db()
    q = client.table("outreach.automation_tasks").select("*")
    if status:
        q = q.eq("status", status)
    if owner_system:
        q = q.eq("owner_system", owner_system)
    res = q.order("created_at", desc=True).execute()
    return {"total": len(res.data), "automations": res.data}


@router.put("/{task_id}/", summary="Update automation state or payload")
def update_automation(task_id: int, update: AutomationTaskUpdate):
    payload = {k: v for k, v in update.model_dump().items() if v is not None}
    res = db().table("outreach.automation_tasks").update(payload).eq("id", task_id).execute()
    if not res.data:
        raise HTTPException(404, "Automation task not found")
    return res.data[0]


@router.post("/{task_id}/run/", summary="Record a manual or automatic automation execution")
def run_automation(task_id: int):
    client = db()
    task = client.table("outreach.automation_tasks").select("*").eq("id", task_id).execute()
    if not task.data:
        raise HTTPException(404, "Automation task not found")

    row = task.data[0]
    res = client.table("outreach.automation_runs").insert({
        "task_id": task_id,
        "status": "queued",
        "summary": f"{row['owner_system']} accepted task {row['name']}",
        "payload": row.get("payload", {}),
        "created_at": datetime.utcnow().isoformat(),
    }).execute()
    return res.data[0]


@router.get("/runs/", summary="List recent automation executions")
def list_automation_runs(limit: int = 50):
    res = db().table("outreach.automation_runs").select("*").order("created_at", desc=True).limit(limit).execute()
    return {"total": len(res.data), "runs": res.data}
