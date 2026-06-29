-- 003_growth_ops_schema.sql
-- Growth operations tables for landing-page signals, Apify source runs,
-- and dashboard-driven automation management.

create table if not exists outreach.page_visits (
  id            bigserial primary key,
  campaign_id   bigint references outreach.campaigns(id) on delete set null,
  lead_id       bigint references outreach.leads(id) on delete set null,
  draft_id      bigint references outreach.email_drafts(id) on delete set null,
  visitor_email text,
  visitor_name  text,
  company_name  text,
  page_url      text not null,
  referrer      text,
  utm_source    text,
  utm_campaign  text,
  metadata      jsonb default '{}'::jsonb,
  created_at    timestamptz default now()
);

create index if not exists page_visits_campaign_idx on outreach.page_visits (campaign_id);
create index if not exists page_visits_lead_idx on outreach.page_visits (lead_id);
create index if not exists page_visits_created_idx on outreach.page_visits (created_at desc);

create table if not exists outreach.chat_signals (
  id          bigserial primary key,
  session_id  text not null,
  campaign_id bigint references outreach.campaigns(id) on delete set null,
  lead_id     bigint references outreach.leads(id) on delete set null,
  message     text not null,
  sentiment   text,
  qualified   boolean default false,
  metadata    jsonb default '{}'::jsonb,
  created_at  timestamptz default now()
);

create index if not exists chat_signals_session_idx on outreach.chat_signals (session_id);
create index if not exists chat_signals_campaign_idx on outreach.chat_signals (campaign_id);

create table if not exists outreach.booking_signals (
  id           bigserial primary key,
  campaign_id  bigint references outreach.campaigns(id) on delete set null,
  lead_id      bigint references outreach.leads(id) on delete set null,
  name         text not null,
  email        text not null,
  company      text,
  booking_time timestamptz not null,
  source       text default 'landing_page',
  metadata     jsonb default '{}'::jsonb,
  created_at   timestamptz default now()
);

create index if not exists booking_signals_campaign_idx on outreach.booking_signals (campaign_id);
create index if not exists booking_signals_created_idx on outreach.booking_signals (created_at desc);

create table if not exists outreach.source_runs (
  id                bigserial primary key,
  source_type       text not null,
  status            text not null default 'queued',
  search_term       text,
  industry          text,
  city              text,
  raw_count         int default 0,
  normalized_count  int default 0,
  payload           jsonb default '{}'::jsonb,
  response_snapshot jsonb default '{}'::jsonb,
  completed_at      timestamptz,
  created_at        timestamptz default now()
);

create index if not exists source_runs_type_idx on outreach.source_runs (source_type, created_at desc);

create table if not exists outreach.automation_tasks (
  id                bigserial primary key,
  name              text not null,
  owner_system      text not null,
  task_type         text not null,
  trigger_type      text not null,
  trigger_value     text,
  priority          text default 'medium',
  status            text default 'active',
  requires_approval boolean default true,
  payload           jsonb default '{}'::jsonb,
  created_at        timestamptz default now()
);

create index if not exists automation_tasks_owner_idx on outreach.automation_tasks (owner_system, status);

create table if not exists outreach.automation_runs (
  id         bigserial primary key,
  task_id     bigint references outreach.automation_tasks(id) on delete cascade,
  status      text not null default 'queued',
  summary     text,
  payload     jsonb default '{}'::jsonb,
  created_at  timestamptz default now()
);

create index if not exists automation_runs_task_idx on outreach.automation_runs (task_id, created_at desc);
