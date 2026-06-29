"""
models/outreach.py

Pydantic schemas for the outreach system. These are the contracts between
your API layer and the rest of the world — every request and response
is validated against these models before any business logic runs.

Naming convention:
  - *In   = data coming into the API (create / update requests)
  - *Out  = data going out of the API (responses)
  - *Row  = raw database row shape (internal use only)
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, EmailStr, Field


# ── Lead ──────────────────────────────────────────────────────────────────────

class LeadIn(BaseModel):
    name: str
    company: str
    email: EmailStr
    role: Optional[str] = None
    industry: Optional[str] = None     # legal | ecommerce | fintech
    city: Optional[str] = None
    phone: Optional[str] = None
    source: str = "manual"             # apollo | manual | csv | webhook
    notes: Optional[str] = None
    extra_data: dict[str, Any] = {}


class LeadBatchIn(BaseModel):
    leads: list[LeadIn]


class LeadStatusUpdate(BaseModel):
    status: str   # new | contacted | replied | converted | dead


class LeadOut(BaseModel):
    id: int
    name: str
    company: str
    email: str
    role: Optional[str]
    industry: Optional[str]
    city: Optional[str]
    status: str
    source: str
    created_at: datetime


# ── Campaign ──────────────────────────────────────────────────────────────────

class CampaignIn(BaseModel):
    name: str
    segment: str                            # legal | ecommerce | fintech
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    extra_data: dict[str, Any] = {}


class CampaignOut(BaseModel):
    id: int
    name: str
    segment: str
    status: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    sent_count: int
    replied_count: int
    meeting_count: int
    bounced_count: int
    rating: float
    created_at: datetime


# ── Rating ────────────────────────────────────────────────────────────────────

class RatingBreakdown(BaseModel):
    value: float        # percentage
    points: float       # weighted points scored
    max: float          # maximum possible points


class CampaignRatingOut(BaseModel):
    campaign_id: int
    name: str
    total: float
    grade: str          # S | A | B | C | F
    breakdown: dict[str, RatingBreakdown]
    weakest_axis: str
    diagnosis: str
    recommended_action: str
    raw: dict[str, int]


# ── Plan ──────────────────────────────────────────────────────────────────────

class PlanStep(BaseModel):
    day: int
    action: str
    batch_size: int
    status: str = "pending"   # pending | done | skipped


class PlanOut(BaseModel):
    id: int
    campaign_id: int
    title: str
    steps: list[PlanStep]
    status: str
    created_at: datetime


# ── Goal ──────────────────────────────────────────────────────────────────────

class GoalIn(BaseModel):
    goal_type: str          # meetings | replies | sent | revenue
    target_value: float
    deadline: Optional[datetime] = None


class GoalProgressOut(BaseModel):
    id: int
    goal_type: str
    target: float
    current: float
    pct_complete: float
    status: str             # On Track | At Risk | Behind


class GoalsOut(BaseModel):
    campaign: str
    goals: list[GoalProgressOut]


# ── Email Draft ───────────────────────────────────────────────────────────────

class DraftIn(BaseModel):
    campaign_id: int
    lead_id: int
    subject: str
    body: str
    extra_data: dict[str, Any] = {}


class DraftUpdate(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    status: Optional[str] = None


class DraftOut(BaseModel):
    id: int
    campaign_id: int
    lead_id: int
    subject: str
    body: str
    version: int
    status: str             # draft | approved | sent | replied | bounced
    gmail_draft_id: Optional[str]
    sent_at: Optional[datetime]
    created_at: datetime


class GenerateDraftsIn(BaseModel):
    """
    Request body for AI-powered bulk draft generation.
    Gemini reads the lead list and produces personalised emails
    for each one using the segment-specific tone and pain framing.
    """
    campaign_id: int
    lead_ids: list[int]
    custom_instructions: Optional[str] = None   # override default tone/angle


# ── Event ─────────────────────────────────────────────────────────────────────

class EventIn(BaseModel):
    campaign_id: int
    lead_id: int
    draft_id: Optional[int] = None
    event_type: str     # sent | opened | replied | meeting_booked | bounced
    metadata: dict[str, Any] = {}


# ── Dashboard ─────────────────────────────────────────────────────────────────

class CampaignSummary(BaseModel):
    id: int
    name: str
    segment: str
    sent: int
    replies: int
    meetings: int
    rating: float
    grade: str
    weakest_axis: str


class DashboardOut(BaseModel):
    active_campaigns: int
    totals: dict[str, int]
    overall_reply_rate: float
    overall_conversion_rate: float
    campaigns: list[CampaignSummary]
