create table if not exists outreach.social_touchpoints (
  id            bigserial primary key,
  source_key    text unique not null,
  platform      text not null,
  channel       text not null,
  event_type    text not null,
  status        text default 'sent',
  external_id   text default '',
  account_key   text default '',
  actor_key     text default '',
  occurred_at   timestamptz,
  scheduled_for timestamptz,
  metadata      jsonb default '{}'::jsonb,
  created_at    timestamptz default now()
);

create index if not exists social_touchpoints_platform_idx on outreach.social_touchpoints (platform, occurred_at desc);
create index if not exists social_touchpoints_channel_idx on outreach.social_touchpoints (channel, occurred_at desc);
create index if not exists social_touchpoints_status_idx on outreach.social_touchpoints (status);
create index if not exists social_touchpoints_metadata_idx on outreach.social_touchpoints using gin (metadata);

create table if not exists outreach.social_runtime_snapshots (
  id               bigserial primary key,
  source_key       text unique not null,
  runtime          text not null default 'github-cron',
  status           text default 'ok',
  ran_at           timestamptz,
  due_slots        jsonb default '[]'::jsonb,
  executed_slots   jsonb default '[]'::jsonb,
  partial_failures jsonb default '[]'::jsonb,
  metadata         jsonb default '{}'::jsonb,
  created_at       timestamptz default now()
);

create index if not exists social_runtime_snapshots_runtime_idx on outreach.social_runtime_snapshots (runtime, ran_at desc);
