"""
models/automation.py

Pydantic schemas for company-wide automations, landing-page signals,
and Apify-powered sourcing runs.
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, HttpUrl


class AutomationTaskIn(BaseModel):
    name: str
    owner_system: str = Field(description="jarvis | cmo | cto | ops | intel")
    task_type: str = Field(description="campaign_cycle | monitor | alert | enrichment | report")
    trigger_type: str = Field(description="manual | schedule | event")
    trigger_value: Optional[str] = None
    priority: str = "medium"
    requires_approval: bool = True
    payload: dict[str, Any] = {}


class AutomationTaskUpdate(BaseModel):
    status: Optional[str] = None
    payload: Optional[dict[str, Any]] = None


class AutomationTaskOut(BaseModel):
    id: int
    name: str
    owner_system: str
    task_type: str
    trigger_type: str
    trigger_value: Optional[str]
    priority: str
    status: str
    requires_approval: bool
    payload: dict[str, Any]
    created_at: datetime


class AutomationRunOut(BaseModel):
    id: int
    task_id: int
    status: str
    summary: str
    payload: dict[str, Any]
    created_at: datetime


class LandingVisitIn(BaseModel):
    campaign_id: Optional[int] = None
    lead_id: Optional[int] = None
    draft_id: Optional[int] = None
    visitor_email: Optional[str] = None
    visitor_name: Optional[str] = None
    company_name: Optional[str] = None
    page_url: str
    referrer: Optional[str] = None
    utm_source: Optional[str] = None
    utm_campaign: Optional[str] = None
    metadata: dict[str, Any] = {}


class ChatSignalIn(BaseModel):
    session_id: str
    campaign_id: Optional[int] = None
    lead_id: Optional[int] = None
    message: str
    sentiment: Optional[str] = None
    qualified: bool = False
    metadata: dict[str, Any] = {}


class BookingSignalIn(BaseModel):
    campaign_id: Optional[int] = None
    lead_id: Optional[int] = None
    name: str
    email: str
    company: Optional[str] = None
    booking_time: datetime
    source: str = "landing_page"
    metadata: dict[str, Any] = {}


class ApifyRunIn(BaseModel):
    actor_id: Optional[str] = None
    search_term: Optional[str] = None
    industry: Optional[str] = None
    city: Optional[str] = None
    start_urls: list[HttpUrl] = []
    max_items: int = 25
    dataset_mapping: dict[str, str] = {}
