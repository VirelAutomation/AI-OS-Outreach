"""Social outreach activity sync and dashboard helpers."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

from database.supabase import db

log = logging.getLogger(__name__)

_DEFAULT_DATA_DIR = Path(os.getenv("DATA_DIR", "")).expanduser() if os.getenv("DATA_DIR") else None


def _resolve_data_dir(data_dir: str | Path | None = None) -> Path:
    if data_dir:
        return Path(data_dir).expanduser()
    if _DEFAULT_DATA_DIR:
        return _DEFAULT_DATA_DIR
    return Path(__file__).resolve().parents[3]


def _sqlite_rows(db_path: Path, query: str, args: tuple = ()) -> list[sqlite3.Row]:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(query, args).fetchall()
    finally:
        conn.close()


def collect_local_touchpoints(data_dir: str | Path | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Read recent social activity straight from local SQLite/runtime state."""
    runtime_dir = _resolve_data_dir(data_dir)
    if data_dir or _DEFAULT_DATA_DIR:
        ig_db = runtime_dir / "outreach.db"
        fb_db = runtime_dir / "fb_outreach.db"
    else:
        ig_db = runtime_dir / "ig_outreach" / "outreach.db"
        fb_db = runtime_dir / "fb_outreach" / "fb_outreach.db"
    rows: list[dict[str, Any]] = []

    for row in _sqlite_rows(
        ig_db,
        """
        SELECT user_id, username, full_name, business_type, region, followers, has_website, dm_sent_at
        FROM ig_outreach
        ORDER BY dm_sent_at DESC
        LIMIT ?
        """,
        (limit,),
    ):
        rows.append({
            "source_key": f"ig_dm:{row['user_id']}",
            "platform": "instagram",
            "channel": "dm",
            "event_type": "dm_sent",
            "status": "sent",
            "occurred_at": row["dm_sent_at"],
            "metadata": {
                "username": row["username"],
                "full_name": row["full_name"],
                "business_type": row["business_type"],
                "region": row["region"],
                "followers": row["followers"],
                "has_website": bool(row["has_website"]),
            },
        })

    for row in _sqlite_rows(
        ig_db,
        """
        SELECT id, user_id, username, followup_number, scheduled_for, sent_at, status
        FROM ig_followups
        ORDER BY COALESCE(sent_at, scheduled_for) DESC
        LIMIT ?
        """,
        (limit,),
    ):
        rows.append({
            "source_key": f"ig_followup:{row['id']}",
            "platform": "instagram",
            "channel": "followup",
            "event_type": "followup_sent" if row["sent_at"] else "followup_scheduled",
            "status": row["status"],
            "scheduled_for": row["scheduled_for"],
            "occurred_at": row["sent_at"] or row["scheduled_for"],
            "metadata": {
                "user_id": row["user_id"],
                "username": row["username"],
                "followup_number": row["followup_number"],
            },
        })

    for row in _sqlite_rows(
        ig_db,
        """
        SELECT media_id, username, hashtag, comment_text, commented_at
        FROM ig_comments
        ORDER BY commented_at DESC
        LIMIT ?
        """,
        (limit,),
    ):
        rows.append({
            "source_key": f"ig_comment:{row['media_id']}",
            "platform": "instagram",
            "channel": "comment",
            "event_type": "comment_posted",
            "status": "sent",
            "occurred_at": row["commented_at"],
            "metadata": {
                "username": row["username"],
                "hashtag": row["hashtag"],
                "comment_text": row["comment_text"],
            },
        })

    for row in _sqlite_rows(
        fb_db,
        """
        SELECT fb_uid, profile_url, group_source, niche, sent_at, whatsapp_number, nationality, friend_request_sent
        FROM fb_dms
        ORDER BY sent_at DESC
        LIMIT ?
        """,
        (limit,),
    ):
        rows.append({
            "source_key": f"fb_dm:{row['fb_uid']}",
            "platform": "facebook",
            "channel": "dm",
            "event_type": "dm_sent",
            "status": "sent",
            "occurred_at": row["sent_at"],
            "metadata": {
                "profile_url": row["profile_url"],
                "group_source": row["group_source"],
                "niche": row["niche"],
                "whatsapp_number": row["whatsapp_number"],
                "nationality": row["nationality"],
                "friend_request_sent": bool(row["friend_request_sent"]),
            },
        })

    for row in _sqlite_rows(
        fb_db,
        """
        SELECT id, fb_uid, profile_url, followup_number, scheduled_for, sent_at, status
        FROM fb_followups
        ORDER BY COALESCE(sent_at, scheduled_for) DESC
        LIMIT ?
        """,
        (limit,),
    ):
        rows.append({
            "source_key": f"fb_followup:{row['id']}",
            "platform": "facebook",
            "channel": "followup",
            "event_type": "followup_sent" if row["sent_at"] else "followup_scheduled",
            "status": row["status"],
            "scheduled_for": row["scheduled_for"],
            "occurred_at": row["sent_at"] or row["scheduled_for"],
            "metadata": {
                "fb_uid": row["fb_uid"],
                "profile_url": row["profile_url"],
                "followup_number": row["followup_number"],
            },
        })

    for row in _sqlite_rows(
        fb_db,
        """
        SELECT id, group_id, group_name, niche, posted_at
        FROM fb_posts
        WHERE verified = 1
        ORDER BY posted_at DESC
        LIMIT ?
        """,
        (limit,),
    ):
        rows.append({
            "source_key": f"fb_post:{row['id']}",
            "platform": "facebook",
            "channel": "group_post",
            "event_type": "post_published",
            "status": "sent",
            "occurred_at": row["posted_at"],
            "metadata": {
                "group_id": row["group_id"],
                "group_name": row["group_name"],
                "niche": row["niche"],
            },
        })

    for row in _sqlite_rows(
        fb_db,
        """
        SELECT post_id, group_id, group_name, niche, comment_text, commented_at
        FROM fb_comments
        ORDER BY commented_at DESC
        LIMIT ?
        """,
        (limit,),
    ):
        rows.append({
            "source_key": f"fb_comment:{row['post_id']}",
            "platform": "facebook",
            "channel": "comment",
            "event_type": "comment_posted",
            "status": "sent",
            "occurred_at": row["commented_at"],
            "metadata": {
                "group_id": row["group_id"],
                "group_name": row["group_name"],
                "niche": row["niche"],
                "comment_text": row["comment_text"],
            },
        })

    rows.sort(key=lambda item: item.get("occurred_at") or "", reverse=True)
    return rows[:limit]


