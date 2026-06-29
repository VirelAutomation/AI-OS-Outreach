"""
Virel Automation — Full System Test Audit

Tests every channel, drafts all messages, reports what's ready.
Run this before deployment to confirm everything works.

Usage:
    python test_audit.py              # full audit (no sends, just drafts)
    python test_audit.py --channel ig # Instagram only
    python test_audit.py --channel fb # Facebook only
    python test_audit.py --channel email # Gmail only
    python test_audit.py --channel all   # everything (default)

Output:
    [PASS] / [FAIL] / [WARN] for each subsystem
    Sample messages for every channel and niche
    Gmail drafts created in your Drafts folder (if configured)
    Final score: X/N systems ready
"""

import os, sys, json, sqlite3, argparse, logging, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent
load_dotenv(ROOT / "forge_system" / ".env")

sys.path.insert(0, str(ROOT / "ig_outreach"))
sys.path.insert(0, str(ROOT / "fb_outreach"))
sys.path.insert(0, str(ROOT / "forge_system" / "forge_system"))

_IST = timezone(timedelta(hours=5, minutes=30))

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
log = logging.getLogger("virel.audit")

PASS  = "[PASS]"
FAIL  = "[FAIL]"
WARN  = "[WARN]"
INFO  = "[INFO]"
DRAFT = "[DRAFT]"

results = {}


def _header(title: str):
    print(f"\n{'=' * 65}")
    print(f"  {title}")
    print('=' * 65)


def _check(label: str, ok: bool, detail: str = ""):
    icon = PASS if ok else FAIL
    line = f"  {icon} {label}"
    if detail:
        line += f"  →  {detail}"
    print(line)
    results[label] = ok
    return ok


# ══════════════════════════════════════════════════════════════════════════════
# 1. INSTAGRAM
# ══════════════════════════════════════════════════════════════════════════════

def audit_instagram():
    _header("CHANNEL 1: INSTAGRAM DMs")

    # Session file or cloud env export
    session_file = ROOT / "ig_outreach" / "session_virel.json"
    has_session_env = bool(os.getenv("INSTAGRAM_SESSION") or os.getenv("INSTAGRAM_SESSION_ID"))
    if session_file.exists():
        age_hours = (time.time() - session_file.stat().st_mtime) / 3600
        _check("IG session file", True, f"age {age_hours:.1f}h — {'fresh' if age_hours < 72 else 'may be stale'}")
    elif has_session_env:
        _check("IG session env", True, "INSTAGRAM_SESSION or INSTAGRAM_SESSION_ID set (cloud-ready)")
    else:
        _check("IG session file", False, "missing — set INSTAGRAM_SESSION env or run ig_outreach/main.py locally")

    # Credentials in env
    has_user = bool(os.getenv("INSTAGRAM_USERNAME"))
    has_pass = bool(os.getenv("INSTAGRAM_PASSWORD"))
    _check("INSTAGRAM_USERNAME env", has_user)
    _check("INSTAGRAM_PASSWORD env", has_pass)

    # Gemini key (for account validation)
    has_gemini = bool(
        os.getenv("GEMINI_API_KEY_JARVIS") or
        os.getenv("GEMINI_API_KEY_DEVAN") or
        os.getenv("GEMINI_API_KEY")
    )
    _check("Gemini key (account validator)", has_gemini,
           "validation falls back to keyword match if missing — still works")

    # Outreach DB
    ig_db = ROOT / "ig_outreach" / "outreach.db"
    if ig_db.exists():
        conn = sqlite3.connect(ig_db)
        total = conn.execute("SELECT COUNT(*) FROM ig_outreach").fetchone()[0]
        today = conn.execute(
            "SELECT COUNT(*) FROM ig_outreach WHERE dm_sent_at LIKE ?",
            (f"{datetime.now(_IST).strftime('%Y-%m-%d')}%",)
        ).fetchone()[0]
        pending_fu = conn.execute("SELECT COUNT(*) FROM ig_followups WHERE status='pending'").fetchone()[0]
        conn.close()
        _check("IG SQLite DB", True, f"total={total} | today={today} | followups_pending={pending_fu}")
    else:
        _check("IG SQLite DB", False, "will be created on first run")

    # Sample DM drafts
    print()
    print("  SAMPLE DMs (not sent — review before enabling):")
    print()

    import dm_engine

    samples = [
        ("10:00 AM  India — Digital Marketing Agency",
         dm_engine.generate_dm(None, "targetuser", "digital marketing agency", "We run paid ads for brands", False, "india")),
        ("10:00 AM  India — Digital Agency (no website)",
         dm_engine.generate_dm(None, "targetuser", "digital marketing agency", "Social media marketing agency", False, "india")),
        (" 9:00 PM  US — HVAC",
         dm_engine.generate_dm(None, "targetuser", "hvac", "HVAC contractor serving the Dallas area", True, "us")),
        (" 9:15 PM  US — Med Spa",
         dm_engine.generate_dm(None, "targetuser", "med spa", "Aesthetic clinic | Botox | Fillers", True, "us")),
        (" 9:30 PM  US — Coach",
         dm_engine.generate_dm(None, "targetuser", "coach", "Business coach helping entrepreneurs scale", True, "us")),
        (" 9:30 PM  US — Consultant",
         dm_engine.generate_dm(None, "targetuser", "consultant", "Marketing consultant for B2B companies", True, "us")),
    ]

    for label, msg in samples:
        print(f"  [{label}]")
        print(f"    \"{msg}\"")
        print()

    print()
    print("  SCHEDULE:")
    print("    10:00 AM IST → 10 DMs to digital marketing agencies (India)")
    print("     9:00 PM IST → 3 HVAC + 5 Med Spa + 2 Coach/Consultant (US)")
    print("    11:00 AM IST → Follow-ups")
    print("    10:00 PM IST → Follow-ups")
    print("    Hourly :30   → Reply check")


