"""
models/asi.py — Pydantic schemas for the ASI Orchestrator and AEI network.

The ASI (Artificial Superintelligence) layer coordinates multiple AEI
(Artificial Expert Intelligence) agents via the Nexus message bus.
Each schema represents a contract between the orchestrator, the AEIs,
and the API layer.
"""

from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime


# ── Nexus inter-AEI messaging ─────────────────────────────────────────────────

class NexusTask(BaseModel):
    task_id: str
    source:  str                        # sending AEI name or "orchestrator"
    target:  str                        # receiving AEI name
    task_type: str                      # analyze | execute | report | coordinate
    payload: dict[str, Any] = {}
    priority: int = Field(5, ge=1, le=10)   # 1 = critical, 10 = background
    created_at: Optional[datetime] = None


class NexusResponse(BaseModel):
    task_id:     str
    aei:         str
    status:      str                    # completed | failed | delegated | pending
    result:      Optional[dict[str, Any]] = None
    insights:    list[str] = []
    next_actions: list[dict[str, Any]] = []
    confidence:  float = 1.0
    latency_ms:  Optional[int] = None


# ── Orchestrator command/response ─────────────────────────────────────────────

class OrchestratorCommand(BaseModel):
    command:    str                     # natural language command
    user_id:    Optional[str] = None
    context:    dict[str, Any] = {}
    target_aei: Optional[str] = None   # route directly to a specific AEI if set


class OrchestratorResponse(BaseModel):
    command_id:    str
    response:      str                  # direct answer to the command
    actions_taken: list[dict[str, Any]] = []
    aeis_involved: list[str] = []
    insights:      list[str] = []
    next_steps:    list[str] = []
    confidence:    float = 0.9


# ── System health and status ──────────────────────────────────────────────────

class AEIStatus(BaseModel):
    name:        str
    description: str
    status:      str = "active"         # active | degraded | offline
    capabilities: list[str] = []
    last_active: Optional[datetime] = None
    tasks_completed: int = 0


class SystemStatus(BaseModel):
    status:       str                   # operational | degraded | offline
    aeis:         dict[str, AEIStatus]
    active_campaigns: int = 0
    active_sessions:  int = 0
    orchestrator_version: str = "1.0.0"
    asi_level:    str = "AEI-Coordinated"
    uptime_note:  str = ""


# ── Analytics AEI ─────────────────────────────────────────────────────────────

class CampaignAnalysis(BaseModel):
    campaign_id:     int
    name:            str
    rating:          float
    grade:           str
    weakest_axis:    str
    diagnosis:       str
    ai_recommendation: str


class AnalyticsReport(BaseModel):
    campaigns_analyzed: int
    analysis:    list[CampaignAnalysis]
    summary:     str


class PipelineForecast(BaseModel):
    campaign_id:                  int
    sent_so_far:                  int
    remaining_to_send:            int
    current_reply_rate:           float
    current_conversion_rate:      float
    projected_additional_replies: int
    projected_additional_meetings: int
    total_projected_meetings:     int


# ── Intel AEI ─────────────────────────────────────────────────────────────────

class IntelBrief(BaseModel):
    company:             str
    industry:            str
    pain_points:         list[str]
    decision_makers:     list[str]
    hook_angle:          str
    competitive_context: str


class LeadEnrichmentResult(BaseModel):
    lead_id:       int
    enriched:      bool
    brief:         IntelBrief
    notes_updated: bool


# ── Intel research request ────────────────────────────────────────────────────

class ResearchRequest(BaseModel):
    company_name: str
    industry:     str = ""
