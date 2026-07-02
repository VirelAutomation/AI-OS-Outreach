"""
Virel Automation unified IG + FB outreach scheduler.

Schedule (IST / Asia-Kolkata):
  06:00 -> IG + FB comments: India DMA
  10:00 -> India IG DMs + India/AUS comments + AUS FB posts
  14:00 -> UK IG DMs + UK FB DMs/comments/posts
  18:00 -> India comments + India FB posts
  20:00 -> US HVAC + MedSpa IG DMs
  21:00 -> US Coach + Consultant IG DMs + IG comments + US FB DMs
  22:00 -> US comments + US FB posts
  02:00 -> US late comments
  11:00 + 22:30 -> IG follow-ups
  Every :30 -> IG reply check
  Every 5 min -> heartbeat
"""

import argparse
import logging
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SCHED] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("virel.sched")

_ROOT = Path(__file__).parent.parent
_IG = Path(__file__).parent / "main.py"
_FB = _ROOT / "fb_outreach" / "main.py"
_IST = timezone(timedelta(hours=5, minutes=30))
_COMMENT = "25"
_COMMENT_INDIA = "15"
_COMMENT_PM = "25"

_consecutive_failures = 0
_MAX_FAILURES = 5

_FAIL_CLOSED_MARKERS = (
    "challenge detected",
    "checkpoint",
    "temporarily blocked",
    "temporarily restricted",
    "security check",
    "login_required",
)
_RATE_LIMIT_MARKERS = (
    "rate limit",
    "rate limited",
    "too many requests",
    "we limit how often",
)


def _run(script: Path, args: list[str], job_name: str = "", platform: str = "unknown") -> dict:
    global _consecutive_failures

    job = job_name or f"{script.name} {' '.join(args)}"
    summary = {
        "platform": platform,
        "script": script.name,
        "job": job,
        "ok": False,
        "challenge": False,
        "rate_limited": False,
        "timed_out": False,
        "exit_code": None,
        "stdout_excerpt": "",
        "stderr_excerpt": "",
    }

    try:
        log.info(f"[JOB] {job}")
        result = subprocess.run(
            [sys.executable, str(script)] + args,
            cwd=str(_ROOT),
            capture_output=True,
            text=True,
            timeout=3600,
        )
        summary["exit_code"] = result.returncode
        summary["stdout_excerpt"] = "\n".join(result.stdout.strip().splitlines()[-20:]) if result.stdout else ""
        summary["stderr_excerpt"] = result.stderr[:500] if result.stderr else ""
        if result.stdout:
            for line in result.stdout.strip().splitlines()[-20:]:
                log.info(f"  | {line}")

        signal_text = "\n".join(filter(None, [result.stdout, result.stderr])).lower()
        summary["challenge"] = any(marker in signal_text for marker in _FAIL_CLOSED_MARKERS)
        summary["rate_limited"] = any(marker in signal_text for marker in _RATE_LIMIT_MARKERS)
        summary["ok"] = (
            result.returncode == 0
            and not summary["challenge"]
            and not summary["rate_limited"]
        )

        if summary["ok"]:
            _consecutive_failures = 0
            log.info(f"[JOB] {job} OK")
        else:
            _consecutive_failures += 1
            log.error(f"[JOB FAIL] {job} (exit {result.returncode}, failure #{_consecutive_failures})")
            if result.stderr:
                log.error(f"  stderr: {result.stderr[:500]}")
            if summary["challenge"]:
                log.error(f"[FAIL-CLOSED] {platform} challenge/checkpoint detected; stop retrying this job in this run.")
            if summary["rate_limited"]:
                log.error(f"[FAIL-CLOSED] {platform} rate-limit detected; stop retrying this job in this run.")
            if _consecutive_failures >= _MAX_FAILURES:
                log.critical(f"[SCHED] {_MAX_FAILURES} consecutive failures - check system")
                _consecutive_failures = 0
    except subprocess.TimeoutExpired:
        summary["timed_out"] = True
        summary["stderr_excerpt"] = "Timed out after 1 hour"
        log.error(f"[JOB] {job} timed out after 1 hour")
    except Exception as exc:
        summary["stderr_excerpt"] = str(exc)
        log.error(f"[JOB] {job} crashed: {exc}")

    return summary


