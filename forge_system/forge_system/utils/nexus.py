"""
utils/nexus.py — The Nexus inter-AEI communication bus.

Nexus is the message-passing substrate connecting the ASI Orchestrator to all
AEI agents. It uses Redis Streams for async, durable message delivery and
Supabase for persistent event logging and audit trails.

Architecture:
  - Each AEI has a dedicated Redis stream: nexus:{aei_name}:stream
  - Producers call send_to_aei() to enqueue a task for another AEI
  - Consumers call read_aei_messages() to drain their queue
  - All messages are logged to jarvis.nexus_events in Supabase for audit
  - The orchestrator broadcasts are published on nexus:broadcast channel

TTL: Nexus streams auto-trim to 500 messages per AEI to prevent unbounded growth.
"""

import json
import uuid
import logging
from datetime import datetime, timezone

from database.redis_client import r
from database.supabase import db

logger = logging.getLogger(__name__)

_STREAM_MAXLEN = 500    # trim each AEI stream to last 500 messages


async def send_to_aei(
    source: str,
    target: str,
    task_type: str,
    payload: dict,
    priority: int = 5,
) -> str:
    """
    Enqueue a task on the target AEI's Nexus stream.

    Returns the task_id so the caller can track the message.
    Also logs the event to Supabase for audit and future learning.
    """
    task_id = str(uuid.uuid4())[:12]
    message = {
        "task_id":   task_id,
        "source":    source,
        "target":    target,
        "task_type": task_type,
        "payload":   json.dumps(payload),
        "priority":  str(priority),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    client = r()
    stream_key = f"nexus:{target}:stream"
    await client.xadd(stream_key, message, maxlen=_STREAM_MAXLEN, approximate=True)

    # Also publish to the orchestrator broadcast channel for real-time monitoring
    await client.publish("nexus:broadcast", json.dumps({**message, "payload": payload}))

    # Persist to Supabase for audit (fire-and-forget — non-blocking best-effort)
    try:
        db().table("jarvis.nexus_events").insert({
            "task_id":   task_id,
            "source":    source,
            "target":    target,
            "task_type": task_type,
            "payload":   payload,
            "priority":  priority,
            "status":    "dispatched",
        }).execute()
    except Exception as e:
        logger.warning("Nexus Supabase log failed (non-critical): %s", e)

    logger.info("Nexus: %s → %s [%s] id=%s", source, target, task_type, task_id)
    return task_id


async def read_aei_messages(aei_name: str, count: int = 10) -> list[dict]:
    """
    Read pending messages from an AEI's stream.
    Returns decoded message dicts. Does not auto-acknowledge (caller must ack).
    """
    client = r()
    stream_key = f"nexus:{aei_name}:stream"

    exists = await client.exists(stream_key)
    if not exists:
        return []

    entries = await client.xrange(stream_key, count=count)
    result = []
    for stream_id, fields in entries:
        msg = dict(fields)
        msg["_stream_id"] = stream_id
        if "payload" in msg:
            try:
                msg["payload"] = json.loads(msg["payload"])
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(msg)

    return result


async def ack_message(aei_name: str, stream_id: str):
    """Delete a processed message from the stream (acknowledgement)."""
    await r().xdel(f"nexus:{aei_name}:stream", stream_id)


async def get_stream_length(aei_name: str) -> int:
    """Return the number of pending messages in an AEI's stream."""
    client = r()
    key = f"nexus:{aei_name}:stream"
    length = await client.xlen(key)
    return length or 0


async def broadcast_insight(source_aei: str, insight: str, priority: int = 5):
    """
    Broadcast a high-priority insight to all AEIs and log it.
    Used by the orchestrator to surface strategic findings.
    """
    message = {
        "type":      "insight",
        "source":    source_aei,
        "insight":   insight,
        "priority":  str(priority),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await r().publish("nexus:insights", json.dumps(message))
    logger.info("Nexus broadcast insight from %s: %s", source_aei, insight[:80])