# ══════════════════════════════════════════════════════════════════════════════
# 2. FACEBOOK
# ══════════════════════════════════════════════════════════════════════════════

def audit_facebook():
    _header("CHANNEL 2: FACEBOOK POSTS + DMs")

    # Session file
    session_file = ROOT / "fb_outreach" / "session_fb.txt"
    _check("FB session file", session_file.exists(),
           "present" if session_file.exists() else "missing — run fb_outreach/main.py --post once locally")

    # Credentials
    _check("FACEBOOK_EMAIL env", bool(os.getenv("FACEBOOK_EMAIL")))
    _check("FACEBOOK_PASSWORD env", bool(os.getenv("FACEBOOK_PASSWORD")))

    # Chrome driver
    import shutil
    chrome = shutil.which("chromedriver") or (ROOT / "fb_outreach" / "chromedriver.exe").exists()
    _check("ChromeDriver found", bool(chrome))

    # FB DB
    fb_db_path = ROOT / "fb_outreach" / "fb_outreach.db"
    if fb_db_path.exists():
        conn = sqlite3.connect(fb_db_path)
        groups = conn.execute("SELECT COUNT(*) FROM fb_groups WHERE status='active'").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM fb_groups WHERE status='pending'").fetchone()[0]
        posts = conn.execute("SELECT COUNT(*) FROM fb_posts").fetchone()[0]
        dms = conn.execute("SELECT COUNT(*) FROM fb_dms").fetchone()[0]
        conn.close()
        _check("FB SQLite DB", True, f"groups_active={groups} | groups_pending={pending} | posts={posts} | dms={dms}")
        if groups == 0:
            print(f"  {WARN} No active groups yet — run: python fb_outreach/main.py --join")
    else:
        _check("FB SQLite DB", False, "will be created on first run")

    # Sample posts
    print()
    print("  SAMPLE POSTS (not sent — review before enabling):")
    print()

    import fb_posts

    post_samples = [
        ("US/Australia — HVAC", fb_posts.get_post("hvac")),
        ("US/Australia — Med Spa", fb_posts.get_post("med spa")),
        ("US/Australia — Coach", fb_posts.get_post("coach")),
        ("India — Business Owner", fb_posts.get_post("business_owner")),
    ]

    for label, post in post_samples:
        print(f"  [{label}]")
        for line in post.strip().splitlines():
            print(f"    {line}")
        print()

    # Group requirements
    print()
    print("  FACEBOOK GROUP REQUIREMENTS:")
    print("    US/Australia — All niches: min 500 members (default)")
    print("    US Business owners: min 30,000 members")
    print("    UK — Coaches: min 3,000 members")
    print("    UK — Business owners: min 5,000 members")
    print("    UK — HVAC: min 500 members")
    print("    Australia — Business owners: min 3,000 members")
    print("    India — Business owners: min 500 members")
    print()
    print("  POSTS SCHEDULE:")
    print("    Morning 10 AM: post in US/Australia groups (HVAC, Med Spa, Coach)")
    print("    Morning 10 AM: post in India business owner groups")
    print()
    print("  DMs SCHEDULE (15/day):")
    print("    Morning: 5 digital marketing agencies (5 go to Gmail instead of DM)")
    print("    Evening: 5 HVAC + 5 Med Spa + 3 Coach + 2 Consultant = 15 total")