def _ig(*args, job=""):
    return _run(_IG, list(args), job, platform="instagram")


def _fb(*args, job=""):
    return _run(_FB, list(args), job, platform="facebook")


def _ig_market_region(region: str) -> str:
    """Map scheduler market labels onto the IG engine's supported region set."""
    if region in {"uk", "australia"}:
        return "us"
    return region


def _heartbeat():
    log.info(f"[HEARTBEAT] Alive - {datetime.now(_IST).strftime('%H:%M IST')}")


def _parallel(*callables):
    """Run callables simultaneously in a thread pool and collect their results."""
    results = []
    with ThreadPoolExecutor(max_workers=len(callables)) as pool:
        futures = [pool.submit(fn) for fn in callables]
        for future in as_completed(futures):
            try:
                value = future.result()
                if value is None:
                    continue
                if isinstance(value, list):
                    results.extend(value)
                else:
                    results.append(value)
            except Exception as exc:
                log.error(f"[PARALLEL] Job raised: {exc}")
                results.append({
                    "platform": "unknown",
                    "script": "parallel",
                    "job": "parallel-callable",
                    "ok": False,
                    "challenge": False,
                    "rate_limited": False,
                    "timed_out": False,
                    "exit_code": None,
                    "stdout_excerpt": "",
                    "stderr_excerpt": str(exc),
                })
    return results


def _ig_comments(niche: str, region: str, label: str, limit: str = _COMMENT):
    return _ig(
        "--comments",
        "--niche",
        niche,
        "--region",
        _ig_market_region(region),
        "--comment-limit",
        limit,
        job=f"IG comments {label}",
    )


def _fb_comments(niche: str, region: str, label: str):
    return _fb("--comments", "--niche", niche, "--region", region, "--comment-limit", _COMMENT, job=f"FB comments {label}")


def _fb_posts(region: str, niche: str, label: str):
    return _fb("--posts", "--niche", niche, "--region", region, job=f"FB posts {label}")


def _slot_0600():
    return _parallel(
        lambda: _ig_comments("digital_marketing_agency", "india", "India DMA 6am"),
        lambda: _fb_comments("digital_marketing_agency", "india", "India DMA 6am"),
    )


def _slot_1000():
    results = []
    results.append(_ig("--region", "india", "--niche", "digital_marketing_agency", "--limit", "10", job="India DMA DMs"))
    results.extend(_parallel(
        lambda: _ig_comments("digital_marketing_agency", "india", "India DMA 10am", limit=_COMMENT_INDIA),
        lambda: _fb_comments("digital_marketing_agency", "india", "India DMA 10am"),
    ))
    results.extend(_parallel(
        lambda: _ig_comments("hvac", "australia", "AUS HVAC 10am"),
        lambda: _fb_comments("hvac", "australia", "AUS HVAC 10am"),
    ))
    results.extend(_parallel(
        lambda: _ig_comments("med_spa", "australia", "AUS MedSpa 10am"),
        lambda: _fb_comments("med_spa", "australia", "AUS MedSpa 10am"),
    ))
    results.append(_fb_posts("australia", "hvac", "AUS HVAC"))
    results.append(_fb_posts("australia", "med_spa", "AUS MedSpa"))
    return results


