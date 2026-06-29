"""
Virel Automation — Unified IG + FB Outreach Scheduler

NICHE RULES:
  India only  → digital_marketing_agency
  US/UK/AUS/CA → hvac | med_spa | coach

COMMENT CADENCE: 25 comments every 4 hours per platform = 150 IG + 150 FB per day
FB GROUP POSTS:  every 4 hours
IG DMs:          India 10am, UK 2pm, AUS 10am, US 9pm (all IST)
FB DMs:          US 9:30pm, UK 2:30pm IST

SCHEDULE (all IST / Asia/Kolkata):
  06:00 → IG + FB comments: India DMA (25 each)
  10:00 → IG DMs India DMA (10) | IG + FB comments: AUS/CA HVAC+MedSpa (25 each)
  10:00 → FB group posts: AUS/CA
  14:00 → IG DMs UK HVAC+MedSpa+Coach (10) | IG + FB comments: UK (25 each)
  14:00 → FB group posts: UK | FB DMs UK (5)
  18:00 → IG + FB comments: India DMA round 2 (25 each)
  18:00 → FB group posts: India
  21:00 → IG DMs US HVAC+MedSpa+Coach (10) | FB DMs US (10)
  22:00 → IG + FB comments: US (25 each)
  22:00 → FB group posts: US
  02:00 → IG + FB comments: US late / UK early (25 each)
  Hourly :30 → Reply check (IG)
  11:00 + 22:30 → Follow-ups
  Every 5 min → Heartbeat

Usage:
    python ig_outreach/scheduler.py           # run permanently
    python ig_outreach/scheduler.py --now     # fire right region now
    python ig_outreach/scheduler.py --status  # print stats
    python ig_outreach/scheduler.py --test    # show schedule and exit
"""

import argparse, logging, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SCHED] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("virel.sched")

_ROOT    = Path(__file__).parent.parent
_IG      = Path(__file__).parent / "main.py"
_FB      = _ROOT / "fb_outreach" / "main.py"
_IST     = timezone(timedelta(hours=5, minutes=30))
_COMMENT = "25"   # comments per batch per platform

_consecutive_failures = 0
_MAX_FAILURES = 5

_COMMENT_INDIA = "15"   # 10AM India slot (15 IG comments)
_COMMENT_PM    = "25"   # 9PM US slot  (25 IG comments)


# ── Subprocess runner ─────────────────────────────────────────────────────────

def _run(script: Path, args: list, job_name: str = ""):
    global _consecutive_failures
    try:
        log.info(f"[JOB] {job_name or script.name + ' ' + ' '.join(args)}")
        result = subprocess.run(
            [sys.executable, str(script)] + args,
            cwd=str(_ROOT),
            capture_output=True, text=True, timeout=3600,
        )
        if result.stdout:
            for line in result.stdout.strip().splitlines()[-20:]:
                log.info(f"  | {line}")
        if result.returncode != 0:
            _consecutive_failures += 1
            log.error(f"[JOB FAIL] {job_name} (exit {result.returncode}, failure #{_consecutive_failures})")
            if result.stderr:
                log.error(f"  stderr: {result.stderr[:500]}")
            if _consecutive_failures >= _MAX_FAILURES:
                log.critical(f"[SCHED] {_MAX_FAILURES} consecutive failures — check system")
                _consecutive_failures = 0
        else:
            _consecutive_failures = 0
            log.info(f"[JOB] {job_name} OK")
    except subprocess.TimeoutExpired:
        log.error(f"[JOB] {job_name} timed out after 1 hour")
    except Exception as e:
        log.error(f"[JOB] {job_name} crashed: {e}")


def _ig(*args, job=""):
    _run(_IG, list(args), job)

def _fb(*args, job=""):
    _run(_FB, list(args), job)

def _heartbeat():
    log.info(f"[HEARTBEAT] Alive — {datetime.now(_IST).strftime('%H:%M IST')}")


