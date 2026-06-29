"""
Creates all required Supabase tables for the IG outreach system.
Run once: python ig_outreach/create_tables.py
"""
import os, sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / "forge_system" / ".env")

import httpx

URL = os.getenv("SUPABASE_URL", "").rstrip("/")
KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

HEADERS = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
}

# Supabase exposes a SQL query endpoint at /rest/v1/rpc if you create a function,
# OR via the pg meta API at /pg/query (service role only on self-hosted).
# For hosted Supabase the only DDL path through the API is the management endpoint.
MGMT_HEADERS = {
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
}

PROJECT_REF = URL.replace("https://", "").split(".")[0]  # zfairbyuarmtgjwpncid

SQL = """
CREATE TABLE IF NOT EXISTS ig_outreach (
    id            BIGSERIAL PRIMARY KEY,
    user_id       TEXT NOT NULL,
    username      TEXT NOT NULL,
    full_name     TEXT,
    business_type TEXT,
    region        TEXT,
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
    followup_number INT DEFAULT 1,
    scheduled_for   TIMESTAMPTZ NOT NULL,
    sent_at         TIMESTAMPTZ,
    status          TEXT DEFAULT 'pending',
    message_sent    TEXT
);

CREATE INDEX IF NOT EXISTS idx_fu_scheduled ON ig_followups (scheduled_for)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_outreach_uid ON ig_outreach (user_id);
"""

def try_mgmt_api():
    """Try Supabase management API (works with personal access tokens)."""
    resp = httpx.post(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        headers=MGMT_HEADERS,
        json={"query": SQL},
        timeout=15,
    )
    return resp.status_code, resp.text


def try_rpc():
    """Try running SQL via a Supabase RPC exec function if it exists."""
    resp = httpx.post(
        f"{URL}/rest/v1/rpc/exec_sql",
        headers=HEADERS,
        json={"sql": SQL},
        timeout=15,
    )
    return resp.status_code, resp.text


def check_table_exists(table: str) -> bool:
    resp = httpx.get(
        f"{URL}/rest/v1/{table}",
        headers=HEADERS,
        params={"select": "user_id", "limit": "1"},
        timeout=10,
    )
    return isinstance(resp.json(), list)


if __name__ == "__main__":
    print(f"Project ref: {PROJECT_REF}")
    print(f"Supabase URL: {URL}\n")

    # Check if tables already exist
    if check_table_exists("ig_outreach"):
        print("Tables already exist.")
        sys.exit(0)

    print("Tables not found — attempting to create via management API...")
    code, text = try_mgmt_api()
    print(f"Management API response: {code} — {text[:200]}")

    if code == 200:
        print("Tables created successfully via management API.")
        sys.exit(0)

    print("\nManagement API needs a personal access token (not a project key).")
    print("\nTo create the tables, go to:")
    print(f"  https://supabase.com/dashboard/project/{PROJECT_REF}/sql/new")
    print("\nPaste this SQL and click Run:\n")
    print(SQL)
