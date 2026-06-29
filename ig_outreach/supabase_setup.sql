-- Run ONCE in Supabase dashboard → SQL Editor

CREATE TABLE IF NOT EXISTS ig_outreach (
    id            BIGSERIAL PRIMARY KEY,
    user_id       TEXT NOT NULL,
    username      TEXT NOT NULL,
    full_name     TEXT,
    business_type TEXT,
    region        TEXT,           -- 'india' | 'us'
    followers     INT,
    has_website   BOOLEAN DEFAULT FALSE,
    message_sent  TEXT,
    dm_sent_at    TIMESTAMPTZ DEFAULT now(),
    replied       BOOLEAN DEFAULT FALSE,
    replied_at    TIMESTAMPTZ,
    UNIQUE (user_id)
);

CREATE TABLE IF NOT EXISTS ig_followups (
    id              BIGSERIAL PRIMARY KEY,
    outreach_id     BIGINT REFERENCES ig_outreach(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL,
    username        TEXT NOT NULL,
    followup_number INT DEFAULT 1,      -- 1 = first follow-up, 2 = second
    scheduled_for   TIMESTAMPTZ NOT NULL,
    sent_at         TIMESTAMPTZ,
    status          TEXT DEFAULT 'pending',  -- pending | sent | skipped (replied)
    message_sent    TEXT
);

CREATE INDEX IF NOT EXISTS idx_followups_scheduled ON ig_followups (scheduled_for)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_outreach_user ON ig_outreach (user_id);
