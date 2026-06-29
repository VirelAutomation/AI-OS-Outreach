"""
Virel Automation — Gmail Email Scheduler

SCHEDULE (IST):
  10:00 AM → 10 emails to Indian business owners, fintech, digital marketing agencies
             (tone: peer/familiar, mention from India)
   9:00 PM → 10 emails to HVAC firms in US (5), Australia (3), Canada (2)

Usage:
    python email_scheduler.py               # run permanently
    python email_scheduler.py --draft-only  # create Gmail drafts only (no send)
    python email_scheduler.py --test        # show what would fire, print sample emails
    python email_scheduler.py --morning     # fire morning campaign now (draft mode)
    python email_scheduler.py --evening     # fire evening campaign now (draft mode)

Notes:
  - All emails are created as Gmail drafts first
  - Review drafts in Gmail before enabling --send
  - Gmail credentials required: GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET,
    GMAIL_REFRESH_TOKEN, GMAIL_SENDER_EMAIL in forge_system/.env
  - Lead source: Supabase outreach.leads table
"""

import os, sys, json, logging, asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / "forge_system" / ".env")

sys.path.insert(0, str(ROOT / "forge_system" / "forge_system"))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

import email_templates as tpl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [EMAIL] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("virel.email")

_IST = timezone(timedelta(hours=5, minutes=30))

# ── Config ─────────────────────────────────────────────────────────────────────

MORNING_LIMIT  = 10   # emails per morning run
EVENING_LIMIT  = 10   # emails per evening run

MORNING_TARGETS = [
    {"type": "digital_marketing_agency", "count": 10, "region": "india"},
]

EVENING_TARGETS = [
    {"type": "hvac", "count": 5, "region": "us"},
    {"type": "hvac", "count": 3, "region": "au"},
    {"type": "hvac", "count": 2, "region": "ca"},
]


# ── Gmail helpers ─────────────────────────────────────────────────────────────

def _gmail_configured() -> bool:
    return all([
        os.getenv("GMAIL_CLIENT_ID") or os.getenv("GMAIL_REFRESH_TOKEN"),
        os.getenv("GMAIL_REFRESH_TOKEN"),
        os.getenv("GMAIL_SENDER_EMAIL"),
    ])


async def _create_draft(to_email: str, subject: str, body: str) -> str:
    try:
        from services.gmail import create_draft
        draft_id = await create_draft(to_email, subject, body)
        return draft_id or ""
    except Exception as e:
        log.error(f"Draft creation failed for {to_email}: {e}")
        return ""


def _get_leads(industry_filter: str, limit: int) -> list[dict]:
    """Pull leads from Supabase. Falls back to empty list if not configured."""
    try:
        from database.supabase import db
        q = (db().table("outreach.leads")
             .select("name,email,company,industry")
             .ilike("industry", f"%{industry_filter}%")
             .eq("status", "new")
             .limit(limit))
        return q.execute().data or []
    except Exception as e:
        log.warning(f"Could not fetch leads for '{industry_filter}': {e}")
        return []


# ── Campaign runners ──────────────────────────────────────────────────────────

async def run_morning_campaign(draft_only: bool = True):
    """10 AM IST — India outreach (digital agencies, fintech, business owners)."""
    now = datetime.now(_IST).strftime("%Y-%m-%d %H:%M IST")
    log.info(f"[MORNING] Starting India campaign — {now}")

    if not _gmail_configured():
        log.warning("[MORNING] Gmail not configured — showing sample drafts only")
        _print_morning_samples()
        return

    total_sent = 0
    for target in MORNING_TARGETS:
        if total_sent >= MORNING_LIMIT:
            break
        leads = _get_leads(target["type"], target["count"])
        if not leads:
            log.info(f"  [MORNING] No leads for '{target['type']}' — using placeholder")
            leads = [{"name": "there", "email": "", "company": "", "industry": target["type"]}]

        for lead in leads:
            if total_sent >= MORNING_LIMIT:
                break
            name    = lead.get("name") or "there"
            email   = lead.get("email") or ""
            if not email:
                continue
            subject, body = tpl.get_morning_india(target["type"])
            body_rendered = tpl.render(body, name=name.split()[0] if name != "there" else "there")

            if draft_only:
                draft_id = await _create_draft(email, subject, body_rendered)
                status = f"draft_id={draft_id}" if draft_id else "draft failed"
                log.info(f"  [DRAFT] {email} | {target['type']} | {status}")
            else:
                # TODO: add send logic here when ready
                log.info(f"  [WOULD SEND] {email} | {subject[:50]}")

            total_sent += 1

    log.info(f"[MORNING] Done — {total_sent} emails drafted")