def _parallel(*callables):
    """Run callables simultaneously in a thread pool. Blocks until all done."""
    with ThreadPoolExecutor(max_workers=len(callables)) as pool:
        futures = [pool.submit(fn) for fn in callables]
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                log.error(f"[PARALLEL] Job raised: {e}")


# ── Niche comment helpers ─────────────────────────────────────────────────────

def _ig_comments(niche: str, region: str, label: str, limit: str = _COMMENT):
    _ig("--comments", "--niche", niche, "--region", region,
        "--comment-limit", limit, job=f"IG comments {label}")

def _fb_comments(niche: str, region: str, label: str):
    _fb("--comments", "--niche", niche, "--region", region,
        "--comment-limit", _COMMENT, job=f"FB comments {label}")

def _fb_posts(region: str, niche: str, label: str):
    _fb("--posts", "--niche", niche, "--region", region,
        job=f"FB posts {label}")


# ── 06:00 IST — India DMA round 1 ─────────────────────────────────────────────

def _slot_0600():
    _parallel(
        lambda: _ig_comments("digital_marketing_agency", "india", "India DMA 6am"),
        lambda: _fb_comments("digital_marketing_agency", "india", "India DMA 6am"),
    )


# ── 10:00 IST — India DMs + AUS/CA comments + FB posts ───────────────────────

def _slot_1000():
    # India IG DMs (sequential — single account rate-limit concern)
    _ig("--region", "india", "--niche", "digital_marketing_agency", "--limit", "10",
        job="India DMA DMs")
    # India IG comments: 15 (per schedule) + FB comments in parallel
    _parallel(
        lambda: _ig_comments("digital_marketing_agency", "india", "India DMA 10am", limit=_COMMENT_INDIA),
        lambda: _fb_comments("digital_marketing_agency", "india", "India DMA 10am"),
    )
    # AUS HVAC: IG + FB comments in parallel
    _parallel(
        lambda: _ig_comments("hvac", "australia", "AUS HVAC 10am"),
        lambda: _fb_comments("hvac", "australia", "AUS HVAC 10am"),
    )
    # AUS MedSpa: IG + FB comments in parallel
    _parallel(
        lambda: _ig_comments("med_spa", "australia", "AUS MedSpa 10am"),
        lambda: _fb_comments("med_spa", "australia", "AUS MedSpa 10am"),
    )
    # AUS FB group posts
    _fb_posts("australia", "hvac",    "AUS HVAC")
    _fb_posts("australia", "med_spa", "AUS MedSpa")


# ── 14:00 IST — UK DMs + comments + FB posts ─────────────────────────────────

def _slot_1400():
    # UK IG DMs (sequential — single IG account)
    _ig("--region", "uk", "--niche", "hvac",    "--limit", "4", job="UK HVAC DMs")
    _ig("--region", "uk", "--niche", "med_spa", "--limit", "3", job="UK MedSpa DMs")
    _ig("--region", "uk", "--niche", "coach",   "--limit", "3", job="UK Coach DMs")
    # UK FB DMs + IG comments in parallel (FB DMs use FB browser, IG comments use API — no conflict)
    _parallel(
        lambda: _fb("--dms", "--region", "uk", "--limit", "5", job="UK FB DMs"),
        lambda: _ig_comments("hvac",    "uk", "UK HVAC 2pm"),
    )
    _parallel(
        lambda: _ig_comments("med_spa", "uk", "UK MedSpa 2pm"),
        lambda: _fb_comments("hvac",    "uk", "UK HVAC 2pm"),
    )
    _parallel(
        lambda: _fb_comments("coach",   "uk", "UK Coach 2pm"),
        lambda: _fb_posts("uk", "hvac", "UK HVAC"),
    )
    _fb_posts("uk", "med_spa", "UK MedSpa")
    _fb_posts("uk", "coach",   "UK Coach")