def _slot_1400():
    results = []
    ig_region = _ig_market_region("uk")
    results.append(_ig("--region", ig_region, "--niche", "hvac", "--limit", "4", job="UK HVAC DMs"))
    results.append(_ig("--region", ig_region, "--niche", "med_spa", "--limit", "3", job="UK MedSpa DMs"))
    results.append(_ig("--region", ig_region, "--niche", "coach", "--limit", "3", job="UK Coach DMs"))
    results.extend(_parallel(
        lambda: _fb("--dms", "--region", "uk", "--limit", "5", job="UK FB DMs"),
        lambda: _ig_comments("hvac", "uk", "UK HVAC 2pm"),
    ))
    results.extend(_parallel(
        lambda: _ig_comments("med_spa", "uk", "UK MedSpa 2pm"),
        lambda: _fb_comments("hvac", "uk", "UK HVAC 2pm"),
    ))
    results.extend(_parallel(
        lambda: _fb_comments("coach", "uk", "UK Coach 2pm"),
        lambda: _fb_posts("uk", "hvac", "UK HVAC"),
    ))
    results.append(_fb_posts("uk", "med_spa", "UK MedSpa"))
    results.append(_fb_posts("uk", "coach", "UK Coach"))
    return results


def _slot_1800():
    results = _parallel(
        lambda: _ig_comments("digital_marketing_agency", "india", "India DMA 6pm"),
        lambda: _fb_comments("digital_marketing_agency", "india", "India DMA 6pm"),
    )
    results.append(_fb_posts("india", "digital_marketing_agency", "India DMA"))
    return results


def _slot_2000():
    return [
        _ig("--region", "us", "--niche", "hvac", "--limit", "5", job="US HVAC DMs"),
        _ig("--region", "us", "--niche", "med_spa", "--limit", "5", job="US MedSpa DMs"),
    ]


def _slot_2100():
    results = []
    results.append(_ig("--region", "us", "--niche", "coach", "--limit", "5", job="US Coach DMs"))
    results.append(_ig("--region", "us", "--niche", "consultant", "--limit", "5", job="US Consultant DMs"))
    results.extend(_parallel(
        lambda: _ig_comments("coach", "us", "US Coach 9pm", limit=_COMMENT_PM),
        lambda: _fb("--dms", "--region", "us", "--limit", "10", job="US FB DMs"),
    ))
    return results


def _slot_2200():
    results = _parallel(
        lambda: _ig_comments("hvac", "us", "US HVAC 10pm"),
        lambda: _fb_comments("hvac", "us", "US HVAC 10pm"),
    )
    results.extend(_parallel(
        lambda: _ig_comments("med_spa", "us", "US MedSpa 10pm"),
        lambda: _fb_comments("coach", "us", "US Coach 10pm"),
    ))
    results.append(_fb_posts("us", "hvac", "US HVAC"))
    results.append(_fb_posts("us", "med_spa", "US MedSpa"))
    results.append(_fb_posts("us", "coach", "US Coach"))
    return results


def _slot_0200():
    results = _parallel(
        lambda: _ig_comments("hvac", "us", "US HVAC 2am late"),
        lambda: _fb_comments("hvac", "us", "US HVAC 2am late"),
    )
    results.extend(_parallel(
        lambda: _ig_comments("coach", "us", "US Coach 2am late"),
        lambda: _fb_comments("coach", "us", "US Coach 2am late"),
    ))
    return results


