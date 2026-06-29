"""
Virel Automation — IG Outreach Engine v3
Production-grade: all failure points hardened.

Usage:
    python ig_outreach/main.py --region india
    python ig_outreach/main.py --region us
    python ig_outreach/main.py --region auto     # IST time-based (default)
    python ig_outreach/main.py --followups       # send due follow-ups
    python ig_outreach/main.py --check-replies   # scan inbox, cancel follow-ups
    python ig_outreach/main.py --status          # print stats and exit
"""

import os, sys, time, random, argparse, logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
_env = Path(__file__).parent.parent / "forge_system" / ".env"
load_dotenv(_env if _env.exists() else Path(".env"))

sys.path.insert(0, str(Path(__file__).parent))
import db, ig_client, target_finder, dm_engine, ig_alerts, ig_comments
from google import genai

# ── Config ────────────────────────────────────────────────────────────────────

DAILY_LIMIT = int(os.getenv("INSTAGRAM_DAILY_DM_LIMIT", "5"))
LOG_FILE    = Path(__file__).parent / "outreach.log"
_IST        = timezone(timedelta(hours=5, minutes=30))

# Gemini key pool — validated at startup
_KEYS: list[str] = [k for k in [
    os.getenv("GEMINI_API_KEY_DEVAN"),
    os.getenv("GEMINI_API_KEY_AKHIL"),
    os.getenv("GEMINI_API_KEY_NOAH"),
    os.getenv("GEMINI_API_KEY_ZOYA"),
    os.getenv("GEMINI_API_KEY_KING"),
    os.getenv("GEMINI_API_KEY_JARVIS"),
    os.getenv("GEMINI_API_KEY"),
] if k]
_key_idx = 0

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ]
)
log = logging.getLogger("virel.ig")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _gemini() -> genai.Client | None:
    if not _KEYS:
        log.warning("[Gemini] No API keys configured — keyword-only mode")
        return None
    key = _KEYS[_key_idx % len(_KEYS)]
    return genai.Client(api_key=key)


def _rotate_gemini():
    global _key_idx
    _key_idx = (_key_idx + 1) % max(len(_KEYS), 1)
    log.info(f"[Gemini] Rotated to key #{_key_idx}")


def _resolve_region(arg: str) -> str:
    if arg in ("india", "us"):
        return arg
    # India: 6am–3pm IST; US: all other hours
    ist_hour = datetime.now(_IST).hour
    return "india" if 6 <= ist_hour < 15 else "us"


def _jitter(lo=45, hi=90):
    time.sleep(random.uniform(lo, hi))


# ── Reply monitoring ──────────────────────────────────────────────────────────

def run_check_replies(cl):
    db.init_db()
    log.info("[REPLIES] Scanning inbox...")

    # Get all user IDs we've ever messaged
    import sqlite3
    conn = sqlite3.connect(db.DB_PATH)
    rows = conn.execute("SELECT user_id, username FROM ig_outreach WHERE replied=0").fetchall()
    conn.close()
    if not rows:
        log.info("[REPLIES] No active leads to check.")
        return

    known = {r[0]: r[1] for r in rows}
    replied_ids = ig_client.check_inbox_for_replies(cl, set(known.keys()))
    for uid in replied_ids:
        db.mark_replied(uid)
        log.info(f"[REPLY] @{known.get(uid, uid)} replied — follow-ups cancelled")
    log.info(f"[REPLIES] Done — {len(replied_ids)} replies found")


# ── Follow-up engine ──────────────────────────────────────────────────────────

def run_followups(cl):
    db.init_db()
    due = db.get_due_followups()
    if not due:
        log.info("[FOLLOWUPS] Nothing due.")
        return
    log.info(f"[FOLLOWUPS] {len(due)} due.")
    sent = 0
    for fu in due:
        uid  = fu["user_id"]
        uname= fu["username"]
        num  = fu["followup_number"]
        msg  = dm_engine.FOLLOWUP_1 if num == 1 else dm_engine.FOLLOWUP_2
        log.info(f"  Sending followup #{num} to @{uname}...")
        if ig_client.send_dm(cl, uid, msg):
            db.mark_followup_sent(fu["id"], msg)
            sent += 1
            log.info(f"  [sent] @{uname}")
            _jitter(30, 60)
        else:
            log.warning(f"  [fail] @{uname}")
    log.info(f"[FOLLOWUPS] {sent}/{len(due)} sent")


# ── Main outreach engine ──────────────────────────────────────────────────────