def _upsert_touchpoints(client, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    inserted = 0
    table = client.table("outreach.social_touchpoints")
    for row in rows:
        payload = {
            "source_key": row["source_key"],
            "platform": row["platform"],
            "channel": row["channel"],
            "event_type": row["event_type"],
            "status": row.get("status", "sent"),
            "occurred_at": row.get("occurred_at"),
            "scheduled_for": row.get("scheduled_for"),
            "account_key": row.get("account_key", ""),
            "actor_key": row.get("actor_key", ""),
            "external_id": row.get("external_id", ""),
            "metadata": row.get("metadata", {}),
        }
        table.upsert(payload, on_conflict="source_key").execute()
        inserted += 1
    return inserted


def _upsert_runtime_snapshot(client, snapshot: dict[str, Any]) -> None:
    client.table("outreach.social_runtime_snapshots").upsert({
        "source_key": snapshot["source_key"],
        "runtime": snapshot.get("runtime", "github-cron"),
        "status": snapshot.get("status", "ok"),
        "ran_at": snapshot.get("ran_at"),
        "due_slots": snapshot.get("due_slots", []),
        "executed_slots": snapshot.get("executed_slots", []),
        "partial_failures": snapshot.get("partial_failures", []),
        "metadata": snapshot.get("metadata", {}),
    }, on_conflict="source_key").execute()


def sync_runtime_state(
    data_dir: str | Path | None = None,
    tick_summary: dict[str, Any] | None = None,
    extra_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Mirror local runtime state into Supabase for dashboard visibility."""
    rows = collect_local_touchpoints(data_dir=data_dir, limit=250)
    if extra_events:
        rows.extend(extra_events)

    result = {
        "ok": False,
        "source": "local_runtime",
        "activity_count": len(rows),
        "mirrored_events": 0,
        "snapshot_created": False,
        "sync_error": None,
    }

    try:
        client = db()
    except Exception as exc:
        result["sync_error"] = f"db_unavailable: {exc}"
        return result

    try:
        inserted = _upsert_touchpoints(client, rows)
        if tick_summary:
            tick_key = tick_summary.get("tick_bucket") or tick_summary.get("reply_check_bucket") or tick_summary.get("ran_at_ist", "")
            _upsert_runtime_snapshot(client, {
                "source_key": f"github-cron:{tick_key}",
                "runtime": "github-cron",
                "status": "partial" if tick_summary.get("partial_failures") else "ok",
                "ran_at": tick_summary.get("ran_at_ist"),
                "due_slots": tick_summary.get("due_slots", []),
                "executed_slots": tick_summary.get("executed_slots", []),
                "partial_failures": tick_summary.get("partial_failures", []),
                "metadata": tick_summary,
            })
            result["snapshot_created"] = True
        result["ok"] = True
        result["source"] = "supabase_live"
        result["mirrored_events"] = inserted
        return result
    except Exception as exc:
        log.warning("Social runtime sync failed: %s", exc)
        result["sync_error"] = str(exc)
        return result


def list_recent_social_activity(limit: int = 20) -> dict[str, Any]:
    """Prefer Supabase, fall back to local runtime state."""
    try:
        client = db()
        touchpoints = (
            client.table("outreach.social_touchpoints")
            .select("source_key,platform,channel,event_type,status,occurred_at,scheduled_for,metadata")
            .order("occurred_at", desc=True)
            .limit(limit)
            .execute()
        )
        snapshots = (
            client.table("outreach.social_runtime_snapshots")
            .select("source_key,runtime,status,ran_at,due_slots,executed_slots,partial_failures,metadata")
            .order("ran_at", desc=True)
            .limit(1)
            .execute()
        )
        activity = touchpoints.data or []
        snapshot = (snapshots.data or [None])[0]
        return {
            "source": "supabase_live",
            "activity": activity,
            "runtime_snapshot": snapshot,
            "summary": summarize_touchpoints(activity),
        }
    except Exception:
        activity = collect_local_touchpoints(limit=limit)
        return {
            "source": "local_runtime",
            "activity": activity,
            "runtime_snapshot": None,
            "summary": summarize_touchpoints(activity),
        }


def summarize_touchpoints(activity: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "total": len(activity),
        "by_platform": {},
        "by_channel": {},
        "failures": 0,
    }
    for item in activity:
        platform = item.get("platform", "unknown")
        channel = item.get("channel", "unknown")
        status = item.get("status", "unknown")
        summary["by_platform"][platform] = summary["by_platform"].get(platform, 0) + 1
        summary["by_channel"][channel] = summary["by_channel"].get(channel, 0) + 1
        if status not in {"sent", "pending", "skipped"}:
            summary["failures"] += 1
    return summary


def to_jsonable(value: Any) -> str:
    return json.dumps(value, default=str)
