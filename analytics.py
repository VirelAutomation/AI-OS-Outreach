"""
Virel Automation — Performance Analytics

Tracks reply rates, comment engagement, email performance, timing data.
Jarvis calls get_performance_report() to get charts + insights.

SQLite tables (auto-created):
  message_variants     — subject lines, DM templates, openers
  variant_performance  — sent/replied per variant per day
  timing_performance   — channel performance by hour of day
  comment_performance  — comment engagement by hashtag + region
"""

import sqlite3, json, os, logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

log  = logging.getLogger("virel.analytics")
_IST = timezone(timedelta(hours=5, minutes=30))
_DATA_DIR = Path(os.getenv("DATA_DIR", str(Path(__file__).parent))).expanduser()
_DB  = _DATA_DIR / "analytics.db"
_IG_DB = _DATA_DIR / "outreach.db" if (_DATA_DIR / "outreach.db").exists() else Path(__file__).parent / "ig_outreach" / "outreach.db"
_FB_DB = _DATA_DIR / "fb_outreach.db" if (_DATA_DIR / "fb_outreach.db").exists() else Path(__file__).parent / "fb_outreach" / "fb_outreach.db"


# ══════════════════════════════════════════════════════════════════════════════
# DB INIT
# ══════════════════════════════════════════════════════════════════════════════

