create extension if not exists "pgcrypto";

create table if not exists public.products (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  description text,
  pricing_label text,
  attributed_revenue numeric not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists public.prospects (
  id uuid primary key default gen_random_uuid(),
  full_name text not null,
  email text,
  company_name text,
  role_title text,
  industry text not null,
  city text,
  source text not null default 'manual',
  status text not null default 'new',
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists public.call_logs (
  id uuid primary key default gen_random_uuid(),
  prospect_id uuid references public.prospects(id) on delete set null,
  prospect_name text not null,
  company_name text,
  vertical text,
  outcome text not null,
  notes text,
  follow_up_date date,
  logged_at timestamptz not null default now()
);

create table if not exists public.campaigns (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  target_vertical text not null,
  status text not null default 'draft',
  total_sent integer not null default 0,
  open_rate numeric not null default 0,
  reply_rate numeric not null default 0,
  positive_reply_rate numeric not null default 0,
  meetings_booked integer not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists public.campaign_steps (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  step_number integer not null,
  subject_line text,
  sent_count integer not null default 0,
  open_count integer not null default 0,
  reply_count integer not null default 0,
  meeting_count integer not null default 0
);

create table if not exists public.campaign_events (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  prospect_id uuid references public.prospects(id) on delete set null,
  event_type text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.deals (
  id uuid primary key default gen_random_uuid(),
  prospect_id uuid references public.prospects(id) on delete set null,
  prospect_name text not null,
  company_name text,
  vertical text,
  stage text not null default 'Lead',
  value_estimate numeric not null default 0,
  close_probability numeric not null default 0.08,
  created_at timestamptz not null default now()
);

create table if not exists public.deal_stage_history (
  id uuid primary key default gen_random_uuid(),
  deal_id uuid not null references public.deals(id) on delete cascade,
  from_stage text,
  to_stage text not null,
  changed_at timestamptz not null default now(),
  reason text
);

create table if not exists public.meetings (
  id uuid primary key default gen_random_uuid(),
  prospect_id uuid references public.prospects(id) on delete set null,
  prospect_name text not null,
  company_name text,
  meeting_type text not null,
  start_at timestamptz not null,
  status text not null default 'scheduled',
  notes text,
  value_estimate numeric not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists public.booking_requests (
  id uuid primary key default gen_random_uuid(),
  full_name text not null,
  email text not null,
  company_name text,
  requested_at timestamptz not null,
  source text not null default 'landing_page_chat',
  notes text,
  status text not null default 'requested',
  created_at timestamptz not null default now()
);

create table if not exists public.content_items (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  content_type text not null,
  vertical text,
  status text not null default 'backlog',
  source_note text,
  created_at timestamptz not null default now()
);

create table if not exists public.agent_runs (
  id uuid primary key default gen_random_uuid(),
  agent_name text not null,
  prompt text not null,
  response text,
  tools_used jsonb not null default '[]'::jsonb,
  guardrails jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.analytics_roots (
  id uuid primary key default gen_random_uuid(),
  collection_name text not null,
  root_hash text not null,
  record_count integer not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists public.analytics_global_roots (
  id uuid primary key default gen_random_uuid(),
  root_hash text not null,
  created_at timestamptz not null default now()
);

alter table public.products enable row level security;
alter table public.prospects enable row level security;
alter table public.call_logs enable row level security;
alter table public.campaigns enable row level security;
alter table public.campaign_steps enable row level security;
alter table public.campaign_events enable row level security;
alter table public.deals enable row level security;
alter table public.deal_stage_history enable row level security;
alter table public.meetings enable row level security;
alter table public.booking_requests enable row level security;
alter table public.content_items enable row level security;
alter table public.agent_runs enable row level security;
alter table public.analytics_roots enable row level security;
alter table public.analytics_global_roots enable row level security;

-- Demo/public read for now. Tighten to authenticated owner-only before real deployment.
drop policy if exists "public_products_read" on public.products;
create policy "public_products_read" on public.products for select to anon, authenticated using (true);

drop policy if exists "public_booking_requests_insert" on public.booking_requests;
create policy "public_booking_requests_insert" on public.booking_requests for insert to anon, authenticated with check (true);

drop policy if exists "public_booking_requests_read" on public.booking_requests;
create policy "public_booking_requests_read" on public.booking_requests for select to authenticated using (true);
