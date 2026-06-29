"""
Virel Automation — Outreach Optimizer Agent

Reads performance data, identifies what's underperforming, generates new
message variants using Gemini, adjusts timing based on reply patterns,
and deploys improvements automatically.

Jarvis calls this via the optimizer_run tool. Can also run standalone.

Usage:
    python optimizer_agent.py                    # full optimize run (dry_run=True)
    python optimizer_agent.py --apply            # apply changes to live templates
    python optimizer_agent.py --channel email    # email only
    python optimizer_agent.py --channel ig_dm    # IG DMs only
    python optimizer_agent.py --focus timing     # timing adjustments only
    python optimizer_agent.py --focus openers    # new message openers only
"""

import os, sys, json, logging, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / "forge_system" / ".env")

import google.generativeai as genai

log  = logging.getLogger("virel.optimizer")
_IST = timezone(timedelta(hours=5, minutes=30))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [OPT] %(message)s")


# ══════════════════════════════════════════════════════════════════════════════
# GEMINI KEY
# ══════════════════════════════════════════════════════════════════════════════

def _get_gemini_key() -> str:
    for k, v in os.environ.items():
        if k.startswith("GEMINI_API_KEY") and v and "MODEL" not in k:
            return v
    return ""


# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS — what's underperforming?
# ══════════════════════════════════════════════════════════════════════════════

def _read_performance() -> dict:
    sys.path.insert(0, str(ROOT))
    try:
        import analytics
        return analytics.get_performance_report(channel="all", period="week")
    except Exception as e:
        return {"error": str(e)}


def _identify_weak_spots(perf: dict) -> list[dict]:
    """Return list of things that need improvement."""
    weak = []

    # Check IG niche reply rates
    for n in perf.get("ig_by_niche", []):
        if "error" in n:
            continue
        if n["sent"] >= 5 and n["reply_rate"] < 3.0:
            weak.append({
                "channel":  "ig_dm",
                "niche":    n["niche"],
                "issue":    f"Low reply rate: {n['reply_rate']}% over {n['sent']} sends",
                "priority": "high" if n["reply_rate"] < 1.0 else "medium",
            })

    # Check comment hashtag engagement
    comments = perf.get("ig_comments", {})
    for h in comments.get("top_hashtags", []):
        if h["comments"] >= 10 and h["replies"] == 0:
            weak.append({
                "channel":  "ig_comment",
                "hashtag":  h["hashtag"],
                "issue":    f"0 reply-backs from {h['comments']} comments",
                "priority": "medium",
            })

    # Check timing
    hourly = perf.get("ig_hourly_sent", {})
    if len(hourly) >= 3:
        best_rr = max(
            (hourly[h]["replied"] / max(1, hourly[h]["sent"]) for h in hourly),
            default=0
        )
        for h in hourly:
            rr = hourly[h]["replied"] / max(1, hourly[h]["sent"])
            if hourly[h]["sent"] >= 5 and rr < best_rr * 0.3:
                weak.append({
                    "channel": "ig_dm",
                    "issue":   f"Low performance at {h:02d}:00 IST ({rr*100:.1f}% vs best {best_rr*100:.1f}%)",
                    "priority": "low",
                    "type":    "timing",
                })

    return weak


# ══════════════════════════════════════════════════════════════════════════════
# VARIANT GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def _generate_new_dm_opener(niche: str, region: str, current_message: str = "") -> str:
    """Generate a new DM opener for a niche using Gemini."""
    key = _get_gemini_key()
    if not key:
        return ""

    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    region_context = {
        "india": "Indian digital marketing agencies and businesses",
        "us":    "US coaches, consultants, HVAC contractors, med spas",
    }.get(region, "business owners")

    current_note = f"\nCurrent message: '{current_message}'\nThis is getting <3% reply rate. Make something significantly different.\n" if current_message else ""

    prompt = f"""Write 3 different cold DM openers for Instagram for {region_context} in the {niche} niche.
We built an AI employee that handles their lead generation and outreach 24/7.
{current_note}
Rules:
- Max 30 words each
- Must start differently (no two can start with "hey")
- Conversational, not salesy
- Focus on their problem, not our product
- Plain ASCII only

Format: just the 3 messages, one per line, no numbering."""

    r = model.generate_content(prompt)
    return r.text.strip()