def run_outreach(cl, region: str, limit: int, niche: str = None):
    db.init_db()
    stats     = db.get_all_stats()
    already   = db.get_daily_count()
    remaining = min(limit, DAILY_LIMIT - already)

    niche_tag = f" | niche: {niche}" if niche else ""
    log.info(f"[START] {region.upper()}{niche_tag} | Total ever: {stats['total']} | Today: {already} | Followups pending: {stats['pending_followups']}")

    if remaining <= 0:
        log.info(f"[STOP] Daily limit {DAILY_LIMIT} reached.")
        return

    log.info(f"[INFO] Sending up to {remaining} DMs\n")

    keywords       = target_finder.get_keyword_pool(region, niche=niche)
    gemini         = _gemini()
    sent           = 0
    searched       = set()
    empty_searches = 0   # consecutive keywords returning 0 results

    # Follower range tuned per niche
    follow_min = 300
    follow_max = 1_500
    if niche in ("coach", "consultant"):
        follow_min, follow_max = 500, 2_000
    elif niche == "digital_marketing_agency":
        follow_min, follow_max = 200, 3_000
    elif niche in ("hvac", "med_spa"):
        follow_min, follow_max = 100, 5_000

    for keyword in keywords:
        if sent >= remaining:
            break
        if keyword in searched:
            continue
        searched.add(keyword)

        log.info(f"[SEARCH] '{keyword}'")
        uids = ig_client.search_users_by_keyword(cl, keyword, limit=40)
        log.info(f"  -> {len(uids)} accounts found")

        if not uids:
            empty_searches += 1
            if empty_searches >= 5:
                msg = "5 consecutive empty searches — account likely checkpoint-blocked."
                log.error(f"[BLOCKED] {msg}")
                ig_alerts.alert("Instagram search blocked", msg + " Open app on phone to verify.", level="error")
                return sent
        else:
            empty_searches = 0

        for uid in uids:
            if sent >= remaining:
                break
            if db.has_been_messaged(uid):
                continue

            info = ig_client.get_user_info_by_id(cl, int(uid))
            if not info:
                continue

            username  = getattr(info, "username",       "") or ""
            full_name = getattr(info, "full_name",      "") or ""
            bio       = getattr(info, "biography",      "") or ""
            followers = getattr(info, "follower_count",  0) or 0
            following = getattr(info, "following_count", 0) or 0
            is_biz    = bool(getattr(info, "is_business",  False))
            has_web   = bool(getattr(info, "external_url", ""))

            if followers < follow_min or followers > follow_max:
                continue
            if not bio.strip() and not full_name.strip():
                continue

            v = target_finder.validate_account(
                gemini, username, full_name, bio,
                followers, following, is_biz, has_web,
                niche=niche,
            )

            if not v.get("is_valid") or v.get("confidence", 0) < 60:
                log.info(f"  [skip] @{username} ({followers}f) — {v.get('reason','')[:60]}")
                continue

            biz_type = v.get("business_type") or "coach"
            conf     = v.get("confidence", 0)
            log.info(f"  [TARGET] @{username} | {biz_type} | {followers}f | conf {conf}%")

            message = dm_engine.generate_dm(None, username, biz_type, bio, has_web, region,
                                             followers=followers)
            log.info(f"  [MSG] {message}")

            if ig_client.send_dm(cl, uid, message):
                db.mark_as_messaged(
                    user_id=uid, username=username, full_name=full_name,
                    business_type=biz_type, region=region, followers=followers,
                    has_website=has_web, message=message,
                )
                sent += 1
                log.info(f"  [SENT #{sent}/{remaining}] @{username}")
                _jitter(45, 90)
            else:
                log.warning(f"  [FAIL] @{username}")

    total = db.get_daily_count()
    log.info(f"\n[DONE] Sent {sent} DMs | Today total: {total}/{DAILY_LIMIT}")
    if sent > 0:
        ig_alerts.alert(f"IG DMs complete — {sent} sent", f"Total today: {total}/{DAILY_LIMIT}", level="ok")
    elif sent == 0 and remaining > 0:
        ig_alerts.alert("IG DMs — 0 sent", "No valid targets found or all searches blocked.", level="warn")


def _ist_now():
    return datetime.now(_IST)


# ── Status ────────────────────────────────────────────────────────────────────

