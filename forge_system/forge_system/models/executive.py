"""Pydantic request contracts for executive-layer workflows."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class ReplyTriageIn(BaseModel):
    campaign_id: int
    lead_id: int
    reply_text: str
    draft_id: Optional[int] = None
    metadata: dict[str, Any] = {}


class GovernanceRunIn(BaseModel):
    limit: int = 500
    domain_tags: Optional[list[str]] = None
    min_quality: Optional[float] = None
    max_examples: Optional[int] = None


class FollowUpTaskOut(BaseModel):
    id: int
    lead_id: int
    campaign_id: Optional[int] = None
    owner_executive: str
    reason: str
    due_at: datetime
    priority: str
    status: str