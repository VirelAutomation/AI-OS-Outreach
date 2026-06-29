"""
jarvis_strategic.py — The Strategic Brain.

Upgrades Jarvis from intent-matching to true agentic planning.

When you say "20x sales", this agent:
  1. Reads current state (DMs/day, reply rate, conversion rate)
  2. Calculates what's needed (accounts, DM volume, platforms, timing)
  3. Builds an execution plan with HJB-optimal scheduling
  4. Executes it — actually starts runs, not just advises
  5. Monitors results and replans continuously

Uses Claude with proper tool calling — not keyword matching.
Claude decides which tools to call and in what order.
"""

import os, json, subprocess, sys, sqlite3, logging, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import anthropic

log  = logging.getLogger("virel.jarvis.strategic")
_IST = timezone(timedelta(hours=5, minutes=30))

_ROOT      = Path(__file__).parent.parent.parent.parent.absolute()
_IG_DB     = _ROOT / "ig_outreach" / "outreach.db"
_FB_DB     = _ROOT / "fb_outreach" / "fb_outreach.db"
_IG_LOG    = _ROOT / "ig_outreach" / "outreach.log"
_FB_LOG    = _ROOT / "fb_outreach" / "fb_outreach.log"
_AGENT_LOG = _ROOT / "agent.log"
_CONFIG    = _ROOT / "outreach_config.json"


# ── Tool definitions for Claude ───────────────────────────────────────────────

TOOLS = [
    {
        "name": "get_outreach_metrics",
        "description": (
            "Get current outreach performance metrics: DMs sent today/all-time, "
            "reply rates, platform health, pending queue. Essential before planning."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_lead_pipeline",
        "description": (
            "Get the full lead pipeline: how many leads collected, replied, "
            "booked calls, converted to sales. Needed to calculate conversion rate."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "calculate_scale_plan",
        "description": (
            "Given a growth target (e.g. '20x sales', '100 leads per day'), "
            "calculates required DM volume, number of accounts, platform mix, "
            "and daily schedule using HJB optimal control."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "e.g. '20x', '100 leads/day', '5 sales/week'"},
                "current_dms_per_day": {"type": "integer"},
                "current_leads_per_day": {"type": "number"},
                "conversion_rate": {"type": "number", "description": "lead-to-sale rate, 0-1"},
            },
            "required": ["target"],
        },
    },
    {
        "name": "get_system_capabilities",
        "description": (
            "Returns what the system can currently do: active FB/IG accounts, "
            "groups joined, daily limits, platform health, queued DMs."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "execute_outreach",
        "description": (
            "Actually executes an outreach run right now. "
            "Specify platform (fb/ig), niche, region, and DM limit."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "platform":  {"type": "string", "enum": ["fb", "ig", "both"]},
                "action":    {"type": "string", "enum": ["dm", "post", "join", "followups", "all"]},
                "niche":     {"type": "string", "enum": ["coach", "hvac", "med spa", "business_owner"]},
                "limit":     {"type": "integer", "description": "Max DMs to send"},
                "region":    {"type": "string", "enum": ["us", "india", "auto"]},
            },
            "required": ["platform", "action"],
        },
    },
    {
        "name": "update_daily_limits",
        "description": "Update the daily DM/post limits for FB and/or IG.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fb_dms":   {"type": "integer"},
                "ig_dms":   {"type": "integer"},
                "fb_posts": {"type": "integer"},
            },
            "required": [],
        },
    },
    {
        "name": "read_recent_logs",
        "description": "Read the last N lines of FB or IG outreach logs to diagnose issues.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "enum": ["fb", "ig", "agent"]},
                "lines":    {"type": "integer", "default": 30},
            },
            "required": ["platform"],
        },
    },
    {
        "name": "get_whatsapp_leads",
        "description": "Get collected WhatsApp numbers from FB profile scraping (Indian leads).",
        "input_schema": {
            "type": "object",
            "properties": {
                "nationality": {"type": "string", "enum": ["indian", "all"]},
            },
            "required": [],
        },
    },
    {
        "name": "run_outreach_agent",
        "description": (
            "Start the autonomous day-long outreach agent that runs all day, "
            "optimises timing, switches platforms when needed, and hits the daily target."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "background": {"type": "boolean", "description": "Run in background (non-blocking)"},
            },
            "required": [],
        },
    },
]


# ── Tool implementations ──────────────────────────────────────────────────────

