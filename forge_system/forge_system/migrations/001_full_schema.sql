-- ══════════════════════════════════════════════════════════════
-- FORGE SYSTEM — COMPLETE DATABASE MIGRATION
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor)
-- Run sections in order: Extensions → Schemas → Outreach → Jarvis → Functions
-- ══════════════════════════════════════════════════════════════


-- ── 1. Extensions ─────────────────────────────────────────────
create extension if not exists vector;  -- pgvector for Jarvis memory embeddings


-- ── 2. Schemas ────────────────────────────────────────────────
create schema if not exists outreach;
create schema if not exists jarvis;


-- ══════════════════════════════════════════════════════════════
-- OUTREACH SCHEMA
-- ══════════════════════════════════════════════════════════════

create table outreach.leads (
  id          bigserial primary key,
  name        text not null,
  company     text not null,
  email       text unique not null,
  role        text,
  industry    text,            -- legal | ecommerce | fintech
  city        text,
  phone       text,
  source      text default 'manual',  -- apollo | manual | csv | webhook
  status      text default 'new',     -- new | contacted | replied | converted | dead
  notes       text,
  extra_data  jsonb default '{}'::jsonb,
  created_at  timestamptz default now()
);

-- Indexes designed around the actual query patterns in the routers
create index on outreach.leads (industry);
create index on outreach.leads (city);
create index on outreach.leads (status);
create index on outreach.leads (industry, city);          -- composite for filtered list views
create index on outreach.leads using gin (extra_data);    -- for querying inside Apollo JSON fields


create table outreach.campaigns (
  id            bigserial primary key,
  name          text unique not null,
  segment       text,
  status        text default 'draft',   -- draft | active | paused | closed
  start_date    timestamptz,
  end_date      timestamptz,
  total_leads   int default 0,
  sent_count    int default 0,
  opened_count  int default 0,
  replied_count int default 0,
  meeting_count int default 0,
  bounced_count int default 0,
  rating        float default 0.0,
  extra_data    jsonb default '{}'::jsonb,
  created_at    timestamptz default now()
);

create index on outreach.campaigns (status);
create index on outreach.campaigns (segment);


create table outreach.plans (
  id           bigserial primary key,
  campaign_id  bigint references outreach.campaigns(id) on delete cascade,
  title        text,
  steps        jsonb default '[]'::jsonb,   -- array of {day, action, batch_size, status}
  status       text default 'active',       -- active | archived
  created_at   timestamptz default now()
);

create index on outreach.plans (campaign_id, status);


create table outreach.goals (
  id             bigserial primary key,
  campaign_id    bigint references outreach.campaigns(id) on delete cascade,
  goal_type      text,          -- meetings | replies | sent | revenue
  target_value   float,
  current_value  float default 0.0,
  deadline       timestamptz,
  status         text default 'active',   -- active | hit | missed | archived
  created_at     timestamptz default now()
);

create index on outreach.goals (campaign_id, status);


create table outreach.email_drafts (
  id              bigserial primary key,
  campaign_id     bigint references outreach.campaigns(id) on delete cascade,
  lead_id         bigint references outreach.leads(id),
  subject         text,
  body            text,
  version         int default 1,
  status          text default 'draft',   -- draft | approved | sent | replied | bounced
  gmail_draft_id  text,
  sent_at         timestamptz,
  extra_data      jsonb default '{}'::jsonb,
  created_at      timestamptz default now()
);

create index on outreach.email_drafts (campaign_id);
create index on outreach.email_drafts (lead_id);
create index on outreach.email_drafts (status);
create index on outreach.email_drafts (campaign_id, status);  -- for draft review queue


create table outreach.events (
  id           bigserial primary key,
  campaign_id  bigint references outreach.campaigns(id) on delete cascade,
  lead_id      bigint references outreach.leads(id),
  draft_id     bigint references outreach.email_drafts(id),
  event_type   text,       -- sent | opened | replied | meeting_booked | bounced
  metadata     jsonb default '{}'::jsonb,
  created_at   timestamptz default now()
);

-- This index is critical — campaign metric recomputation queries events by campaign_id constantly
create index on outreach.events (campaign_id);
create index on outreach.events (campaign_id, event_type);
create index on outreach.events (lead_id);


-- ══════════════════════════════════════════════════════════════
-- JARVIS SCHEMA
-- ══════════════════════════════════════════════════════════════

create table jarvis.conversations (
  id                     bigserial primary key,
  session_id             text not null,
  user_id                text,
  role                   text not null,       -- user | assistant | system
  content                text not null,
  model_version          text,
  latency_ms             int,
  processed_for_training boolean default false,
  created_at             timestamptz default now()
);