# ══════════════════════════════════════════════════════════════════════════════
# 3. GMAIL
# ══════════════════════════════════════════════════════════════════════════════

def audit_gmail(create_drafts: bool = True):
    _header("CHANNEL 3: GMAIL EMAIL CAMPAIGNS")

    # Check credentials
    has_client_id     = bool(os.getenv("GMAIL_CLIENT_ID"))
    has_secret        = bool(os.getenv("GMAIL_CLIENT_SECRET"))
    has_refresh       = bool(os.getenv("GMAIL_REFRESH_TOKEN"))
    has_sender        = bool(os.getenv("GMAIL_SENDER_EMAIL"))

    _check("GMAIL_CLIENT_ID env",     has_client_id)
    _check("GMAIL_CLIENT_SECRET env", has_secret)
    _check("GMAIL_REFRESH_TOKEN env", has_refresh)
    _check("GMAIL_SENDER_EMAIL env",  has_sender)

    gmail_ready = all([has_client_id, has_secret, has_refresh, has_sender])

    if gmail_ready:
        print()
        print(f"  {INFO} Gmail configured — checking API connection...")
        try:
            import asyncio
            from services.gmail import provider_status
            status = asyncio.run(provider_status(live=True))
            _check("Gmail API connection", status.get("status") not in ("error", "not_configured"),
                   f"sent_today={status.get('sent_today', '?')} | cap={status.get('daily_cap', 20)} | "
                   f"remaining={status.get('remaining_today', '?')}")
        except Exception as e:
            _check("Gmail API connection", False, str(e)[:80])

    import email_templates as tpl

    # Sample emails
    print()
    print("  SAMPLE EMAILS (morning India campaign — drafts only):")
    print()

    morning_types = [
        ("Digital Marketing Agency x4", "digital_marketing_agency"),
        ("Fintech Firm x3", "fintech"),
        ("Business Owner x3", "business_owner"),
    ]
    for label, t in morning_types:
        subj, body = tpl.get_morning_india(t)
        print(f"  [{label}]")
        print(f"  Subject: {subj}")
        print(f"  ─────────────────────────────────────────")
        for line in tpl.render(body, name="[Recipient]").strip().splitlines():
            print(f"  {line}")
        print()

    print()
    print("  SAMPLE EMAILS (evening HVAC campaign — drafts only):")
    print()

    evening_targets = [
        ("US HVAC x5", "us"),
        ("Australia HVAC x3", "au"),
        ("Canada HVAC x2", "ca"),
    ]
    for label, region in evening_targets:
        subj, body = tpl.get_evening_hvac(region)
        print(f"  [{label}]")
        print(f"  Subject: {subj}")
        print(f"  ─────────────────────────────────────────")
        for line in tpl.render(body, name="[Recipient]").strip().splitlines():
            print(f"  {line}")
        print()

    # Create actual Gmail drafts if configured
    if gmail_ready and create_drafts:
        print()
        print("  Creating Gmail drafts for review...")
        try:
            import asyncio
            from services.gmail import create_draft

            test_drafts = [
                # Morning India
                ("morning_india_dma", *tpl.get_morning_india("digital_marketing_agency")),
                ("morning_india_fintech", *tpl.get_morning_india("fintech")),
                ("morning_india_biz", *tpl.get_morning_india("business_owner")),
                # Evening HVAC
                ("evening_us_hvac", *tpl.get_evening_hvac("us")),
                ("evening_au_hvac", *tpl.get_evening_hvac("au")),
                ("evening_ca_hvac", *tpl.get_evening_hvac("ca")),
            ]

            async def make_drafts():
                created = []
                for name, subj, body in test_drafts:
                    sender = os.getenv("GMAIL_SENDER_EMAIL", "")
                    # Draft to self — review in Gmail Drafts folder
                    draft_id = await create_draft(sender, f"[TEST] {subj}", tpl.render(body, name="[Recipient]"))
                    created.append((name, draft_id))
                    print(f"  {DRAFT} {name}: {'draft_id=' + draft_id if draft_id else 'FAILED'}")
                return created

            asyncio.run(make_drafts())
            print()
            print("  [✓] Open Gmail > Drafts to review all 6 test drafts before enabling sends")
        except Exception as e:
            print(f"  {WARN} Could not create drafts: {e}")
    elif not gmail_ready:
        print()
        print(f"  {WARN} Gmail not fully configured — drafts skipped")
        print("  Add to forge_system/.env:")
        print("    GMAIL_CLIENT_ID=...")
        print("    GMAIL_CLIENT_SECRET=...")
        print("    GMAIL_REFRESH_TOKEN=...")
        print("    GMAIL_SENDER_EMAIL=your@email.com")

    print()
    print("  GMAIL SCHEDULE:")
    print("    10:00 AM IST → 10 emails — India (4 DMA + 3 fintech + 3 biz owners)")
    print("     9:00 PM IST → 10 emails — HVAC (5 US + 3 AU + 2 CA)")
    print("  Run: python email_scheduler.py --test")
    print("  Run: python email_scheduler.py --morning  (creates drafts)")
    print("  Run: python email_scheduler.py --evening  (creates drafts)")


