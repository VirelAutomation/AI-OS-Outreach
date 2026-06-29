"""
Persistence layer — SQLite primary, Supabase sync when tables exist.

Tables (run supabase_setup.sql once):
  ig_outreach   — every DM sent
  ig_followups  — day-3 and day-7 follow-ups
"""

import os, sqlite3, logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

log = logging.getLogger("virel.db")

_SUPA_URL  = os.getenv("SUPABASE_URL", "").rstrip("/")
_SUPA_KEY  = os.getenv("SUPABASE_SERVICE_KEY", "")
_SUPABASE_OK = False          # set True only after successful table probe

_DATA    = Path(os.getenv("DATA_DIR", "")) if os.getenv("DATA_DIR") else None
DB_PATH  = (_DATA / "outreach.db") if _DATA else Path(__file__).parent / "outreach.db"
FOLLOWUP_DAYS = [3, 7]

# IST = UTC+5:30  (no DST — India doesn't observe DST)
_IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> datetime:
    return datetime.now(_IST)


def _today_ist() -> str:
    return _now_ist().strftime("%Y-%m-%d")


# ── Supabase helpers ──────────────────────────────────────────────────────────

def _h():
    return {
        "apikey": _SUPA_KEY,
        "Authorization": f"Bearer {_SUPA_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "return=representation",
    }


def _supa_get(table: str, params: dict) -> list:
    try:
        with httpx.Client(timeout=8) as c:
            r = c.get(f"{_SUPA_URL}/rest/v1/{table}", headers=_h(), params=params)
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        log.debug(f"[DB] Supabase GET {table} failed: {e}")
        return []


def _supa_post(table: str, payload, upsert=False) -> dict | None:
    try:
        h = _h()
        if upsert:
            h["Prefer"] = "resolution=ignore-duplicates,return=representation"
        with httpx.Client(timeout=8) as c:
            r = c.post(f"{_SUPA_URL}/rest/v1/{table}", headers=h, json=payload)
        data = r.json()
        return data[0] if isinstance(data, list) and data else None
    except Exception as e:
        log.debug(f"[DB] Supabase POST {table} failed: {e}")
        return None


def _supa_patch(table: str, match: dict, payload: dict):
    try:
        params = {k: f"eq.{v}" for k, v in match.items()}
        with httpx.Client(timeout=8) as c:
            c.patch(f"{_SUPA_URL}/rest/v1/{table}", headers=_h(), params=params, json=payload)
    except Exception as e:
        log.debug(f"[DB] Supabase PATCH {table} failed: {e}")


def _probe_supabase() -> bool:
    """True if ig_outreach table exists and is reachable."""
    if not (_SUPA_URL and _SUPA_KEY):
        return False
    try:
        with httpx.Client(timeout=6) as c:
            r = c.get(f"{_SUPA_URL}/rest/v1/ig_outreach",
                      headers=_h(), params={"select": "user_id", "limit": "1"})
        data = r.json()
        # list = table exists (even empty);  dict with 'code' = table missing / error
        return isinstance(data, list) and "code" not in str(data)
    except Exception:
        return False


# ── SQLite setup ──────────────────────────────────────────────────────────────

