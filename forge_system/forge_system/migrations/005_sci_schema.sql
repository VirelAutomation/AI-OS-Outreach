-- SCI runtime persistence schema

create table if not exists jarvis.sci_world_states (
  id                 bigserial primary key,
  founder_id         text not null,
  company_name       text not null,
  target_state       text not null,
  calendar_events    jsonb default '[]'::jsonb,
  availability_windows jsonb default '[]'::jsonb,
  founder_notes      jsonb default '[]'::jsonb,
  company_constraints jsonb default '[]'::jsonb,
  backlog            jsonb default '[]'::jsonb,
  focus_areas        jsonb default '[]'::jsonb,
  growth_hypotheses  jsonb default '[]'::jsonb,
  context_sources    jsonb default '[]'::jsonb,
  metadata           jsonb default '{}'::jsonb,
  created_at         timestamptz default now()
);

create index if not exists sci_world_states_founder_idx
  on jarvis.sci_world_states (founder_id, created_at desc);

create table if not exists jarvis.sci_objective_graphs (
  id                 bigserial primary key,
  graph_id           text unique not null,
  founder_id         text not null default 'founder',
  target_state       text not null,
  summary            text not null,
  nodes              jsonb default '[]'::jsonb,
  selected_plan_id   text,
  created_at         timestamptz default now()
);

create index if not exists sci_objective_graphs_founder_idx
  on jarvis.sci_objective_graphs (founder_id, created_at desc);

create table if not exists jarvis.sci_counterfactual_plans (
  id                 bigserial primary key,
  plan_id            text unique not null,
  graph_id           text not null,
  title              text not null,
  reasoning          text not null,
  leverage_score     float not null default 0,
  feasibility_score  float not null default 0,
  risk_score         float not null default 0,
  why_selected       text,
  node_sequence      jsonb default '[]'::jsonb,
  created_at         timestamptz default now()
);

create index if not exists sci_counterfactual_plans_graph_idx
  on jarvis.sci_counterfactual_plans (graph_id, created_at desc);

create table if not exists jarvis.sci_task_allocations (
  id                 bigserial primary key,
  allocation_id      text unique not null,
  graph_id           text not null,
  node_id            text not null,
  owner              text not null,
  title              text not null,
  rationale          text not null,
  start_at           timestamptz,
  end_at             timestamptz,
  status             text not null default 'planned',
  approval_required  boolean not null default false,
  risk_level         text not null default 'medium',
  created_at         timestamptz default now()
);

create index if not exists sci_task_allocations_owner_idx
  on jarvis.sci_task_allocations (owner, created_at desc);

create table if not exists jarvis.sci_policy_decisions (
  id                 bigserial primary key,
  decision_id        text unique not null,
  graph_id           text not null,
  node_id            text not null,
  title              text not null,
  rationale          text not null,
  risk_level         text not null,
  action_type        text not null,
  status             text not null default 'pending',
  approval_required  boolean not null default true,
  reviewed_by        text,
  review_note        text,
  reviewed_at        timestamptz,
  created_at         timestamptz default now()
);

create index if not exists sci_policy_decisions_status_idx
  on jarvis.sci_policy_decisions (status, created_at desc);

create table if not exists jarvis.sci_agent_execution_traces (
  id                 bigserial primary key,
  trace_id           text unique not null,
  graph_id           text not null,
  node_id            text,
  agent_name         text not null,
  action_type        text not null,
  status             text not null,
  summary            text not null,
  evidence_refs      jsonb default '[]'::jsonb,
  payload            jsonb default '{}'::jsonb,
  created_at         timestamptz default now()
);

create index if not exists sci_execution_traces_graph_idx
  on jarvis.sci_agent_execution_traces (graph_id, created_at desc);

create table if not exists jarvis.sci_evidence_packages (
  id                 bigserial primary key,
  evidence_id        text unique not null,
  graph_id           text not null,
  title              text not null,
  summary            text not null,
  sources            jsonb default '[]'::jsonb,
  artifacts          jsonb default '[]'::jsonb,
  created_at         timestamptz default now()
);

create table if not exists jarvis.sci_model_evaluations (
  id                 bigserial primary key,
  eval_id            text unique not null,
  scenario           text not null,
  planner_model      text not null,
  executor_model     text not null,
  plan_quality       float not null default 0,
  routing_quality    float not null default 0,
  latency_ms         integer not null default 0,
  estimated_cost     float not null default 0,
  summary            text not null,
  created_at         timestamptz default now()
);

create index if not exists sci_model_evaluations_created_idx
  on jarvis.sci_model_evaluations (created_at desc);
