"""
models/sci.py

Pydantic contracts for the SCI Jarvis runtime.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["low", "medium", "high"]
PolicyStatus = Literal["pending", "approved", "rejected", "auto_approved"]
ExecutionStatus = Literal["planned", "running", "completed", "blocked", "failed"]


class CalendarWindow(BaseModel):
    start_at: datetime
    end_at: datetime
    label: str
    source_event_id: str | None = None
    energy: Literal["deep_work", "meeting", "admin"] = "deep_work"


class FounderContextIn(BaseModel):
    founder_id: str = "founder"
    company_name: str | None = None
    target_state: str
    founder_notes: list[str] = Field(default_factory=list)
    company_constraints: list[str] = Field(default_factory=list)
    tasks_backlog: list[str] = Field(default_factory=list)
    focus_areas: list[str] = Field(default_factory=list)
    mode: Literal["advisory", "approval", "autonomous"] = "approval"
    refresh_calendar: bool = True


class ManualWorldStateUpdateIn(BaseModel):
    founder_id: str = "founder"
    target_state: str | None = None
    founder_notes: list[str] | None = None
    company_constraints: list[str] | None = None
    tasks_backlog: list[str] | None = None
    focus_areas: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GrowthHypothesis(BaseModel):
    title: str
    rationale: str
    expected_impact: str
    uncertainty: str
    next_action: str
    owner: str = "jarvis"


class WorldState(BaseModel):
    founder_id: str
    company_name: str
    target_state: str
    calendar_events: list[dict[str, Any]] = Field(default_factory=list)
    availability_windows: list[CalendarWindow] = Field(default_factory=list)
    founder_notes: list[str] = Field(default_factory=list)
    company_constraints: list[str] = Field(default_factory=list)
    backlog: list[str] = Field(default_factory=list)
    focus_areas: list[str] = Field(default_factory=list)
    growth_hypotheses: list[GrowthHypothesis] = Field(default_factory=list)
    context_sources: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class ObjectiveNode(BaseModel):
    id: str
    title: str
    description: str
    owner: str
    priority: int = 1
    depends_on: list[str] = Field(default_factory=list)
    success_metric: str
    risk_level: RiskLevel = "medium"
    action_type: Literal["internal_plan", "founder_task", "external_write", "system_change"] = "founder_task"
    evidence: list[str] = Field(default_factory=list)


class ObjectiveGraph(BaseModel):
    graph_id: str
    target_state: str
    summary: str
    nodes: list[ObjectiveNode]
    selected_plan_id: str | None = None
    created_at: datetime | None = None


class CounterfactualPlan(BaseModel):
    plan_id: str
    graph_id: str
    title: str
    reasoning: str
    leverage_score: float
    feasibility_score: float
    risk_score: float
    why_selected: str | None = None
    node_sequence: list[str] = Field(default_factory=list)
    created_at: datetime | None = None


class TaskAllocation(BaseModel):
    allocation_id: str
    graph_id: str
    node_id: str
    owner: str
    title: str
    rationale: str
    start_at: datetime | None = None
    end_at: datetime | None = None
    status: ExecutionStatus = "planned"
    approval_required: bool = False
    risk_level: RiskLevel = "medium"
    created_at: datetime | None = None


class AgentExecutionTrace(BaseModel):
    trace_id: str
    graph_id: str
    node_id: str | None = None
    agent_name: str
    action_type: str
    status: ExecutionStatus
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class EvidencePackage(BaseModel):
    evidence_id: str
    graph_id: str
    title: str
    summary: str
    sources: list[str] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime | None = None


class PolicyDecision(BaseModel):
    decision_id: str
    graph_id: str
    node_id: str
    title: str
    rationale: str
    risk_level: RiskLevel
    action_type: str
    status: PolicyStatus = "pending"
    approval_required: bool = True
    created_at: datetime | None = None


class ApprovalDecisionIn(BaseModel):
    status: Literal["approved", "rejected"]
    reviewer: str = "operator"
    note: str | None = None


class ModelEvalSummary(BaseModel):
    eval_id: str
    scenario: str
    planner_model: str
    executor_model: str
    plan_quality: float
    routing_quality: float
    latency_ms: int
    estimated_cost: float
    summary: str
    created_at: datetime | None = None


class SciCycleResult(BaseModel):
    world_state: WorldState
    objective_graph: ObjectiveGraph
    selected_plan: CounterfactualPlan
    allocations: list[TaskAllocation]
    approvals: list[PolicyDecision]
    executions: list[AgentExecutionTrace]
    evidence_package: EvidencePackage
    model_eval: ModelEvalSummary