def _generate_new_email_openers(campaign: str, current_subject: str = "") -> list[dict]:
    """Generate new subject lines + opening sentences for email campaigns."""
    key = _get_gemini_key()
    if not key:
        return []

    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    if "india" in campaign:
        context = "Indian digital marketing agencies and fintech companies. Sender is also from India."
    elif "hvac" in campaign:
        context = "HVAC contractors in US, Australia, and Canada."
    else:
        context = "business owners"

    prompt = f"""Generate 5 cold email subject lines for outreach to {context}.
We built an AI employee that handles their lead gen and outreach 24/7.
{f"Current subject: '{current_subject}' — this needs improvement." if current_subject else ""}

Rules:
- Under 60 characters
- No clickbait or ALL CAPS
- Specific to their industry
- Conversational

Format: just the 5 subject lines, one per line."""

    r = model.generate_content(prompt)
    subjects = [s.strip() for s in r.text.strip().splitlines() if s.strip()][:5]

    return [{"subject": s, "campaign": campaign} for s in subjects]


# ══════════════════════════════════════════════════════════════════════════════
# TIMING OPTIMIZER
# ══════════════════════════════════════════════════════════════════════════════

def _optimise_timing(perf: dict) -> list[dict]:
    """Suggest timing adjustments based on performance data + timezone logic."""
    suggestions = []

    hourly = perf.get("ig_hourly_sent", {})
    if not hourly or len(hourly) < 4:
        return [{
            "type": "timing",
            "suggestion": "Need more data (7+ days) to optimise timing. Current schedule is fine.",
        }]

    best_hours = sorted(
        hourly.keys(),
        key=lambda h: hourly[h]["replied"] / max(1, hourly[h]["sent"]),
        reverse=True
    )[:3]

    for niche, region in [("digital_marketing_agency", "india"), ("hvac", "us"), ("coach", "us")]:
        # India: business hours 9am-6pm IST
        # US: 9am-6pm EST = 7:30pm-4:30am IST → evening IST works well
        if region == "india":
            optimal = [10, 11, 14, 15]
            current = 10  # our current schedule
        else:
            optimal = [20, 21, 22]  # IST (8-10pm = 2:30pm-4:30pm EST)
            current = 21

        if best_hours and best_hours[0] not in optimal:
            suggestions.append({
                "type":       "timing",
                "channel":    "ig_dm",
                "niche":      niche,
                "region":     region,
                "current":    f"{current:02d}:00 IST",
                "suggested":  f"{best_hours[0]:02d}:00 IST",
                "reason":     f"Best reply rate at {best_hours[0]:02d}:00 IST based on {len(hourly)} hours of data",
            })

    # Email timezone check
    suggestions.append({
        "type":     "timing",
        "channel":  "email",
        "current":  "10:00 AM IST (India), 9:00 PM IST (US/AU/CA)",
        "check":    "India emails at 10am IST = 4:30am UTC = good for India. US 9pm IST = 10:30am EST = good for US East.",
        "status":   "timezones OK",
    })

    return suggestions


# ══════════════════════════════════════════════════════════════════════════════
# APPLY CHANGES
# ══════════════════════════════════════════════════════════════════════════════

