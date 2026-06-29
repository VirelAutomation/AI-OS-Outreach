"""
jarvis_outreach.py
Jarvis intent engine for all outreach operations.

Handles:
  - Instagram DM runs (region, limit, niche)
  - Facebook group posts and DMs
  - Live config changes (limits, niches, follower ranges)
  - Status reports from both systems
  - Follow-up scheduling and reply checks
"""

import asyncio, json, re, subprocess, sys, logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

log = logging.getLogger("virel.jarvis.outreach")

_ROOT       = Path(__file__).parent.parent.parent.parent.absolute()
_IG_SCRIPT  = _ROOT / "ig_outreach"  / "main.py"
_FB_SCRIPT  = _ROOT / "fb_outreach"  / "main.py"
_CONFIG     = _ROOT / "outreach_config.json"
_IG_DB      = _ROOT / "ig_outreach"  / "outreach.db"
_FB_DB      = _ROOT / "fb_outreach"  / "fb_outreach.db"
_IG_LOG     = _ROOT / "ig_outreach"  / "outreach.log"
_FB_LOG     = _ROOT / "fb_outreach"  / "fb_outreach.log"


# ── Config helpers ────────────────────────────────────────────────────────────

def _load_config() -> dict:
    try:
        return json.loads(_CONFIG.read_text())
    except Exception:
        return {}


def _save_config(cfg: dict, updated_by: str = "jarvis"):
    cfg["last_updated"] = datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat()
    cfg["updated_by"]   = updated_by
    _CONFIG.write_text(json.dumps(cfg, indent=2))


def _num(text: str, default: int) -> int:
    m = re.search(r"\b(\d+)\b", text)
    return max(1, min(int(m.group(1)), 500)) if m else default


# ── Subprocess helpers ────────────────────────────────────────────────────────

def _fire_background(script: Path, args: list[str], log_file: Path) -> int:
    """Launch a long-running script as a detached background process. Returns PID."""
    proc = subprocess.Popen(
        [sys.executable, str(script)] + args,
        cwd=str(_ROOT),
        stdout=open(log_file, "a"),
        stderr=subprocess.STDOUT,
    )
    return proc.pid


def _run_sync(script: Path, args: list[str], timeout: int = 120) -> str:
    """Run subprocess and capture output — only for quick operations (<2 min)."""
    try:
        result = subprocess.run(
            [sys.executable, str(script)] + args,
            cwd=str(_ROOT),
            capture_output=True, text=True, timeout=timeout,
        )
        out = (result.stdout + result.stderr).strip()
        lines = [l for l in out.splitlines() if l.strip() and not l.startswith("HTTP")]
        return "\n".join(lines[-30:]) if lines else "Done."
    except subprocess.TimeoutExpired:
        return "Timed out — task is still running in background."
    except Exception as e:
        return f"Error: {e}"


# ── IG tools ──────────────────────────────────────────────────────────────────

async def ig_run(region: str = "auto", limit: int = 20) -> str:
    """Fire IG outreach as a background process — returns immediately."""
    cfg = _load_config()
    if not cfg.get("ig", {}).get("enabled", True):
        return "Instagram outreach is currently disabled. Say 'enable instagram' to turn it on."
    pid = _fire_background(_IG_SCRIPT, ["--region", region, "--limit", str(limit)], _IG_LOG)
    log.info(f"[IG] Outreach started — PID {pid} | region={region} limit={limit}")
    return (
        f"Instagram outreach started (PID {pid})\n"
        f"  region={region}  limit={limit}\n"
        f"Check progress: 'ig status' or view log at ig_outreach/outreach.log"
    )


def ig_status() -> str:
    """Pull IG stats from SQLite."""
    try:
        import sqlite3
        if not _IG_DB.exists():
            return "No Instagram DMs sent yet."
        conn  = sqlite3.connect(_IG_DB)
        total = conn.execute("SELECT COUNT(*) FROM ig_outreach").fetchone()[0]
        today = conn.execute(
            "SELECT COUNT(*) FROM ig_outreach WHERE dm_sent_at LIKE ?",
            (f"{datetime.now().strftime('%Y-%m-%d')}%",)
        ).fetchone()[0]
        pending_fu = conn.execute(
            "SELECT COUNT(*) FROM ig_followups WHERE status='pending'"
        ).fetchone()[0]
        recent = conn.execute(
            "SELECT username, business_type, followers, region, dm_sent_at "
            "FROM ig_outreach ORDER BY dm_sent_at DESC LIMIT 5"
        ).fetchall()
        conn.close()
        cfg   = _load_config()
        limit = cfg.get("ig", {}).get("daily_limit", 20)
        lines = [
            f"Instagram Outreach:",
            f"  Total DMs sent: {total}",
            f"  Today: {today}/{limit}",
            f"  Pending follow-ups: {pending_fu}",
            f"  Last 5:",
        ]
        for r in recent:
            lines.append(f"    @{r[0]} | {r[1]} | {r[2]} followers | {r[3]} | {str(r[4])[:10]}")
        return "\n".join(lines)
    except Exception as e:
        return f"IG status error: {e}"


def ig_followups() -> str:
    return _run_sync(_IG_SCRIPT, ["--followups"], timeout=300)


def ig_check_replies() -> str:
    return _run_sync(_IG_SCRIPT, ["--check-replies"], timeout=300)


# ── FB tools ──────────────────────────────────────────────────────────────────

async def fb_join(niche: str = None) -> str:
    args = ["--join"]
    if niche:
        args += ["--niche", niche]
    pid = _fire_background(_FB_SCRIPT, args, _FB_LOG)
    return f"Facebook group join started (PID {pid}){' niche=' + niche if niche else ''}\nCheck: 'fb status'"