# ── 18:00 IST — India DMA round 2 ────────────────────────────────────────────

def _slot_1800():
    _parallel(
        lambda: _ig_comments("digital_marketing_agency", "india", "India DMA 6pm"),
        lambda: _fb_comments("digital_marketing_agency", "india", "India DMA 6pm"),
    )
    _fb_posts("india", "digital_marketing_agency", "India DMA")


# ── 20:00 IST — US HVAC + MedSpa DMs (10:30am EST — US daytime) ──────────────

def _slot_2000():
    # IG DMs: sequential (single IG account) — 5 HVAC + 5 MedSpa = 10 total
    _ig("--region", "us", "--niche", "hvac",    "--limit", "5", job="US HVAC DMs")
    _ig("--region", "us", "--niche", "med_spa", "--limit", "5", job="US MedSpa DMs")


# ── 21:00 IST — US Coaches + Consultants DMs + 25 IG comments ─────────────────

def _slot_2100():
    # IG DMs: coaches + consultants (10 total, sequential)
    _ig("--region", "us", "--niche", "coach",      "--limit", "5", job="US Coach DMs")
    _ig("--region", "us", "--niche", "consultant", "--limit", "5", job="US Consultant DMs")
    # 25 IG comments + FB DMs in parallel (different processes — no conflict)
    _parallel(
        lambda: _ig_comments("coach", "us", "US Coach 9pm", limit=_COMMENT_PM),
        lambda: _fb("--dms", "--region", "us", "--limit", "10", job="US FB DMs"),
    )


# ── 22:00 IST — US prime time comments + FB posts ────────────────────────────

def _slot_2200():
    _parallel(
        lambda: _ig_comments("hvac",    "us", "US HVAC 10pm"),
        lambda: _fb_comments("hvac",    "us", "US HVAC 10pm"),
    )
    _parallel(
        lambda: _ig_comments("med_spa", "us", "US MedSpa 10pm"),
        lambda: _fb_comments("coach",   "us", "US Coach 10pm"),
    )
    # FB group posts
    _fb_posts("us", "hvac",    "US HVAC")
    _fb_posts("us", "med_spa", "US MedSpa")
    _fb_posts("us", "coach",   "US Coach")


# ── 02:00 IST — US late / CA / UK early (9pm EST / 6pm PST) ─────────────────

