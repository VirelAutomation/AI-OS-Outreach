"""
database/redis_client.py

All Redis operations for the FORGE system in one module.
Every key follows the pattern: namespace:entity:id
Every key has a TTL — nothing lives in Redis forever.

Upstash Redis requires SSL (rediss://) — the pool is configured for that.
"""

import json
import hashlib
import redis.asyncio as redis
from typing import Optional
from functools import lru_cache
from config import get_settings


def _pool_kwargs(url: str, password: str = '') -> dict:
    """Build ConnectionPool kwargs; SSL only for Upstash/rediss URLs."""
    kwargs: dict = {'decode_responses': True}
    if password:
        kwargs['password'] = password
    if url.startswith('rediss://'):
        import ssl
        kwargs['connection_class'] = redis.SSLConnection
        kwargs['ssl_cert_reqs'] = ssl.CERT_NONE
    return kwargs


@lru_cache
def get_pool() -> redis.ConnectionPool:
    s = get_settings()
    return redis.ConnectionPool.from_url(
        s.redis_url,
        **_pool_kwargs(s.redis_url, s.redis_password),
    )


def r() -> redis.Redis:
    return redis.Redis(connection_pool=get_pool())


# ── Session working memory ─────────────────────────────────────────────────────

async def set_session(session_id: str, data: dict, ttl: int = 7200):
    """Store Jarvis session state as a hash. TTL default = 2 hours."""
    client = r()
    await client.hset(f"jarvis:session:{session_id}", mapping={
        k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
        for k, v in data.items()
    })
    await client.expire(f"jarvis:session:{session_id}", ttl)


async def get_session(session_id: str) -> Optional[dict]:
    client = r()
    raw = await client.hgetall(f"jarvis:session:{session_id}")
    if not raw:
        return None
    result = {}
    for k, v in raw.items():
        try:
            result[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            result[k] = v
    return result


async def delete_session(session_id: str):
    await r().delete(f"jarvis:session:{session_id}")


# ── Short-term message buffer ──────────────────────────────────────────────────

async def push_message(session_id: str, message: dict, ttl: int = 86400):
    """
    Push a conversation turn to the message buffer.
    Trims to last 20 messages — this is the context window for Jarvis.
    TTL default = 24 hours.
    """
    client = r()
    key = f"jarvis:messages:{session_id}"
    await client.rpush(key, json.dumps(message))
    await client.ltrim(key, -20, -1)
    await client.expire(key, ttl)


async def get_messages(session_id: str) -> list[dict]:
    raw = await r().lrange(f"jarvis:messages:{session_id}", 0, -1)
    return [json.loads(m) for m in raw]


async def clear_messages(session_id: str):
    await r().delete(f"jarvis:messages:{session_id}")


# ── Embedding cache ────────────────────────────────────────────────────────────

def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


async def cache_embedding(text: str, vector: list[float], ttl: int = 259200):
    """Cache a computed embedding for 3 days. Key is a hash of the input text."""
    await r().set(
        f"jarvis:embed:{_text_hash(text)}",
        json.dumps(vector),
        ex=ttl,
    )


async def get_cached_embedding(text: str) -> Optional[list[float]]:
    val = await r().get(f"jarvis:embed:{_text_hash(text)}")
    return json.loads(val) if val else None


# ── Inference result cache ─────────────────────────────────────────────────────

async def cache_inference(prompt_hash: str, result: str, ttl: int = 3600):
    await r().set(f"jarvis:infer:{prompt_hash}", result, ex=ttl)


async def get_cached_inference(prompt_hash: str) -> Optional[str]:
    return await r().get(f"jarvis:infer:{prompt_hash}")


# ── Training signal stream ─────────────────────────────────────────────────────

async def publish_training_signal(example_id: int, domain_tag: str, quality: float):
    """
    Publish a signal to the training stream. The segregation agent writes here
    when it produces a new training example above the quality threshold.
    The training worker reads from this stream to know when to batch and train.
    """
    await r().xadd("jarvis:stream:training", {
        "example_id": str(example_id),
        "domain_tag": domain_tag,
        "quality_score": str(quality),
    })


async def read_training_signals(count: int = 100, last_id: str = "0") -> list[dict]:
    """Read pending training signals from the stream."""
    client = r()
    entries = await client.xread({"jarvis:stream:training": last_id}, count=count)
    if not entries:
        return []
    return [{"stream_id": eid, **fields} for _, stream in entries for eid, fields in stream]


# ── Rate limiting ──────────────────────────────────────────────────────────────

async def check_rate_limit(user_id: str, limit: int = 30, window: int = 60) -> bool:
    """
    INCR + EXPIRE pattern. Returns True if the request is within the limit.
    On the first call within a window, sets the expiry. Subsequent calls
    increment the counter until it expires naturally.
    """
    client = r()
    key = f"jarvis:ratelimit:{user_id}"
    count = await client.incr(key)
    if count == 1:
        await client.expire(key, window)
    return count <= limit


# ── Training run lock ──────────────────────────────────────────────────────────

async def acquire_training_lock(run_id: str, ttl: int = 14400) -> bool:
    """
    Prevent duplicate training runs with a distributed lock.
    Returns True if the lock was acquired, False if another run is active.
    TTL = 4 hours to cover the longest expected training job.
    """
    client = r()
    result = await client.set(
        "jarvis:lock:training_run",
        run_id,
        ex=ttl,
        nx=True,    # only set if key does NOT exist
    )
    return result is True


async def release_training_lock():
    await r().delete("jarvis:lock:training_run")