def _sqlite_init():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ig_outreach (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       TEXT UNIQUE NOT NULL,
            username      TEXT NOT NULL,
            full_name     TEXT,
            business_type TEXT,
            region        TEXT,
            followers     INTEGER,
            has_website   INTEGER DEFAULT 0,
            message_sent  TEXT,
            dm_sent_at    TEXT DEFAULT (datetime('now','localtime')),
            replied       INTEGER DEFAULT 0,
            replied_at    TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ig_followups (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            outreach_id     INTEGER,
            user_id         TEXT NOT NULL,
            username        TEXT NOT NULL,
            followup_number INTEGER DEFAULT 1,
            scheduled_for   TEXT NOT NULL,
            sent_at         TEXT,
            status          TEXT DEFAULT 'pending',
            message_sent    TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ig_comments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            media_id     TEXT UNIQUE NOT NULL,
            media_url    TEXT,
            user_id      TEXT,
            username     TEXT,
            caption_peek TEXT,
            comment_text TEXT,
            hashtag      TEXT,
            commented_at TEXT DEFAULT (datetime('now','localtime')),
            liked        INTEGER DEFAULT 0,
            replied_back INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def has_commented(media_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute("SELECT 1 FROM ig_comments WHERE media_id=?", (str(media_id),)).fetchone()
    conn.close()
    return row is not None


def log_comment(media_id: str, username: str, comment_text: str,
                hashtag: str = "", user_id: str = "", media_url: str = "",
                caption_peek: str = ""):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT OR IGNORE INTO ig_comments
            (media_id, media_url, user_id, username, caption_peek, comment_text, hashtag)
        VALUES (?,?,?,?,?,?,?)
    """, (str(media_id), media_url, str(user_id), username,
          caption_peek[:200], comment_text, hashtag))
    conn.commit()
    conn.close()


def get_comments_today() -> int:
    today = _today_ist()
    conn  = sqlite3.connect(DB_PATH)
    n     = conn.execute(
        "SELECT COUNT(*) FROM ig_comments WHERE commented_at LIKE ?", (f"{today}%",)
    ).fetchone()[0]
    conn.close()
    return n


def get_comment_stats() -> dict:
    conn = sqlite3.connect(DB_PATH)
    stats = {
        "total":          conn.execute("SELECT COUNT(*) FROM ig_comments").fetchone()[0],
        "today":          get_comments_today(),
        "replied_back":   conn.execute("SELECT COUNT(*) FROM ig_comments WHERE replied_back=1").fetchone()[0],
        "recent":         conn.execute(
            "SELECT username, comment_text, hashtag, commented_at FROM ig_comments ORDER BY commented_at DESC LIMIT 5"
        ).fetchall(),
    }
    conn.close()
    return stats


# ── Public API ────────────────────────────────────────────────────────────────

def init_db():
    global _SUPABASE_OK
    _sqlite_init()   # always init SQLite as the source of truth
    if _probe_supabase():
        _SUPABASE_OK = True
        log.info("[DB] SQLite (primary) + Supabase (sync)")
    else:
        log.info("[DB] SQLite only — run supabase_setup.sql to enable cloud sync")


def has_been_messaged(user_id: str) -> bool:
    """SQLite is the authoritative source — fast local check."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT 1 FROM ig_outreach WHERE user_id=?", (str(user_id),)).fetchone()
    conn.close()
    return row is not None


def mark_as_messaged(user_id: str, username: str, full_name: str,
                     business_type: str, region: str, followers: int,
                     has_website: bool, message: str):
    """Write to SQLite immediately, sync to Supabase in background."""
    now_ist = _now_ist().isoformat()

    # 1. SQLite write (always)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("""
        INSERT OR IGNORE INTO ig_outreach
            (user_id, username, full_name, business_type, region, followers,
             has_website, message_sent, dm_sent_at)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (str(user_id), username, full_name, business_type, region,
          followers, int(has_website), message, now_ist))
    outreach_id = cur.lastrowid
    conn.commit()

    if outreach_id:
        for i, day in enumerate(FOLLOWUP_DAYS):
            scheduled = (_now_ist() + timedelta(days=day)).isoformat()
            conn.execute("""
                INSERT INTO ig_followups
                    (outreach_id, user_id, username, followup_number, scheduled_for)
                VALUES (?,?,?,?,?)
            """, (outreach_id, str(user_id), username, i + 1, scheduled))
        conn.commit()
    conn.close()

    # 2. Supabase sync (best-effort)
    if _SUPABASE_OK:
        row = _supa_post("ig_outreach", {
            "user_id": str(user_id), "username": username, "full_name": full_name,
            "business_type": business_type, "region": region, "followers": followers,
            "has_website": has_website, "message_sent": message, "dm_sent_at": now_ist,
        }, upsert=True)
        if row and row.get("id"):
            for i, day in enumerate(FOLLOWUP_DAYS):
                scheduled = (_now_ist() + timedelta(days=day)).isoformat()
                _supa_post("ig_followups", {
                    "outreach_id": row["id"], "user_id": str(user_id),
                    "username": username, "followup_number": i + 1,
                    "scheduled_for": scheduled, "status": "pending",
                })


def get_due_followups() -> list:
    """Pull from SQLite — only pending ones where the lead hasn't replied."""
    conn = sqlite3.connect(DB_PATH)
    now = _now_ist().isoformat()
    rows = conn.execute("""
        SELECT f.id, f.outreach_id, f.user_id, f.username, f.followup_number
        FROM ig_followups f
        JOIN ig_outreach o ON o.id = f.outreach_id
        WHERE f.status = 'pending'
          AND f.scheduled_for <= ?
          AND o.replied = 0
        ORDER BY f.scheduled_for
    """, (now,)).fetchall()
    conn.close()
    return [{"id": r[0], "outreach_id": r[1], "user_id": r[2],
             "username": r[3], "followup_number": r[4]} for r in rows]


def mark_followup_sent(followup_id: int, message: str):
    now = _now_ist().isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE ig_followups SET status='sent', sent_at=?, message_sent=?
        WHERE id=? AND status='pending'
    """, (now, message, followup_id))
    conn.commit()
    conn.close()
    if _SUPABASE_OK:
        _supa_patch("ig_followups", {"id": followup_id}, {
            "status": "sent", "sent_at": now, "message_sent": message,
        })


def mark_replied(user_id: str):
    now = _now_ist().isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE ig_outreach SET replied=1, replied_at=? WHERE user_id=?",
                 (now, str(user_id)))
    conn.execute("UPDATE ig_followups SET status='skipped' WHERE user_id=? AND status='pending'",
                 (str(user_id),))
    conn.commit()
    conn.close()
    if _SUPABASE_OK:
        _supa_patch("ig_outreach", {"user_id": str(user_id)}, {"replied": True, "replied_at": now})


def get_daily_count() -> int:
    """Count using IST date so limit resets at midnight IST, not UTC."""
    today = _today_ist()
    conn = sqlite3.connect(DB_PATH)
    n = conn.execute(
        "SELECT COUNT(*) FROM ig_outreach WHERE dm_sent_at LIKE ?", (f"{today}%",)
    ).fetchone()[0]
    conn.close()
    return n


def get_all_stats() -> dict:
    conn = sqlite3.connect(DB_PATH)
    total   = conn.execute("SELECT COUNT(*) FROM ig_outreach").fetchone()[0]
    today   = get_daily_count()
    pending = conn.execute(
        "SELECT COUNT(*) FROM ig_followups WHERE status='pending'"
    ).fetchone()[0]
    conn.close()
    return {"total": total, "today": today, "pending_followups": pending}