def _slot_0200():
    _parallel(
        lambda: _ig_comments("hvac",  "us", "US HVAC 2am late"),
        lambda: _fb_comments("hvac",  "us", "US HVAC 2am late"),
    )
    _parallel(
        lambda: _ig_comments("coach", "us", "US Coach 2am late"),
        lambda: _fb_comments("coach", "us", "US Coach 2am late"),
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def _print_schedule():
    log.info("=" * 65)
    log.info("  Virel Automation — Unified IG + FB Outreach Scheduler")
    log.info("=" * 65)
    log.info("  06:00 IST → IG+FB comments: India DMA (25 each)")
    log.info("  10:00 IST → IG DMs India DMA (10) | Gmail India DMA (10)")
    log.info("            → IG comments India (15) | FB comments India (25)")
    log.info("            → IG+FB comments AUS HVAC+MedSpa (25 ea) | FB posts AUS")
    log.info("  14:00 IST → IG DMs UK (10) | FB DMs UK (5)")
    log.info("            → IG+FB comments UK (25 ea) | FB posts UK")
    log.info("  18:00 IST → IG+FB comments India DMA round 2 (25 each)")
    log.info("            → FB group posts: India")
    log.info("  20:00 IST → IG DMs US HVAC (5) + MedSpa (5) = 10 DMs")
    log.info("  21:00 IST → IG DMs US Coach (5) + Consultant (5) = 10 DMs")
    log.info("            → 25 IG comments | FB DMs US (10)")
    log.info("  22:00 IST → IG+FB comments US (25 ea) | FB posts US")
    log.info("  02:00 IST → IG+FB comments US late (25 each)")
    log.info("  11:00 IST → Follow-ups (AM)")
    log.info("  22:30 IST → Follow-ups (PM)")
    log.info("  Hourly :30 → Reply check")
    log.info("  Every 5min → Heartbeat")
    log.info("=" * 65)
    log.info("  IG comments: 150/day | FB comments: 150/day")
    log.info("  IG DMs: 30/day | FB DMs: 15/day | FB posts: ~8/day")
    log.info("  Total touchpoints: ~353/day")
    log.info("=" * 65)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--now",    action="store_true", help="Fire current time slot now")
    parser.add_argument("--status", action="store_true", help="Print stats and exit")
    parser.add_argument("--test",   action="store_true", help="Show schedule dry-run and exit")
    args = parser.parse_args()

    if args.status:
        _ig("--status", job="status")
        return

    if args.test:
        _print_schedule()
        return

    if args.now:
        h = datetime.now(_IST).hour
        if 5 <= h < 8:
            _slot_0600()
        elif 8 <= h < 12:
            _slot_1000()
        elif 12 <= h < 16:
            _slot_1400()
        elif 16 <= h < 19:
            _slot_1800()
        elif h == 19 or h == 20:
            _slot_2000()
        elif h == 21:
            _slot_2100()
        elif h >= 22:
            _slot_2200()
        else:
            _slot_0200()
        return

    sched = BlockingScheduler(timezone="Asia/Kolkata")

    sched.add_job(_slot_0600, CronTrigger(hour=6,  minute=0,  timezone="Asia/Kolkata"),
                  id="slot_0600", misfire_grace_time=300)
    sched.add_job(_slot_1000, CronTrigger(hour=10, minute=0,  timezone="Asia/Kolkata"),
                  id="slot_1000", misfire_grace_time=300)
    sched.add_job(_slot_1400, CronTrigger(hour=14, minute=0,  timezone="Asia/Kolkata"),
                  id="slot_1400", misfire_grace_time=300)
    sched.add_job(_slot_1800, CronTrigger(hour=18, minute=0,  timezone="Asia/Kolkata"),
                  id="slot_1800", misfire_grace_time=300)
    sched.add_job(_slot_2000, CronTrigger(hour=20, minute=0,  timezone="Asia/Kolkata"),
                  id="slot_2000", misfire_grace_time=300)
    sched.add_job(_slot_2100, CronTrigger(hour=21, minute=0,  timezone="Asia/Kolkata"),
                  id="slot_2100", misfire_grace_time=300)
    sched.add_job(_slot_2200, CronTrigger(hour=22, minute=0,  timezone="Asia/Kolkata"),
                  id="slot_2200", misfire_grace_time=300)
    sched.add_job(_slot_0200, CronTrigger(hour=2,  minute=0,  timezone="Asia/Kolkata"),
                  id="slot_0200", misfire_grace_time=300)

    # Follow-ups
    sched.add_job(lambda: _ig("--followups", job="followups-am"),
                  CronTrigger(hour=11, minute=0,  timezone="Asia/Kolkata"),
                  id="fu_am", misfire_grace_time=300)
    sched.add_job(lambda: _ig("--followups", job="followups-pm"),
                  CronTrigger(hour=22, minute=30, timezone="Asia/Kolkata"),
                  id="fu_pm", misfire_grace_time=300)

    # Reply scan
    sched.add_job(lambda: _ig("--check-replies", job="reply-check"),
                  CronTrigger(minute=30, timezone="Asia/Kolkata"),
                  id="replies", misfire_grace_time=120)

    # Heartbeat
    sched.add_job(_heartbeat,
                  CronTrigger(minute="*/5", timezone="Asia/Kolkata"),
                  id="heartbeat")

    _print_schedule()

    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("[SCHED] Shutting down cleanly.")
        sched.shutdown(wait=False)


if __name__ == "__main__":
    main()
