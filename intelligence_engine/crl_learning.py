"""
Train CRL-style reply learning from the live IG/FB outreach databases.

Outputs:
  - JSON state snapshot
  - JSONL dataset for downstream/HF use
  - Mermaid causal graph
  - Reader-friendly learning report
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from .causal_engine import CausalEngine, CausalObservation

_ROOT = Path(__file__).parent.parent
_DATA_DIR = Path(os.getenv("DATA_DIR", str(_ROOT))).expanduser()
_ARTIFACT_DIR = _DATA_DIR / "intelligence_engine"
_IG_DB = _DATA_DIR / "outreach.db" if (_DATA_DIR / "outreach.db").exists() else _ROOT / "ig_outreach" / "outreach.db"
_FB_DB = _DATA_DIR / "fb_outreach.db" if (_DATA_DIR / "fb_outreach.db").exists() else _ROOT / "fb_outreach" / "fb_outreach.db"


def _ensure_artifact_dir() -> Path:
    _ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    return _ARTIFACT_DIR


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _days_since(value: str | None) -> float | None:
    dt = _parse_dt(value)
    if not dt:
        return None
    now = datetime.now(dt.tzinfo or timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 86400.0)


def _normalize_niche(raw: str | None) -> str:
    text = (raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "digital_marketing_agency": "digital_marketing_agency",
        "digital_marketing_agencies": "digital_marketing_agency",
        "dma": "digital_marketing_agency",
        "medspa": "med_spa",
        "med_spa": "med_spa",
        "coaches": "coach",
        "consultants": "consultant",
    }
    return aliases.get(text, text or "unknown")


def _message_flags(message: str, username: str = "", full_name: str = "") -> dict:
    msg = (message or "").lower()
    uname = (username or "").lower().strip()
    fname = (full_name or "").lower().strip()
    personal_tokens = [token for token in [uname, fname.split(" ")[0] if fname else ""] if token and len(token) >= 3]
    return {
        "sent_case_study": any(token in msg for token in ("case study", "example client", "for one of our clients", "results for")),
        "sent_price_early": any(token in msg for token in ("$", "price", "pricing", "/mo", "per month")),
        "personalized_message": any(token in msg for token in personal_tokens) or ("your page" in msg or "saw you in" in msg),
        "used_social_proof": any(token in msg for token in ("clients", "results", "booked calls", "case study", "human sounding")),
    }


def _load_ig_observations() -> List[CausalObservation]:
    if not _IG_DB.exists():
        return []

    conn = sqlite3.connect(_IG_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM ig_outreach").fetchall()
    comment_first = {str(r["user_id"]) for r in conn.execute("SELECT DISTINCT user_id FROM ig_comments WHERE user_id IS NOT NULL AND user_id != ''")}
    followups = defaultdict(list)
    for row in conn.execute("SELECT user_id, scheduled_for, sent_at FROM ig_followups"):
        user_id = str(row["user_id"])
        sent_at = row["sent_at"] or row["scheduled_for"]
        followups[user_id].append(sent_at)
    conn.close()

    observations: List[CausalObservation] = []
    for row in rows:
        niche = _normalize_niche(row["business_type"])
        message = row["message_sent"] or ""
        user_id = str(row["user_id"])
        sent_at = row["dm_sent_at"]
        followup_days = min((_days_since(ts) for ts in followups.get(user_id, []) if _days_since(ts) is not None), default=None)
        msg_flags = _message_flags(message, row["username"], row["full_name"])
        days_since_sent = _days_since(sent_at)
        observations.append(CausalObservation(
            lead_id=f"ig:{user_id}",
            niche=niche,
            region=(row["region"] or "unknown").lower(),
            platform="instagram",
            interventions={
                "sent_comment_first": user_id in comment_first,
                "sent_case_study": msg_flags["sent_case_study"],
                "sent_price_early": msg_flags["sent_price_early"],
                "sent_followup_2d": followup_days is not None and followup_days <= 2.5,
                "targeted_right_niche": niche not in {"unknown", ""},
                "personalized_message": msg_flags["personalized_message"],
                "used_social_proof": msg_flags["used_social_proof"],
            },
            behaviors={
                "lead_replied": bool(row["replied"]),
                "lead_asked_price": False,
                "lead_booked_call": False,
                "lead_engaged_comment": user_id in comment_first,
                "lead_sent_long_msg": False,
                "lead_ghosted": not bool(row["replied"]) and days_since_sent is not None and days_since_sent >= 5,
            },
            confounders={
                "lead_is_high_intent_niche": niche in {"hvac", "med_spa", "coach", "consultant"},
                "lead_is_decision_maker": bool(row["has_website"]) or int(row["followers"] or 0) >= 500,
                "lead_is_us_uk": (row["region"] or "").lower() in {"us", "uk", "australia", "canada"},
            },
            outcome=bool(row["replied"]),
            timestamp=_parse_dt(sent_at).timestamp() if _parse_dt(sent_at) else 0.0,
        ))
    return observations


def _load_fb_observations() -> List[CausalObservation]:
    if not _FB_DB.exists():
        return []

    conn = sqlite3.connect(_FB_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM fb_dms").fetchall()
    followups = defaultdict(list)
    for row in conn.execute("SELECT fb_uid, scheduled_for, sent_at FROM fb_followups"):
        user_id = str(row["fb_uid"])
        sent_at = row["sent_at"] or row["scheduled_for"]
        followups[user_id].append(sent_at)
    conn.close()

    observations: List[CausalObservation] = []
    for row in rows:
        niche = _normalize_niche(row["niche"])
        message = row["message_sent"] or ""
        uid = str(row["fb_uid"])
        sent_at = row["sent_at"]
        followup_days = min((_days_since(ts) for ts in followups.get(uid, []) if _days_since(ts) is not None), default=None)
        msg_flags = _message_flags(message)
        days_since_sent = _days_since(sent_at)
        warm_source = bool(row["group_source"])
        observations.append(CausalObservation(
            lead_id=f"fb:{uid}",
            niche=niche,
            region=(row["nationality"] or "unknown").lower(),
            platform="facebook",
            interventions={
                "sent_comment_first": False,
                "sent_case_study": msg_flags["sent_case_study"],
                "sent_price_early": msg_flags["sent_price_early"],
                "sent_followup_2d": followup_days is not None and followup_days <= 2.5,
                "targeted_right_niche": niche not in {"unknown", ""},
                "personalized_message": msg_flags["personalized_message"] or warm_source,
                "used_social_proof": msg_flags["used_social_proof"] or warm_source,
            },
            behaviors={
                "lead_replied": bool(row["replied"]),
                "lead_asked_price": False,
                "lead_booked_call": False,
                "lead_engaged_comment": warm_source,
                "lead_sent_long_msg": False,
                "lead_ghosted": not bool(row["replied"]) and days_since_sent is not None and days_since_sent >= 5,
            },
            confounders={
                "lead_is_high_intent_niche": niche in {"hvac", "med_spa", "coach", "consultant"},
                "lead_is_decision_maker": bool(row["whatsapp_number"]) or bool(row["group_source"]),
                "lead_is_us_uk": (row["nationality"] or "").lower() in {"us", "uk", "australia", "canada"},
            },
            outcome=bool(row["replied"]),
            timestamp=_parse_dt(sent_at).timestamp() if _parse_dt(sent_at) else 0.0,
        ))
    return observations


def build_reply_learning_engine() -> CausalEngine:
    engine = CausalEngine(effect_name="reply_outcome")
    observations = [*_load_ig_observations(), *_load_fb_observations()]
    engine.rebuild(observations)
    return engine


def export_learning_artifacts(engine: CausalEngine) -> dict:
    artifact_dir = _ensure_artifact_dir()
    state_path = artifact_dir / "reply_crl_state.json"
    dataset_path = artifact_dir / "reply_crl_dataset.jsonl"
    graph_json_path = artifact_dir / "reply_crl_graph.json"
    graph_mermaid_path = artifact_dir / "reply_crl_graph.mmd"

    engine.save_state(state_path)
    dataset_path.write_text(
        "\n".join(json.dumps(obs, default=str) for obs in [asdict(o) for o in engine._observations]) + ("\n" if engine._observations else ""),
        encoding="utf-8",
    )
    graph_json_path.write_text(json.dumps(engine.build_causal_graph(), indent=2), encoding="utf-8")
    graph_mermaid_path.write_text(engine.export_graph_mermaid(), encoding="utf-8")

    return {
        "artifact_dir": artifact_dir.name,
        "state_path": state_path.name,
        "dataset_path": dataset_path.name,
        "graph_json_path": graph_json_path.name,
        "graph_mermaid_path": graph_mermaid_path.name,
    }


def build_learning_report(export: bool = True) -> dict:
    engine = build_reply_learning_engine()
    artifacts = export_learning_artifacts(engine) if export else {}
    mechanisms = engine.mechanisms()
    positive = [m for m in mechanisms if m["strength"] > 0][:5]
    negative = [m for m in mechanisms if m["strength"] < 0][:5]

    platform_counts = Counter(obs.platform for obs in engine._observations)
    niche_counts = Counter(obs.niche for obs in engine._observations)
    reply_rates = defaultdict(lambda: {"sent": 0, "replied": 0})
    for obs in engine._observations:
        key = f"{obs.platform}:{obs.niche}"
        reply_rates[key]["sent"] += 1
        reply_rates[key]["replied"] += int(obs.outcome)

    top_segments = sorted(
        (
            {
                "segment": segment,
                "sent": stats["sent"],
                "reply_rate": round(stats["replied"] / max(1, stats["sent"]) * 100, 1),
            }
            for segment, stats in reply_rates.items()
        ),
        key=lambda row: (-row["reply_rate"], -row["sent"], row["segment"]),
    )[:10]

    total_replies = sum(int(obs.outcome) for obs in engine._observations)
    all_zero_replies = bool(engine._observations) and total_replies == 0

    recommendations = []
    if all_zero_replies:
        recommendations.append(
            "All logged IG/FB outreach samples are at 0% reply. Fix account trust, session health, and deliverability before copy optimization."
        )
    if positive:
        recommendations.append(f"Lean harder on '{positive[0]['cause']}' — strongest positive reply effect at {positive[0]['strength']:+.3f}.")
    if negative:
        recommendations.append(f"Reduce '{negative[0]['cause']}' in its current form — strongest negative reply effect at {negative[0]['strength']:+.3f}.")
    if not recommendations:
        recommendations.append("Not enough evidence yet. Keep logging replies and follow-up outcomes to sharpen the causal graph.")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "effect_target": engine.effect_name,
        "observation_count": engine.n_observations(),
        "reply_count": total_replies,
        "platform_counts": dict(platform_counts),
        "top_niches": niche_counts.most_common(10),
        "top_segments": top_segments,
        "positive_mechanisms": positive,
        "negative_mechanisms": negative,
        "graph_mermaid": engine.export_graph_mermaid(),
        "recommendations": recommendations,
        "artifacts": artifacts,
    }


if __name__ == "__main__":
    report = build_learning_report(export=True)
    print(json.dumps(report, indent=2))
