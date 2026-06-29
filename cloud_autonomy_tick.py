"""
GitHub cron tick runner for free-tier autonomous outreach mode.

This is the pragmatic fallback when there is no true always-on host:
  - GitHub Actions wakes up on a schedule
  - This script decides what is due in IST
  - It runs the missed/current outreach slot once
  - It runs reply checks and follow-ups
  - It refreshes CRL artifacts from the latest IG/FB outcome logs
  - It records state under DATA_DIR so the next cron tick can recover
"""

from __future__ import annotations

import json
import os
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from intelligence_engine.crl_learning import build_learning_report
from ig_outreach import scheduler as social_sched


_IST = timezone(timedelta(hours=5, minutes=30))
_DATA_DIR = Path(os.getenv("DATA_DIR", str(Path(__file__).parent / ".runtime" / "github-social"))).expanduser()
_STATE_FILE = _DATA_DIR / "github_social_state.json"
_REPORT_FILE = _DATA_DIR / "github_social_last_report.json"
_OPTIMIZER_FILE = _DATA_DIR / "github_social_optimizer.json"

_SLOT_FUNCS: dict[int, tuple[str, Callable[[], None]]] = {
    2: ("slot_0200", social_sched._slot_0200),
    6: ("slot_0600", social_sched._slot_0600),
    10: ("slot_1000", social_sched._slot_1000),
    14: ("slot_1400", social_sched._slot_1400),
    18: ("slot_1800", social_sched._slot_1800),
    20: ("slot_2000", social_sched._slot_2000),
    21: ("slot_2100", social_sched._slot_2100),
    22: ("slot_2200", social_sched._slot_2200),
}
_FOLLOWUP_HOURS = {11, 22}
_MISS_GRACE_HOURS = 2


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
        "crl_runs": {},
        "optimizer_runs": {},
        "notes": [],
    })
    for key in ["slots", "reply_checks", "followups", "crl_runs", "optimizer_runs"]:
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
    day["notes"] = day["notes"][-50:]


def _run_slot(hour: int, day: dict):
    slot_key, fn = _SLOT_FUNCS[hour]
    if slot_key in day["slots"]:
        return
    social_sched.log.info(f"[CLOUD-TICK] Running outreach slot {slot_key}")
    fn()
    day["slots"][slot_key] = _now_ist().isoformat()


def _run_reply_check(day: dict, hour_bucket: str):
    if hour_bucket in day["reply_checks"]:
        return
    social_sched.log.info("[CLOUD-TICK] Running hourly reply check")
    social_sched._ig("--check-replies", job=f"cloud-reply-check-{hour_bucket}")
    day["reply_checks"][hour_bucket] = _now_ist().isoformat()


def _run_followups(day: dict, hour: int):
    key = f"{hour:02d}"
    if key in day["followups"]:
        return
    social_sched.log.info(f"[CLOUD-TICK] Running follow-ups for {key}:00 IST")
    social_sched._ig("--followups", job=f"cloud-followups-{key}")
    day["followups"][key] = _now_ist().isoformat()


def _run_crl(day: dict, hour_bucket: str) -> dict:
    if hour_bucket in day["crl_runs"]:
        if _REPORT_FILE.exists():
            return json.loads(_REPORT_FILE.read_text(encoding="utf-8"))
        return {}
    report = build_learning_report(export=True)
    _REPORT_FILE.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    day["crl_runs"][hour_bucket] = _now_ist().isoformat()
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
    hour_bucket = now.strftime("%Y-%m-%dT%H")

    state = _load_state()
    day = _day_state(state, day_key)

    executed_slots: list[str] = []
    caught_up_slots: list[str] = []
    due_slots: list[str] = []

    for hour, (slot_key, _) in sorted(_SLOT_FUNCS.items()):
        delta = now.hour - hour
        if delta < 0 or delta > _MISS_GRACE_HOURS or slot_key in day["slots"]:
            continue
        due_slots.append(slot_key)
        if execute:
            _run_slot(hour, day)
            executed_slots.append(slot_key)
            if delta > 0:
                caught_up_slots.append(slot_key)

    if execute:
        _run_reply_check(day, hour_bucket)

    followups_due = now.hour in _FOLLOWUP_HOURS
    if execute and followups_due:
        _run_followups(day, now.hour)

    crl_report = _run_crl(day, hour_bucket) if execute else build_learning_report(export=False)
    optimizer_report = None
    if execute and now.hour in {12, 23}:
        optimizer_report = _run_optimizer(day, now.hour, crl_report)

    summary = {
        "ok": True,
        "execute": execute,
        "ran_at_ist": now.isoformat(),
        "data_dir": str(_DATA_DIR),
        "due_slots": due_slots,
        "executed_slots": executed_slots,
        "caught_up_slots": caught_up_slots,
        "reply_check_hour": hour_bucket,
        "followups_due": followups_due,
        "followups_ran": execute and followups_due,
        "crl_observation_count": crl_report.get("observation_count", 0),
        "crl_reply_count": crl_report.get("reply_count", 0),
        "optimizer_ran": bool(optimizer_report),
        "recommendation": (crl_report.get("recommendations") or [""])[0],
    }
    if not execute:
        return summary

    _REPORT_FILE.write_text(json.dumps({"tick_summary": summary, "crl_report": crl_report}, indent=2, default=str), encoding="utf-8")

    _append_note(day, f"Tick complete. Slots={executed_slots or ['none']} replies={summary['crl_reply_count']}")
    _prune_state(state)
    _save_state(state)
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", action="store_true", help="Show what this tick would do without executing outreach.")
    args = parser.parse_args()
    print(json.dumps(run_tick(execute=not args.plan), indent=2))