def _tool_get_outreach_metrics() -> dict:
    result = {"fb": {}, "ig": {}, "timestamp": datetime.now(_IST).isoformat()}

    # Facebook metrics
    try:
        conn = sqlite3.connect(_FB_DB)
        today = datetime.now(_IST).strftime("%Y-%m-%d")
        result["fb"] = {
            "dms_today":         conn.execute("SELECT COUNT(*) FROM fb_dms WHERE sent_at LIKE ?", (f"{today}%",)).fetchone()[0],
            "dms_total":         conn.execute("SELECT COUNT(*) FROM fb_dms").fetchone()[0],
            "fr_only_today":     conn.execute("SELECT COUNT(*) FROM fb_dms WHERE sent_at LIKE ? AND message_sent LIKE '%(pending%'", (f"{today}%",)).fetchone()[0],
            "groups_active":     conn.execute("SELECT COUNT(*) FROM fb_groups WHERE status='active'").fetchone()[0],
            "queue_pending":     conn.execute("SELECT COUNT(*) FROM fb_dm_queue WHERE status='pending'").fetchone()[0],
            "posts_today":       conn.execute("SELECT COUNT(*) FROM fb_posts WHERE posted_at LIKE ? AND verified=1", (f"{today}%",)).fetchone()[0],
            "whatsapp_collected":conn.execute("SELECT COUNT(*) FROM fb_dms WHERE whatsapp_number IS NOT NULL").fetchone()[0],
        }
        conn.close()
    except Exception as e:
        result["fb"]["error"] = str(e)

    # Instagram metrics
    try:
        conn = sqlite3.connect(_IG_DB)
        today = datetime.now(_IST).strftime("%Y-%m-%d")
        result["ig"] = {
            "dms_today":   conn.execute("SELECT COUNT(*) FROM ig_outreach WHERE dm_sent_at LIKE ?", (f"{today}%",)).fetchone()[0],
            "dms_total":   conn.execute("SELECT COUNT(*) FROM ig_outreach").fetchone()[0],
            "replied":     conn.execute("SELECT COUNT(*) FROM ig_outreach WHERE replied=1").fetchone()[0],
            "followups_pending": conn.execute("SELECT COUNT(*) FROM ig_followups WHERE status='pending'").fetchone()[0],
        }
        # Reply rate
        total = result["ig"]["dms_total"]
        if total > 0:
            result["ig"]["reply_rate"] = round(result["ig"]["replied"] / total, 3)
        conn.close()
    except Exception as e:
        result["ig"]["error"] = str(e)

    return result


def _tool_get_lead_pipeline() -> dict:
    """Read lead/conversion data from Supabase or local DB."""
    try:
        conn  = sqlite3.connect(_IG_DB)
        total = conn.execute("SELECT COUNT(*) FROM ig_outreach").fetchone()[0]
        replied = conn.execute("SELECT COUNT(*) FROM ig_outreach WHERE replied=1").fetchone()[0]
        conn.close()

        fb_conn = sqlite3.connect(_FB_DB)
        fb_total = fb_conn.execute("SELECT COUNT(*) FROM fb_dms").fetchone()[0]
        fb_conn.close()

        total_contacts = total + fb_total
        reply_rate     = round(replied / max(1, total), 3)

        return {
            "total_contacts_ever":   total_contacts,
            "ig_dms_sent":           total,
            "fb_dms_sent":           fb_total,
            "replies_received":      replied,
            "reply_rate":            reply_rate,
            "estimated_call_rate":   round(reply_rate * 0.3, 3),   # 30% of replies → call
            "estimated_close_rate":  round(reply_rate * 0.3 * 0.2, 3),  # 20% of calls → sale
            "note": "Update close_rate with real data as you close deals",
        }
    except Exception as e:
        return {"error": str(e)}


