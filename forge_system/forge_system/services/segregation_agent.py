"""
services/segregation_agent.py

The segregation agent runs on a schedule (or triggered manually) and curates
raw conversation data into training examples that are worth fine-tuning Jarvis on.

The core insight is that not all interactions are equal training signal.
A conversation where Jace corrected Jarvis, or where Jarvis received
a thumbs-down, is gold — it contains both the wrong and the right response.
A conversation that was just an empty session is noise.

The scoring function below implements a simple multi-factor quality gate.
Conversations that pass the threshold get formatted as instruction-response
pairs and written to jarvis.training_examples. A Redis signal is published
so the training worker knows new data is available.
"""

import hashlib
from datetime import datetime, timezone
from database.supabase import db
from database.redis_client import publish_training_signal
from config import get_settings


def _quality_score(conversation_rows: list[dict], feedback: list[dict]) -> float:
    """
    Score a conversation session on 0.0–1.0 scale.

    Factors considered:
    - Has at least one assistant turn with substantive content (> 50 chars)
    - Was not a pure one-liner exchange
    - Has a positive feedback signal (thumbs_up or explicit rating >= 0.7)
    - Has a correction signal (highest value — correction = ground truth)
    - No negative-only signals with no correction attached

    Returns a float between 0.0 and 1.0.
    """
    if not conversation_rows:
        return 0.0

    assistant_turns = [r for r in conversation_rows if r["role"] == "assistant"]
    if not assistant_turns:
        return 0.0

    # Base score from content quality
    avg_len = sum(len(t["content"]) for t in assistant_turns) / len(assistant_turns)
    base = min(avg_len / 500, 0.5)  # caps at 0.5 from length alone

    # Feedback adjustments
    feedback_boost = 0.0
    for f in feedback:
        if f["signal_type"] == "correction" and f.get("corrected_text"):
            feedback_boost = max(feedback_boost, 0.5)   # correction is the most valuable signal
        elif f["signal_type"] == "thumbs_up":
            feedback_boost = max(feedback_boost, 0.3)
        elif f["signal_type"] == "explicit_rating" and f.get("score", 0) >= 0.7:
            feedback_boost = max(feedback_boost, 0.3)
        elif f["signal_type"] == "thumbs_down" and not feedback_boost:
            feedback_boost = -0.2   # negative with no correction is low value

    return min(max(base + feedback_boost, 0.0), 1.0)


def _format_training_example(
    session_rows: list[dict],
    feedback: list[dict],
    system_prompt: str = "",
) -> list[dict]:
    """
    Convert a session's conversation rows into one or more training examples.

    If a correction exists, the corrected text replaces the original assistant
    response — this is the most important transformation. The model learns
    what Jarvis should have said, not what it did say.

    Returns a list of dicts ready for insertion into jarvis.training_examples.
    """
    examples = []
    correction_map = {f["conversation_id"]: f["corrected_text"] for f in feedback
                      if f["signal_type"] == "correction" and f.get("corrected_text")}

    user_turns = [r for r in session_rows if r["role"] == "user"]
    assistant_turns = [r for r in session_rows if r["role"] == "assistant"]

    # Pair user and assistant turns in order
    for u, a in zip(user_turns, assistant_turns):
        response = correction_map.get(a["id"], a["content"])
        examples.append({
            "instruction": u["content"],
            "response": response,
            "system_prompt": system_prompt,
        })

    return examples


async def run_segregation_cycle(limit: int = 200) -> dict:
    """
    Main entry point. Pull unprocessed conversations, score them,
    write passing examples to training_examples, publish Redis signals.

    Returns a summary dict with counts for monitoring.
    """
    s = get_settings()
    client = db()
    threshold = s.training_quality_threshold

    # Fetch recent conversations not yet flagged as processed
    # Grouped by session_id so we evaluate whole conversations, not individual turns
    sessions_res = (
        client.table("jarvis.conversations")
        .select("session_id")
        .eq("processed_for_training", False)
        .limit(limit)
        .execute()
    )

    if not sessions_res.data:
        return {"processed": 0, "passed": 0, "failed": 0}

    session_ids = list({r["session_id"] for r in sessions_res.data})

    processed = passed = failed = 0

    for session_id in session_ids:
        # Fetch all turns for this session
        turns_res = (
            client.table("jarvis.conversations")
            .select("*")
            .eq("session_id", session_id)
            .order("created_at")
            .execute()
        )
        turns = turns_res.data or []

        # Fetch any feedback attached to turns in this session
        turn_ids = [t["id"] for t in turns]
        feedback_res = (
            client.table("jarvis.feedback")
            .select("*")
            .in_("conversation_id", turn_ids)
            .execute()
        )
        feedback = feedback_res.data or []

        score = _quality_score(turns, feedback)
        processed += 1

        if score >= threshold:
            examples = _format_training_example(turns, feedback)
            for ex in examples:
                insert_res = (
                    client.table("jarvis.training_examples")
                    .insert({
                        "source_type": "conversation",
                        "instruction": ex["instruction"],
                        "response": ex["response"],
                        "system_prompt": ex.get("system_prompt", ""),
                        "quality_score": score,
                        "domain_tag": "general",
                        "processed": False,
                    })
                    .execute()
                )
                if insert_res.data:
                    example_id = insert_res.data[0]["id"]
                    await publish_training_signal(example_id, "general", score)
            passed += 1
        else:
            failed += 1

        # Mark these conversation rows as processed so the next cycle skips them
        client.table("jarvis.conversations").update(
            {"processed_for_training": True}
        ).eq("session_id", session_id).execute()

    return {"processed": processed, "passed": passed, "failed": failed, "threshold": threshold}