# ══════════════════════════════════════════════════════════════════════════════
# 4. BACKEND / INFRASTRUCTURE
# ══════════════════════════════════════════════════════════════════════════════

def audit_backend():
    _header("CHANNEL 4: BACKEND INFRASTRUCTURE")

    # Supabase
    _check("SUPABASE_URL env",    bool(os.getenv("SUPABASE_URL")))
    _check("SUPABASE_ANON_KEY env",  bool(os.getenv("SUPABASE_ANON_KEY")))
    _check("SUPABASE_SERVICE_KEY env", bool(os.getenv("SUPABASE_SERVICE_KEY")))

    supabase_ok = bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_KEY"))
    if supabase_ok:
        try:
            from database.supabase import db
            leads = db().table("outreach.leads").select("id", count="exact").limit(1).execute()
            _check("Supabase connection", True, f"leads_count≈{leads.count}")
        except Exception as e:
            _check("Supabase connection", False, str(e)[:80])

    # Redis
    _check("REDIS_URL env", bool(os.getenv("REDIS_URL")))
    redis_ok = bool(os.getenv("REDIS_URL"))
    if redis_ok:
        try:
            import asyncio
            from database.redis_client import r
            async def ping():
                client = r()
                return await client.ping()
            ok = asyncio.run(ping())
            _check("Redis connection", ok)
        except Exception as e:
            _check("Redis connection", False, str(e)[:60])

    # Anthropic (Jarvis Core)
    _check("ANTHROPIC_API_KEY env", bool(os.getenv("ANTHROPIC_API_KEY")),
           "required for Jarvis Core (agentic loop)")

    # Gemini keys
    gemini_count = sum(1 for k, v in os.environ.items()
                       if k.startswith("GEMINI_API_KEY") and v and "MODEL" not in k)
    _check("Gemini API keys", gemini_count > 0, f"{gemini_count} key(s) configured")

    # .env file
    env_file = ROOT / "forge_system" / ".env"
    _check(".env file", env_file.exists(), str(env_file))

    # Backend imports
    try:
        import fastapi
        _check("FastAPI installed", True)
    except ImportError:
        _check("FastAPI installed", False, "pip install fastapi")

    try:
        from instagrapi import Client
        _check("instagrapi installed", True)
    except ImportError:
        _check("instagrapi installed", False, "pip install instagrapi")

    try:
        import anthropic
        _check("anthropic SDK installed", True)
    except ImportError:
        _check("anthropic SDK installed", False, "pip install anthropic")