def _tool_calculate_scale_plan(target: str, current_dms_per_day: int = 11,
                                current_leads_per_day: float = 0.5,
                                conversion_rate: float = 0.006) -> dict:
    """
    HJB-inspired resource planning.

    Given a growth target, computes:
    - Required daily DM volume
    - Number of accounts needed
    - Platform mix
    - Expected timeline
    """
    import re as _re

    # Parse multiplier or absolute target
    multiplier = 1
    abs_sales_day = None

    m = _re.search(r"(\d+)x", target.lower())
    if m:
        multiplier = int(m.group(1))

    m2 = _re.search(r"(\d+)\s*(?:leads?|contacts?)\s*/?\s*day", target.lower())
    if m2:
        abs_leads_day = int(m2.group(1))
    else:
        abs_leads_day = int(current_leads_per_day * multiplier) if multiplier > 1 else None

    m3 = _re.search(r"(\d+)\s*sales?\s*/?\s*(?:day|week|month)", target.lower())
    if m3:
        num = int(m3.group(1))
        if "week" in target: abs_sales_day = num / 7
        elif "month" in target: abs_sales_day = num / 30
        else: abs_sales_day = num

    # Calculate required DMs
    if abs_sales_day:
        required_leads_day = abs_sales_day / max(0.001, conversion_rate)
    elif abs_leads_day:
        required_leads_day = abs_leads_day
    else:
        required_leads_day = current_leads_per_day * multiplier

    # Assume 5% of DMs become leads (reply + interested)
    dm_to_lead_rate    = 0.05
    required_dms_day   = required_leads_day / max(0.001, dm_to_lead_rate)

    # Account requirements (safe DM limit per account)
    SAFE_FB_DMS_PER_ACCOUNT = 15   # per day
    SAFE_IG_DMS_PER_ACCOUNT = 5

    fb_accounts_needed = max(1, int(required_dms_day * 0.7 / SAFE_FB_DMS_PER_ACCOUNT) + 1)
    ig_accounts_needed = max(1, int(required_dms_day * 0.3 / SAFE_IG_DMS_PER_ACCOUNT) + 1)

    # Timeline (with current 1 account each)
    current_daily_capacity = (1 * SAFE_FB_DMS_PER_ACCOUNT) + (1 * SAFE_IG_DMS_PER_ACCOUNT)
    weeks_to_target = round(required_dms_day / max(1, current_daily_capacity), 1)

    return {
        "target_parsed":          target,
        "required_leads_per_day": round(required_leads_day, 1),
        "required_dms_per_day":   round(required_dms_day, 1),
        "platform_split": {
            "facebook": f"{round(required_dms_day * 0.7)} DMs/day across {fb_accounts_needed} accounts",
            "instagram": f"{round(required_dms_day * 0.3)} DMs/day across {ig_accounts_needed} accounts",
        },
        "accounts_needed": {
            "facebook": fb_accounts_needed,
            "instagram": ig_accounts_needed,
        },
        "current_capacity":  current_daily_capacity,
        "gap_to_fill":       round(required_dms_day - current_dms_per_day, 1),
        "weeks_at_current":  weeks_to_target,
        "immediate_actions": [
            f"Create {fb_accounts_needed - 1} more Facebook accounts (warm them for 7 days first)",
            f"Create {ig_accounts_needed - 1} more Instagram accounts",
            f"Join {fb_accounts_needed * 10} Facebook groups across all accounts",
            f"Send WhatsApp messages to {int(required_dms_day * 0.1)} collected numbers/day",
            f"Increase current FB DMs to {SAFE_FB_DMS_PER_ACCOUNT}/day and IG to {SAFE_IG_DMS_PER_ACCOUNT}/day",
        ],
        "daily_schedule": {
            "08:00 IST": "Indian leads — IG + FB DMs for India niche",
            "14:00 IST": "US leads — FB DMs for coach/consultant niche",
            "18:00 IST": "US leads prime time — IG + FB for US niches",
            "20:00 IST": "WhatsApp follow-ups to Indian numbers",
        },
    }


def _tool_get_system_capabilities() -> dict:
    metrics = _tool_get_outreach_metrics()
    try:
        fb_conn    = sqlite3.connect(_FB_DB)
        fb_groups  = fb_conn.execute("SELECT COUNT(*) FROM fb_groups WHERE status='active'").fetchone()[0]
        fb_pending = fb_conn.execute("SELECT COUNT(*) FROM fb_groups WHERE status='pending'").fetchone()[0]
        fb_conn.close()
    except Exception:
        fb_groups = fb_pending = 0

    cfg = {}
    try:
        cfg = json.loads(_CONFIG.read_text()) if _CONFIG.exists() else {}
    except Exception:
        pass

    return {
        "facebook": {
            "accounts":       1,
            "groups_active":  fb_groups,
            "groups_pending": fb_pending,
            "daily_dm_limit": int(os.getenv("FACEBOOK_DAILY_DM_LIMIT", "10")),
            "daily_post_limit": int(os.getenv("FACEBOOK_DAILY_POST_LIMIT", "10")),
            "session_saved":  (_ROOT / "fb_outreach" / "session_fb.txt").exists(),
            "dms_today":      metrics.get("fb", {}).get("dms_today", 0),
        },
        "instagram": {
            "accounts":       1,
            "daily_dm_limit": int(os.getenv("INSTAGRAM_DAILY_DM_LIMIT", "5")),
            "session_saved":  (_ROOT / "ig_outreach" / "session_virel.json").exists(),
            "dms_today":      metrics.get("ig", {}).get("dms_today", 0),
            "health":         "ok" if (_ROOT / "ig_outreach" / "session_virel.json").exists() else "no_session",
        },
        "whatsapp": {
            "numbers_collected": metrics.get("fb", {}).get("whatsapp_collected", 0),
            "sender_built":      False,
            "note": "WhatsApp sender not yet built — numbers are collected and stored",
        },
        "channels_available": ["facebook_dm", "facebook_post", "instagram_dm"],
        "channels_building":  ["whatsapp_dm", "linkedin_dm", "twitter_dm"],
    }


