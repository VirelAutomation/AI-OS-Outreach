-- Executive ops schema extensions for Akhil and King

create table if not exists outreach.lead_management_actions (
  id               bigserial primary key,
  lead_id          bigint references outreach.leads(id) on delete cascade,
  campaign_id      bigint references outreach.campaigns(id) on delete cascade,
  event_id         bigint references outreach.events(id) on delete set null,
  executive_name   text default 'akhil',
  classification   text,
  status_before    text,
  status_after     text,
  summary          text,
  next_action      text,
  confidence       float,
  payload          jsonb default '{}'::jsonb,
  created_at       timestamptz default now()
);

create index if not exists lead_management_actions_lead_idx on outreach.lead_management_actions (lead_id, created_at desc);
create index if not exists lead_management_actions_campaign_idx on outreach.lead_management_actions (campaign_id, created_at desc);

create table if not exists outreach.follow_up_tasks (
  id               bigserial primary key,
  lead_id          bigint references outreach.leads(id) on delete cascade,
  campaign_id      bigint references outreach.campaigns(id) on delete set null,
  owner_executive  text default 'akhil',
  reason           text,
  due_at           timestamptz not null,
  priority         text default 'medium',
  status           text default 'open',
  payload          jsonb default '{}'::jsonb,
  created_at       timestamptz default now()
);

create index if not exists follow_up_tasks_due_idx on outreach.follow_up_tasks (status, due_at);
create index if not exists follow_up_tasks_lead_idx on outreach.follow_up_tasks (lead_id, created_at desc);

create table if not exists jarvis.training_governance_runs (
  id                  bigserial primary key,
  run_id              text unique not null,
  governor            text default 'king',
  scope               jsonb default '{}'::jsonb,
  segregation_summary jsonb default '{}'::jsonb,
  readiness_summary   jsonb default '{}'::jsonb,
  status              text default 'completed',
  started_at          timestamptz,
  completed_at        timestamptz,
  created_at          timestamptz default now()
);

create index if not exists training_governance_runs_created_idx on jarvis.training_governance_runs (created_at desc);

create table if not exists jarvis.agent_evaluations (
  id               bigserial primary key,
  agent_name       text not null,
  executive_owner  text,
  evaluation_type  text,
  score            float,
  verdict          text,
  summary          text,
  payload          jsonb default '{}'::jsonb,
  created_at       timestamptz default now()
);

create index if not exists agent_evaluations_agent_idx on jarvis.agent_evaluations (agent_name, created_at desc);
