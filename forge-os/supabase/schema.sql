-- FORGE OS minimal persistence schema.
-- Run this in Supabase SQL Editor.
-- This stores the current single-page OS state as one JSON document while the backend evolves.

create table if not exists public.forge_settings (
  id text primary key,
  state jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.forge_settings enable row level security;

drop policy if exists "forge_settings_public_read" on public.forge_settings;
create policy "forge_settings_public_read"
on public.forge_settings
for select
to anon, authenticated
using (true);

drop policy if exists "forge_settings_public_write" on public.forge_settings;
create policy "forge_settings_public_write"
on public.forge_settings
for insert
to anon, authenticated
with check (true);

drop policy if exists "forge_settings_public_update" on public.forge_settings;
create policy "forge_settings_public_update"
on public.forge_settings
for update
to anon, authenticated
using (true)
with check (true);

-- Production note:
-- The public write policies above are acceptable only for a local/demo founder OS.
-- Before real users or customer data, replace them with authenticated owner-only policies.
