"""
SQLite persistence for Facebook outreach.
Groups joined, posts made, members DMed, follow-ups, checkpoints.
"""

import sqlite3, logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

import os

log      = logging.getLogger("virel.fb.db")
_DATA    = Path(os.getenv("DATA_DIR", "")) if os.getenv("DATA_DIR") else None
DB_PATH  = (_DATA / "fb_outreach.db") if _DATA else Path(__file__).parent.absolute() / "fb_outreach.db"
_IST     = timezone(timedelta(hours=5, minutes=30))

FOLLOWUP_DAYS = [3, 7]


def _migrate(conn):
    """Add missing columns from schema updates without dropping existing data."""

    # If fb_dms is missing fb_uid (old schema), drop and recreate — safe since 0 DMs ever
    dms_cols = {r[1] for r in conn.execute("PRAGMA table_info(fb_dms)").fetchall()}
    if dms_cols and "fb_uid" not in dms_cols:
        log.info("[DB] fb_dms missing fb_uid — recreating table (no DM data lost)")
        conn.execute("DROP TABLE IF EXISTS fb_followups")
        conn.execute("DROP TABLE IF EXISTS fb_dms")
        conn.execute("""
            CREATE TABLE fb_dms (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                fb_uid              TEXT UNIQUE NOT NULL,
                profile_url         TEXT,
                group_source        TEXT,
                niche               TEXT,
                message_sent        TEXT,
                sent_at             TEXT,
                replied             INTEGER DEFAULT 0,
                replied_at          TEXT,
                whatsapp_number     TEXT,
                nationality         TEXT,
                friend_request_sent INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE fb_followups (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                dm_id           INTEGER REFERENCES fb_dms(id),
                fb_uid          TEXT NOT NULL,
                profile_url     TEXT,
                followup_number INTEGER DEFAULT 1,
                scheduled_for   TEXT NOT NULL,
                status          TEXT DEFAULT 'pending',
                message_sent    TEXT,
                sent_at         TEXT
            )
        """)
        conn.commit()

    migrations = [
        ("fb_posts",    "verified",             "INTEGER DEFAULT 0"),
        ("fb_posts",    "niche",                "TEXT"),
        ("fb_dms",      "niche",                "TEXT"),
        ("fb_dms",      "whatsapp_number",      "TEXT"),
        ("fb_dms",      "nationality",          "TEXT"),
        ("fb_dms",      "friend_request_sent",  "INTEGER DEFAULT 0"),
        ("fb_groups",   "status",               "TEXT DEFAULT 'active'"),
        ("fb_followups","profile_url",          "TEXT"),
    ]
    existing = {}
    for table, col, _ in migrations:
        if table not in existing:
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            existing[table] = cols
        if col not in existing[table]:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {_}")
            log.info(f"[DB] Migration: added {table}.{col}")


def _now() -> str:
    return datetime.now(_IST).isoformat()


def _today() -> str:
    return datetime.now(_IST).strftime("%Y-%m-%d")


