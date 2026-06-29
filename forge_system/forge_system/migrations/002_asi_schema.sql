-- ─────────────────────────────────────────────────────────────────────────────
-- 002_asi_schema.sql — ASI Orchestrator and AEI network tables
-- Run after 001_full_schema.sql in Supabase SQL Editor.
-- ─────────────────────────────────────────────────────────────────────────────


-- ── Nexus inter-AEI message log ───────────────────────────────────────────────
-- Records every message dispatched across the Nexus bus for audit and learning.
CREATE TABLE IF NOT EXISTS jarvis.nexus_events (
    id          BIGSERIAL PRIMARY KEY,
    task_id     TEXT        NOT NULL,
    source      TEXT        NOT NULL,       -- sending AEI or "orchestrator"
    target      TEXT        NOT NULL,       -- receiving AEI
    task_type   TEXT        NOT NULL,
    payload     JSONB       NOT NULL DEFAULT '{}',
    priority    INTEGER     NOT NULL DEFAULT 5,
    status      TEXT        NOT NULL DEFAULT 'dispatched',  -- dispatched | completed | failed
    result      JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_nexus_target    ON jarvis.nexus_events(target);
CREATE INDEX IF NOT EXISTS idx_nexus_status    ON jarvis.nexus_events(status);
CREATE INDEX IF NOT EXISTS idx_nexus_created   ON jarvis.nexus_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_nexus_task_id   ON jarvis.nexus_events(task_id);


-- ── Orchestrator command audit log ────────────────────────────────────────────
-- Every command sent to the ASI Orchestrator is persisted here for
-- audit, learning, and replay.
CREATE TABLE IF NOT EXISTS jarvis.orchestrator_commands (
    id          BIGSERIAL PRIMARY KEY,
    command_id  TEXT        NOT NULL UNIQUE,
    user_id     TEXT,
    command     TEXT        NOT NULL,
    response    TEXT        NOT NULL DEFAULT '',
    actions     JSONB       NOT NULL DEFAULT '[]',
    insights    JSONB       NOT NULL DEFAULT '[]',
    next_steps  JSONB       NOT NULL DEFAULT '[]',
    aeis        JSONB       NOT NULL DEFAULT '[]',
    confidence  REAL        NOT NULL DEFAULT 0.85,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orch_user      ON jarvis.orchestrator_commands(user_id);
CREATE INDEX IF NOT EXISTS idx_orch_created   ON jarvis.orchestrator_commands(created_at DESC);


-- ── Intel AEI company research cache ─────────────────────────────────────────
-- Caches company research briefs for 7 days to avoid redundant Gemini calls
-- and ensure consistent context across email generation and conversation.
CREATE TABLE IF NOT EXISTS jarvis.intel_briefings (
    id                  BIGSERIAL PRIMARY KEY,
    company             TEXT        NOT NULL,
    industry            TEXT        NOT NULL DEFAULT '',
    pain_points         JSONB       NOT NULL DEFAULT '[]',
    decision_makers     JSONB       NOT NULL DEFAULT '[]',
    hook_angle          TEXT        NOT NULL DEFAULT '',
    competitive_context TEXT        NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '7 days'
);

CREATE INDEX IF NOT EXISTS idx_intel_company  ON jarvis.intel_briefings(company);
CREATE INDEX IF NOT EXISTS idx_intel_industry ON jarvis.intel_briefings(industry);
CREATE INDEX IF NOT EXISTS idx_intel_expires  ON jarvis.intel_briefings(expires_at);


-- ── AEI performance tracking ──────────────────────────────────────────────────
-- Tracks AEI task completion, latency, and error rates over time.
-- Used by the Orchestrator to route tasks preferentially to healthy AEIs.
CREATE TABLE IF NOT EXISTS jarvis.aei_metrics (
    id              BIGSERIAL PRIMARY KEY,
    aei_name        TEXT        NOT NULL,
    task_type       TEXT        NOT NULL,
    status          TEXT        NOT NULL,   -- completed | failed
    latency_ms      INTEGER,
    error_detail    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_aei_metrics_name    ON jarvis.aei_metrics(aei_name);
CREATE INDEX IF NOT EXISTS idx_aei_metrics_status  ON jarvis.aei_metrics(status);
CREATE INDEX IF NOT EXISTS idx_aei_metrics_created ON jarvis.aei_metrics(created_at DESC);


-- ── Daily ops digest log ──────────────────────────────────────────────────────
-- Stores OPS AEI daily digest outputs for the team's historical reference.
CREATE TABLE IF NOT EXISTS jarvis.ops_digests (
    id          BIGSERIAL PRIMARY KEY,
    digest_date DATE        NOT NULL UNIQUE,
    health      TEXT        NOT NULL,
    bullets     JSONB       NOT NULL DEFAULT '[]',
    full_data   JSONB       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ops_digest_date ON jarvis.ops_digests(digest_date DESC);


-- ── Table and column documentation ───────────────────────────────────────────
COMMENT ON TABLE jarvis.nexus_events         IS 'Inter-AEI communication log for the Nexus message bus';
COMMENT ON TABLE jarvis.orchestrator_commands IS 'Audit trail of all ASI Orchestrator commands and responses';
COMMENT ON TABLE jarvis.intel_briefings      IS 'Cached company research briefs from the Intel AEI (7-day TTL)';
COMMENT ON TABLE jarvis.aei_metrics          IS 'AEI task performance metrics for routing and monitoring';
COMMENT ON TABLE jarvis.ops_digests          IS 'Daily operations digest history from the OPS AEI';
