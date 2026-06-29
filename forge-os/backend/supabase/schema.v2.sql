-- FORGE OS Schema v2
-- Apply after schema.v1.sql.
-- This file keeps the current public tables as canonical runtime storage
-- and adds the missing persistence layers for the full Forge OS roadmap.

create extension if not exists "vector";

create schema if not exists jarvis;

-- Core singleton state used by the frontend and orchestrator.
create table if not exists public.forge_settings (
  id text primary key,
  state jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.jarvis_messages (
  id uuid primary key default gen_random_uuid(),
  role text not null check (role in ('user', 'jarvis')),
  content text not null,
  context_snapshot jsonb,
  created_at timestamptz not null default now()
);

alter table public.jarvis_messages
  add column if not exists context_snapshot jsonb;

create table if not exists public.calendar_events_cache (
  id text primary key,
  summary text,
  description text,
  start_time timestamptz,
  end_time timestamptz,
  status text not null default 'confirmed',
  jarvis_priority text,
  jarvis_notes text,
  synced_at timestamptz not null default now()
);

create table if not exists public.self_dev_state (
  id text primary key default 'jace',
  goals jsonb not null default '[]'::jsonb,
  habits jsonb not null default '{}'::jsonb,
  learning jsonb not null default '[]'::jsonb,
  reflections jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.jarvis_grades (
  id uuid primary key default gen_random_uuid(),
  week_key text not null,
  grade text not null,
  score numeric not null,
  breakdown jsonb not null default '{}'::jsonb,
  recommendations jsonb not null default '[]'::jsonb,
  headline text,
  honest_truth text,
  created_at timestamptz not null default now()
);

-- Public-schema operating tables that are still missing from v1.
create table if not exists public.outreach_drafts (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid references public.prospects(id) on delete set null,
  campaign_id uuid references public.campaigns(id) on delete set null,
  subject text not null,
  body text not null,
  channel text not null default 'email',
  mode text not null default 'draft',
  provider text,
  provider_metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.outreach_send_events (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid references public.prospects(id) on delete set null,
  draft_id uuid references public.outreach_drafts(id) on delete set null,
  campaign_id uuid references public.campaigns(id) on delete set null,
  recipient_email text not null,
  channel text not null default 'email',
  status text not null default 'queued' check (status in ('queued', 'sent', 'failed', 'blocked')),
  provider_message_id text,
  reason text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.outreach_reply_events (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid references public.prospects(id) on delete set null,
  send_event_id uuid references public.outreach_send_events(id) on delete set null,
  intent text not null check (intent in ('interested', 'neutral', 'unsubscribe', 'objection', 'meeting_intent')),
  raw_text text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.outbound_suppressions (
  id uuid primary key default gen_random_uuid(),
  prospect_id uuid references public.prospects(id) on delete set null,
  email text not null,
  reason text not null,
  source text not null default 'lead_management',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (email)
);

create table if not exists public.prospect_enrichment_runs (
  id uuid primary key default gen_random_uuid(),
  prospect_id uuid references public.prospects(id) on delete cascade,
  provider text not null,
  mode text not null default 'manual',
  recent_signal text,
  recommended_angle text,
  enrichment_summary text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.campaign_goals (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  goal_type text not null,
  target_value numeric not null,
  current_value numeric not null default 0,
  deadline timestamptz,
  status text not null default 'active' check (status in ('active', 'archived', 'completed')),
  created_at timestamptz not null default now()
);

create table if not exists public.campaign_execution_plans (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  title text,
  steps jsonb not null default '[]'::jsonb,
  status text not null default 'active' check (status in ('active', 'completed', 'archived')),
  start_date timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create table if not exists public.page_visits (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid references public.campaigns(id) on delete set null,
  prospect_id uuid references public.prospects(id) on delete set null,
  draft_id uuid references public.outreach_drafts(id) on delete set null,
  visitor_email text,
  visitor_name text,
  company_name text,
  page_url text,
  referrer text,
  utm_source text,
  utm_campaign text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.chat_signals (
  id uuid primary key default gen_random_uuid(),
  session_id text,
  campaign_id uuid references public.campaigns(id) on delete set null,
  prospect_id uuid references public.prospects(id) on delete set null,
  message text not null,
  sentiment text,
  qualified boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.booking_signals (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid references public.campaigns(id) on delete set null,
  prospect_id uuid references public.prospects(id) on delete set null,
  booking_request_id uuid references public.booking_requests(id) on delete set null,
  meeting_id uuid references public.meetings(id) on delete set null,
  name text,
  email text,
  company text,
  booking_time timestamptz,
  source text not null default 'landing_page',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.automation_tasks (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  owner_system text,
  task_type text,
  trigger_type text,
  trigger_value text,
  priority text not null default 'medium',
  status text not null default 'active',
  requires_approval boolean not null default true,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.automation_runs (
  id uuid primary key default gen_random_uuid(),
  task_id uuid references public.automation_tasks(id) on delete set null,
  status text not null default 'queued' check (status in ('queued', 'running', 'done', 'failed')),
  summary text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.content_calendar_items (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  platform text,
  content_type text,
  status text not null default 'planned',
  publish_at timestamptz,
  owner_system text,
  source_item_id uuid references public.content_items(id) on delete set null,
  notes text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.agent_run_steps (
  id uuid primary key default gen_random_uuid(),
  agent_run_id uuid references public.agent_runs(id) on delete cascade,
  step_index integer not null,
  actor text not null,
  action text not null,
  status text not null default 'planned',
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- Private Jarvis data for memory, evaluations, and training.
create table if not exists jarvis.long_term_memory (
  id bigserial primary key,
  user_id text not null,
  memory_type text,
  content text not null,
  importance double precision not null default 0.5,
  embedding vector(768),
  access_count integer not null default 0,
  last_accessed timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists jarvis.feedback (
  id bigserial primary key,
  session_id text,
  user_id text,
  rating integer check (rating between 1 and 5),
  comment text,
  created_at timestamptz not null default now()
);

create table if not exists jarvis.training_examples (
  id bigserial primary key,
  session_id text,
  user_input text not null,
  ideal_output text not null,
  quality_score double precision not null default 0.5,
  domain_tag text,
  processed boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists jarvis.training_runs (
  id bigserial primary key,
  run_id text unique,
  status text not null default 'pending',
  examples integer not null default 0,
  metrics jsonb not null default '{}'::jsonb,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists jarvis.intel_briefings (
  id bigserial primary key,
  topic text not null,
  content text,
  sources jsonb not null default '[]'::jsonb,
  prospect_id uuid references public.prospects(id) on delete set null,
  created_at timestamptz not null default now()
);

create table if not exists jarvis.nexus_events (
  id bigserial primary key,
  event_type text not null,
  payload jsonb not null default '{}'::jsonb,
  source_agent text,
  created_at timestamptz not null default now()
);

create table if not exists jarvis.agent_evaluations (
  id bigserial primary key,
  agent_name text not null,
  executive_owner text,
  evaluation_type text,
  score double precision,
  verdict text,
  summary text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists jarvis.training_governance_runs (
  id bigserial primary key,
  run_id text unique,
  governor text not null default 'king',
  scope jsonb not null default '{}'::jsonb,
  segregation_summary jsonb not null default '{}'::jsonb,
  readiness_summary jsonb not null default '{}'::jsonb,
  status text not null default 'completed',
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now()
);

create or replace function jarvis.match_memories(
  query_embedding vector(768),
  match_user_id text,
  match_count integer default 5
)
returns table (
  id bigint,
  content text,
  importance double precision,
  similarity double precision
)
language sql
stable
as $$
  select
    memory.id,
    memory.content,
    memory.importance,
    1 - (memory.embedding <=> query_embedding) as similarity
  from jarvis.long_term_memory as memory
  where memory.user_id = match_user_id
    and memory.embedding is not null
  order by memory.embedding <=> query_embedding
  limit match_count;
$$;

create or replace function jarvis.bump_memory_access(memory_id bigint)
returns void
language sql
as $$
  update jarvis.long_term_memory
  set access_count = access_count + 1,
      last_accessed = now()
  where id = memory_id;
$$;

create index if not exists idx_outreach_drafts_lead on public.outreach_drafts(lead_id, created_at desc);
create index if not exists idx_outreach_send_events_lead on public.outreach_send_events(lead_id, created_at desc);
create index if not exists idx_outreach_send_events_status on public.outreach_send_events(status, created_at desc);
create index if not exists idx_outreach_reply_events_lead on public.outreach_reply_events(lead_id, created_at desc);
create index if not exists idx_outbound_suppressions_email on public.outbound_suppressions(email);
create index if not exists idx_prospect_enrichment_runs_prospect on public.prospect_enrichment_runs(prospect_id, created_at desc);
create index if not exists idx_campaign_goals_campaign on public.campaign_goals(campaign_id);
create index if not exists idx_campaign_execution_plans_campaign on public.campaign_execution_plans(campaign_id);
create index if not exists idx_page_visits_campaign on public.page_visits(campaign_id, created_at desc);
create index if not exists idx_chat_signals_session on public.chat_signals(session_id, created_at desc);
create index if not exists idx_booking_signals_campaign on public.booking_signals(campaign_id, created_at desc);
create index if not exists idx_automation_runs_task on public.automation_runs(task_id, created_at desc);
create index if not exists idx_content_calendar_items_status on public.content_calendar_items(status, publish_at);
create index if not exists idx_agent_run_steps_run on public.agent_run_steps(agent_run_id, step_index);
create index if not exists idx_jarvis_messages_created_at on public.jarvis_messages(created_at desc);
create index if not exists idx_jarvis_grades_week_key on public.jarvis_grades(week_key, created_at desc);
create index if not exists idx_calendar_events_cache_start on public.calendar_events_cache(start_time);
create index if not exists idx_jarvis_memory_user on jarvis.long_term_memory(user_id);
create index if not exists idx_jarvis_memory_embedding on jarvis.long_term_memory using ivfflat (embedding vector_cosine_ops);
create index if not exists idx_jarvis_feedback_session on jarvis.feedback(session_id, created_at desc);
create index if not exists idx_jarvis_training_examples_processed on jarvis.training_examples(processed, created_at desc);
create index if not exists idx_jarvis_training_runs_status on jarvis.training_runs(status, created_at desc);
create index if not exists idx_jarvis_intel_briefings_prospect on jarvis.intel_briefings(prospect_id, created_at desc);
create index if not exists idx_jarvis_nexus_events_type on jarvis.nexus_events(event_type, created_at desc);
create index if not exists idx_jarvis_agent_evaluations_agent on jarvis.agent_evaluations(agent_name, created_at desc);

alter table public.forge_settings enable row level security;
alter table public.jarvis_messages enable row level security;
alter table public.calendar_events_cache enable row level security;
alter table public.self_dev_state enable row level security;
alter table public.jarvis_grades enable row level security;
alter table public.outreach_drafts enable row level security;
alter table public.outreach_send_events enable row level security;
alter table public.outreach_reply_events enable row level security;
alter table public.outbound_suppressions enable row level security;
alter table public.prospect_enrichment_runs enable row level security;
alter table public.campaign_goals enable row level security;
alter table public.campaign_execution_plans enable row level security;
alter table public.page_visits enable row level security;
alter table public.chat_signals enable row level security;
alter table public.booking_signals enable row level security;
alter table public.automation_tasks enable row level security;
alter table public.automation_runs enable row level security;
alter table public.content_calendar_items enable row level security;
alter table public.agent_run_steps enable row level security;
alter table jarvis.long_term_memory enable row level security;
alter table jarvis.feedback enable row level security;
alter table jarvis.training_examples enable row level security;
alter table jarvis.training_runs enable row level security;
alter table jarvis.intel_briefings enable row level security;
alter table jarvis.nexus_events enable row level security;
alter table jarvis.agent_evaluations enable row level security;
alter table jarvis.training_governance_runs enable row level security;

drop policy if exists "forge_settings_public_read" on public.forge_settings;
create policy "forge_settings_public_read" on public.forge_settings
  for select to anon, authenticated using (true);

drop policy if exists "forge_settings_public_write" on public.forge_settings;
create policy "forge_settings_public_write" on public.forge_settings
  for insert to anon, authenticated with check (true);

drop policy if exists "forge_settings_public_update" on public.forge_settings;
create policy "forge_settings_public_update" on public.forge_settings
  for update to anon, authenticated using (true) with check (true);

drop policy if exists "jarvis_messages_read" on public.jarvis_messages;
create policy "jarvis_messages_read" on public.jarvis_messages
  for select to authenticated using (true);

drop policy if exists "jarvis_messages_insert" on public.jarvis_messages;
create policy "jarvis_messages_insert" on public.jarvis_messages
  for insert to anon, authenticated with check (true);

drop policy if exists "calendar_cache_read" on public.calendar_events_cache;
create policy "calendar_cache_read" on public.calendar_events_cache
  for select to authenticated using (true);

drop policy if exists "calendar_cache_write" on public.calendar_events_cache;
create policy "calendar_cache_write" on public.calendar_events_cache
  for all to authenticated using (true) with check (true);

drop policy if exists "self_dev_read" on public.self_dev_state;
create policy "self_dev_read" on public.self_dev_state
  for select to anon, authenticated using (true);

drop policy if exists "self_dev_write" on public.self_dev_state;
create policy "self_dev_write" on public.self_dev_state
  for all to anon, authenticated using (true) with check (true);

drop policy if exists "jarvis_grades_read" on public.jarvis_grades;
create policy "jarvis_grades_read" on public.jarvis_grades
  for select to authenticated using (true);

drop policy if exists "jarvis_grades_insert" on public.jarvis_grades;
create policy "jarvis_grades_insert" on public.jarvis_grades
  for insert to authenticated with check (true);

drop policy if exists "outreach_drafts_auth_all" on public.outreach_drafts;
create policy "outreach_drafts_auth_all" on public.outreach_drafts
  for all to authenticated using (true) with check (true);

drop policy if exists "outreach_send_events_auth_all" on public.outreach_send_events;
create policy "outreach_send_events_auth_all" on public.outreach_send_events
  for all to authenticated using (true) with check (true);

drop policy if exists "outreach_reply_events_auth_all" on public.outreach_reply_events;
create policy "outreach_reply_events_auth_all" on public.outreach_reply_events
  for all to authenticated using (true) with check (true);

drop policy if exists "outbound_suppressions_auth_all" on public.outbound_suppressions;
create policy "outbound_suppressions_auth_all" on public.outbound_suppressions
  for all to authenticated using (true) with check (true);

drop policy if exists "prospect_enrichment_runs_auth_all" on public.prospect_enrichment_runs;
create policy "prospect_enrichment_runs_auth_all" on public.prospect_enrichment_runs
  for all to authenticated using (true) with check (true);

drop policy if exists "campaign_goals_auth_all" on public.campaign_goals;
create policy "campaign_goals_auth_all" on public.campaign_goals
  for all to authenticated using (true) with check (true);

drop policy if exists "campaign_execution_plans_auth_all" on public.campaign_execution_plans;
create policy "campaign_execution_plans_auth_all" on public.campaign_execution_plans
  for all to authenticated using (true) with check (true);

drop policy if exists "page_visits_read" on public.page_visits;
create policy "page_visits_read" on public.page_visits
  for select to authenticated using (true);

drop policy if exists "page_visits_insert" on public.page_visits;
create policy "page_visits_insert" on public.page_visits
  for insert to anon, authenticated with check (true);

drop policy if exists "chat_signals_read" on public.chat_signals;
create policy "chat_signals_read" on public.chat_signals
  for select to authenticated using (true);

drop policy if exists "chat_signals_insert" on public.chat_signals;
create policy "chat_signals_insert" on public.chat_signals
  for insert to anon, authenticated with check (true);

drop policy if exists "booking_signals_read" on public.booking_signals;
create policy "booking_signals_read" on public.booking_signals
  for select to authenticated using (true);

drop policy if exists "booking_signals_insert" on public.booking_signals;
create policy "booking_signals_insert" on public.booking_signals
  for insert to anon, authenticated with check (true);

drop policy if exists "automation_tasks_auth_all" on public.automation_tasks;
create policy "automation_tasks_auth_all" on public.automation_tasks
  for all to authenticated using (true) with check (true);

drop policy if exists "automation_runs_auth_all" on public.automation_runs;
create policy "automation_runs_auth_all" on public.automation_runs
  for all to authenticated using (true) with check (true);

drop policy if exists "content_calendar_items_auth_all" on public.content_calendar_items;
create policy "content_calendar_items_auth_all" on public.content_calendar_items
  for all to authenticated using (true) with check (true);

drop policy if exists "agent_run_steps_auth_all" on public.agent_run_steps;
create policy "agent_run_steps_auth_all" on public.agent_run_steps
  for all to authenticated using (true) with check (true);

drop policy if exists "jarvis_memory_auth_all" on jarvis.long_term_memory;
create policy "jarvis_memory_auth_all" on jarvis.long_term_memory
  for all to authenticated using (true) with check (true);

drop policy if exists "jarvis_feedback_auth_all" on jarvis.feedback;
create policy "jarvis_feedback_auth_all" on jarvis.feedback
  for all to authenticated using (true) with check (true);

drop policy if exists "jarvis_training_examples_auth_all" on jarvis.training_examples;
create policy "jarvis_training_examples_auth_all" on jarvis.training_examples
  for all to authenticated using (true) with check (true);

drop policy if exists "jarvis_training_runs_auth_all" on jarvis.training_runs;
create policy "jarvis_training_runs_auth_all" on jarvis.training_runs
  for all to authenticated using (true) with check (true);

drop policy if exists "jarvis_intel_briefings_auth_all" on jarvis.intel_briefings;
create policy "jarvis_intel_briefings_auth_all" on jarvis.intel_briefings
  for all to authenticated using (true) with check (true);

drop policy if exists "jarvis_nexus_events_auth_all" on jarvis.nexus_events;
create policy "jarvis_nexus_events_auth_all" on jarvis.nexus_events
  for all to authenticated using (true) with check (true);

drop policy if exists "jarvis_agent_evaluations_auth_all" on jarvis.agent_evaluations;
create policy "jarvis_agent_evaluations_auth_all" on jarvis.agent_evaluations
  for all to authenticated using (true) with check (true);

drop policy if exists "jarvis_training_governance_runs_auth_all" on jarvis.training_governance_runs;
create policy "jarvis_training_governance_runs_auth_all" on jarvis.training_governance_runs
  for all to authenticated using (true) with check (true);

grant usage on schema jarvis to authenticated, service_role;
grant select, insert, update, delete on all tables in schema jarvis to authenticated, service_role;
grant usage, select on all sequences in schema jarvis to authenticated, service_role;
grant execute on all functions in schema jarvis to authenticated, service_role;