def init_db():
    conn = sqlite3.connect(_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS message_variants (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            channel     TEXT NOT NULL,   -- ig_dm / ig_comment / fb_dm / email
            niche       TEXT,
            region      TEXT,
            variant_type TEXT,           -- opener / subject / body / full
            content     TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            active      INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS variant_performance (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            variant_id  INTEGER REFERENCES message_variants(id),
            sent        INTEGER DEFAULT 0,
            replied     INTEGER DEFAULT 0,
            clicked     INTEGER DEFAULT 0,
            date        TEXT DEFAULT (date('now','localtime'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS timing_performance (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            channel     TEXT NOT NULL,
            niche       TEXT,
            region      TEXT,
            hour_ist    INTEGER,         -- 0-23
            sent        INTEGER DEFAULT 0,
            replied     INTEGER DEFAULT 0,
            date        TEXT DEFAULT (date('now','localtime'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS comment_performance (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            hashtag      TEXT NOT NULL,
            niche        TEXT,
            region       TEXT,
            comments_sent INTEGER DEFAULT 0,
            profile_visits INTEGER DEFAULT 0,  -- estimated from follower gain
            replied_back  INTEGER DEFAULT 0,
            date         TEXT DEFAULT (date('now','localtime'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS email_performance (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign    TEXT,            -- morning_india / evening_hvac_us
            subject     TEXT,
            sent        INTEGER DEFAULT 0,
            opened      INTEGER DEFAULT 0,
            replied     INTEGER DEFAULT 0,
            date        TEXT DEFAULT (date('now','localtime'))
        )
    """)
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ASCII CHART
# ══════════════════════════════════════════════════════════════════════════════

def ascii_bar_chart(data: list[tuple], title: str = "", width: int = 40) -> str:
    """
    data: list of (label, value) tuples.
    Returns a formatted ASCII bar chart string.
    """
    if not data:
        return f"{title}\n  (no data)"

    max_val = max(v for _, v in data) or 1
    lines   = []
    if title:
        lines.append(title)
        lines.append("-" * (width + 20))

    for label, value in data:
        bar_len = int((value / max_val) * width)
        bar     = "#" * bar_len
        pct     = f"{value:.1f}" if isinstance(value, float) else str(value)
        lines.append(f"  {label:<25} {bar:<{width}} {pct}")

    lines.append("-" * (width + 20))
    return "\n".join(lines)


def ascii_line_chart(hours: list[int], values: list[int], title: str = "") -> str:
    """24-hour line chart for timing data."""
    if not values:
        return f"{title}\n  (no data)"

    max_val = max(values) or 1
    height  = 8
    lines   = []
    if title:
        lines.append(title)

    for row in range(height, 0, -1):
        threshold = (row / height) * max_val
        line = f"  {row * max_val // height:3d} |"
        for v in values:
            line += " # " if v >= threshold else "   "
        lines.append(line)

    lines.append("      " + "-" * (len(values) * 3 + 1))
    hour_label = "       " + "".join(f"{h:3d}" for h in hours)
    lines.append(hour_label)
    lines.append("       (hour IST)")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# DATA READERS (from existing DBs)
# ══════════════════════════════════════════════════════════════════════════════

def _get_ig_niche_performance(period_days: int = 30) -> list[dict]:
    if not _IG_DB.exists():
        return []
    try:
        conn = sqlite3.connect(_IG_DB)
        rows = conn.execute("""
            SELECT business_type, COUNT(*) as sent, SUM(replied) as replied,
                   SUM(replied) * 100.0 / COUNT(*) as reply_rate
            FROM ig_outreach
            WHERE dm_sent_at >= date('now', ?)
            GROUP BY business_type
            ORDER BY reply_rate DESC
        """, (f"-{period_days} days",)).fetchall()
        conn.close()
        return [{"niche": r[0] or "unknown", "sent": r[1], "replied": r[2] or 0,
                 "reply_rate": round(r[3] or 0, 1)} for r in rows]
    except Exception as e:
        return [{"error": str(e)}]


def _get_ig_region_performance(period_days: int = 30) -> list[dict]:
    if not _IG_DB.exists():
        return []
    try:
        conn = sqlite3.connect(_IG_DB)
        rows = conn.execute("""
            SELECT region, COUNT(*) as sent, SUM(replied) as replied,
                   SUM(replied) * 100.0 / COUNT(*) as reply_rate
            FROM ig_outreach
            WHERE dm_sent_at >= date('now', ?)
            GROUP BY region ORDER BY reply_rate DESC
        """, (f"-{period_days} days",)).fetchall()
        conn.close()
        return [{"region": r[0] or "unknown", "sent": r[1], "replied": r[2] or 0,
                 "reply_rate": round(r[3] or 0, 1)} for r in rows]
    except Exception as e:
        return [{"error": str(e)}]


def _get_ig_hourly_performance(period_days: int = 30) -> dict:
    """Returns hour → {sent, replied} for IST hours."""
    if not _IG_DB.exists():
        return {}
    try:
        conn = sqlite3.connect(_IG_DB)
        # dm_sent_at is stored in IST format already
        rows = conn.execute("""
            SELECT CAST(substr(dm_sent_at, 12, 2) AS INTEGER) as hour_ist,
                   COUNT(*) as sent, SUM(replied) as replied
            FROM ig_outreach
            WHERE dm_sent_at >= date('now', ?)
              AND length(dm_sent_at) >= 13
            GROUP BY hour_ist ORDER BY hour_ist
        """, (f"-{period_days} days",)).fetchall()
        conn.close()
        return {r[0]: {"sent": r[1], "replied": r[2] or 0} for r in rows}
    except Exception as e:
        return {}


def _get_ig_comment_stats() -> dict:
    if not _IG_DB.exists():
        return {}
    try:
        conn = sqlite3.connect(_IG_DB)
        total = conn.execute("SELECT COUNT(*) FROM ig_comments").fetchone()[0]
        today = conn.execute(
            "SELECT COUNT(*) FROM ig_comments WHERE commented_at LIKE ?",
            (f"{datetime.now(_IST).strftime('%Y-%m-%d')}%",)
        ).fetchone()[0]
        replied = conn.execute(
            "SELECT COUNT(*) FROM ig_comments WHERE replied_back=1"
        ).fetchone()[0]

        top_hashtags = conn.execute("""
            SELECT hashtag, COUNT(*) as cnt, SUM(replied_back) as replies
            FROM ig_comments GROUP BY hashtag ORDER BY replies DESC, cnt DESC LIMIT 10
        """).fetchall()

        conn.close()
        return {
            "total_comments": total,
            "today": today,
            "replied_back": replied,
            "reply_rate": f"{round(replied / max(1, total) * 100, 1)}%",
            "top_hashtags": [{"hashtag": r[0], "comments": r[1], "replies": r[2] or 0}
                             for r in top_hashtags],
        }
    except Exception as e:
        return {"error": str(e)}


def _get_daily_totals(days: int = 14) -> list[dict]:
    if not _IG_DB.exists():
        return []
    try:
        conn = sqlite3.connect(_IG_DB)
        rows = conn.execute("""
            SELECT date(dm_sent_at) as d, COUNT(*) as dms, SUM(replied) as replies
            FROM ig_outreach
            WHERE dm_sent_at >= date('now', ?)
            GROUP BY d ORDER BY d
        """, (f"-{days} days",)).fetchall()
        conn.close()
        return [{"date": r[0], "dms_sent": r[1], "replies": r[2] or 0,
                 "reply_rate": round((r[2] or 0) / max(1, r[1]) * 100, 1)} for r in rows]
    except Exception as e:
        return [{"error": str(e)}]


# ══════════════════════════════════════════════════════════════════════════════
# MAIN REPORT BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def get_performance_report(channel: str = "all", metric: str = "all",
                           period: str = "week") -> dict:
    """Main entry point for Jarvis analytics_performance tool."""
    init_db()

    period_days = {"today": 1, "week": 7, "month": 30, "all_time": 365}.get(period, 7)
    report = {
        "generated":  datetime.now(_IST).strftime("%Y-%m-%d %H:%M IST"),
        "period":     period,
        "period_days": period_days,
        "channel":    channel,
        "metric":     metric,
    }

    if channel in ("ig_dm", "all"):
        # ── Niche breakdown ──────────────────────────────────────────────────
        niche_data = _get_ig_niche_performance(period_days)
        report["ig_by_niche"] = niche_data
        if niche_data and not any("error" in d for d in niche_data):
            chart_data = [(d["niche"], d["reply_rate"]) for d in niche_data]
            report["chart_ig_niche_reply_rate"] = ascii_bar_chart(
                chart_data, f"IG Reply Rate by Niche (last {period_days}d) %"
            )

        # ── Region breakdown ─────────────────────────────────────────────────
        region_data = _get_ig_region_performance(period_days)
        report["ig_by_region"] = region_data
        if region_data and not any("error" in d for d in region_data):
            chart_data = [(d["region"], d["reply_rate"]) for d in region_data]
            report["chart_ig_region_reply_rate"] = ascii_bar_chart(
                chart_data, f"IG Reply Rate by Region (last {period_days}d) %"
            )

        # ── Hour-of-day ───────────────────────────────────────────────────────
        hourly = _get_ig_hourly_performance(period_days)
        if hourly:
            hours  = sorted(hourly.keys())
            values = [hourly[h]["sent"] for h in hours]
            replies = [hourly[h]["replied"] for h in hours]
            report["ig_hourly_sent"] = {h: hourly[h] for h in hours}
            report["chart_ig_timing_sent"] = ascii_line_chart(
                hours, values, f"IG DMs Sent by Hour IST (last {period_days}d)"
            )
            reply_rates = [round(hourly[h]["replied"] / max(1, hourly[h]["sent"]) * 100, 1)
                          for h in hours]
            report["chart_ig_timing_reply_rate"] = ascii_bar_chart(
                [(f"{h:02d}:00", r) for h, r in zip(hours, reply_rates)],
                f"IG Reply Rate by Hour IST %"
            )

        # ── Daily trend ───────────────────────────────────────────────────────
        daily = _get_daily_totals(period_days)
        report["ig_daily_trend"] = daily
        if daily:
            chart_data = [(d["date"][-5:], d["dms_sent"]) for d in daily]
            report["chart_ig_daily_volume"] = ascii_bar_chart(
                chart_data, f"IG DMs per Day (last {period_days}d)"
            )

    if channel in ("ig_comment", "all"):
        comment_stats = _get_ig_comment_stats()
        report["ig_comments"] = comment_stats
        if comment_stats.get("top_hashtags"):
            chart_data = [(f"#{h['hashtag'][:20]}", h["comments"])
                         for h in comment_stats["top_hashtags"]]
            report["chart_ig_top_hashtags"] = ascii_bar_chart(
                chart_data, "Top Hashtags by Comments Posted"
            )

    if channel in ("email", "all"):
        report["email_note"] = (
            "Email performance tracking requires reply tracking setup. "
            "Add GMAIL_TRACK_REPLIES=true to .env to enable open/reply tracking."
        )

    # ── Insights + recommendations ────────────────────────────────────────────
    insights = []
    niche_data = report.get("ig_by_niche", [])
    if niche_data and not any("error" in d for d in niche_data):
        best = max(niche_data, key=lambda x: x["reply_rate"], default=None)
        worst = min(niche_data, key=lambda x: x["reply_rate"], default=None)
        if best:
            insights.append(f"Best niche: {best['niche']} at {best['reply_rate']}% reply rate")
        if worst and worst != best:
            insights.append(f"Worst niche: {worst['niche']} at {worst['reply_rate']}% — consider new message variant")

    hourly = report.get("ig_hourly_sent", {})
    if hourly:
        best_hour = max(hourly, key=lambda h: hourly[h]["replied"] / max(1, hourly[h]["sent"]))
        insights.append(f"Best sending hour: {best_hour:02d}:00 IST "
                       f"({round(hourly[best_hour]['replied']/max(1,hourly[best_hour]['sent'])*100,1)}% reply rate)")

    report["insights"]        = insights
    report["recommendations"] = _generate_recommendations(report)

    return report


def _generate_recommendations(report: dict) -> list[str]:
    recs = []

    niche_data = report.get("ig_by_niche", [])
    if niche_data and not any("error" in d for d in niche_data):
        low_performers = [d for d in niche_data if d["reply_rate"] < 2.0 and d["sent"] >= 10]
        for lp in low_performers:
            recs.append(
                f"Run optimizer on '{lp['niche']}' DM variant — {lp['reply_rate']}% reply rate "
                f"over {lp['sent']} sends. Try new opener."
            )

    hourly = report.get("ig_hourly_sent", {})
    if hourly:
        hours_with_data = [h for h in hourly if hourly[h]["sent"] >= 5]
        if hours_with_data:
            best = max(hours_with_data, key=lambda h: hourly[h]["replied"] / max(1, hourly[h]["sent"]))
            worst = min(hours_with_data, key=lambda h: hourly[h]["replied"] / max(1, hourly[h]["sent"]))
            if best != worst:
                recs.append(
                    f"Shift DM timing toward {best:02d}:00 IST (best performance). "
                    f"Avoid {worst:02d}:00 IST (worst performance)."
                )

    comment_stats = report.get("ig_comments", {})
    if comment_stats:
        top = comment_stats.get("top_hashtags", [])
        no_engagement = [h for h in top if h["replies"] == 0 and h["comments"] >= 5]
        if no_engagement:
            recs.append(
                f"Hashtags with 0 reply-back: {', '.join('#' + h['hashtag'] for h in no_engagement[:3])}. "
                f"Swap these for higher-engagement alternatives."
            )

    if not recs:
        recs.append("Not enough data yet. Keep running for 7+ days to get meaningful insights.")

    return recs


def get_crl_learning_report(export: bool = True) -> dict:
    """Train/export reply-learning CRL artifacts from the live IG/FB DBs."""
    try:
        from intelligence_engine.crl_learning import build_learning_report
        return build_learning_report(export=export)
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# LOGGING HELPERS (called by outreach scripts)
# ══════════════════════════════════════════════════════════════════════════════

def log_timing(channel: str, niche: str, region: str, hour_ist: int, sent: int, replied: int = 0):
    init_db()
    conn = sqlite3.connect(_DB)
    conn.execute("""
        INSERT INTO timing_performance (channel, niche, region, hour_ist, sent, replied)
        VALUES (?,?,?,?,?,?)
    """, (channel, niche, region, hour_ist, sent, replied))
    conn.commit()
    conn.close()


def log_comment_hashtag(hashtag: str, niche: str, region: str, comments: int, replied_back: int = 0):
    init_db()
    conn = sqlite3.connect(_DB)
    # Upsert today's row
    today = datetime.now(_IST).strftime("%Y-%m-%d")
    existing = conn.execute(
        "SELECT id, comments_sent, replied_back FROM comment_performance "
        "WHERE hashtag=? AND date=?", (hashtag, today)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE comment_performance SET comments_sent=?, replied_back=? WHERE id=?",
            (existing[1] + comments, existing[2] + replied_back, existing[0])
        )
    else:
        conn.execute(
            "INSERT INTO comment_performance (hashtag, niche, region, comments_sent, replied_back, date) "
            "VALUES (?,?,?,?,?,?)",
            (hashtag, niche, region, comments, replied_back, today)
        )
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    channel = sys.argv[1] if len(sys.argv) > 1 else "all"
    period  = sys.argv[2] if len(sys.argv) > 2 else "week"

    report = get_performance_report(channel=channel, period=period)

    print(f"\n{'='*65}")
    print(f"  VIREL ANALYTICS — {channel.upper()} — last {period}")
    print(f"  Generated: {report['generated']}")
    print(f"{'='*65}\n")

    for key, val in report.items():
        if key.startswith("chart_"):
            print(val)
            print()
        elif key == "insights":
            print("INSIGHTS:")
            for i in val:
                print(f"  - {i}")
            print()
        elif key == "recommendations":
            print("RECOMMENDATIONS:")
            for r in val:
                print(f"  -> {r}")
            print()
        elif isinstance(val, list) and val and isinstance(val[0], dict):
            print(f"{key.upper()}:")
            for row in val:
                print(f"  {row}")
            print()