def _conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS fb_groups (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id     TEXT UNIQUE NOT NULL,
            group_name   TEXT,
            group_url    TEXT,
            niche        TEXT,
            joined_at    TEXT,
            last_post_at TEXT,
            post_count   INTEGER DEFAULT 0,
            status       TEXT DEFAULT 'active'
        );
        CREATE TABLE IF NOT EXISTS fb_posts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id     TEXT NOT NULL,
            group_name   TEXT,
            niche        TEXT,
            message      TEXT,
            verified     INTEGER DEFAULT 0,
            posted_at    TEXT
        );
        CREATE TABLE IF NOT EXISTS fb_dms (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            fb_uid       TEXT UNIQUE NOT NULL,
            profile_url  TEXT,
            group_source TEXT,
            niche        TEXT,
            message_sent TEXT,
            sent_at      TEXT,
            replied      INTEGER DEFAULT 0,
            replied_at   TEXT
        );
        CREATE TABLE IF NOT EXISTS fb_followups (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            dm_id           INTEGER REFERENCES fb_dms(id),
            fb_uid          TEXT NOT NULL,
            profile_url     TEXT,
            followup_number INTEGER DEFAULT 1,
            scheduled_for   TEXT NOT NULL,
            status          TEXT DEFAULT 'pending',
            message_sent    TEXT,
            sent_at         TEXT
        );
        CREATE TABLE IF NOT EXISTS fb_checkpoint (
            id          INTEGER PRIMARY KEY,
            action      TEXT,
            group_id    TEXT,
            fb_uid      TEXT,
            saved_at    TEXT
        );
        CREATE TABLE IF NOT EXISTS fb_dm_queue (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            fb_uid        TEXT NOT NULL,
            profile_url   TEXT,
            group_source  TEXT,
            niche         TEXT,
            message       TEXT,
            reason        TEXT,
            scheduled_for TEXT NOT NULL,
            attempts      INTEGER DEFAULT 0,
            status        TEXT DEFAULT 'pending',
            created_at    TEXT
        );
        CREATE TABLE IF NOT EXISTS fb_comments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id      TEXT UNIQUE NOT NULL,
            group_id     TEXT,
            group_name   TEXT,
            niche        TEXT,
            comment_text TEXT,
            commented_at TEXT DEFAULT (datetime('now','localtime'))
        );
    """)
    conn.commit()

    # Migrations — add columns that didn't exist in earlier versions
    _migrate(conn)
    conn.commit()

    # Verify tables actually exist
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    required = {"fb_groups", "fb_posts", "fb_dms", "fb_followups", "fb_checkpoint", "fb_comments"}
    missing  = required - tables
    conn.close()

    if missing:
        raise RuntimeError(f"[DB] Tables not created: {missing}")
    log.info(f"[DB] OK — {DB_PATH.name}")


# ── Groups ────────────────────────────────────────────────────────────────────

def has_joined(group_id: str) -> bool:
    conn = _conn()
    row  = conn.execute("SELECT 1 FROM fb_groups WHERE group_id=?", (group_id,)).fetchone()
    conn.close()
    return row is not None


def get_groups_count_for_niche(niche: str) -> int:
    conn = _conn()
    n    = conn.execute(
        "SELECT COUNT(*) FROM fb_groups WHERE niche=? AND status='active'", (niche,)
    ).fetchone()[0]
    conn.close()
    return n


def log_group_joined(group_id: str, group_name: str, group_url: str, niche: str,
                     status: str = "active"):
    conn = _conn()
    conn.execute("""
        INSERT OR IGNORE INTO fb_groups (group_id, group_name, group_url, niche, joined_at, status)
        VALUES (?,?,?,?,?,?)
    """, (group_id, group_name, group_url, niche, _now(), status))
    conn.commit()
    conn.close()


def get_pending_groups() -> list[dict]:
    conn  = _conn()
    rows  = conn.execute(
        "SELECT group_id, group_name, group_url, niche FROM fb_groups WHERE status='pending'"
    ).fetchall()
    conn.close()
    return [{"group_id": r[0], "group_name": r[1], "group_url": r[2], "niche": r[3]} for r in rows]


def activate_group(group_id: str):
    conn = _conn()
    conn.execute("UPDATE fb_groups SET status='active' WHERE group_id=?", (group_id,))
    conn.commit()
    conn.close()


def posted_today(group_id: str) -> bool:
    conn = _conn()
    row  = conn.execute(
        "SELECT 1 FROM fb_posts WHERE group_id=? AND posted_at LIKE ? AND verified=1",
        (group_id, f"{_today()}%")
    ).fetchone()
    conn.close()
    return row is not None


def log_post(group_id: str, group_name: str, niche: str, message: str, verified: bool = True):
    conn = _conn()
    conn.execute("""
        INSERT INTO fb_posts (group_id, group_name, niche, message, verified, posted_at)
        VALUES (?,?,?,?,?,?)
    """, (group_id, group_name, niche, message, int(verified), _now()))
    conn.execute("""
        UPDATE fb_groups SET last_post_at=?, post_count=post_count+1 WHERE group_id=?
    """, (_now(), group_id))
    conn.commit()
    conn.close()


def get_joined_groups(niche: str = None) -> list[dict]:
    conn  = _conn()
    query = "SELECT group_id, group_name, group_url, niche FROM fb_groups WHERE status='active'"
    args  = ()
    if niche:
        query += " AND niche=?"
        args   = (niche,)
    rows = conn.execute(query, args).fetchall()
    conn.close()
    return [{"group_id": r[0], "group_name": r[1], "group_url": r[2], "niche": r[3]}
            for r in rows]


def posts_today() -> int:
    conn = _conn()
    n    = conn.execute(
        "SELECT COUNT(*) FROM fb_posts WHERE posted_at LIKE ? AND verified=1", (f"{_today()}%",)
    ).fetchone()[0]
    conn.close()
    return n


# ── DMs ───────────────────────────────────────────────────────────────────────

def has_been_dmed(fb_uid: str) -> bool:
    conn = _conn()
    row  = conn.execute("SELECT 1 FROM fb_dms WHERE fb_uid=?", (fb_uid,)).fetchone()
    conn.close()
    return row is not None


def log_dm(fb_uid: str, profile_url: str, group_source: str, niche: str, message: str,
           whatsapp_number: str = None, nationality: str = None, friend_request_sent: bool = False):
    conn  = _conn()
    cur   = conn.execute("""
        INSERT OR IGNORE INTO fb_dms
            (fb_uid, profile_url, group_source, niche, message_sent, sent_at,
             whatsapp_number, nationality, friend_request_sent)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (fb_uid, profile_url, group_source, niche, message, _now(),
          whatsapp_number, nationality, int(friend_request_sent)))
    dm_id = cur.lastrowid
    if dm_id:
        for i, day in enumerate(FOLLOWUP_DAYS):
            from datetime import timedelta
            scheduled = (datetime.now(_IST) + timedelta(days=day)).isoformat()
            conn.execute("""
                INSERT INTO fb_followups (dm_id, fb_uid, profile_url, followup_number, scheduled_for)
                VALUES (?,?,?,?,?)
            """, (dm_id, fb_uid, profile_url, i + 1, scheduled))
    conn.commit()
    conn.close()


