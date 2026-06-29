"""
Virel Automation — Facebook Group Outreach
Targets: HVAC, Med Spas, Coaches (US)

Usage:
    python fb_outreach/main.py --join           # find + join groups (run once per week)
    python fb_outreach/main.py --post           # post in joined groups (10/day, 8-15m gaps)
    python fb_outreach/main.py --dm             # DM group members (20/day, 3-8m gaps)
    python fb_outreach/main.py --followups      # send due follow-ups (day 3 + day 7)
    python fb_outreach/main.py --all            # join + post + dm in one run
    python fb_outreach/main.py --status         # print stats

Daily flow for max reply rate:
    Morning (10am):   python fb_outreach/main.py --post
    Afternoon (2pm):  python fb_outreach/main.py --dm
    (DMs reference the group — 20-30% reply rate vs 5% cold)
"""

import os, sys, logging, argparse
from pathlib import Path
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_env = Path(__file__).parent.parent / "forge_system" / ".env"
load_dotenv(_env if _env.exists() else Path(".env"))

sys.path.insert(0, str(Path(__file__).parent))
import fb_db, fb_groups, fb_dm, fb_alerts, fb_comments
from fb_login import login
from fb_browser import build_driver

LOG_FILE = Path(__file__).parent.absolute() / "fb_outreach.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ]
)
log = logging.getLogger("virel.fb")

DAILY_POSTS          = int(os.getenv("FACEBOOK_DAILY_POST_LIMIT",    "10"))
DAILY_DMS            = int(os.getenv("FACEBOOK_DAILY_DM_LIMIT",      "10"))
MAX_GROUPS_PER_NICHE = int(os.getenv("FACEBOOK_MAX_GROUPS_PER_NICHE", "10"))
ALL_NICHES           = ["hvac", "med_spa", "med spa", "coach", "business_owner"]


