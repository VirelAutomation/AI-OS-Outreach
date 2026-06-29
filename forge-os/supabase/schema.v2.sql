-- FORGE OS Schema v2
-- Run this in Supabase SQL Editor AFTER schema.v1.sql.
-- Adds: Jarvis chat history, calendar cache, self-dev state, grade history.

-- ── Jarvis chat history ────────────────────────────────────────────────────
create table if not exists public.jarvis_messages (
  id uuid primary key default gen_random_uuid(),
  role text not null check (role in ('user', 'jarvis')),
  content text not null,
  context_snapshot jsonb,
  created_at timestamptz not null default now()
);

alter table public.jarvis_messages enable row level security;

create policy "jarvis_messages_read" on public.jarvis_messages
  for select to authenticated using (true);

create policy "jarvis_messages_insert" on public.jarvis_messages
  for insert to anon, authenticated with check (true);

-- ── Google Calendar event cache ────────────────────────────────────────────
create table if not exists public.calendar_events_cache (
  id text primary key,
  summary text,
  description text,
  start_time timestamptz,
  end_time timestamptz,
  status text default 'confirmed',
  jarvis_priority text,
  jarvis_notes text,
  synced_at timestamptz not null default now()
);

alter table public.calendar_events_cache enable row level security;

create policy "calendar_cache_read" on public.calendar_events_cache
  for select to authenticated using (true);

create policy "calendar_cache_write" on public.calendar_events_cache
  for all to anon, authenticated using (true) with check (true);

-- ── Self development state (singleton per operator) ────────────────────────
create table if not exists public.self_dev_state (
  id text primary key default 'jace',
  goals jsonb not null default '[]'::jsonb,
  habits jsonb not null default '{}'::jsonb,
  learning jsonb not null default '[]'::jsonb,
  reflections jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.self_dev_state enable row level security;

create policy "self_dev_read" on public.self_dev_state
  for select to anon, authenticated using (true);

create policy "self_dev_write" on public.self_dev_state
  for all to anon, authenticated using (true) with check (true);

-- ── Jarvis weekly grades ───────────────────────────────────────────────────
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

alter table public.jarvis_grades enable row level security;

create policy "jarvis_grades_read" on public.jarvis_grades
  for select to authenticated using (true);

create policy "jarvis_grades_insert" on public.jarvis_grades
  for insert to anon, authenticated with check (true);

-- ── Missing write policies for v1 tables (fix RLS gaps) ───────────────────
-- These tables had RLS enabled but no write policies — backend admin bypasses
-- RLS via service role, but these are needed for completeness.

create policy if not exists "prospects_write" on public.prospects
  for all to authenticated using (true) with check (true);

create policy if not exists "campaigns_write" on public.campaigns
  for all to authenticated using (true) with check (true);

create policy if not exists "meetings_write" on public.meetings
  for all to authenticated using (true) with check (true);

create policy if not exists "deals_write" on public.deals
  for all to authenticated using (true) with check (true);

create policy if not exists "agent_runs_write" on public.agent_runs
  for all to authenticated using (true) with check (true);

create policy if not exists "content_items_write" on public.content_items
  for all to authenticated using (true) with check (true);

-- Read policies for v1 tables that only had write or no policies
create policy if not exists "prospects_read" on public.prospects
  for select to authenticated using (true);

create policy if not exists "campaigns_read" on public.campaigns
  for select to authenticated using (true);

create policy if not exists "meetings_read" on public.meetings
  for select to authenticated using (true);

create policy if not exists "deals_read" on public.deals
  for select to authenticated using (true);

create policy if not exists "agent_runs_read" on public.agent_runs
  for select to authenticated using (true);

create policy if not exists "call_logs_read" on public.call_logs
  for select to authenticated using (true);

create policy if not exists "call_logs_write" on public.call_logs
  for all to authenticated using (true) with check (true);
