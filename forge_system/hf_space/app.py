import os
from typing import Any

import gradio as gr
import requests


SCI_API_BASE_URL = os.getenv("SCI_API_BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("SCI_API_KEY", "").strip()


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["x-api-key"] = API_KEY
    return headers


def run_sci_cycle(target_state: str, constraints: str, backlog: str, focus_areas: str) -> tuple[str, str, str]:
    payload: dict[str, Any] = {
        "founder_id": "founder",
        "target_state": target_state,
        "company_constraints": [item.strip() for item in constraints.splitlines() if item.strip()],
        "tasks_backlog": [item.strip() for item in backlog.splitlines() if item.strip()],
        "focus_areas": [item.strip() for item in focus_areas.splitlines() if item.strip()],
        "mode": "approval",
        "refresh_calendar": False,
    }
    response = requests.post(
        f"{SCI_API_BASE_URL}/api/jarvis/objectives",
        json=payload,
        headers=_headers(),
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    graph = data.get("objective_graph", {})
    eval_summary = data.get("model_eval", {})
    approvals = data.get("approvals", [])

    plan_markdown = "\n".join(
        f"- P{node.get('priority', 0)} | {node.get('owner', 'jarvis')} | {node.get('title', 'Untitled')}"
        for node in (graph.get("nodes") or [])
    ) or "- No objectives returned."

    eval_markdown = "\n".join(
        [
            f"- Planner: {eval_summary.get('planner_model', 'unknown')}",
            f"- Executor: {eval_summary.get('executor_model', 'unknown')}",
            f"- Plan quality: {eval_summary.get('plan_quality', 0)}",
            f"- Routing quality: {eval_summary.get('routing_quality', 0)}",
            f"- Latency: {eval_summary.get('latency_ms', 0)} ms",
            f"- Estimated cost: ${eval_summary.get('estimated_cost', 0)}",
        ]
    )

    approval_markdown = "\n".join(
        f"- {item.get('action_type', 'action')} | {item.get('status', 'pending')} | {item.get('title', 'Untitled')}"
        for item in approvals
    ) or "- No approval decisions returned."

    return plan_markdown, eval_markdown, approval_markdown


demo = gr.Interface(
    fn=run_sci_cycle,
    inputs=[
        gr.Textbox(
            label="Target state",
            value="Reach $50k MRR by protecting founder deep work and increasing booked meetings.",
            lines=3,
        ),
        gr.Textbox(
            label="Constraints",
            value="Founder time is fragmented\nCurrent systems are reactive",
            lines=4,
        ),
        gr.Textbox(
            label="Backlog",
            value="Fix outbound handoff\nProtect calendar blocks\nClarify offer positioning",
            lines=4,
        ),
        gr.Textbox(
            label="Focus areas",
            value="growth\nsystems\ncalendar",
            lines=3,
        ),
    ],
    outputs=[
        gr.Markdown(label="Objective graph"),
        gr.Markdown(label="Model eval"),
        gr.Markdown(label="Approval queue"),
    ],
    title="Jarvis SCI Evaluation Harness",
    description="Minimal Hugging Face Space for running the SCI planning loop against the forge_system backend.",
)


if __name__ == "__main__":
    demo.launch()
