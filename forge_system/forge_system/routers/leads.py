"""
routers/leads.py — Lead management endpoints.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from database.supabase import db
from models.outreach import LeadIn, LeadBatchIn, LeadOut, LeadStatusUpdate
import csv, io

router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("/", summary="Add a single lead")
def create_lead(lead: LeadIn):
    client = db()
    existing = client.table("outreach.leads").select("id").eq("email", lead.email).execute()
    if existing.data:
        raise HTTPException(409, f"Lead {lead.email} already exists")
    res = client.table("outreach.leads").insert(lead.model_dump()).execute()
    return res.data[0]


@router.post("/batch/", summary="Bulk import from JSON list")
def create_batch(batch: LeadBatchIn):
    client = db()
    created = skipped = 0
    for lead in batch.leads:
        existing = client.table("outreach.leads").select("id").eq("email", lead.email).execute()
        if existing.data:
            skipped += 1
            continue
        client.table("outreach.leads").insert(lead.model_dump()).execute()
        created += 1
    return {"created": created, "skipped": skipped}


@router.post("/import-csv/", summary="Upload a CSV file of leads")
async def import_csv(file: UploadFile = File(...)):
    """
    Accepts a CSV with columns: name, company, email, role, industry, city.
    Extra columns are stored in extra_data automatically.
    """
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    known = {"name", "company", "email", "role", "industry", "city", "phone", "notes"}
    leads = []
    for row in reader:
        extra = {k: v for k, v in row.items() if k not in known}
        leads.append(LeadIn(
            name=row.get("name", ""),
            company=row.get("company", ""),
            email=row.get("email", ""),
            role=row.get("role"),
            industry=row.get("industry"),
            city=row.get("city"),
            phone=row.get("phone"),
            notes=row.get("notes"),
            source="csv",
            extra_data=extra,
        ))
    return create_batch(LeadBatchIn(leads=leads))


@router.get("/", summary="List leads with optional filters")
def get_leads(industry: str = None, city: str = None, status: str = None, limit: int = 100, offset: int = 0):
    client = db()
    q = client.table("outreach.leads").select("*")
    if industry: q = q.eq("industry", industry)
    if city:     q = q.eq("city", city)
    if status:   q = q.eq("status", status)
    res = q.range(offset, offset + limit - 1).execute()
    return {"total": len(res.data), "leads": res.data}


@router.put("/{lead_id}/status/", summary="Update lead status")
def update_status(lead_id: int, update: LeadStatusUpdate):
    client = db()
    res = client.table("outreach.leads").update({"status": update.status}).eq("id", lead_id).execute()
    if not res.data:
        raise HTTPException(404, "Lead not found")
    return res.data[0]