def print_status():
    db.init_db()
    stats = db.get_all_stats()
    log.info("=== STATUS ===")
    log.info(f"Total DMs (all time): {stats['total']}")
    log.info(f"Today (IST):          {stats['today']}/{DAILY_LIMIT}")
    log.info(f"Pending follow-ups:   {stats['pending_followups']}")
    log.info(f"Remaining today:      {max(0, DAILY_LIMIT - stats['today'])}")
    # Comment stats
    try:
        cs = db.get_comment_stats()
        log.info(f"\nComments total:       {cs['total']}")
        log.info(f"Comments today:       {cs['today']}/20")
        log.info(f"Replied back:         {cs['replied_back']}")
        if cs["recent"]:
            log.info("\nRecent comments:")
            for r in cs["recent"]:
                log.info(f"  @{r[0]:<25} #{r[2]:<20} {str(r[3])[:16]}")
                log.info(f"    '{r[1][:60]}'")
    except Exception:
        pass

    import sqlite3
    if db.DB_PATH.exists():
        conn = sqlite3.connect(db.DB_PATH)
        rows = conn.execute(
            "SELECT username, business_type, followers, region, dm_sent_at "
            "FROM ig_outreach ORDER BY dm_sent_at DESC LIMIT 10"
        ).fetchall()
        if rows:
            log.info("\nRecent DMs:")
            for r in rows:
                log.info(f"  @{r[0]:<30} {r[1]:<25} {r[2]:>5} followers | {r[3]} | {str(r[4])[:16]}")
        conn.close()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Virel IG Outreach")
    parser.add_argument("--region",        choices=["india","us","auto"], default="us")
    parser.add_argument("--niche",         choices=["coach","all","hvac","med_spa","digital_marketing_agency","consultant"], default="coach")
    parser.add_argument("--limit",         type=int, default=DAILY_LIMIT)
    parser.add_argument("--comments",      action="store_true", help="Post comments on hashtag posts (20/day)")
    parser.add_argument("--comment-user",  type=str,  help="Comment on a specific user's posts before DMing")
    parser.add_argument("--comment-limit", type=int,  default=20)
    parser.add_argument("--followups",     action="store_true")
    parser.add_argument("--check-replies", action="store_true")
    parser.add_argument("--status",        action="store_true")
    args = parser.parse_args()

    log.info("=" * 55)
    log.info("  Virel Automation — IG Outreach Engine v3")
    log.info("=" * 55)

    if args.status:
        print_status()
        return

    try:
        cl = ig_client.build_client()
        cl = ig_client.login(cl)
    except RuntimeError as e:
        # Challenge / 2FA — needs manual intervention
        msg = str(e)
        log.error(f"[FATAL] {msg}")
        ig_alerts.alert("Instagram login blocked", msg, level="error")
        sys.exit(1)
    except Exception as e:
        log.error(f"[FATAL] Login failed: {e}")
        ig_alerts.alert("Instagram login failed", str(e)[:200], level="error")
        sys.exit(1)

    # Probe for full account checkpoint before wasting time on all keywords
    if ig_client.is_account_blocked(cl):
        msg = (
            "Every API endpoint is returning 403. "
            "Open Instagram on your phone, log into @virel.automation and complete the security check. "
            "Then update INSTAGRAM_SESSION env var with the new session."
        )
        log.error(f"[BLOCKED] {msg}")
        ig_alerts.alert("Instagram account checkpoint", msg, level="error")
        sys.exit(1)

    try:
        if args.check_replies:
            run_check_replies(cl)
        elif args.followups:
            run_followups(cl)
        elif args.comments:
            niche  = args.niche if args.niche != "all" else "coach"
            region = _resolve_region(args.region)
            log.info(f"[COMMENTS] Starting — niche: {niche}, region: {region}, limit: {args.comment_limit}")
            posted = ig_comments.run_comments(cl, niche=niche, daily_limit=args.comment_limit, region=region)
            log.info(f"[COMMENTS] Done — {posted} comments posted today")
        elif args.comment_user:
            log.info(f"[COMMENT-USER] Engaging with @{args.comment_user}")
            n = ig_comments.comment_on_user_posts(cl, args.comment_user, amount=3)
            log.info(f"[COMMENT-USER] {n} comments posted on @{args.comment_user}")
        else:
            region = _resolve_region(args.region)
            niche  = None if args.niche == "all" else args.niche
            log.info(f"[REGION] {region.upper()} | [NICHE] {niche or 'all'} | [LIMIT] {args.limit}")
            run_outreach(cl, region=region, limit=args.limit, niche=niche)
    except KeyboardInterrupt:
        log.info("[STOP] Interrupted by user.")
    except Exception as e:
        log.error(f"[ERROR] {e}", exc_info=True)
        ig_alerts.alert("IG Outreach crashed", f"{type(e).__name__}: {str(e)[:200]}", level="error")
        sys.exit(1)


if __name__ == "__main__":
    main()
