"""
utils/embeddings.py

Handles all vector operations: generating embeddings from text,
retrieving semantically similar memories from Supabase via pgvector,
and storing new memories with their embeddings.

Uses Gemini's embedding model (models/text-embedding-004) which produces
768-dimensional vectors. If you switch to OpenAI's text-embedding-3-small
(1536 dimensions), update the vector column size in the migration SQL.

The Redis embedding cache is checked before every API call â€” this is
important for cost and latency. The same phrase asked twice never hits
the Gemini API twice within the cache TTL.
"""

import google.generativeai as genai
from database.supabase import db
from database.redis_client import get_cached_embedding, cache_embedding
from config import get_settings


async def embed_text(text: str) -> list[float]:
    """
    Produce a vector embedding for a piece of text.
    Checks the Redis cache first. On miss, calls Gemini and caches the result.
    """
    # Check cache first
    cached = await get_cached_embedding(text)
    if cached:
        return cached

    # Generate fresh embedding
    s = get_settings()
    genai.configure(api_key=s.gemini_key_for("king"))
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text,
        task_type="retrieval_query",
    )
    vector = result["embedding"]

    # Cache for 3 days
    await cache_embedding(text, vector)
    return vector


async def retrieve_memories(
    user_id: str,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    """
    Retrieve the most semantically similar memories for a user.
    Calls the match_memories Postgres function (defined in migration SQL)
    which uses pgvector's cosine distance operator (<=>).

    Returns a list of memory dicts with id, content, importance, similarity.
    Higher similarity = more relevant to the query.
    """
    client = db()
    result = client.rpc("match_memories", {
        "query_embedding": query_embedding,
        "match_user_id": user_id,
        "match_count": top_k,
    }).execute()
    return result.data or []


async def store_memory(
    user_id: str,
    memory_type: str,
    content: str,
    importance: float = 0.5,
) -> dict:
    """
    Store a new long-term memory with its embedding.
    The embedding is generated and cached in the same call.
    """
    embedding = await embed_text(content)
    client = db()
    result = client.table("jarvis.long_term_memory").insert({
        "user_id": user_id,
        "memory_type": memory_type,
        "content": content,
        "importance": importance,
        "embedding": embedding,
    }).execute()
    return result.data[0] if result.data else {}


async def bump_memory_access(memory_id: int):
    """
    Update last_accessed and increment access_count for a retrieved memory.
    Called after a memory is used in a Jarvis response â€” frequently accessed
    memories have higher importance in the decay model (to be implemented).
    """
    client = db()
    client.rpc("bump_memory_access", {"memory_id": memory_id}).execute()

