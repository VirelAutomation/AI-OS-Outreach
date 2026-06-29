"""SCI runtime orchestration for Jarvis."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from itertools import zip_longest
from uuid import uuid4

import google.generativeai as genai

from config import get_settings
from models.sci import (
    AgentExecutionTrace,
    ApprovalDecisionIn,
    CalendarWindow,
    CounterfactualPlan,
    EvidencePackage,
    FounderContextIn,
    GrowthHypothesis,
    ManualWorldStateUpdateIn,
    ModelEvalSummary,
    ObjectiveGraph,
    ObjectiveNode,
    PolicyDecision,
    SciCycleResult,
    TaskAllocation,
    WorldState,
)
from services.google_calendar import list_events
from services.sci_repository import SciRepository

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_iso(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    if "T" not in normalized:
        normalized = f"{normalized}T00:00:00+00:00"
    return datetime.fromisoformat(normalized)


def build_availability_windows(events: list[dict], now: datetime | None = None) -> list[CalendarWindow]:
    reference = now or _now()
    horizon_end = reference + timedelta(days=7)
    busy_blocks: list[tuple[datetime, datetime]] = []

    for event in events:
        try:
            start = _parse_iso(event["start"])
            end_at = _parse_iso(event["end"])
        except Exception:
            continue
        busy_blocks.append((start, end_at))

    busy_blocks.sort(key=lambda item: item[0])
    windows: list[CalendarWindow] = []
    cursor = reference
    for start, end_at in busy_blocks:
        if start > cursor:
            windows.append(
                CalendarWindow(
                    start_at=cursor,
                    end_at=start,
                    label="Open focus block",
                    energy="deep_work" if start.hour >= 10 else "admin",
                )
            )
        if end_at > cursor:
            cursor = end_at
    if cursor < horizon_end:
        windows.append(
            CalendarWindow(
                start_at=cursor,
                end_at=horizon_end,
                label="Open focus block",
                energy="deep_work",
            )
        )
    return [
        window
        for window in windows
        if (window.end_at - window.start_at) >= timedelta(minutes=45)
    ][:12]


def generate_growth_hypotheses(target_state: str, backlog: list[str], focus_areas: list[str]) -> list[GrowthHypothesis]:
    anchors = focus_areas or ["pipeline growth", "offer positioning", "system leverage"]
    backlog_hint = backlog[0] if backlog else "Founder attention is fragmented"
    return [
        GrowthHypothesis(
            title="Tighten the highest-leverage offer narrative",
            rationale=f"Target state '{target_state}' requires clearer conversion pressure. Current blocker: {backlog_hint}.",
            expected_impact="Improves reply-to-meeting conversion and founder clarity.",
            uncertainty="Medium",
            next_action=f"Pressure-test messaging for {anchors[0]}.",
        ),
        GrowthHypothesis(
            title="Protect founder deep work for compounding systems",
            rationale="Without defended build windows, execution stays reactive and growth compounds slowly.",
            expected_impact="Increases strategic throughput without adding headcount.",
            uncertainty="Low",
            next_action="Reserve at least two uninterrupted build blocks this week.",
        ),
        GrowthHypothesis(
            title="Build a live bottleneck ledger",
            rationale="SCI needs explicit contradictions to route work and update heuristics.",
            expected_impact="Improves prioritization accuracy and faster blocked-task recovery.",
            uncertainty="Low",
            next_action=f"Turn the top friction in {anchors[-1]} into a tracked initiative.",
        ),
    ]


def _strip_json(text: str) -> str:
    trimmed = text.strip()
    if "```" not in trimmed:
        return trimmed
    segment = trimmed.split("```")[1]
    if segment.startswith("json"):
        segment = segment[4:]
    return segment.strip()


class SciService:
    def __init__(self):
        self.settings = get_settings()
        self.repo = SciRepository()

    def _configure_model(self):
        genai.configure(api_key=self.settings.gemini_key_for("jarvis"))
        return genai.GenerativeModel(self.settings.gemini_model_reasoning)

    def _planner_prompt(self, state: WorldState) -> str:
        return "\n".join(
            [
                "You are JARVIS SCI, a target-state operator.",
                "Think in causal interventions, founder allocations, contradictions, and survivability.",
                "Return strict JSON with keys: summary, objectives, plans.",
                "Each objective needs: id, title, description, owner, priority, depends_on, success_metric, risk_level, action_type, evidence.",
                "Each plan needs: title, reasoning, leverage_score, feasibility_score, risk_score, node_sequence, why_selected.",
                f"WORLD_STATE={state.model_dump_json()}",
            ]
        )

    def _heuristic_graph(self, state: WorldState) -> tuple[ObjectiveGraph, list[CounterfactualPlan]]:
        graph_id = str(uuid4())
        nodes = [
            ObjectiveNode(
                id="clarify_target",
                title="Clarify numeric path to target state",
                description="Translate the founder target into a measurable path with constraints and leverage points.",
                owner="jarvis",
                priority=1,
                success_metric="A measurable path with weekly checkpoint metrics exists.",
                risk_level="low",
                action_type="internal_plan",
                evidence=state.founder_notes[:2] or ["Founder target state"],
            ),
            ObjectiveNode(
                id="protect_founder_time",
                title="Protect founder deep work blocks",
                description="Schedule high-leverage build and review windows around calendar constraints.",
                owner=state.founder_id,
                priority=2,
                depends_on=["clarify_target"],
                success_metric="At least two protected work blocks are allocated this week.",
                risk_level="low",
                action_type="founder_task",
                evidence=[window.label for window in state.availability_windows[:2]] or ["No windows yet"],
            ),
            ObjectiveNode(
                id="ship_growth_initiative",
                title="Ship the top growth initiative",
                description="Turn the highest-confidence hypothesis into concrete execution steps.",
                owner="research",
                priority=3,
                depends_on=["clarify_target"],
                success_metric="One growth initiative is ready for execution with owner and evidence.",
                risk_level="medium",
                action_type="external_write",
                evidence=[hypothesis.title for hypothesis in state.growth_hypotheses[:2]],
            ),
            ObjectiveNode(
                id="close_feedback_loop",
                title="Create execution feedback loop",
                description="Capture outcomes, blockers, and heuristic changes after execution.",
                owner="memory",
                priority=4,
                depends_on=["ship_growth_initiative"],
                success_metric="SCI has a persisted trace and updated bottleneck ledger.",
                risk_level="low",
                action_type="system_change",
                evidence=["Execution traces persisted"],
            ),
        ]
        graph = ObjectiveGraph(
            graph_id=graph_id,
            target_state=state.target_state,
            summary="Jarvis is prioritizing measurement clarity, protected founder time, and one compounding growth initiative.",
            nodes=nodes,
        )
        plans = [
            CounterfactualPlan(
                plan_id=str(uuid4()),
                graph_id=graph_id,
                title="Founder-time-first plan",
                reasoning="Protect time before expanding outbound complexity so the founder can execute the highest-leverage systems work.",
                leverage_score=0.91,
                feasibility_score=0.88,
                risk_score=0.24,
                why_selected="Best balance of founder capacity, execution speed, and compounding leverage.",
                node_sequence=["clarify_target", "protect_founder_time", "ship_growth_initiative", "close_feedback_loop"],
            ),
            CounterfactualPlan(
                plan_id=str(uuid4()),
                graph_id=graph_id,
                title="Outbound-volume-first plan",
                reasoning="Bias toward top-of-funnel expansion before internal systems are tightened.",
                leverage_score=0.76,
                feasibility_score=0.69,
                risk_score=0.51,
                node_sequence=["clarify_target", "ship_growth_initiative", "protect_founder_time", "close_feedback_loop"],
            ),
            CounterfactualPlan(
                plan_id=str(uuid4()),
                graph_id=graph_id,
                title="Evidence-hardening-first plan",
                reasoning="Spend the cycle increasing certainty before execution.",
                leverage_score=0.62,
                feasibility_score=0.92,
                risk_score=0.18,
                node_sequence=["clarify_target", "close_feedback_loop", "ship_growth_initiative", "protect_founder_time"],
            ),
        ]
        graph.selected_plan_id = plans[0].plan_id
        return graph, plans

    def _llm_graph(self, state: WorldState) -> tuple[ObjectiveGraph, list[CounterfactualPlan]]:
        graph, fallback_plans = self._heuristic_graph(state)
        try:
            model = self._configure_model()
            result = model.generate_content(self._planner_prompt(state))
            payload = json.loads(_strip_json(result.text))
            nodes = [
                ObjectiveNode(
                    id=item.get("id") or f"node_{index+1}",
                    title=item["title"],
                    description=item["description"],
                    owner=item.get("owner") or "jarvis",
                    priority=item.get("priority", index + 1),
                    depends_on=item.get("depends_on") or [],
                    success_metric=item.get("success_metric") or "Outcome is advanced measurably.",
                    risk_level=item.get("risk_level", "medium"),
                    action_type=item.get("action_type", "founder_task"),
                    evidence=item.get("evidence") or [],
                )
                for index, item in enumerate(payload.get("objectives") or [])
                if item.get("title") and item.get("description")
            ]
            plans = [
                CounterfactualPlan(
                    plan_id=str(uuid4()),
                    graph_id=graph.graph_id,
                    title=item["title"],
                    reasoning=item["reasoning"],
                    leverage_score=float(item.get("leverage_score", 0.7)),
                    feasibility_score=float(item.get("feasibility_score", 0.7)),
                    risk_score=float(item.get("risk_score", 0.3)),
                    why_selected=item.get("why_selected"),
                    node_sequence=item.get("node_sequence") or [],
                )
                for item in (payload.get("plans") or [])
                if item.get("title") and item.get("reasoning")
            ]
            if nodes:
                graph.summary = payload.get("summary") or graph.summary
                graph.nodes = nodes
            if plans:
                selected = sorted(plans, key=lambda plan: (-(plan.leverage_score + plan.feasibility_score - plan.risk_score)))[0]
                selected.why_selected = selected.why_selected or "Selected by highest composite score."
                graph.selected_plan_id = selected.plan_id
                return graph, plans
        except Exception as exc:
            logger.warning("SCI planner fell back to heuristic graph: %s", exc)
        return graph, fallback_plans

    def _build_allocations(self, graph: ObjectiveGraph, windows: list[CalendarWindow], mode: str) -> list[TaskAllocation]:
        allocations: list[TaskAllocation] = []
        for node, window in zip_longest(graph.nodes, windows, fillvalue=None):
            if node is None:
                continue
            approval_required = node.risk_level != "low" or node.action_type in {"external_write", "system_change"}
            allocations.append(
                TaskAllocation(
                    allocation_id=str(uuid4()),
                    graph_id=graph.graph_id,
                    node_id=node.id,
                    owner=node.owner,
                    title=node.title,
                    rationale=node.description,
                    start_at=window.start_at if isinstance(window, CalendarWindow) else None,
                    end_at=window.end_at if isinstance(window, CalendarWindow) else None,
                    status="planned" if approval_required or mode != "autonomous" else "running",
                    approval_required=approval_required,
                    risk_level=node.risk_level,
                )
            )
        return allocations

    def _policy_decisions(self, graph: ObjectiveGraph, allocations: list[TaskAllocation], mode: str) -> list[PolicyDecision]:
        decisions: list[PolicyDecision] = []
        allocation_map = {allocation.node_id: allocation for allocation in allocations}
        for node in graph.nodes:
            allocation = allocation_map.get(node.id)
            approval_required = allocation.approval_required if allocation else True
            status = "pending"
            if not approval_required:
                status = "auto_approved" if mode == "autonomous" else "approved"
            decisions.append(
                PolicyDecision(
                    decision_id=str(uuid4()),
                    graph_id=graph.graph_id,
                    node_id=node.id,
                    title=node.title,
                    rationale=f"{node.description} Action type: {node.action_type}.",
                    risk_level=node.risk_level,
                    action_type=node.action_type,
                    status=status,
                    approval_required=approval_required,
                )
            )
        return decisions

    def _execution_traces(self, graph: ObjectiveGraph, allocations: list[TaskAllocation], approvals: list[PolicyDecision]) -> list[AgentExecutionTrace]:
        approval_map = {decision.node_id: decision for decision in approvals}
        traces: list[AgentExecutionTrace] = []
        for allocation in allocations:
            decision = approval_map.get(allocation.node_id)
            status = "blocked" if decision and decision.approval_required else "completed"
            action_type = "founder_allocation" if allocation.owner == "founder" else "subagent_dispatch"
            traces.append(
                AgentExecutionTrace(
                    trace_id=str(uuid4()),
                    graph_id=graph.graph_id,
                    node_id=allocation.node_id,
                    agent_name=allocation.owner,
                    action_type=action_type,
                    status=status,
                    summary=f"{allocation.title} routed to {allocation.owner}.",
                    evidence_refs=[allocation.node_id],
                    payload={"approval_required": allocation.approval_required},
                )
            )
        return traces

    def _evidence_package(self, state: WorldState, graph: ObjectiveGraph, plan: CounterfactualPlan) -> EvidencePackage:
        artifacts = [
            {"type": "world_state", "target_state": state.target_state},
            {"type": "selected_plan", "plan_id": plan.plan_id, "title": plan.title},
            {"type": "calendar_windows", "count": len(state.availability_windows)},
        ]
        return EvidencePackage(
            evidence_id=str(uuid4()),
            graph_id=graph.graph_id,
            title=f"SCI evidence for {state.target_state[:80]}",
            summary="Jarvis packaged the founder context, selected plan, and scheduling rationale for auditability.",
            sources=state.context_sources,
            artifacts=artifacts,
        )

    def _model_eval(self, graph: ObjectiveGraph, state: WorldState) -> ModelEvalSummary:
        planner_model = self.settings.gemini_model_reasoning
        executor_model = self.settings.gemini_model_default
        complexity = max(len(graph.nodes), 1)
        latency_ms = 900 + complexity * 120
        return ModelEvalSummary(
            eval_id=str(uuid4()),
            scenario="weekly_founder_planning",
            planner_model=planner_model,
            executor_model=executor_model,
            plan_quality=round(min(0.7 + complexity * 0.04, 0.95), 2),
            routing_quality=0.84,
            latency_ms=latency_ms,
            estimated_cost=round(0.02 * complexity, 2),
            summary=f"Planner compared a {complexity}-node objective graph for {state.company_name}.",
        )

    async def run_cycle(self, payload: FounderContextIn) -> SciCycleResult:
        calendar_sync = await list_events(days=7) if payload.refresh_calendar else {"events": [], "source": "manual"}
        events = calendar_sync.get("events") or []
        world_state = WorldState(
            founder_id=payload.founder_id,
            company_name=payload.company_name or self.settings.company_name,
            target_state=payload.target_state,
            calendar_events=events,
            availability_windows=build_availability_windows(events),
            founder_notes=payload.founder_notes,
            company_constraints=payload.company_constraints,
            backlog=payload.tasks_backlog,
            focus_areas=payload.focus_areas,
            growth_hypotheses=generate_growth_hypotheses(payload.target_state, payload.tasks_backlog, payload.focus_areas),
            context_sources=["google_calendar" if events else "manual_context", "founder_input"],
            metadata={"mode": payload.mode, "calendar_source": calendar_sync.get("source")},
        )

        objective_graph, plans = self._llm_graph(world_state)
        selected_plan = next((plan for plan in plans if plan.plan_id == objective_graph.selected_plan_id), plans[0])
        allocations = self._build_allocations(objective_graph, world_state.availability_windows, payload.mode)
        approvals = self._policy_decisions(objective_graph, allocations, payload.mode)
        executions = self._execution_traces(objective_graph, allocations, approvals)
        evidence_package = self._evidence_package(world_state, objective_graph, selected_plan)
        model_eval = self._model_eval(objective_graph, world_state)

        self.repo.insert("world_states", world_state.model_dump(mode="json", exclude_none=True))
        objective_payload = objective_graph.model_dump(mode="json", exclude_none=True)
        objective_payload["founder_id"] = payload.founder_id
        self.repo.insert("objective_graphs", objective_payload)
        self.repo.bulk_insert("counterfactual_plans", [plan.model_dump(mode="json", exclude_none=True) for plan in plans])
        self.repo.bulk_insert("task_allocations", [allocation.model_dump(mode="json", exclude_none=True) for allocation in allocations])
        self.repo.bulk_insert("policy_decisions", [decision.model_dump(mode="json", exclude_none=True) for decision in approvals])
        self.repo.bulk_insert("agent_execution_traces", [trace.model_dump(mode="json", exclude_none=True) for trace in executions])
        self.repo.insert("evidence_packages", evidence_package.model_dump(mode="json", exclude_none=True))
        self.repo.insert("model_evaluations", model_eval.model_dump(mode="json", exclude_none=True))

        return SciCycleResult(
            world_state=world_state,
            objective_graph=objective_graph,
            selected_plan=selected_plan,
            allocations=allocations,
            approvals=approvals,
            executions=executions,
            evidence_package=evidence_package,
            model_eval=model_eval,
        )

    def latest_world_state(self, founder_id: str = "founder") -> dict | None:
        return self.repo.latest_one("world_states", founder_id=founder_id)

    def latest_graphs(self, limit: int = 10, founder_id: str | None = None) -> list[dict]:
        return self.repo.list_latest("objective_graphs", limit=limit, founder_id=founder_id)

    def latest_allocations(self, limit: int = 20, owner: str | None = None) -> list[dict]:
        return self.repo.list_latest("task_allocations", limit=limit, owner=owner)

    def latest_approvals(self, limit: int = 20, status: str | None = None) -> list[dict]:
        return self.repo.list_latest("policy_decisions", limit=limit, status=status)

    def latest_executions(self, limit: int = 20) -> list[dict]:
        return self.repo.list_latest("agent_execution_traces", limit=limit)

    def latest_evals(self, limit: int = 20) -> list[dict]:
        return self.repo.list_latest("model_evaluations", limit=limit)

    def apply_world_state_update(self, payload: ManualWorldStateUpdateIn) -> dict[str, object]:
        latest = self.latest_world_state(payload.founder_id)
        merged = {
            "founder_id": payload.founder_id,
            "company_name": (latest or {}).get("company_name") or self.settings.company_name,
            "target_state": payload.target_state or (latest or {}).get("target_state") or "Increase company leverage",
            "calendar_events": (latest or {}).get("calendar_events") or [],
            "availability_windows": (latest or {}).get("availability_windows") or [],
            "founder_notes": payload.founder_notes if payload.founder_notes is not None else (latest or {}).get("founder_notes", []),
            "company_constraints": payload.company_constraints if payload.company_constraints is not None else (latest or {}).get("company_constraints", []),
            "backlog": payload.tasks_backlog if payload.tasks_backlog is not None else (latest or {}).get("backlog", []),
            "focus_areas": payload.focus_areas if payload.focus_areas is not None else (latest or {}).get("focus_areas", []),
            "growth_hypotheses": (latest or {}).get("growth_hypotheses") or [],
            "context_sources": (latest or {}).get("context_sources") or ["manual_update"],
            "metadata": {**((latest or {}).get("metadata") or {}), **payload.metadata},
        }
        state = WorldState.model_validate(merged)
        return self.repo.insert("world_states", state.model_dump(mode="json", exclude_none=True))

    def record_approval(self, decision_id: str, payload: ApprovalDecisionIn) -> dict | None:
        updated = self.repo.update_by_id(
            "policy_decisions",
            "decision_id",
            decision_id,
            {
                "status": payload.status,
                "reviewed_by": payload.reviewer,
                "review_note": payload.note or "",
                "reviewed_at": _now().isoformat(),
            },
        )
        if updated and updated.get("node_id"):
            allocation = self.repo.update_where(
                "task_allocations",
                {
                    "status": "planned" if payload.status == "approved" else "blocked",
                },
                node_id=updated["node_id"],
                graph_id=updated["graph_id"],
            )
            if allocation:
                self.repo.insert(
                    "agent_execution_traces",
                    AgentExecutionTrace(
                        trace_id=str(uuid4()),
                        graph_id=updated["graph_id"],
                        node_id=updated["node_id"],
                        agent_name=payload.reviewer,
                        action_type="approval_review",
                        status="completed",
                        summary=f"{payload.reviewer} marked decision {payload.status}.",
                        payload={"note": payload.note or ""},
                    ).model_dump(mode="json", exclude_none=True),
                )
        return updated