def dms_today() -> int:
    conn = _conn()
    n    = conn.execute(
        "SELECT COUNT(*) FROM fb_dms WHERE sent_at LIKE ?", (f"{_today()}%",)
    ).fetchone()[0]
    conn.close()
    return n


def queue_pending_dm(fb_uid: str, profile_url: str, group_source: str,
                     niche: str, message: str, reason: str, scheduled_for: str):
    """Queue a DM that couldn't be sent — will be retried at scheduled_for."""
    conn = _conn()
    conn.execute("""
        INSERT OR IGNORE INTO fb_dm_queue
            (fb_uid, profile_url, group_source, niche, message, reason, scheduled_for, created_at)
        VALUES (?,?,?,?,?,?,?,?)
    """, (fb_uid, profile_url, group_source, niche, message, reason, scheduled_for, _now()))
    conn.commit()
    conn.close()


def get_pending_dm_queue() -> list[dict]:
    """Return all pending DMs that are due now or overdue."""
    now  = _now()
    conn = _conn()
    rows = conn.execute("""
        SELECT id, fb_uid, profile_url, group_source, niche, message, attempts
        FROM fb_dm_queue
        WHERE status='pending' AND scheduled_for <= ? AND attempts < 3
        ORDER BY scheduled_for
    """, (now,)).fetchall()
    conn.close()
    return [{"id": r[0], "fb_uid": r[1], "profile_url": r[2], "group_source": r[3],
             "niche": r[4], "message": r[5], "attempts": r[6]} for r in rows]


def mark_queue_sent(qid: int):
    conn = _conn()
    conn.execute("UPDATE fb_dm_queue SET status='sent' WHERE id=?", (qid,))
    conn.commit()
    conn.close()


def increment_queue_attempt(qid: int, next_scheduled: str):
    conn = _conn()
    conn.execute("""
        UPDATE fb_dm_queue SET attempts=attempts+1, scheduled_for=? WHERE id=?
    """, (next_scheduled, qid))
    conn.commit()
    conn.close()


def get_pending_queue_count() -> int:
    conn = _conn()
    n    = conn.execute("SELECT COUNT(*) FROM fb_dm_queue WHERE status='pending'").fetchone()[0]
    conn.close()
    return n


def get_whatsapp_leads(nationality: str = None) -> list[dict]:
    conn  = _conn()
    query = "SELECT fb_uid, profile_url, whatsapp_number, nationality, niche, sent_at FROM fb_dms WHERE whatsapp_number IS NOT NULL"
    args  = ()
    if nationality:
        query += " AND nationality=?"
        args   = (nationality,)
    query += " ORDER BY sent_at DESC"
    rows = conn.execute(query, args).fetchall()
    conn.close()
    return [{"fb_uid": r[0], "profile_url": r[1], "whatsapp_number": r[2],
             "nationality": r[3], "niche": r[4], "sent_at": r[5]} for r in rows]