def _print_schedule():
    log.info("=" * 65)
    log.info("  Virel Automation - Unified IG + FB Outreach Scheduler")
    log.info("=" * 65)
    log.info("  06:00 IST -> IG+FB comments: India DMA (25 each)")
    log.info("  10:00 IST -> IG DMs India DMA (10) | Gmail India DMA (10)")
    log.info("            -> IG comments India (15) | FB comments India (25)")
    log.info("            -> IG+FB comments AUS HVAC+MedSpa (25 ea) | FB posts AUS")
    log.info("  14:00 IST -> IG DMs UK (10) | FB DMs UK (5)")
    log.info("            -> IG+FB comments UK (25 ea) | FB posts UK")
    log.info("  18:00 IST -> IG+FB comments India DMA round 2 (25 each)")
    log.info("            -> FB group posts: India")
    log.info("  20:00 IST -> IG DMs US HVAC (5) + MedSpa (5) = 10 DMs")
    log.info("  21:00 IST -> IG DMs US Coach (5) + Consultant (5) = 10 DMs")
    log.info("            -> 25 IG comments | FB DMs US (10)")
    log.info("  22:00 IST -> IG+FB comments US (25 ea) | FB posts US")
    log.info("  02:00 IST -> IG+FB comments US late (25 each)")
    log.info("  11:00 IST -> Follow-ups (AM)")
    log.info("  22:30 IST -> Follow-ups (PM)")
    log.info("  Every :30 -> Reply check")
    log.info("  Every 5min -> Heartbeat")
    log.info("=" * 65)
    log.info("  IG comments: 150/day | FB comments: 150/day")
    log.info("  IG DMs: 30/day | FB DMs: 15/day | FB posts: ~8/day")
    log.info("  Total touchpoints: ~353/day")
    log.info("=" * 65)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--now", action="store_true", help="Fire current time slot now")
    parser.add_argument("--status", action="store_true", help="Print stats and exit")
    parser.add_argument("--test", action="store_true", help="Show schedule dry-run and exit")
    args = parser.parse_args()

    if args.status:
        _ig("--status", job="status")
        return

    if args.test:
        _print_schedule()
        return

    if args.now:
        hour = datetime.now(_IST).hour
        if 5 <= hour < 8:
            _slot_0600()
        elif 8 <= hour < 12:
            _slot_1000()
        elif 12 <= hour < 16:
            _slot_1400()
        elif 16 <= hour < 19:
            _slot_1800()
        elif hour in {19, 20}:
            _slot_2000()
        elif hour == 21:
            _slot_2100()
        elif hour >= 22:
            _slot_2200()
        else:
            _slot_0200()
        return

    sched = BlockingScheduler(timezone="Asia/Kolkata")

    sched.add_job(_slot_0600, CronTrigger(hour=6, minute=0, timezone="Asia/Kolkata"), id="slot_0600", misfire_grace_time=300)
    sched.add_job(_slot_1000, CronTrigger(hour=10, minute=0, timezone="Asia/Kolkata"), id="slot_1000", misfire_grace_time=300)
    sched.add_job(_slot_1400, CronTrigger(hour=14, minute=0, timezone="Asia/Kolkata"), id="slot_1400", misfire_grace_time=300)
    sched.add_job(_slot_1800, CronTrigger(hour=18, minute=0, timezone="Asia/Kolkata"), id="slot_1800", misfire_grace_time=300)
    sched.add_job(_slot_2000, CronTrigger(hour=20, minute=0, timezone="Asia/Kolkata"), id="slot_2000", misfire_grace_time=300)
    sched.add_job(_slot_2100, CronTrigger(hour=21, minute=0, timezone="Asia/Kolkata"), id="slot_2100", misfire_grace_time=300)
    sched.add_job(_slot_2200, CronTrigger(hour=22, minute=0, timezone="Asia/Kolkata"), id="slot_2200", misfire_grace_time=300)
    sched.add_job(_slot_0200, CronTrigger(hour=2, minute=0, timezone="Asia/Kolkata"), id="slot_0200", misfire_grace_time=300)

    sched.add_job(lambda: _ig("--followups", job="followups-am"), CronTrigger(hour=11, minute=0, timezone="Asia/Kolkata"), id="fu_am", misfire_grace_time=300)
    sched.add_job(lambda: _ig("--followups", job="followups-pm"), CronTrigger(hour=22, minute=30, timezone="Asia/Kolkata"), id="fu_pm", misfire_grace_time=300)
    sched.add_job(lambda: _ig("--check-replies", job="reply-check"), CronTrigger(minute=30, timezone="Asia/Kolkata"), id="replies", misfire_grace_time=120)
    sched.add_job(_heartbeat, CronTrigger(minute="*/5", timezone="Asia/Kolkata"), id="heartbeat")

    _print_schedule()

    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("[SCHED] Shutting down cleanly.")
        sched.shutdown(wait=False)


if __name__ == "__main__":
    main()