def _banner():
    log.info("=" * 55)
    log.info("  Virel Automation — Facebook Group Outreach")
    log.info("=" * 55)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--join",         action="store_true")
    parser.add_argument("--post",         action="store_true")
    parser.add_argument("--posts",        action="store_true", help="Alias for --post (used by scheduler)")
    parser.add_argument("--dm",           action="store_true")
    parser.add_argument("--dms",          action="store_true", help="Alias for --dm (used by scheduler)")
    parser.add_argument("--comments",     action="store_true", help="Comment on group posts (25/slot)")
    parser.add_argument("--followups",    action="store_true")
    parser.add_argument("--all",          action="store_true")
    parser.add_argument("--status",       action="store_true")
    parser.add_argument("--discover",     action="store_true", help="Scan your joined Facebook groups and add them to DB")
    parser.add_argument("--verify",       action="store_true", help="Re-check pending groups to see if admin approved you")
    parser.add_argument("--retry-pending",action="store_true", help="Retry queued DMs from previous failed runs")
    parser.add_argument("--whatsapp",     action="store_true", help="List collected WhatsApp numbers (Indian leads first)")
    parser.add_argument("--niche",        choices=ALL_NICHES + ["consultant", "digital_marketing_agency"],
                        default=None)
    parser.add_argument("--region",       choices=["us", "uk", "australia", "india", "ca"], default=None)
    parser.add_argument("--limit",        type=int, default=None, help="Override daily DM limit for this run")
    parser.add_argument("--comment-limit",type=int, default=25,   help="Comments to post in this run")
    parser.add_argument("--headless",     action="store_true", help="Headless Chrome (higher bot risk)")
    args = parser.parse_args()

    # Aliases
    if args.posts:
        args.post = True
    if args.dms:
        args.dm = True

    _banner()

    fb_db.init_db()

    if args.status:
        s = fb_db.get_stats()
        log.info(f"Groups active:      {s['groups_joined']}")
        log.info(f"Groups pending:     {s['groups_pending']} (awaiting admin approval)")
        log.info(f"DM queue pending:   {s['dm_queue_pending']} (scheduled for retry)")
        log.info(f"Posts total:        {s['posts_total']} | today: {s['posts_today']}/{DAILY_POSTS}")
        log.info(f"DMs total:          {s['dms_total']} | today: {s['dms_today']}/{DAILY_DMS}")
        log.info(f"Comments total:     {s.get('comments_total', 0)} | today: {s.get('comments_today', 0)}")
        log.info(f"Pending followups:  {s['pending_followups']}")

        # Show checkpoint if any
        cp = fb_db.get_checkpoint()
        if cp:
            log.info(f"Last checkpoint:   {cp['action']} | group={cp['group_id']} | uid={cp['fb_uid']}")
        return

    if args.whatsapp:
        fb_db.init_db()
        leads = fb_db.get_whatsapp_leads()
        if not leads:
            log.info("[WHATSAPP] No WhatsApp numbers collected yet. Run --dm first.")
            return
        # Indian leads first
        indian = [l for l in leads if l["nationality"] == "indian"]
        other  = [l for l in leads if l["nationality"] != "indian"]
        log.info(f"\n[WHATSAPP] {len(leads)} total | {len(indian)} Indian (WhatsApp guaranteed)\n")
        log.info("=== INDIAN LEADS (WhatsApp) ===")
        for l in indian:
            log.info(f"  {l['whatsapp_number']}  @{l['fb_uid']}  [{l['niche']}]  {l['profile_url']}")
        if other:
            log.info("\n=== OTHER LEADS (phone found) ===")
            for l in other:
                log.info(f"  {l['whatsapp_number']}  @{l['fb_uid']}  [{l['niche']}]  {l['nationality'] or '?'}")
        return

    # Check if any browser action was requested
    if not any([args.join, args.post, args.dm, args.comments, args.followups, args.all,
                args.discover, args.verify, args.retry_pending]):
        parser.print_help()
        return

    log.info("[BROWSER] Starting Chrome...")
    driver = build_driver(headless=args.headless)

    try:
        if not login(driver):
            log.error("[FATAL] Facebook login failed. Add credentials to forge_system/.env")
            log.error("  FACEBOOK_EMAIL=your@email.com")
            log.error("  FACEBOOK_PASSWORD=yourpassword")
            return

        # Resume from checkpoint if there was a crash
        cp = fb_db.get_checkpoint()
        if cp:
            log.info(f"[RESUME] Found checkpoint: {cp['action']} — resuming...")

        if args.verify:
            log.info("\n[VERIFY] Checking pending group approvals...")
            fb_groups.verify_pending_groups(driver)

        if args.discover:
            niche = args.niche or "business_owner"
            log.info(f"\n[DISCOVER] Adding existing groups → niche: {niche}")
            added = fb_groups.discover_existing_groups(driver, niche=niche)
            log.info(f"[DISCOVER] Done — {len(added)} groups added")

        if args.all or args.join:
            niches = [args.niche] if args.niche else ALL_NICHES
            for niche in niches:
                log.info(f"\n[JOIN] Niche: {niche}")
                joined = fb_groups.search_and_join_groups(
                    driver, niche, max_join=5, max_total=MAX_GROUPS_PER_NICHE
                )
                log.info(f"[JOIN] {niche}: {len(joined)} new groups")

        if args.all or args.post:
            log.info("\n[POST] Starting group posts...")
            niche_filter = args.niche if args.niche else None
            fb_groups.post_in_groups(driver, daily_limit=DAILY_POSTS, niche=niche_filter)

        if args.comments:
            niche  = args.niche or "business_owner"
            region = args.region or "us"
            limit  = args.comment_limit
            log.info(f"\n[COMMENTS] Commenting on group posts — niche={niche}, region={region}, limit={limit}")
            done = fb_comments.run_comments(driver, niche=niche, region=region, daily_limit=limit)
            log.info(f"[COMMENTS] Done — {done} comments posted")

        if args.all or args.dm:
            log.info("\n[DM] Starting member outreach...")
            dm_limit = args.limit or DAILY_DMS
            # Always drain the pending queue first before new DMs
            fb_dm.run_pending_queue(driver)
            fb_dm.run_dm_outreach(driver, daily_limit=dm_limit)

        if args.followups:
            log.info("\n[FOLLOWUPS] Sending due follow-ups...")
            fb_dm.run_followups(driver)

        if args.retry_pending:
            log.info("\n[QUEUE] Retrying pending DMs...")
            fb_dm.run_pending_queue(driver)

    except KeyboardInterrupt:
        log.info("\n[STOP] Interrupted by user.")
    except Exception as e:
        log.error(f"[ERROR] {e}", exc_info=True)
        fb_alerts.alert(
            "FB Outreach crashed",
            f"{type(e).__name__}: {str(e)[:200]}",
            level="error"
        )
        from fb_browser import screenshot
        try:
            screenshot(driver, "crash")
        except Exception:
            pass
    finally:
        try:
            driver.quit()
        except Exception:
            pass
        log.info("[BROWSER] Chrome closed.")

        # Print final stats
        s = fb_db.get_stats()
        log.info(f"\n[FINAL] Posts today: {s['posts_today']} | DMs today: {s['dms_today']}")


if __name__ == "__main__":
    main()