# ══════════════════════════════════════════════════════════════════════════════
# FINAL REPORT
# ══════════════════════════════════════════════════════════════════════════════

def final_report():
    _header("FULL SCHEDULE SUMMARY")

    print("""
  TIME (IST)    CHANNEL     ACTION
  ----------    ---------   -----------------------------------------
  10:00 AM      Instagram   10 DMs -- India digital marketing agencies
  10:00 AM      Facebook    Post in 4 groups (US/AU + India)
  10:00 AM      Gmail       10 emails -- India agencies/fintech/biz
  ---------     ---------   -----------------------------------------
   9:00 PM      Instagram   3 HVAC + 5 Med Spa + 2 Coach (US)
   9:00 PM      Facebook    15 DMs (5 DMA + HVAC/spa/coach)
   9:00 PM      Gmail       10 emails -- HVAC US/AU/CA
  ---------     ---------   -----------------------------------------
  11:00 AM      Instagram   Follow-ups
  10:00 PM      Instagram   Follow-ups
  Hourly :30    Instagram   Reply check (inbox scan)
  ---------     ---------   -----------------------------------------

  Daily totals:
    Instagram DMs: 20/day  (10 morning + 10 evening)
    Facebook posts: 4/day  (2 US/AU + 2 India)
    Facebook DMs:  15/day
    Gmail emails:  20/day  (10 morning + 10 evening)
    Total touchpoints: ~59/day
""")

    _header("AUDIT RESULTS")
    passed = sum(1 for v in results.values() if v)
    total  = len(results)
    failed = [k for k, v in results.items() if not v]

    print(f"\n  Score: {passed}/{total} checks passed")

    if failed:
        print(f"\n  {FAIL} Items to fix before deployment:")
        for item in failed:
            print(f"    - {item}")

    print()
    if passed == total:
        print("  ALL SYSTEMS GO. Ready to deploy.")
    elif passed >= total * 0.8:
        print("  MOSTLY READY. Fix the items above and you're good.")
    else:
        print("  NOT READY. Several critical systems need configuration.")

    print()
    print("  How to run each component:")
    print("    IG scheduler:    python ig_outreach/scheduler.py")
    print("    Email scheduler: python email_scheduler.py")
    print("    FB outreach:     python fb_outreach/main.py --post")
    print("    FB DMs:          python fb_outreach/main.py --dm")
    print("    Full agent:      python outreach_agent.py")
    print("    Backend API:     cd forge_system && uvicorn forge_system.main:app")
    print()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Virel Automation — Full System Test Audit")
    parser.add_argument("--channel", choices=["ig", "fb", "email", "backend", "all"], default="all")
    parser.add_argument("--no-drafts", action="store_true", help="Skip creating Gmail drafts")
    args = parser.parse_args()

    now = datetime.now(_IST).strftime("%Y-%m-%d %H:%M IST")

    print()
    print("=" * 65)
    print("  VIREL AUTOMATION -- FULL SYSTEM TEST AUDIT")
    print(f"  {now}")
    print("=" * 65)

    channel = args.channel
    create_drafts = not args.no_drafts

    if channel in ("ig", "all"):
        audit_instagram()
    if channel in ("fb", "all"):
        audit_facebook()
    if channel in ("email", "all"):
        audit_gmail(create_drafts=create_drafts)
    if channel in ("backend", "all"):
        audit_backend()

    final_report()


if __name__ == "__main__":
    main()