def mark_replied(fb_uid: str):
    now  = _now()
    conn = _conn()
    conn.execute("UPDATE fb_dms SET replied=1, replied_at=? WHERE fb_uid=?", (now, fb_uid))
    conn.execute("UPDATE fb_followups SET status='skipped' WHERE fb_uid=? AND status='pending'", (fb_uid,))
    conn.commit()
    conn.close()


def get_due_followups() -> list[dict]:
    now  = _now()
    conn = _conn()
    rows = conn.execute("""
        SELECT f.id, f.fb_uid, f.profile_url, f.followup_number
        FROM fb_followups f
        JOIN fb_dms d ON d.id = f.dm_id
        WHERE f.status='pending' AND f.scheduled_for <= ? AND d.replied=0
        ORDER BY f.scheduled_for
    """, (now,)).fetchall()
    conn.close()
    return [{"id": r[0], "fb_uid": r[1], "profile_url": r[2], "followup_number": r[3]}
            for r in rows]


def mark_followup_sent(fid: int, message: str):
    conn = _conn()
    conn.execute("""
        UPDATE fb_followups SET status='sent', sent_at=?, message_sent=? WHERE id=? AND status='pending'
    """, (_now(), message, fid))
    conn.commit()
    conn.close()


# ── Checkpoint ────────────────────────────────────────────────────────────────

def save_checkpoint(action: str, group_id: str = "", fb_uid: str = ""):
    conn = _conn()
    conn.execute("DELETE FROM fb_checkpoint")
    conn.execute("""
        INSERT INTO fb_checkpoint (id, action, group_id, fb_uid, saved_at)
        VALUES (1, ?, ?, ?, ?)
    """, (action, group_id, fb_uid, _now()))
    conn.commit()
    conn.close()


def clear_checkpoint():
    conn = _conn()
    conn.execute("DELETE FROM fb_checkpoint")
    conn.commit()
    conn.close()


def get_checkpoint() -> dict | None:
    conn = _conn()
    row  = conn.execute("SELECT action, group_id, fb_uid FROM fb_checkpoint LIMIT 1").fetchone()
    conn.close()
    return {"action": row[0], "group_id": row[1], "fb_uid": row[2]} if row else None


# ── Stats ─────────────────────────────────────────────────────────────────────

# ── FB Comments ───────────────────────────────────────────────────────────────

def has_fb_commented_on(post_id: str) -> bool:
    conn = _conn()
    row  = conn.execute("SELECT 1 FROM fb_comments WHERE post_id=?", (str(post_id),)).fetchone()
    conn.close()
    return row is not None


def log_fb_comment(post_id: str, group_id: str, group_name: str, niche: str, comment_text: str):
    conn = _conn()
    conn.execute("""
        INSERT OR IGNORE INTO fb_comments (post_id, group_id, group_name, niche, comment_text)
        VALUES (?,?,?,?,?)
    """, (str(post_id), group_id, group_name, niche, comment_text))
    conn.commit()
    conn.close()


def get_fb_comments_today() -> int:
    today = _today()
    conn  = _conn()
    n     = conn.execute(
        "SELECT COUNT(*) FROM fb_comments WHERE commented_at LIKE ?", (f"{today}%",)
    ).fetchone()[0]
    conn.close()
    return n


def get_stats() -> dict:
    conn = _conn()
    stats = {
        "groups_joined":     conn.execute("SELECT COUNT(*) FROM fb_groups WHERE status='active'").fetchone()[0],
        "groups_pending":    conn.execute("SELECT COUNT(*) FROM fb_groups WHERE status='pending'").fetchone()[0],
        "posts_total":       conn.execute("SELECT COUNT(*) FROM fb_posts WHERE verified=1").fetchone()[0],
        "posts_today":       posts_today(),
        "dms_total":         conn.execute("SELECT COUNT(*) FROM fb_dms").fetchone()[0],
        "dms_today":         dms_today(),
        "comments_total":    conn.execute("SELECT COUNT(*) FROM fb_comments").fetchone()[0],
        "comments_today":    get_fb_comments_today(),
        "pending_followups": conn.execute("SELECT COUNT(*) FROM fb_followups WHERE status='pending'").fetchone()[0],
        "dm_queue_pending":  conn.execute("SELECT COUNT(*) FROM fb_dm_queue WHERE status='pending'").fetchone()[0],
    }
    conn.close()
    return stats
