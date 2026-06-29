"""
models/jarvis.py

Pydantic schemas for the Jarvis intelligence system.
These cover conversations, memory, training pipeline, and events.
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


# ── Conversation ──────────────────────────────────────────────────────────────

class MessageIn(BaseModel):
    session_id: str
    user_id: Optional[str] = None
    content: str
    extra_data: dict[str, Any] = {}


class MessageOut(BaseModel):
    session_id: str
    response: str
    model_version: str
    latency_ms: int
    memory_retrieved: int       # how many memories were used in this response


class ConversationTurn(BaseModel):
    role: str                   # user | assistant | system
    content: str
    created_at: datetime


# ── Memory ────────────────────────────────────────────────────────────────────

class MemoryIn(BaseModel):
    user_id: str
    memory_type: str            # fact | preference | entity | relationship
    content: str
    importance: float = 0.5     # 0.0 - 1.0


class MemoryOut(BaseModel):
    id: int
    user_id: str
    memory_type: str
    content: str
    importance: float
    access_count: int
    last_accessed: datetime
    similarity: Optional[float] = None   # populated on semantic search results


class MemorySearchIn(BaseModel):
    user_id: str
    query: str
    top_k: int = 5


# ── Feedback ─────────────────────────────────────────────────────────────────

class FeedbackIn(BaseModel):
    conversation_id: int
    signal_type: str            # thumbs_up | thumbs_down | correction | explicit_rating
    corrected_text: Optional[str] = None
    score: Optional[float] = None   # 0.0 - 1.0 if explicit rating


# ── Training ──────────────────────────────────────────────────────────────────

class TrainingExampleOut(BaseModel):
    id: int
    source_type: str
    instruction: str
    response: str
    domain_tag: str
    quality_score: float
    processed: bool
    created_at: datetime


class TrainingRunOut(BaseModel):
    id: int
    run_id: str
    base_model: str
    model_version: str
    hf_repo: str
    example_count: int
    domain_tags: list[str]
    validation_loss: Optional[float]
    status: str                 # queued | running | complete | failed
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class TrainingRunIn(BaseModel):
    domain_tags: Optional[list[str]] = None    # None = train on all domains
    min_quality: float = 0.70
    max_examples: Optional[int] = None


# ── Intelligence Event (event sourcing) ───────────────────────────────────────

class IntelligenceEventIn(BaseModel):
    session_id: str
    event_type: str             # query_received | memory_retrieved | response_generated
    payload: dict[str, Any] = {}


class IntelligenceEventOut(BaseModel):
    id: int
    session_id: str
    event_type: str
    payload: dict[str, Any]
    occurred_at: datetime