async def fb_post(niche: str = None) -> str:
    args = ["--post"]
    if niche:
        args += ["--niche", niche]
    pid = _fire_background(_FB_SCRIPT, args, _FB_LOG)
    return f"Facebook posting started (PID {pid}){' niche=' + niche if niche else ''}\nCheck: 'fb status'"


async def fb_dm(niche: str = None) -> str:
    args = ["--dm"]
    if niche:
        args += ["--niche", niche]
    pid = _fire_background(_FB_SCRIPT, args, _FB_LOG)
    return f"Facebook DM outreach started (PID {pid}){' niche=' + niche if niche else ''}\nCheck: 'fb status'"


def fb_status() -> str:
    return _run_sync(_FB_SCRIPT, ["--status"], timeout=30)


# ── Config changes ────────────────────────────────────────────────────────────

def set_ig_limit(limit: int) -> str:
    cfg = _load_config()
    old = cfg.get("ig", {}).get("daily_limit", 20)
    cfg.setdefault("ig", {})["daily_limit"] = limit
    _save_config(cfg)
    return f"Instagram daily DM limit changed: {old} -> {limit}"


def set_fb_post_limit(limit: int) -> str:
    cfg = _load_config()
    old = cfg.get("fb", {}).get("daily_post_limit", 10)
    cfg.setdefault("fb", {})["daily_post_limit"] = limit
    _save_config(cfg)
    return f"Facebook daily post limit changed: {old} -> {limit}"


def set_fb_dm_limit(limit: int) -> str:
    cfg = _load_config()
    old = cfg.get("fb", {}).get("daily_dm_limit", 20)
    cfg.setdefault("fb", {})["daily_dm_limit"] = limit
    _save_config(cfg)
    return f"Facebook daily DM limit changed: {old} -> {limit}"


def set_follower_range(min_f: int, max_f: int) -> str:
    cfg = _load_config()
    cfg.setdefault("ig", {})["follower_min"] = min_f
    cfg.setdefault("ig", {})["follower_max"] = max_f
    _save_config(cfg)
    return f"Instagram follower range set: {min_f} to {max_f}"


def set_ig_region(region: str) -> str:
    if region not in ("india", "us", "auto"):
        return f"Invalid region '{region}'. Use: india, us, auto"
    cfg = _load_config()
    cfg.setdefault("ig", {})["region"] = region
    _save_config(cfg)
    return f"Instagram region set to: {region.upper()}"


def set_us_niches(niches: list[str]) -> str:
    valid = {"hvac", "med spa", "coach", "realtor", "digital marketing agency", "interior designer"}
    cleaned = [n.lower() for n in niches if n.lower() in valid]
    if not cleaned:
        return f"No valid niches found. Valid options: {', '.join(valid)}"
    cfg = _load_config()
    cfg.setdefault("ig", {})["us_niches"] = cleaned
    cfg.setdefault("fb", {})["niches"]    = cleaned
    _save_config(cfg)
    return f"US niches updated to: {', '.join(cleaned)}"


def set_india_niches(niches: list[str]) -> str:
    valid = {"digital marketing agency", "real estate", "interior designer", "realtor"}
    cleaned = [n.lower() for n in niches if n.lower() in valid]
    if not cleaned:
        return f"No valid India niches. Options: {', '.join(valid)}"
    cfg = _load_config()
    cfg.setdefault("ig", {})["india_niches"] = cleaned
    _save_config(cfg)
    return f"India niches updated to: {', '.join(cleaned)}"


def toggle_ig(enabled: bool) -> str:
    cfg = _load_config()
    cfg.setdefault("ig", {})["enabled"] = enabled
    _save_config(cfg)
    return f"Instagram outreach {'enabled' if enabled else 'disabled'}"


def toggle_fb(enabled: bool) -> str:
    cfg = _load_config()
    cfg.setdefault("fb", {})["enabled"] = enabled
    _save_config(cfg)
    return f"Facebook outreach {'enabled' if enabled else 'disabled'}"


def show_config() -> str:
    cfg = _load_config()
    ig  = cfg.get("ig", {})
    fb  = cfg.get("fb", {})
    return (
        f"Current Outreach Config:\n\n"
        f"Instagram:\n"
        f"  Enabled:        {ig.get('enabled', True)}\n"
        f"  Daily limit:    {ig.get('daily_limit', 20)} DMs\n"
        f"  Follower range: {ig.get('follower_min', 300)} - {ig.get('follower_max', 1500)}\n"
        f"  Region:         {ig.get('region', 'auto')}\n"
        f"  India niches:   {', '.join(ig.get('india_niches', []))}\n"
        f"  US niches:      {', '.join(ig.get('us_niches', []))}\n\n"
        f"Facebook:\n"
        f"  Enabled:        {fb.get('enabled', True)}\n"
        f"  Post limit:     {fb.get('daily_post_limit', 10)}/day\n"
        f"  DM limit:       {fb.get('daily_dm_limit', 20)}/day\n"
        f"  Niches:         {', '.join(fb.get('niches', []))}\n\n"
        f"Last updated: {cfg.get('last_updated', 'never')}"
    )


def show_log(system: str = "ig", lines: int = 20) -> str:
    log_file = _IG_LOG if system == "ig" else _FB_LOG
    if not log_file.exists():
        return f"No {system.upper()} log file yet."
    try:
        content = log_file.read_text(encoding="utf-8", errors="replace")
        last_lines = content.strip().splitlines()[-lines:]
        return f"{system.upper()} log (last {lines} lines):\n" + "\n".join(last_lines)
    except Exception as e:
        return f"Could not read log: {e}"


def full_status() -> str:
    ig = ig_status()
    fb = fb_status()
    cfg = show_config()
    return f"{ig}\n\n{fb}\n\n{cfg}"
