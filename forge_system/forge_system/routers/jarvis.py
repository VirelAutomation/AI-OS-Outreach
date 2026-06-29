"""
routers/jarvis.py — Jarvis conversation, memory, feedback, and training endpoints.
"""

import json
import asyncio
import logging
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from database.supabase import db
from agents.jarvis_agent import respond
from utils.embeddings import store_memory, retrieve_memories, embed_text
from services.segregation_agent import run_segregation_cycle
from models.jarvis import MessageIn, FeedbackIn, MemoryIn, MemorySearchIn, TrainingRunIn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jarvis", tags=["jarvis"])


# ── Conversation ───────────────────────────────────────────────────────────────

@router.post("/chat/", summary="Send a message to Jarvis, get a response")
async def chat(message: MessageIn):
    return await respond(message)


@router.websocket("/chat/ws/{session_id}")
async def chat_ws(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time streaming conversation.
    The frontend connects here for the live chat UI. Each text frame
    received is treated as a user message. Jarvis responds in one
    frame (streaming token-by-token is a future enhancement).

    ── FLAG FOR JF ──
    The frontend needs a WebSocket chat component connected to this endpoint.
    See CODEX_PROMPT.md Frontend Requirements section for full spec.
    """
    await websocket.accept()
    try:
        while True:
            user_input = await websocket.receive_text()
            msg = MessageIn(session_id=session_id, content=user_input)
            result = await respond(msg)
            await websocket.send_text(result.response)
    except WebSocketDisconnect:
        pass


# ── Memory ─────────────────────────────────────────────────────────────────────

@router.post("/memory/", summary="Store a new long-term memory for a user")
async def add_memory(memory: MemoryIn):
    result = await store_memory(
        user_id=memory.user_id,
        memory_type=memory.memory_type,
        content=memory.content,
        importance=memory.importance,
    )
    return result


@router.post("/memory/search/", summary="Semantic search over a user's memories")
async def search_memory(search: MemorySearchIn):
    embedding = await embed_text(search.query)
    results = await retrieve_memories(search.user_id, embedding, search.top_k)
    return {"query": search.query, "results": results}


@router.get("/memory/{user_id}/", summary="List all memories for a user")
def list_memories(user_id: str, memory_type: str = None, limit: int = 50):
    client = db()
    q = client.table("jarvis.long_term_memory").select(
        "id, user_id, memory_type, content, importance, access_count, last_accessed, created_at"
    ).eq("user_id", user_id)
    if memory_type:
        q = q.eq("memory_type", memory_type)
    return q.order("importance", desc=True).limit(limit).execute().data


@router.delete("/memory/{memory_id}/", summary="Delete a specific memory")
def delete_memory(memory_id: int):
    client = db()
    client.table("jarvis.long_term_memory").delete().eq("id", memory_id).execute()
    return {"deleted": memory_id}


# ── Feedback ───────────────────────────────────────────────────────────────────

@router.post("/feedback/", summary="Submit feedback on a Jarvis response")
def submit_feedback(feedback: FeedbackIn):
    client = db()
    res = client.table("jarvis.feedback").insert(feedback.model_dump()).execute()
    return res.data[0]


# ── Training pipeline ──────────────────────────────────────────────────────────

@router.post("/training/segregate/", summary="Run the segregation agent cycle manually")
async def run_segregation():
    """
    Manually trigger a segregation cycle. In production this runs on a
    schedule via GitHub Actions or a cron job. Useful for testing and
    for triggering training after a heavy conversation session.
    """
    summary = await run_segregation_cycle(limit=500)
    return summary


@router.get("/training/examples/", summary="List curated training examples")
def get_training_examples(processed: bool = False, domain_tag: str = None, limit: int = 100):
    client = db()
    q = (client.table("jarvis.training_examples").select("*")
         .eq("processed", processed))
    if domain_tag:
        q = q.eq("domain_tag", domain_tag)
    return q.order("quality_score", desc=True).limit(limit).execute().data


@router.get("/training/runs/", summary="List training run history")
def get_training_runs():
    return (db().table("jarvis.training_runs").select("*")
            .order("created_at", desc=True).limit(20).execute().data)


@router.get("/training/status/", summary="Stream live training run status via Server-Sent Events")
async def training_status_sse():
    """
    SSE endpoint: streams training status updates every 5 seconds for up to 10 minutes.
    The frontend's training pipeline page connects here to get live status without polling.

    Event format: data: {json}\n\n
    Reconnect: browser EventSource auto-reconnects on disconnect.
    """
    async def event_generator():
        max_iterations = 120   # 120 × 5s = 10 minutes
        for _ in range(max_iterations):
            try:
                runs = (
                    db()
                    .table("jarvis.training_runs")
                    .select("*")
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                    .data
                )
                payload = runs[0] if runs else {"status": "no_runs"}
                yield f"data: {json.dumps(payload)}\n\n"

                # If training finished or errored, close the stream
                if payload.get("status") in ("completed", "failed", "no_runs"):
                    yield "data: {\"status\": \"stream_closed\"}\n\n"
                    break

            except Exception as e:
                logger.error("SSE training_status error: %s", e)
                yield f"data: {{\"status\": \"error\", \"detail\": \"{str(e)[:80]}\"}}\n\n"
                break

            await asyncio.sleep(5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",    # disable Nginx buffering for SSE
        },
    )