async def run_evening_campaign(draft_only: bool = True):
    """9 PM IST — US/AU/CA HVAC outreach."""
    now = datetime.now(_IST).strftime("%Y-%m-%d %H:%M IST")
    log.info(f"[EVENING] Starting HVAC campaign — {now}")

    if not _gmail_configured():
        log.warning("[EVENING] Gmail not configured — showing sample drafts only")
        _print_evening_samples()
        return

    total_sent = 0
    for target in EVENING_TARGETS:
        if total_sent >= EVENING_LIMIT:
            break
        leads = _get_leads("hvac", target["count"])
        if not leads:
            log.info(f"  [EVENING] No HVAC leads for region {target['region']} — using placeholder")
            leads = [{"name": "there", "email": "", "company": "", "industry": "hvac"}]

        for lead in leads:
            if total_sent >= EVENING_LIMIT:
                break
            name  = lead.get("name") or "there"
            email = lead.get("email") or ""
            if not email:
                continue
            subject, body = tpl.get_evening_hvac(target["region"])
            body_rendered = tpl.render(body, name=name.split()[0] if name != "there" else "there")

            if draft_only:
                draft_id = await _create_draft(email, subject, body_rendered)
                status = f"draft_id={draft_id}" if draft_id else "draft failed"
                log.info(f"  [DRAFT] {email} | HVAC {target['region'].upper()} | {status}")
            else:
                log.info(f"  [WOULD SEND] {email} | {subject[:50]}")

            total_sent += 1

    log.info(f"[EVENING] Done — {total_sent} emails drafted")


def _print_morning_samples():
    log.info("\n  --- MORNING SAMPLE EMAILS (India) ---")
    for t in MORNING_TARGETS:
        subj, body = tpl.get_morning_india(t["type"])
        log.info(f"\n  [{t['type'].upper()} x{t['count']}]")
        log.info(f"  Subject: {subj}")
        for line in tpl.render(body, name="[Recipient]").strip().splitlines():
            log.info(f"  {line}")


def _print_evening_samples():
    log.info("\n  --- EVENING SAMPLE EMAILS (HVAC) ---")
    for t in EVENING_TARGETS:
        subj, body = tpl.get_evening_hvac(t["region"])
        log.info(f"\n  [HVAC {t['region'].upper()} x{t['count']}]")
        log.info(f"  Subject: {subj}")
        for line in tpl.render(body, name="[Recipient]").strip().splitlines():
            log.info(f"  {line}")


# ── Sync wrappers for APScheduler ─────────────────────────────────────────────

def fire_morning():
    asyncio.run(run_morning_campaign(draft_only=True))


def fire_evening():
    asyncio.run(run_evening_campaign(draft_only=True))


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Virel Email Scheduler")
    parser.add_argument("--test",        action="store_true", help="Show schedule + sample emails, exit")
    parser.add_argument("--draft-only",  action="store_true", default=True, help="Create drafts, don't send (default)")
    parser.add_argument("--morning",     action="store_true", help="Fire morning campaign now")
    parser.add_argument("--evening",     action="store_true", help="Fire evening campaign now")
    args = parser.parse_args()

    if args.test:
        log.info("=" * 60)
        log.info("  Virel Email Scheduler — Schedule")
        log.info("=" * 60)
        log.info("  10:00 AM IST → India campaign (10 emails)")
        log.info("    4x Digital Marketing Agencies")
        log.info("    3x Fintech Firms")
        log.info("    3x Business Owners")
        log.info("   9:00 PM IST → US/AU/CA HVAC campaign (10 emails)")
        log.info("    5x US HVAC")
        log.info("    3x Australia HVAC")
        log.info("    2x Canada HVAC")
        log.info(f"  Gmail configured: {'YES' if _gmail_configured() else 'NO — add credentials to .env'}")
        log.info("=" * 60)
        _print_morning_samples()
        _print_evening_samples()
        return

    if args.morning:
        asyncio.run(run_morning_campaign(draft_only=args.draft_only))
        return

    if args.evening:
        asyncio.run(run_evening_campaign(draft_only=args.draft_only))
        return

    sched = BlockingScheduler(timezone="Asia/Kolkata")

    sched.add_job(
        fire_morning,
        CronTrigger(hour=10, minute=0, timezone="Asia/Kolkata"),
        id="email_morning", name="10am India email campaign",
        misfire_grace_time=600,
    )
    sched.add_job(
        fire_evening,
        CronTrigger(hour=21, minute=0, timezone="Asia/Kolkata"),
        id="email_evening", name="9pm HVAC email campaign",
        misfire_grace_time=600,
    )

    log.info("=" * 60)
    log.info("  Virel Email Scheduler running")
    log.info("  10:00 AM → India campaign (10 drafts)")
    log.info("   9:00 PM → HVAC US/AU/CA campaign (10 drafts)")
    log.info("=" * 60)

    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("[EMAIL] Scheduler stopped.")
        sched.shutdown(wait=False)


if __name__ == "__main__":
    main()
