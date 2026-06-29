"""
GitHub cron tick runner for autonomous outreach mode.

This script is the GitHub-driven source of truth for:
  - slot execution
  - IG reply checks
  - IG follow-ups
  - Gmail draft campaigns
  - CRL rebuilds
  - optimizer dry-runs
  - Supabase runtime mirroring
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).parent / "forge_system"))

from email_scheduler import run_evening_campaign, run_morning_campaign
from forge_system.services.social_activity import sync_runtime_state
from intelligence_engine.crl_learning import build_learning_report
from ig_outreach import scheduler as social_sched

_IST = timezone(timedelta(hours=5, minutes=30))
_DATA_DIR = Path(os.getenv("DATA_DIR", str(Path(__file__).parent / ".runtime" / "github-social"))).expanduser()
_STATE_FILE = _DATA_DIR / "github_social_state.json"
_REPORT_FILE = _DATA_DIR / "github_social_last_report.json"
_OPTIMIZER_FILE = _DATA_DIR / "github_social_optimizer.json"

_SLOT_FUNCS: dict[int, tuple[str, Callable[[], list[dict]]]] = {
    2: ("slot_0200", social_sched._slot_0200),
    6: ("slot_0600", social_sched._slot_0600),
    10: ("slot_1000", social_sched._slot_1000),
    14: ("slot_1400", social_sched._slot_1400),
    18: ("slot_1800", social_sched._slot_1800),
    20: ("slot_2000", social_sched._slot_2000),
    21: ("slot_2100", social_sched._slot_2100),
    22: ("slot_2200", social_sched._slot_2200),
}
_FOLLOWUP_SLOTS = {(11, 0), (22, 30)}
_EMAIL_CAMPAIGNS = {
    "email_morning": {"hour": 10, "minute": 0, "runner": run_morning_campaign},
    "email_evening": {"hour": 21, "minute": 0, "runner": run_evening_campaign},
}
_MISS_GRACE_HOURS = 2
_EMAIL_GRACE_MINUTES = 45


def _now_ist() -> datetime:
    return datetime.now(_IST)


def _ensure_dirs():
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_state() -> dict:
    if not _STATE_FILE.exists():
        return {"days": {}}
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"days": {}}


def _save_state(state: dict):
    _ensure_dirs()
    _STATE_FILE.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def _day_state(state: dict, day_key: str) -> dict:
    days = state.setdefault("days", {})
    day = days.setdefault(day_key, {
        "slots": {},
        "reply_checks": {},
        "followups": {},
        "emails": {},
        "crl_runs": {},
        "optimizer_runs": {},
        "sync_runs": {},
        "notes": [],
    })
    for key in ["slots", "reply_checks", "followups", "emails", "crl_runs", "optimizer_runs", "sync_runs"]:
        day.setdefault(key, {})
    day.setdefault("notes", [])
    return day


def _prune_state(state: dict, keep_days: int = 7):
    keys = sorted(state.get("days", {}).keys(), reverse=True)
    for old_key in keys[keep_days:]:
        state["days"].pop(old_key, None)


def _append_note(day: dict, message: str):
    timestamp = _now_ist().isoformat()
    day["notes"].append({"at": timestamp, "message": message})
    day["notes"] = day["notes"][-100:]


def _minute_bucket(now: datetime) -> str:
    minute = 30 if now.minute >= 30 else 0
    return f"{now.strftime('%Y-%m-%dT%H')}:{minute:02d}"


def _failure_events(failures: list[dict]) -> list[dict]:
    events = []
    for failure in failures:
        events.append({
            "source_key": f"runtime_failure:{failure['job']}:{failure['at']}",
            "platform": failure.get("platform", "unknown"),
            "channel": "runtime",
            "event_type": "challenge_detected" if failure.get("challenge") else "rate_limited" if failure.get("rate_limited") else "job_failed",
            "status": "failed",
            "occurred_at": failure["at"],
            "metadata": failure,
        })
    return events


def _email_event(name: str, report: dict, at: str) -> dict:
    return {
        "source_key": f"email_campaign:{name}:{at}",
        "platform": "gmail",
        "channel": "email",
        "event_type": "draft_campaign_ran",
        "status": "sent" if report.get("ok", True) else "failed",
        "occurred_at": at,
        "metadata": report,
    }


def _run_slot(hour: int, day: dict, platform_blocks: set[str], failures: list[dict]):
    slot_key, fn = _SLOT_FUNCS[hour]
    if slot_key in day["slots"]:
        return None
    if platform_blocks:
        note = {
            "status": "skipped",
            "at": _now_ist().isoformat(),
            "blocked_platforms": sorted(platform_blocks),
        }
        day["slots"][slot_key] = note
        _append_note(day, f"Skipped {slot_key}: fail-closed for platforms {sorted(platform_blocks)}")
        return note

    social_sched.log.info(f"[CLOUD-TICK] Running outreach slot {slot_key}")
    results = fn() or []
    slot_failures = []
    for result in results:
        if result.get("challenge") or result.get("rate_limited") or not result.get("ok", False):
            failure = {
                "slot": slot_key,
                "platform": result.get("platform", "unknown"),
                "job": result.get("job", "unknown"),
                "challenge": bool(result.get("challenge")),
                "rate_limited": bool(result.get("rate_limited")),
                "stderr_excerpt": result.get("stderr_excerpt", ""),
                "at": _now_ist().isoformat(),
            }
            slot_failures.append(failure)
            failures.append(failure)
            if failure["platform"] in {"instagram", "facebook"}:
                platform_blocks.add(failure["platform"])

    status = "partial" if slot_failures else "ok"
    entry = {
        "status": status,
        "at": _now_ist().isoformat(),
        "failures": slot_failures,
    }
    day["slots"][slot_key] = entry
    return entry


def _run_reply_check(day: dict, reply_bucket: str, platform_blocks: set[str], failures: list[dict]):
    if reply_bucket in day["reply_checks"]:
        return None
    if "instagram" in platform_blocks:
        day["reply_checks"][reply_bucket] = {"status": "skipped", "at": _now_ist().isoformat()}
        return day["reply_checks"][reply_bucket]

    social_sched.log.info("[CLOUD-TICK] Running half-hour reply check")
    result = social_sched._ig("--check-replies", job=f"cloud-reply-check-{reply_bucket}")
    entry = {"status": "ok", "at": _now_ist().isoformat()}
    if result.get("challenge") or result.get("rate_limited") or not result.get("ok", False):
        entry = {
            "status": "partial",
            "at": _now_ist().isoformat(),
            "failure": {
                "platform": "instagram",
                "job": result.get("job", "reply-check"),
                "challenge": bool(result.get("challenge")),
                "rate_limited": bool(result.get("rate_limited")),
                "stderr_excerpt": result.get("stderr_excerpt", ""),
                "at": _now_ist().isoformat(),
            },
        }
        failures.append(entry["failure"])
        platform_blocks.add("instagram")
    day["reply_checks"][reply_bucket] = entry
    return entry


def _run_followups(day: dict, hour: int, minute: int, platform_blocks: set[str], failures: list[dict]):
    key = f"{hour:02d}:{minute:02d}"
    if key in day["followups"]:
        return None
    if "instagram" in platform_blocks:
        day["followups"][key] = {"status": "skipped", "at": _now_ist().isoformat()}
        return day["followups"][key]

    social_sched.log.info(f"[CLOUD-TICK] Running follow-ups for {key} IST")
    result = social_sched._ig("--followups", job=f"cloud-followups-{hour:02d}{minute:02d}")
    entry = {"status": "ok", "at": _now_ist().isoformat()}
    if result.get("challenge") or result.get("rate_limited") or not result.get("ok", False):
        entry = {
            "status": "partial",
            "at": _now_ist().isoformat(),
            "failure": {
                "platform": "instagram",
                "job": result.get("job", "followups"),
                "challenge": bool(result.get("challenge")),
                "rate_limited": bool(result.get("rate_limited")),
                "stderr_excerpt": result.get("stderr_excerpt", ""),
                "at": _now_ist().isoformat(),
            },
        }
        failures.append(entry["failure"])
        platform_blocks.add("instagram")
    day["followups"][key] = entry
    return entry


def _run_email_campaigns(day: dict, now: datetime, extra_events: list[dict]) -> list[str]:
    ran = []
    for key, config in _EMAIL_CAMPAIGNS.items():
        state_key = f"{config['hour']:02d}:{config['minute']:02d}"
        if state_key in day["emails"]:
            continue
        scheduled = now.replace(hour=config["hour"], minute=config["minute"], second=0, microsecond=0)
        delta_minutes = (now - scheduled).total_seconds() / 60
        if delta_minutes < 0 or delta_minutes > _EMAIL_GRACE_MINUTES:
            continue
        report = asyncio.run(config["runner"](draft_only=True))
        report = report or {"ok": True, "campaign": key}
        day["emails"][state_key] = {
            "status": "ok" if report.get("ok", True) else "partial",
            "at": _now_ist().isoformat(),
            "campaign": key,
            "report": report,
        }
        extra_events.append(_email_event(key, report, _now_ist().isoformat()))
        ran.append(key)
    return ran


def _run_crl(day: dict, tick_bucket: str) -> dict:
    if tick_bucket in day["crl_runs"]:
        if _REPORT_FILE.exists():
            try:
                return json.loads(_REPORT_FILE.read_text(encoding="utf-8")).get("crl_report", {})
            except Exception:
                return {}
        return {}
    report = build_learning_report(export=True)
    day["crl_runs"][tick_bucket] = _now_ist().isoformat()
    return report


def _run_optimizer(day: dict, hour: int, report: dict) -> dict | None:
    key = f"{hour:02d}"
    if key in day["optimizer_runs"]:
        return None
    if report.get("reply_count", 0) > 0 or report.get("observation_count", 0) < 10:
        return None
    try:
        import optimizer_agent

        social_sched.log.info("[CLOUD-TICK] Running optimizer dry-run because replies are still at 0")
        result = optimizer_agent.run(channel="all", dry_run=True, focus="all")
        _OPTIMIZER_FILE.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        day["optimizer_runs"][key] = _now_ist().isoformat()
        return result
    except Exception as exc:
        _append_note(day, f"Optimizer failed: {exc}")
        return {"error": str(exc), "trace": traceback.format_exc()[-500:]}


def run_tick(execute: bool = True) -> dict:
    _ensure_dirs()
    now = _now_ist()
    day_key = now.strftime("%Y-%m-%d")
    tick_bucket = _minute_bucket(now)

    state = _load_state()
    day = _day_state(state, day_key)

    due_slots: list[str] = []
    executed_slots: list[str] = []
    caught_up_slots: list[str] = []
    email_campaigns_ran: list[str] = []
    partial_failures: list[dict] = []
    platform_blocks: set[str] = set()
    extra_events: list[dict] = []

    for hour, (slot_key, _) in sorted(_SLOT_FUNCS.items()):
        delta = now.hour - hour
        if delta < 0 or delta > _MISS_GRACE_HOURS or slot_key in day["slots"]:
            continue
        due_slots.append(slot_key)
        if execute:
            slot_result = _run_slot(hour, day, platform_blocks, partial_failures)
            if slot_result and slot_result.get("status") in {"ok", "partial"}:
                executed_slots.append(slot_key)
                if delta > 0:
                    caught_up_slots.append(slot_key)

    reply_check_bucket = f"{day_key}T{tick_bucket.split('T')[1]}"
    if execute:
        _run_reply_check(day, reply_check_bucket, platform_blocks, partial_failures)

    followups_due = (now.hour, 30 if now.minute >= 30 else 0) in _FOLLOWUP_SLOTS
    if execute and followups_due:
        _run_followups(day, now.hour, 30 if now.minute >= 30 else 0, platform_blocks, partial_failures)

    if execute:
        email_campaigns_ran = _run_email_campaigns(day, now, extra_events)

    crl_report = _run_crl(day, tick_bucket) if execute else build_learning_report(export=False)
    optimizer_report = None
    if execute and now.hour in {12, 23}:
        optimizer_report = _run_optimizer(day, now.hour, crl_report)

    summary = {
        "ok": True,
        "execute": execute,
        "ran_at_ist": now.isoformat(),
        "tick_bucket": tick_bucket,
        "data_dir": str(_DATA_DIR),
        "due_slots": due_slots,
        "executed_slots": executed_slots,
        "caught_up_slots": caught_up_slots,
        "reply_check_bucket": reply_check_bucket,
        "followups_due": followups_due,
        "followups_ran": execute and followups_due,
        "email_campaigns_ran": email_campaigns_ran,
        "blocked_platforms": sorted(platform_blocks),
        "partial_failures": partial_failures,
        "crl_observation_count": crl_report.get("observation_count", 0),
        "crl_reply_count": crl_report.get("reply_count", 0),
        "optimizer_ran": bool(optimizer_report),
        "recommendation": (crl_report.get("recommendations") or [""])[0],
    }
    if not execute:
        return summary

    sync_report = sync_runtime_state(
        data_dir=_DATA_DIR,
        tick_summary=summary,
        extra_events=extra_events + _failure_events(partial_failures),
    )
    summary["social_sync"] = sync_report
    day["sync_runs"][tick_bucket] = sync_report

    _REPORT_FILE.write_text(
        json.dumps(
            {
                "tick_summary": summary,
                "crl_report": crl_report,
                "email_events": extra_events,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    _append_note(
        day,
        f"Tick complete. Slots={executed_slots or ['none']} replies={summary['crl_reply_count']} failures={len(partial_failures)}",
    )
    _prune_state(state)
    _save_state(state)
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", action="store_true", help="Show what this tick would do without executing outreach.")
    args = parser.parse_args()
    print(json.dumps(run_tick(execute=not args.plan), indent=2))