def _tool_execute_outreach(platform: str, action: str, niche: str = "coach",
                            limit: int = 10, region: str = "us") -> dict:
    script = _ROOT / ("fb_outreach" if platform in ("fb", "both") else "ig_outreach") / "main.py"
    args   = []

    if platform in ("fb", "both"):
        args = [f"--{action}", "--niche", niche]
        result = subprocess.run(
            [sys.executable, str(_ROOT / "fb_outreach" / "main.py")] + args,
            capture_output=True, text=True, timeout=7200, cwd=str(_ROOT),
        )
        return {"platform": "fb", "action": action, "exit_code": result.returncode,
                "output": (result.stdout + result.stderr)[-600:]}

    if platform == "ig":
        result = subprocess.run(
            [sys.executable, str(_ROOT / "ig_outreach" / "main.py"),
             "--region", region, "--niche", niche, "--limit", str(limit)],
            capture_output=True, text=True, timeout=3600, cwd=str(_ROOT),
        )
        return {"platform": "ig", "action": "dm", "exit_code": result.returncode,
                "output": (result.stdout + result.stderr)[-600:]}

    return {"error": f"Unknown platform: {platform}"}


def _tool_update_daily_limits(fb_dms: int = None, ig_dms: int = None, fb_posts: int = None) -> dict:
    updated = {}
    if fb_dms is not None:
        os.environ["FACEBOOK_DAILY_DM_LIMIT"] = str(fb_dms)
        updated["FACEBOOK_DAILY_DM_LIMIT"] = fb_dms
    if ig_dms is not None:
        os.environ["INSTAGRAM_DAILY_DM_LIMIT"] = str(ig_dms)
        updated["INSTAGRAM_DAILY_DM_LIMIT"] = ig_dms
    if fb_posts is not None:
        os.environ["FACEBOOK_DAILY_POST_LIMIT"] = str(fb_posts)
        updated["FACEBOOK_DAILY_POST_LIMIT"] = fb_posts

    # Persist to .env
    env_path = _ROOT / "forge_system" / ".env"
    try:
        lines = env_path.read_text().splitlines() if env_path.exists() else []
        new_lines = []
        keys_done = set()
        for line in lines:
            key = line.split("=")[0].strip()
            if key in updated:
                new_lines.append(f"{key}={updated[key]}")
                keys_done.add(key)
            else:
                new_lines.append(line)
        for key, val in updated.items():
            if key not in keys_done:
                new_lines.append(f"{key}={val}")
        env_path.write_text("\n".join(new_lines))
    except Exception as e:
        return {"updated": updated, "env_error": str(e)}

    return {"updated": updated, "status": "saved to .env"}


def _tool_read_recent_logs(platform: str, lines: int = 30) -> str:
    paths = {"fb": _FB_LOG, "ig": _IG_LOG, "agent": _AGENT_LOG}
    path  = paths.get(platform, _FB_LOG)
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        return "\n".join(content.splitlines()[-lines:])
    except Exception as e:
        return f"Could not read log: {e}"


def _tool_get_whatsapp_leads(nationality: str = "indian") -> dict:
    try:
        sys.path.insert(0, str(_ROOT / "fb_outreach"))
        import fb_db
        fb_db.init_db()
        nat  = nationality if nationality != "all" else None
        rows = fb_db.get_whatsapp_leads(nationality=nat)
        return {
            "count":  len(rows),
            "sample": rows[:5],
            "note":   "These are real phone numbers scraped from FB About pages. WhatsApp sender coming soon.",
        }
    except Exception as e:
        return {"error": str(e)}