create index on jarvis.conversations (session_id);
create index on jarvis.conversations (session_id, created_at);
-- Partial index: only unprocessed rows — the segregation agent queries this exclusively
create index on jarvis.conversations (processed_for_training)
  where processed_for_training = false;


create table jarvis.feedback (
  id               bigserial primary key,
  conversation_id  bigint references jarvis.conversations(id),
  signal_type      text,      -- thumbs_up | thumbs_down | correction | explicit_rating
  corrected_text   text,
  score            float,     -- 0.0–1.0 for explicit ratings
  created_at       timestamptz default now()
);

create index on jarvis.feedback (conversation_id);


create table jarvis.training_examples (
  id              bigserial primary key,
  source_type     text,         -- conversation | feedback | outreach | manual
  source_id       bigint,
  instruction     text not null,
  response        text not null,
  system_prompt   text,
  quality_score   float,
  domain_tag      text,         -- general | real_estate | outreach | ops
  used_in_run_id  text,
  processed       boolean default false,
  created_at      timestamptz default now()
);

create index on jarvis.training_examples (processed);
create index on jarvis.training_examples (domain_tag);
create index on jarvis.training_examples (quality_score desc);
-- Partial index: only unprocessed high-quality examples — what the training worker fetches
create index on jarvis.training_examples (quality_score desc)
  where processed = false;


create table jarvis.training_runs (
  id               bigserial primary key,
  run_id           text unique not null,
  base_model       text,
  model_version    text,
  hf_repo          text,
  example_count    int,
  domain_tags      text[],
  validation_loss  float,
  status           text default 'queued',   -- queued | running | complete | failed
  started_at       timestamptz,
  completed_at     timestamptz,
  created_at       timestamptz default now()
);


-- Long-term memory — the most architecturally important table in the Jarvis system
-- The embedding column uses Gemini's text-embedding-004 (768 dimensions)
-- If you switch to OpenAI text-embedding-3-small, change 768 to 1536
create table jarvis.long_term_memory (
  id             bigserial primary key,
  user_id        text not null,
  memory_type    text,        -- fact | preference | entity | relationship
  content        text not null,
  importance     float default 0.5,
  last_accessed  timestamptz default now(),
  access_count   int default 0,
  embedding      vector(768),
  created_at     timestamptz default now()
);

create index on jarvis.long_term_memory (user_id);
-- HNSW index for fast approximate nearest neighbour search
-- m=16 and ef_construction=64 are good defaults — increase for better recall at cost of memory
create index on jarvis.long_term_memory
  using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64);


-- Event store — append-only, never update or delete rows here
-- This is the foundation for the SEI/SII systems later
create table jarvis.event_store (
  id            bigserial primary key,
  stream_id     text not null,         -- which entity this event belongs to
  stream_type   text not null,         -- session | agent | campaign | lead
  event_type    text not null,
  sequence_num  int not null,
  payload       jsonb not null default '{}'::jsonb,
  metadata      jsonb default '{}'::jsonb,
  occurred_at   timestamptz not null default now(),
  unique (stream_id, sequence_num)     -- prevents duplicate events
);

create index on jarvis.event_store (stream_id, sequence_num);
create index on jarvis.event_store (stream_type, occurred_at desc);
create index on jarvis.event_store using gin (payload);


-- ══════════════════════════════════════════════════════════════
-- POSTGRES FUNCTIONS
-- ══════════════════════════════════════════════════════════════

-- Semantic memory search — called from utils/embeddings.py via Supabase RPC
create or replace function match_memories(
  query_embedding  vector(768),
  match_user_id    text,
  match_count      int default 5
)
returns table (
  id           bigint,
  content      text,
  importance   float,
  memory_type  text,
  similarity   float
)
language sql stable as $$
  select
    id,
    content,
    importance,
    memory_type,
    1 - (embedding <=> query_embedding) as similarity
  from jarvis.long_term_memory
  where user_id = match_user_id
  order by embedding <=> query_embedding
  limit match_count;
$$;


-- Bump memory access counter — called after a memory is used in a Jarvis response
create or replace function bump_memory_access(memory_id bigint)
returns void language sql as $$
  update jarvis.long_term_memory
  set
    access_count  = access_count + 1,
    last_accessed = now()
  where id = memory_id;
$$;


-- Next event sequence number for a stream — used by the event store
create or replace function next_sequence(p_stream_id text)
returns int language sql as $$
  select coalesce(max(sequence_num), 0) + 1
  from jarvis.event_store
  where stream_id = p_stream_id;
$$;