def _apply_email_subjects(new_subjects: list[dict], campaign: str):
    """Write new subject lines into email_templates.py."""
    templates_file = ROOT / "email_templates.py"
    if not templates_file.exists():
        return False
    try:
        content = templates_file.read_text(encoding="utf-8")
        new_lines = [f'    "{s["subject"]}",' for s in new_subjects if campaign in s.get("campaign", "")]

        if "india" in campaign:
            marker = "MORNING_SUBJECTS_INDIA = ["
        elif "hvac" in campaign:
            marker = "EVENING_SUBJECTS_HVAC = ["
        else:
            return False

        # Append new subjects to the existing list (don't remove old ones — A/B test)
        insert_at = content.index(marker) + len(marker)
        comment   = f"\n    # Added by optimizer {datetime.now(_IST).strftime('%Y-%m-%d')}:\n"
        new_content = content[:insert_at] + comment + "\n".join(new_lines) + content[insert_at:]
        templates_file.write_text(new_content, encoding="utf-8")
        return True
    except Exception as e:
        log.error(f"Failed to apply email subjects: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# MAIN OPTIMIZER
# ══════════════════════════════════════════════════════════════════════════════

def run(channel: str = "all", dry_run: bool = True, focus: str = "all") -> dict:
    """
    Main entry point. Called by Jarvis via optimizer_run tool.
    Returns a summary of what was found and what was (or would be) changed.
    """
    log.info(f"[OPTIMIZER] channel={channel} dry_run={dry_run} focus={focus}")

    perf  = _read_performance()
    weak  = _identify_weak_spots(perf)

    result = {
        "dry_run":        dry_run,
        "weak_spots":     weak,
        "actions_taken":  [],
        "actions_staged": [],
        "new_variants":   {},
        "timing_report":  [],
    }

    if not _get_gemini_key():
        result["error"] = "No Gemini key found — cannot generate variants"
        return result

    # ── Openers ───────────────────────────────────────────────────────────────
    if focus in ("openers", "all"):
        for spot in weak:
            if spot.get("channel") == "ig_dm" and spot.get("niche"):
                niche   = spot["niche"]
                region  = "india" if "india" in spot.get("niche", "").lower() or "digital" in spot.get("niche", "") else "us"
                log.info(f"[OPT] Generating new DM openers for {niche} ({region})...")
                new_msgs = _generate_new_dm_opener(niche, region)
                result["new_variants"][f"ig_dm_{niche}"] = new_msgs

                if dry_run:
                    result["actions_staged"].append({
                        "action":  "new_ig_dm_opener",
                        "niche":   niche,
                        "region":  region,
                        "preview": new_msgs[:200],
                    })
                else:
                    # Write to dm_engine.py as new template
                    result["actions_taken"].append({
                        "action": "generated_variants",
                        "niche":  niche,
                        "note":   "Review new_variants and add best to dm_engine.py manually",
                    })
                time.sleep(1)

        # Email openers
        if channel in ("email", "all"):
            for campaign in ["morning_india", "evening_hvac_us"]:
                log.info(f"[OPT] Generating new email subjects for {campaign}...")
                new_subjects = _generate_new_email_openers(campaign)
                result["new_variants"][f"email_{campaign}_subjects"] = new_subjects

                if not dry_run:
                    applied = _apply_email_subjects(new_subjects, campaign)
                    result["actions_taken"].append({
                        "action":  "updated_email_subjects",
                        "campaign": campaign,
                        "count":   len(new_subjects),
                        "applied": applied,
                    })
                else:
                    result["actions_staged"].append({
                        "action":   "new_email_subjects",
                        "campaign": campaign,
                        "preview":  [s["subject"] for s in new_subjects[:3]],
                    })
                time.sleep(1)

    # ── Timing ────────────────────────────────────────────────────────────────
    if focus in ("timing", "all"):
        timing_suggestions = _optimise_timing(perf)
        result["timing_report"] = timing_suggestions

        if not dry_run:
            for s in timing_suggestions:
                if s.get("type") == "timing" and s.get("suggested"):
                    result["actions_taken"].append({
                        "action":    "timing_recommendation",
                        "channel":   s.get("channel"),
                        "niche":     s.get("niche"),
                        "suggested": s.get("suggested"),
                        "note":      "Update scheduler manually to change send time",
                    })

    # ── Summary ───────────────────────────────────────────────────────────────
    result["summary"] = {
        "weak_spots_found":   len(weak),
        "variants_generated": len(result["new_variants"]),
        "actions_taken":      len(result["actions_taken"]),
        "actions_staged":     len(result["actions_staged"]),
        "next_step": (
            "Review new_variants above and update dm_engine.py / email_templates.py with the best ones. "
            "Run with --apply to auto-append email subjects."
        ) if dry_run else "Changes applied. Monitor reply rates over next 48h.",
    }

    log.info(f"[OPTIMIZER] Done — {len(weak)} issues | {len(result['new_variants'])} variants generated")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse, sys
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Virel Outreach Optimizer")
    parser.add_argument("--channel", choices=["all", "email", "ig_dm", "ig_comment"], default="all")
    parser.add_argument("--focus",   choices=["all", "openers", "timing", "niche"], default="all")
    parser.add_argument("--apply",   action="store_true", help="Apply changes (default: dry run)")
    args = parser.parse_args()

    result = run(channel=args.channel, dry_run=not args.apply, focus=args.focus)

    print(f"\n{'='*65}")
    print(f"  OPTIMIZER RESULTS")
    print(f"  Mode: {'DRY RUN' if not args.apply else 'LIVE'} | {datetime.now(_IST).strftime('%Y-%m-%d %H:%M IST')}")
    print(f"{'='*65}\n")

    print(f"Weak spots found: {len(result['weak_spots'])}")
    for w in result["weak_spots"]:
        print(f"  [{w.get('priority','?').upper()}] {w.get('channel','')} — {w.get('issue','')}")

    print(f"\nNew variants generated: {len(result['new_variants'])}")
    for name, content in result["new_variants"].items():
        print(f"\n  [{name}]")
        if isinstance(content, list):
            for item in content:
                print(f"    {item}")
        else:
            for line in str(content).strip().splitlines():
                print(f"    {line}")

    print(f"\nTiming report:")
    for t in result.get("timing_report", []):
        print(f"  {t}")

    print(f"\nSummary: {result.get('summary', {})}")

    if result.get("actions_staged"):
        print(f"\nStaged actions (run --apply to execute):")
        for a in result["actions_staged"]:
            print(f"  {a}")

    if result.get("actions_taken"):
        print(f"\nActions taken:")
        for a in result["actions_taken"]:
            print(f"  {a}")
