# JARVIS Sovereign Multi-Agent OS

## Purpose

Jarvis is the CEO/orchestrator layer for FORGE OS. It does not wait for small commands only. It receives company-level goals, reasons causally about the current state, decomposes the goal into interventions, assigns specialist agents, and gates dangerous work for approval.

This v1 is deliberately bounded. It can create task graphs, assign agents, persist runs/logs, ask for API permissions, and hand CTO work back as an approval request. It does not silently mutate code or send email without a governed route.

## Core Loop

1. Operator gives Jarvis a goal.
2. SCI reasoner builds a causal intervention map.
3. Jarvis creates a task DAG.
4. Agent factory assigns work to specialists.
5. Agents either execute planning directly, spawn bounded subtasks, or request approval.
6. Jarvis synthesizes the run and records all state.

## Agents

- `orchestrator`: coordinates the run and final synthesis.
- `cto`: designs/builds systems, asks for APIs/credentials, gates code-changing work.
- `outreach`: lead-to-draft-to-send planning.
- `research`: market/account/prospect discovery.
- `ops`: monitoring, queues, failures, infrastructure checks.
- `crm`: lifecycle, follow-up, meeting stage changes.
- `content`: proposals, case studies, landing copy.
- `analyst`: targets, ratios, projections, KPI math.
- `human`: tasks that require Jace/Akhil.

## CTO Rules

The CTO agent can decide what should be built, which files/modules are likely involved, and which APIs are needed. In `approval` mode it returns `approval_required`; the workspace coding agent or operator must approve and implement.

This is intentional. A production Jarvis should not silently change code, spend API budget, or send emails without a traceable gate.

## New API Surface

- `POST /api/jarvis/sovereign/goal`
  - Body: `{ "goal": "...", "mode": "approval", "maxDepth": 3, "maxAgents": 20 }`
  - Runs SCI decomposition and agent execution.

- `GET /api/jarvis/sovereign/status`
  - Returns recent runs, tasks, logs, and company state.

- `POST /api/jarvis/sovereign/state`
  - Body: `{ "key": "mrr", "value": "0" }`
  - Updates Jarvis world state.

## Persistence

Current v1 persists to `backend/data/jarvis-state.json`. This is better than memory-only state, but it is not the final production store.

Production should move this to Supabase/Postgres tables:

- `jarvis_runs`
- `jarvis_tasks`
- `jarvis_agent_logs`
- `jarvis_company_state`
- `jarvis_permission_requests`
- `jarvis_tool_calls`

## Lead Generation Connection

Jarvis should treat lead generation as a causal system:

- target segment selection affects reply quality
- lead source quality affects draft relevance
- enrichment depth affects personalization
- send volume affects deliverability risk
- reply classification affects meeting conversion

The CTO agent owns building the lead generation system. The outreach and research agents own execution plans. Analytics owns conversion math.