def _tool_run_outreach_agent(background: bool = True) -> dict:
    agent_script = _ROOT / "outreach_agent.py"
    if background:
        subprocess.Popen(
            [sys.executable, str(agent_script)],
            cwd=str(_ROOT),
            stdout=open(_AGENT_LOG, "a"),
            stderr=subprocess.STDOUT,
        )
        return {"status": "started_background", "log": str(_AGENT_LOG)}
    result = subprocess.run(
        [sys.executable, str(agent_script), "--once"],
        capture_output=True, text=True, timeout=600, cwd=str(_ROOT),
    )
    return {"status": "completed", "output": result.stdout[-400:]}


# ── Tool dispatcher ───────────────────────────────────────────────────────────

def _dispatch_tool(name: str, inputs: dict) -> Any:
    dispatch = {
        "get_outreach_metrics":   lambda: _tool_get_outreach_metrics(),
        "get_lead_pipeline":      lambda: _tool_get_lead_pipeline(),
        "calculate_scale_plan":   lambda: _tool_calculate_scale_plan(**inputs),
        "get_system_capabilities":lambda: _tool_get_system_capabilities(),
        "execute_outreach":       lambda: _tool_execute_outreach(**inputs),
        "update_daily_limits":    lambda: _tool_update_daily_limits(**inputs),
        "read_recent_logs":       lambda: _tool_read_recent_logs(**inputs),
        "get_whatsapp_leads":     lambda: _tool_get_whatsapp_leads(**inputs),
        "run_outreach_agent":     lambda: _tool_run_outreach_agent(**inputs),
    }
    fn = dispatch.get(name)
    if not fn:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn()
    except Exception as e:
        return {"error": str(e), "tool": name}


# ── Main strategic agent ──────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Jarvis — the autonomous strategic brain for Virel Automation.

You have full access to the outreach system: Facebook, Instagram, WhatsApp numbers, logs, configs.

When given a goal, you:
1. CHECK current state (always call get_outreach_metrics first)
2. UNDERSTAND what's needed (use calculate_scale_plan for growth goals)
3. FIND every possible route to achieve the goal
4. EXECUTE — actually start runs, update configs, not just advise
5. REPORT clearly: what you did, what the plan is, what the user needs to do

Decision framework (Hamilton-Jacobi principle):
- Always ask: given current state and time remaining today, what action maximises leads?
- If FB is down, switch to IG. If IG is down, use WhatsApp numbers.
- If behind daily target, increase rate. If blocked, find another channel.
- Never just alert — always find a path forward.

For scaling goals ("20x sales", "more leads"):
- Calculate exact requirements (DMs, accounts, platforms)
- Tell the user specifically: how many accounts to create, what to post, when to run
- Start everything you can start immediately
- Give the user a clear TODO list for what only they can do (create accounts, verify phone)

Be direct. Execute. Report results."""


def run(user_message: str, session_history: list = None) -> str:
    """
    Main entry point. Takes a user message, runs the full agentic loop,
    returns Jarvis's final response.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "[JARVIS] ANTHROPIC_API_KEY not set — add it to .env to enable strategic mode."

    client   = anthropic.Anthropic(api_key=api_key)
    messages = list(session_history or [])
    messages.append({"role": "user", "content": user_message})

    log.info(f"[STRATEGIC] Goal: {user_message[:100]}")

    # Agentic loop — keeps going until Claude stops calling tools
    for iteration in range(12):    # max 12 tool calls per request
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Add assistant message to history
        messages.append({"role": "assistant", "content": response.content})

        # Check stop reason
        if response.stop_reason == "end_turn":
            # Extract text response
            for block in response.content:
                if hasattr(block, "text"):
                    log.info(f"[STRATEGIC] Done after {iteration+1} iterations")
                    return block.text
            return "[JARVIS] Done."

        if response.stop_reason != "tool_use":
            break

        # Process tool calls
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            tool_name  = block.name
            tool_input = block.input
            log.info(f"[TOOL] {tool_name}({json.dumps(tool_input)[:100]})")

            result     = _dispatch_tool(tool_name, tool_input)
            result_str = json.dumps(result, default=str)[:4000]   # cap size

            log.info(f"[TOOL] {tool_name} → {result_str[:100]}")

            tool_results.append({
                "type":        "tool_result",
                "tool_use_id": block.id,
                "content":     result_str,
            })

        messages.append({"role": "user", "content": tool_results})

    return "[JARVIS] Reached iteration limit — check agent.log for details."


# ── Async wrapper for jarvis_agent.py compatibility ──────────────────────────

async def strategic_respond(user_message: str, session_history: list = None) -> str:
    """Async wrapper — runs the synchronous Claude call in a thread."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run, user_message, session_history)
