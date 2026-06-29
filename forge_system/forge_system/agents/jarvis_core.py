"""
jarvis_core.py — Universal Agentic System (Gemini-powered).

Gemini 2.0 Flash as the reasoning core with 30+ tools.
Key rotation handles quota limits automatically.
"""

import os, sys, json, subprocess, sqlite3, logging, tempfile, time, traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
_ROOT = Path(__file__).parent.parent.parent.parent.absolute()
load_dotenv(_ROOT / "forge_system" / ".env")

import google.generativeai as genai

log  = logging.getLogger("virel.jarvis.core")
_IST = timezone(timedelta(hours=5, minutes=30))
_MEM_FILE = _ROOT / "jarvis_memory.json"


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY
# ══════════════════════════════════════════════════════════════════════════════

def _load_memory() -> dict:
    try:
        return json.loads(_MEM_FILE.read_text()) if _MEM_FILE.exists() else {}
    except Exception:
        return {}

def _save_memory(mem: dict):
    try:
        _MEM_FILE.write_text(json.dumps(mem, indent=2, default=str))
    except Exception:
        pass

def _remember(key: str, value: Any):
    mem = _load_memory()
    mem[key] = {"value": value, "timestamp": datetime.now(_IST).isoformat()}
    _save_memory(mem)

def _recall(key: str) -> Any:
    mem = _load_memory()
    entry = mem.get(key, {})
    return entry.get("value") if entry else None


# ══════════════════════════════════════════════════════════════════════════════
# TOOL REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

TOOLS = [

    # ── PIPELINE ──────────────────────────────────────────────────────────────

    {
        "name": "pipeline_view",
        "description": (
            "View the full sales pipeline. Shows leads by stage, MRR estimate, "
            "closed clients, active leads, pipeline conversion rates. "
            "Always call this for any revenue/pipeline/deals question."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "stage": {"type": "integer", "description": "Filter by stage 1-7 (optional)"},
                "niche": {"type": "string", "description": "Filter by niche (optional)"},
            },
            "required": [],
        },
    },
    {
        "name": "pipeline_add_lead",
        "description": "Add a new lead to the pipeline when they reply or show interest.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name":        {"type": "string"},
                "business":    {"type": "string"},
                "niche":       {"type": "string"},
                "platform":    {"type": "string", "description": "ig, fb, email, referral"},
                "profile_url": {"type": "string"},
                "offer":       {"type": "string", "description": "ai_voice_receptionist / ai_outreach_system / ai_ads / full_stack"},
                "region":      {"type": "string"},
                "notes":       {"type": "string"},
            },
            "required": ["name", "business", "niche", "platform"],
        },
    },
    {
        "name": "pipeline_move_lead",
        "description": (
            "Move a lead to the next stage. Stages: "
            "1=dm_sent, 2=replied, 3=call_booked, 4=call_done, 5=proposal_sent, 6=closed, 7=lost"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id":   {"type": "string"},
                "new_stage": {"type": "integer"},
                "notes":     {"type": "string"},
            },
            "required": ["lead_id", "new_stage"],
        },
    },

    # ── TASK ASSIGNMENT ───────────────────────────────────────────────────────

    {
        "name": "assign_task_to_jace",
        "description": (
            "Assign a task to Jace for things ONLY a human can do: "
            "cold calls, responding to a specific reply, doing a live demo, "
            "closing a deal, recording a video. Always include WHY and WHAT outcome you expect."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title":       {"type": "string"},
                "description": {"type": "string", "description": "Exact instructions — what to do, who to contact, what to say"},
                "priority":    {"type": "string", "description": "high / medium / low"},
                "due_by":      {"type": "string", "description": "today / tomorrow / this week"},
                "task_type":   {"type": "string", "description": "call / reply / demo / close / other"},
                "lead_id":     {"type": "string", "description": "Pipeline lead ID if related to a lead"},
            },
            "required": ["title", "description", "priority"],
        },
    },
    {
        "name": "get_tasks_for_jace",
        "description": "Get all pending tasks assigned to Jace. Call this to show him what he needs to do.",
        "input_schema": {
            "type": "object",
            "properties": {
                "priority": {"type": "string", "description": "Filter: high / medium / low (optional)"},
            },
            "required": [],
        },
    },
    {
        "name": "complete_task",
        "description": "Mark a task as completed once Jace has done it.",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },

    # ── DAILY BRIEF ───────────────────────────────────────────────────────────

    {
        "name": "daily_brief",
        "description": (
            "Generate a complete CEO brief: outreach performance, pipeline status, "
            "tasks for Jace, what Jarvis is doing autonomously today. "
            "Call this every morning or when asked for a full update."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },

    # ── SOVEREIGN INTELLIGENCE ENGINE ─────────────────────────────────────────

    {
        "name": "intelligence_scan",
        "description": (
            "Run MOIRA-class intelligence scan on the lead pipeline using 110 mathematical "
            "and physics techniques: Hamilton-Jacobi optimal control, Riemannian manifold "
            "trajectory analysis, Multi-Hypothesis Tracking (MHT) for intent, Bayesian "
            "conversion scoring, KL-divergence surprise detection, Kalman engagement "
            "filtering, quantum-ensemble strategy selection, Verkle pattern matching, "
            "and CRL causal attribution. Returns: hot leads, priority actions, "
            "proven causal mechanisms, optimal outreach policy."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "intelligence_lead",
        "description": (
            "Run the full MOIRA intelligence cycle for a specific lead. "
            "Returns: manifold position, curvature signals, geodesic projection, "
            "MHT intent state, Bayesian conversion probability, surprise score, "
            "Kalman engagement trend, HJ optimal action, quantum strategy ranking, "
            "and a plain-English action brief for Jarvis to execute."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id":   {"type": "string"},
                "event":     {"type": "string", "description": "Latest event: replied/asked_price/booked_call/etc."},
                "niche":     {"type": "string"},
                "region":    {"type": "string"},
                "stage":     {"type": "string"},
                "is_intervention": {"type": "boolean"},
            },
            "required": ["lead_id", "event"],
        },
    },
    {
        "name": "intelligence_counterfactual",
        "description": (
            "CRL counterfactual: 'What would have happened if we had done X instead of Y?' "
            "Returns the delta in conversion probability between actual and hypothetical outreach."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id":     {"type": "string"},
                "actual":      {"type": "array", "items": {"type": "string"},
                                "description": "What we actually did (list of intervention names)"},
                "hypothetical":{"type": "array", "items": {"type": "string"},
                                "description": "What we could have done instead"},
            },
            "required": ["lead_id", "actual", "hypothetical"],
        },
    },

    # ── OUTREACH ──────────────────────────────────────────────────────────────

    {
        "name": "outreach_run",
        "description": "Run social media outreach as background process. Returns immediately with PID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "enum": ["fb", "ig", "both"]},
                "action":   {"type": "string", "enum": ["dm", "post", "join", "followups", "discover", "all"]},
                "niche":    {"type": "string", "enum": ["coach", "hvac", "med_spa", "digital_marketing_agency", "consultant", "business_owner"]},
                "limit":    {"type": "integer"},
                "region":   {"type": "string", "enum": ["us", "india", "auto"]},
            },
            "required": ["platform", "action"],
        },
    },
    {
        "name": "outreach_status",
        "description": "Get current outreach stats: DMs sent today/total, reply rates, pending followups, comment counts.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "outreach_set_limit",
        "description": "Change daily DM or post limits for Facebook or Instagram.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "enum": ["fb", "ig"]},
                "type":     {"type": "string", "enum": ["dm", "post", "comment"]},
                "limit":    {"type": "integer"},
            },
            "required": ["platform", "type", "limit"],
        },
    },
    {
        "name": "outreach_agent_start",
        "description": "Start the autonomous day-long outreach agent (HJB-optimal, auto-recovers).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "ig_comment",
        "description": "Post comments on Instagram hashtag posts. 40/day safe limit. Background process.",
        "input_schema": {
            "type": "object",
            "properties": {
                "niche":    {"type": "string", "enum": ["coach", "digital_marketing_agency", "hvac", "med_spa", "consultant"]},
                "region":   {"type": "string", "enum": ["india", "us", "auto"]},
                "limit":    {"type": "integer"},
                "username": {"type": "string"},
            },
            "required": [],
        },
    },

    # ── LEADS ─────────────────────────────────────────────────────────────────

    {
        "name": "leads_list",
        "description": "List leads from the CRM.",
        "input_schema": {
            "type": "object",
            "properties": {
                "industry": {"type": "string"},
                "status":   {"type": "string"},
                "limit":    {"type": "integer"},
            },
            "required": [],
        },
    },
    {
        "name": "leads_add",
        "description": "Add a new lead to the CRM.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name":     {"type": "string"},
                "company":  {"type": "string"},
                "email":    {"type": "string"},
                "industry": {"type": "string"},
                "city":     {"type": "string"},
                "phone":    {"type": "string"},
            },
            "required": ["name", "company", "email"],
        },
    },
    {
        "name": "leads_search",
        "description": "Search leads by name, company, or email.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    },

    # ── EMAIL ─────────────────────────────────────────────────────────────────

    {
        "name": "email_send",
        "description": "Send an email via Gmail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to":      {"type": "string"},
                "subject": {"type": "string"},
                "body":    {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "email_draft",
        "description": "Create a Gmail draft (doesn't send).",
        "input_schema": {
            "type": "object",
            "properties": {
                "to":      {"type": "string"},
                "subject": {"type": "string"},
                "body":    {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "email_generate",
        "description": "Generate a cold outreach email using AI.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_name":  {"type": "string"},
                "company":    {"type": "string"},
                "industry":   {"type": "string"},
                "goal":       {"type": "string"},
                "tone":       {"type": "string"},
            },
            "required": ["lead_name", "goal"],
        },
    },

    # ── CONTENT ───────────────────────────────────────────────────────────────

    {
        "name": "content_generate",
        "description": "Generate any content: DM scripts, FB posts, email copy, ad copy, video scripts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "type":   {"type": "string"},
                "topic":  {"type": "string"},
                "niche":  {"type": "string"},
                "tone":   {"type": "string"},
                "length": {"type": "string", "enum": ["short", "medium", "long"]},
            },
            "required": ["type", "topic"],
        },
    },

    # ── ANALYTICS ─────────────────────────────────────────────────────────────

    {
        "name": "analytics_report",
        "description": "Overall performance report: DMs, posts, comments, reply rates, trends.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scope":  {"type": "string", "enum": ["outreach", "comments", "email", "all"]},
                "period": {"type": "string", "enum": ["today", "week", "month", "all_time"]},
            },
            "required": [],
        },
    },
    {
        "name": "analytics_performance",
        "description": (
            "Pull detailed performance data with ASCII charts: reply rates by niche/region, "
            "best email subject lines, comment engagement rates, time-of-day performance, "
            "timezone analysis. Use this to understand what's working."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel":  {"type": "string", "enum": ["ig_dm", "ig_comment", "fb_dm", "email", "all"]},
                "metric":   {"type": "string", "enum": ["reply_rate", "timing", "niche_breakdown", "variant_performance", "all"]},
                "period":   {"type": "string", "enum": ["week", "month", "all_time"]},
            },
            "required": [],
        },
    },
    {
        "name": "scale_plan",
        "description": "Given a growth goal, calculate DMs/day, accounts, platforms, timeline needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
            },
            "required": ["goal"],
        },
    },

    # ── OPTIMIZER ─────────────────────────────────────────────────────────────

    {
        "name": "optimizer_run",
        "description": (
            "Run the outreach optimizer agent. It reads all performance data, identifies what's "
            "underperforming, generates new message variants, A/B tests openers, adjusts send "
            "timing based on timezone + reply patterns. Deploys improvements automatically."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel":    {"type": "string", "enum": ["email", "ig_dm", "ig_comment", "all"]},
                "dry_run":    {"type": "boolean", "description": "If true, show what would change without applying"},
                "focus":      {"type": "string", "enum": ["openers", "timing", "niche", "all"]},
            },
            "required": [],
        },
    },

    # ── SYSTEM ────────────────────────────────────────────────────────────────

    {
        "name": "system_status",
        "description": "Full system health: all platforms, DB, logs, scheduled tasks, queues.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "read_logs",
        "description": "Read recent logs to diagnose issues.",
        "input_schema": {
            "type": "object",
            "properties": {
                "system": {"type": "string", "enum": ["fb", "ig", "agent", "backend", "email"]},
                "lines":  {"type": "integer"},
            },
            "required": [],
        },
    },
    {
        "name": "notify",
        "description": "Send Slack/Telegram notification.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "level":   {"type": "string", "enum": ["info", "warn", "error", "ok"]},
            },
            "required": ["message"],
        },
    },

    # ── MEMORY ────────────────────────────────────────────────────────────────

    {
        "name": "remember",
        "description": "Store a fact in persistent memory across sessions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key":   {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "recall",
        "description": "Retrieve a fact from persistent memory.",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        },
    },
    {
        "name": "memory_dump",
        "description": "See everything Jarvis currently remembers.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },

    # ── CODE EXECUTION ────────────────────────────────────────────────────────

    {
        "name": "run_code",
        "description": "Write and execute Python code for anything not covered by other tools.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code":        {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["code"],
        },
    },

    # ── WEB / FILES ───────────────────────────────────────────────────────────

    {
        "name": "web_search",
        "description": "Search the web for information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "file_read",
        "description": "Read a file from the project.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "file_write",
        "description": "Write content to a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path":    {"type": "string"},
                "content": {"type": "string"},
                "append":  {"type": "boolean"},
            },
            "required": ["path", "content"],
        },
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# TOOL IMPLEMENTATIONS
# ══════════════════════════════════════════════════════════════════════════════

def _t_outreach_run(platform, action, niche="coach", limit=10, region="auto") -> dict:
    scripts = {
        "fb": _ROOT / "fb_outreach" / "main.py",
        "ig": _ROOT / "ig_outreach" / "main.py",
    }
    ig_log = _ROOT / "ig_outreach" / "outreach.log"
    fb_log = _ROOT / "fb_outreach" / "fb_outreach.log"
    results = {}

    if platform in ("fb", "both"):
        args = [f"--{action}"]
        if niche: args += ["--niche", niche]
        proc = subprocess.Popen(
            [sys.executable, str(scripts["fb"])] + args,
            cwd=str(_ROOT), stdout=open(fb_log, "a"), stderr=subprocess.STDOUT,
        )
        results["fb"] = {"pid": proc.pid, "status": "started", "action": action}

    if platform in ("ig", "both"):
        proc = subprocess.Popen(
            [sys.executable, str(scripts["ig"]),
             "--region", region, "--niche", niche, "--limit", str(limit)],
            cwd=str(_ROOT), stdout=open(ig_log, "a"), stderr=subprocess.STDOUT,
        )
        results["ig"] = {"pid": proc.pid, "status": "started", "region": region, "limit": limit}

    results["note"] = "Running in background. Use outreach_status to check progress."
    return results


def _t_outreach_status() -> dict:
    sys.path.insert(0, str(_ROOT / "fb_outreach"))
    sys.path.insert(0, str(_ROOT / "ig_outreach"))
    result = {}
    try:
        import fb_db; fb_db.init_db()
        result["fb"] = fb_db.get_stats()
    except Exception as e:
        result["fb"] = {"error": str(e)}
    try:
        conn = sqlite3.connect(_ROOT / "ig_outreach" / "outreach.db")
        today = datetime.now(_IST).strftime("%Y-%m-%d")
        result["ig"] = {
            "dms_today":  conn.execute("SELECT COUNT(*) FROM ig_outreach WHERE dm_sent_at LIKE ?", (f"{today}%",)).fetchone()[0],
            "dms_total":  conn.execute("SELECT COUNT(*) FROM ig_outreach").fetchone()[0],
            "replied":    conn.execute("SELECT COUNT(*) FROM ig_outreach WHERE replied=1").fetchone()[0],
        }
        try:
            result["ig"]["comments_today"] = conn.execute(
                "SELECT COUNT(*) FROM ig_comments WHERE commented_at LIKE ?", (f"{today}%",)
            ).fetchone()[0]
            result["ig"]["comments_total"] = conn.execute("SELECT COUNT(*) FROM ig_comments").fetchone()[0]
        except Exception:
            pass
        conn.close()
    except Exception as e:
        result["ig"] = {"error": str(e)}
    return result


def _t_outreach_set_limit(platform, type, limit) -> dict:
    keys = {
        "fb": {"dm": "FACEBOOK_DAILY_DM_LIMIT", "post": "FACEBOOK_DAILY_POST_LIMIT"},
        "ig": {"dm": "INSTAGRAM_DAILY_DM_LIMIT", "post": "INSTAGRAM_DAILY_DM_LIMIT",
               "comment": "INSTAGRAM_DAILY_COMMENT_LIMIT"},
    }
    key = keys.get(platform, {}).get(type, f"{platform.upper()}_{type.upper()}_LIMIT")
    os.environ[key] = str(limit)
    env  = _ROOT / "forge_system" / ".env"
    lines = env.read_text().splitlines() if env.exists() else []
    new   = [f"{key}={limit}" if l.startswith(key) else l for l in lines]
    if not any(l.startswith(key) for l in lines):
        new.append(f"{key}={limit}")
    env.write_text("\n".join(new))
    return {"set": key, "value": limit, "status": "saved"}


def _t_ig_comment(niche="coach", region="auto", limit=20, username=None) -> dict:
    ig_log = _ROOT / "ig_outreach" / "outreach.log"
    if username:
        args = ["--comment-user", username]
    else:
        args = ["--comments", "--niche", niche, "--region", region, "--comment-limit", str(limit)]
    proc = subprocess.Popen(
        [sys.executable, str(_ROOT / "ig_outreach" / "main.py")] + args,
        cwd=str(_ROOT), stdout=open(ig_log, "a"), stderr=subprocess.STDOUT,
    )
    return {"pid": proc.pid, "status": "started", "niche": niche, "region": region, "limit": limit}


def _t_outreach_agent_start() -> dict:
    agent = _ROOT / "outreach_agent.py"
    log_f = _ROOT / "agent.log"
    proc = subprocess.Popen(
        [sys.executable, str(agent)],
        cwd=str(_ROOT), stdout=open(log_f, "a"), stderr=subprocess.STDOUT,
    )
    return {"pid": proc.pid, "status": "started", "log": str(log_f)}


def _t_leads_list(industry=None, status=None, limit=20) -> dict:
    try:
        sys.path.insert(0, str(_ROOT / "forge_system" / "forge_system"))
        from database.supabase import db
        q = db().table("outreach.leads").select("id,name,company,email,industry,status")
        if industry: q = q.ilike("industry", f"%{industry}%")
        if status:   q = q.eq("status", status)
        rows = q.limit(limit).execute().data or []
        return {"count": len(rows), "leads": rows}
    except Exception as e:
        return {"error": str(e)}


def _t_leads_add(name, company, email, industry="", city="", phone="") -> dict:
    try:
        sys.path.insert(0, str(_ROOT / "forge_system" / "forge_system"))
        from database.supabase import db
        db().table("outreach.leads").insert({
            "name": name, "company": company, "email": email,
            "industry": industry, "city": city, "phone": phone, "source": "jarvis",
        }).execute()
        return {"status": "added", "lead": f"{name} @ {company}"}
    except Exception as e:
        return {"error": str(e)}


def _t_leads_search(query, limit=10) -> dict:
    try:
        sys.path.insert(0, str(_ROOT / "forge_system" / "forge_system"))
        from database.supabase import db
        rows = db().table("outreach.leads").select("*").or_(
            f"name.ilike.%{query}%,company.ilike.%{query}%,email.ilike.%{query}%"
        ).limit(limit).execute().data or []
        return {"count": len(rows), "results": rows}
    except Exception as e:
        return {"error": str(e)}


def _t_email_send(to, subject, body, html=None) -> dict:
    try:
        sys.path.insert(0, str(_ROOT / "forge_system" / "forge_system"))
        from services.gmail import send_email
        import asyncio
        asyncio.run(send_email(to=to, subject=subject, body=body, html=html))
        return {"status": "sent", "to": to, "subject": subject}
    except Exception as e:
        return {"error": str(e)}


def _t_email_draft(to, subject, body) -> dict:
    try:
        sys.path.insert(0, str(_ROOT / "forge_system" / "forge_system"))
        from services.gmail import create_draft
        import asyncio
        asyncio.run(create_draft(to=to, subject=subject, body=body))
        return {"status": "draft_created", "to": to}
    except Exception as e:
        return {"error": str(e)}


def _t_email_generate(lead_name, goal, company="", industry="", tone="direct") -> str:
    key = _gemini_keys()[0] if _gemini_keys() else ""
    if not key:
        return "No Gemini key found"
    genai.configure(api_key=key)
    _m = os.getenv("GEMINI_MODEL_DEFAULT", "gemini-2.5-flash")
    r = genai.GenerativeModel(_m).generate_content(
        f"Write a {tone} cold outreach email.\n"
        f"Lead: {lead_name} at {company} ({industry})\nGoal: {goal}\n"
        f"We built an AI employee that handles lead gen and outreach 24/7.\n"
        f"Under 100 words. No fluff. Subject line included."
    )
    return r.text


def _t_content_generate(type, topic, niche="", tone="casual", length="medium") -> str:
    words = {"short": 50, "medium": 150, "long": 400}.get(length, 150)
    key = _gemini_keys()[0] if _gemini_keys() else ""
    if not key:
        return "No Gemini key"
    genai.configure(api_key=key)
    _m = os.getenv("GEMINI_MODEL_DEFAULT", "gemini-2.5-flash")
    r = genai.GenerativeModel(_m).generate_content(
        f"Write a {type} about: {topic}\n"
        f"Audience: {niche or 'business owners'}. Tone: {tone}. ~{words} words.\n"
        f"Context: AI employee for lead gen. Direct and specific."
    )
    return r.text


def _t_analytics_report(scope="all", period="week") -> dict:
    result = {"scope": scope, "period": period, "generated": datetime.now(_IST).isoformat()}
    try:
        sys.path.insert(0, str(_ROOT / "fb_outreach"))
        import fb_db; fb_db.init_db()
        result["fb"] = fb_db.get_stats()
    except Exception as e:
        result["fb_error"] = str(e)
    try:
        conn = sqlite3.connect(_ROOT / "ig_outreach" / "outreach.db")
        result["ig"] = {
            "total_dms":     conn.execute("SELECT COUNT(*) FROM ig_outreach").fetchone()[0],
            "replied":       conn.execute("SELECT COUNT(*) FROM ig_outreach WHERE replied=1").fetchone()[0],
            "pending_fu":    conn.execute("SELECT COUNT(*) FROM ig_followups WHERE status='pending'").fetchone()[0],
        }
        try:
            result["ig"]["total_comments"] = conn.execute("SELECT COUNT(*) FROM ig_comments").fetchone()[0]
        except Exception:
            pass
        conn.close()
    except Exception as e:
        result["ig_error"] = str(e)
    fb = result.get("fb", {})
    ig = result.get("ig", {})
    total_dms = fb.get("dms_total", 0) + ig.get("total_dms", 0)
    total_replied = ig.get("replied", 0)
    result["summary"] = {
        "total_dms":        total_dms,
        "total_posts":      fb.get("posts_total", 0),
        "replies_received": total_replied,
        "reply_rate":       f"{round(total_replied / max(1, total_dms) * 100, 1)}%",
        "total_comments":   ig.get("total_comments", 0),
        "pending_followups":fb.get("pending_followups", 0) + ig.get("pending_fu", 0),
    }
    return result


def _t_analytics_performance(channel="all", metric="all", period="week") -> dict:
    """Pull detailed performance data with ASCII charts."""
    sys.path.insert(0, str(_ROOT))
    try:
        import analytics
        return analytics.get_performance_report(channel=channel, metric=metric, period=period)
    except Exception as e:
        # Fallback: read raw DB data if analytics module unavailable
        result = {"channel": channel, "metric": metric, "period": period}
        try:
            conn = sqlite3.connect(_ROOT / "ig_outreach" / "outreach.db")
            today = datetime.now(_IST).strftime("%Y-%m-%d")
            # Reply rate by niche
            niche_data = conn.execute("""
                SELECT business_type, COUNT(*) as sent, SUM(replied) as replied
                FROM ig_outreach GROUP BY business_type ORDER BY sent DESC
            """).fetchall()
            result["ig_by_niche"] = [
                {"niche": r[0], "sent": r[1], "replied": r[2],
                 "reply_rate": f"{round(r[2]/max(1,r[1])*100,1)}%"}
                for r in niche_data if r[0]
            ]
            # Hour-of-day performance
            hour_data = conn.execute("""
                SELECT substr(dm_sent_at,12,2) as hour, COUNT(*) as sent, SUM(replied) as replied
                FROM ig_outreach GROUP BY hour ORDER BY hour
            """).fetchall()
            result["ig_by_hour"] = [
                {"hour": f"{r[0]}:00", "sent": r[1], "replied": r[2]}
                for r in hour_data if r[0]
            ]
            conn.close()
        except Exception as e2:
            result["error"] = str(e2)
        return result


def _t_scale_plan(goal) -> dict:
    sys.path.insert(0, str(_ROOT / "forge_system" / "forge_system"))
    from agents.jarvis_strategic import _tool_calculate_scale_plan, _tool_get_outreach_metrics
    metrics = _tool_get_outreach_metrics()
    fb      = metrics.get("fb", {})
    ig      = metrics.get("ig", {})
    current_dms = (fb.get("dms_today", 0) + ig.get("dms_today", 0)) or 11
    return _tool_calculate_scale_plan(goal, current_dms_per_day=current_dms)


def _t_optimizer_run(channel="all", dry_run=True, focus="all") -> dict:
    """Run the optimizer agent."""
    sys.path.insert(0, str(_ROOT))
    try:
        import optimizer_agent
        return optimizer_agent.run(channel=channel, dry_run=dry_run, focus=focus)
    except Exception as e:
        return {"error": str(e), "note": "Run: python optimizer_agent.py"}


def _t_system_status() -> dict:
    ig_session = _ROOT / "ig_outreach" / "session_virel.json"
    return {
        "timestamp": datetime.now(_IST).isoformat(),
        "outreach":  _t_outreach_status(),
        "files": {
            "fb_session":  (_ROOT / "fb_outreach" / "session_fb.txt").exists(),
            "ig_session":  ig_session.exists(),
            "ig_session_age_hours": round((time.time() - ig_session.stat().st_mtime) / 3600, 1) if ig_session.exists() else None,
            "agent_log":   (_ROOT / "agent.log").exists(),
            "memory":      _MEM_FILE.exists(),
        },
    }


def _t_read_logs(system="ig", lines=30) -> str:
    paths = {
        "fb":      _ROOT / "fb_outreach" / "fb_outreach.log",
        "ig":      _ROOT / "ig_outreach" / "outreach.log",
        "agent":   _ROOT / "agent.log",
        "backend": _ROOT / "forge_system" / "forge_system" / "backend.log",
        "email":   _ROOT / "email_scheduler.log" if (_ROOT / "email_scheduler.log").exists() else _ROOT / "agent.log",
    }
    path = paths.get(system, paths["ig"])
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        return "\n".join(content.splitlines()[-lines:])
    except Exception as e:
        return f"Cannot read log: {e}"


def _t_notify(message, level="info") -> dict:
    sys.path.insert(0, str(_ROOT / "fb_outreach"))
    try:
        import fb_alerts
        fb_alerts.alert(f"Jarvis: {message[:50]}", message, level=level)
        return {"sent": True}
    except Exception as e:
        return {"error": str(e)}


def _t_run_code(code, description="") -> dict:
    log.info(f"[CODE] {description or code[:60]}")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=str(_ROOT)) as f:
        preamble = (
            "import os, sys, json, sqlite3, subprocess, time, re\n"
            "from pathlib import Path\n"
            f"sys.path.insert(0, r'{_ROOT / 'fb_outreach'}')\n"
            f"sys.path.insert(0, r'{_ROOT / 'ig_outreach'}')\n"
            f"sys.path.insert(0, r'{_ROOT / 'forge_system' / 'forge_system'}')\n"
            f"ROOT = Path(r'{_ROOT}')\n\n"
        )
        f.write(preamble + code)
        tmp = f.name
    try:
        r = subprocess.run([sys.executable, tmp], capture_output=True, text=True, timeout=120, cwd=str(_ROOT))
        return {"exit_code": r.returncode, "output": (r.stdout + r.stderr).strip()[-2000:], "success": r.returncode == 0}
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "output": "Timed out", "success": False}
    except Exception as e:
        return {"exit_code": -1, "output": str(e), "success": False}
    finally:
        try: os.unlink(tmp)
        except Exception: pass


def _t_web_search(query, limit=5) -> dict:
    try:
        import urllib.request, urllib.parse
        url = f"https://ddg-api.herokuapp.com/search?query={urllib.parse.quote(query)}&limit={limit}"
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())
    except Exception:
        return {"note": "Web search not configured", "query": query}


def _t_file_read(path) -> str:
    try:
        return (_ROOT / path).read_text(encoding="utf-8", errors="replace")[:5000]
    except Exception as e:
        return f"Cannot read {path}: {e}"


def _t_file_write(path, content, append=False) -> dict:
    try:
        p = _ROOT / path
        p.parent.mkdir(parents=True, exist_ok=True)
        if append:
            with open(p, "a", encoding="utf-8") as f: f.write(content)
        else:
            p.write_text(content, encoding="utf-8")
        return {"written": str(path), "bytes": len(content)}
    except Exception as e:
        return {"error": str(e)}


# ── Pipeline & Task tools ─────────────────────────────────────────────────────

def _t_pipeline_view(stage=None, niche=None) -> dict:
    sys.path.insert(0, str(_ROOT))
    try:
        import pipeline
        return pipeline.get_pipeline(stage=stage, niche=niche)
    except Exception as e:
        return {"error": str(e)}


def _t_pipeline_add_lead(name, business, niche, platform,
                          profile_url="", offer="ai_outreach_system",
                          region="us", notes="") -> dict:
    sys.path.insert(0, str(_ROOT))
    try:
        import pipeline
        return pipeline.add_lead(name=name, business=business, niche=niche,
                                  platform=platform, profile_url=profile_url,
                                  offer=offer, region=region, notes=notes)
    except Exception as e:
        return {"error": str(e)}


def _t_pipeline_move_lead(lead_id, new_stage, notes="") -> dict:
    sys.path.insert(0, str(_ROOT))
    try:
        import pipeline
        return pipeline.move_lead(lead_id=lead_id, new_stage=new_stage, notes=notes)
    except Exception as e:
        return {"error": str(e)}


def _t_assign_task_to_jace(title, description, priority="medium",
                             due_by="today", task_type="call", lead_id=None) -> dict:
    sys.path.insert(0, str(_ROOT))
    try:
        import pipeline
        return pipeline.assign_task(title=title, description=description,
                                     priority=priority, due_by=due_by,
                                     task_type=task_type, lead_id=lead_id)
    except Exception as e:
        return {"error": str(e)}


def _t_get_tasks_for_jace(priority=None) -> dict:
    sys.path.insert(0, str(_ROOT))
    try:
        import pipeline
        tasks = pipeline.get_pending_tasks(priority=priority)
        return {"count": len(tasks), "tasks": tasks}
    except Exception as e:
        return {"error": str(e)}


def _t_complete_task(task_id) -> dict:
    sys.path.insert(0, str(_ROOT))
    try:
        import pipeline
        return pipeline.complete_task(task_id=task_id)
    except Exception as e:
        return {"error": str(e)}


def _t_daily_brief() -> dict:
    sys.path.insert(0, str(_ROOT))
    try:
        import pipeline
        brief    = pipeline.generate_brief()
        outreach = _t_outreach_status()
        brief["outreach"] = outreach
        return brief
    except Exception as e:
        return _t_outreach_status()


# ── Sovereign Intelligence Engine tools ───────────────────────────────────────

_sovereign_core = None

def _get_sovereign_core():
    global _sovereign_core
    if _sovereign_core is None:
        sys.path.insert(0, str(_ROOT))
        try:
            from intelligence_engine import SovereignCore
            _sovereign_core = SovereignCore()
        except Exception as e:
            log.error(f"[INTELLIGENCE] Failed to load SovereignCore: {e}")
            return None
    return _sovereign_core


def _t_intelligence_scan() -> dict:
    core = _get_sovereign_core()
    if not core:
        return {"error": "intelligence_engine not available", "status": "check numpy is installed"}
    try:
        return core.jarvis_intelligence_scan()
    except Exception as e:
        return {"error": str(e)}


def _t_intelligence_lead(lead_id: str, event: str, niche: str = "default",
                          region: str = "us", stage: str = "",
                          is_intervention: bool = False) -> dict:
    core = _get_sovereign_core()
    if not core:
        return {"error": "intelligence_engine not available"}
    try:
        # Register lead if new
        if lead_id not in core._lead_contexts:
            core.register_lead(lead_id, niche, region, "instagram", stage or "dm_sent")
        package = core.process_event(lead_id, event, is_intervention, stage)
        return {
            "lead_id":             package.lead_id,
            "timestamp":           package.timestamp,
            "geodesic":            package.geodesic_projection,
            "stability":           package.geodesic_stability,
            "intent":              f"{package.dominant_intent} ({package.intent_confidence:.0%})",
            "conversion_p":        package.conversion_probability,
            "tier":                package.probability_tier,
            "surprise":            package.surprise_score,
            "engagement":          f"{package.engagement_level:.2f} {package.engagement_trend}",
            "optimal_action":      package.optimal_action,
            "strategy":            package.optimal_strategy,
            "pattern":             f"{package.pattern_match} → {package.pattern_outcome}",
            "priority":            package.priority_score,
            "brief":               package.action_brief,
            "curvature": {
                "funnel":     package.funnel_curvature,
                "behavioral": package.behavioral_curvature,
                "coupled":    package.coupled_curvature,
                "temporal":   package.temporal_curvature,
            },
        }
    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()[-300:]}


def _t_intelligence_counterfactual(lead_id: str, actual: list,
                                    hypothetical: list) -> dict:
    core = _get_sovereign_core()
    if not core:
        return {"error": "intelligence_engine not available"}
    try:
        return core.causal.counterfactual(lead_id, actual, hypothetical)
    except Exception as e:
        return {"error": str(e)}


# ── Dispatcher ────────────────────────────────────────────────────────────────

def _dispatch(name: str, inputs: dict) -> Any:
    fn_map = {
        "outreach_run":          lambda: _t_outreach_run(**inputs),
        "outreach_status":       lambda: _t_outreach_status(),
        "outreach_set_limit":    lambda: _t_outreach_set_limit(**inputs),
        "outreach_agent_start":  lambda: _t_outreach_agent_start(),
        "ig_comment":            lambda: _t_ig_comment(**inputs),
        "leads_list":            lambda: _t_leads_list(**inputs),
        "leads_add":             lambda: _t_leads_add(**inputs),
        "leads_search":          lambda: _t_leads_search(**inputs),
        "email_send":            lambda: _t_email_send(**inputs),
        "email_draft":           lambda: _t_email_draft(**inputs),
        "email_generate":        lambda: _t_email_generate(**inputs),
        "content_generate":      lambda: _t_content_generate(**inputs),
        "analytics_report":      lambda: _t_analytics_report(**inputs),
        "analytics_performance": lambda: _t_analytics_performance(**inputs),
        "scale_plan":            lambda: _t_scale_plan(**inputs),
        "optimizer_run":         lambda: _t_optimizer_run(**inputs),
        "system_status":         lambda: _t_system_status(),
        "read_logs":             lambda: _t_read_logs(**inputs),
        "notify":                lambda: _t_notify(**inputs),
        "remember":              lambda: (_remember(inputs["key"], inputs["value"]), {"saved": True})[1],
        "recall":                lambda: {"value": _recall(inputs["key"])},
        "memory_dump":           lambda: _load_memory(),
        "run_code":              lambda: _t_run_code(**inputs),
        "web_search":            lambda: _t_web_search(**inputs),
        "file_read":             lambda: _t_file_read(**inputs),
        "file_write":            lambda: _t_file_write(**inputs),
        # ── CEO pipeline & task tools ──────────────────────────────────────────
        "pipeline_view":         lambda: _t_pipeline_view(**inputs),
        "pipeline_add_lead":     lambda: _t_pipeline_add_lead(**inputs),
        "pipeline_move_lead":    lambda: _t_pipeline_move_lead(**inputs),
        "assign_task_to_jace":   lambda: _t_assign_task_to_jace(**inputs),
        "get_tasks_for_jace":    lambda: _t_get_tasks_for_jace(**inputs),
        "complete_task":              lambda: _t_complete_task(**inputs),
        "daily_brief":                lambda: _t_daily_brief(),
        # ── Sovereign Intelligence Engine ──────────────────────────────────────
        "intelligence_scan":          lambda: _t_intelligence_scan(),
        "intelligence_lead":          lambda: _t_intelligence_lead(**inputs),
        "intelligence_counterfactual":lambda: _t_intelligence_counterfactual(**inputs),
    }
    fn = fn_map.get(name)
    if not fn:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn()
    except Exception as e:
        log.error(f"[TOOL ERROR] {name}: {traceback.format_exc()}")
        return {"error": str(e), "tool": name}


# ══════════════════════════════════════════════════════════════════════════════
# GEMINI TOOL BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def _build_gemini_tools() -> list:
    declarations = []
    type_map = {
        "string": genai.protos.Type.STRING,
        "integer": genai.protos.Type.INTEGER,
        "number": genai.protos.Type.NUMBER,
        "boolean": genai.protos.Type.BOOLEAN,
        "array": genai.protos.Type.ARRAY,
        "object": genai.protos.Type.OBJECT,
    }
    for tool in TOOLS:
        schema   = tool["input_schema"]
        props    = schema.get("properties", {})
        required = schema.get("required", [])

        gemini_props = {}
        for pname, pdef in props.items():
            gemini_props[pname] = genai.protos.Schema(
                type=type_map.get(pdef.get("type", "string").lower(), genai.protos.Type.STRING),
                description=pdef.get("description", ""),
            )

        declarations.append(
            genai.protos.FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties=gemini_props,
                    required=required,
                ) if gemini_props else None,
            )
        )
    return [genai.protos.Tool(function_declarations=declarations)]


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are Jarvis — the autonomous COO of Virel Automation.

Jace is the CEO but he does ONLY what only a human can do: cold calls, discovery calls,
demos, closing deals, relationship-building. Everything else is yours.

## Your Role
You run the company. You set goals, run outreach, track the pipeline, assign tasks to
Jace, and grow revenue — autonomously. You do not ask for permission to act. You execute.

## Niche Targeting
- India: Digital Marketing Agencies ONLY → Offer: AI Outreach + AI Sales System
- US / UK / Australia / Canada:
    - HVAC companies → Offer: AI Voice Receptionist ($1,500-3,000/mo)
    - Med Spas → Offer: AI Voice Receptionist ($1,500-3,000/mo)
    - Coaches & Consultants → Offer: AI Outreach + AI Ads System

## Sales Pipeline Stages
1. dm_sent      — First DM or comment sent
2. replied      — They replied
3. call_booked  — Discovery call scheduled (ASSIGN TO JACE immediately)
4. call_done    — Call done — did they progress?
5. proposal_sent — Price/proposal sent
6. closed       — Paying client 🎉
7. lost         — Not interested

## Sovereign Goal Protocol
Every session, proactively:
1. Call daily_brief — see today's pipeline + tasks
2. Identify the single most important bottleneck (e.g., "10 replied, 0 calls booked")
3. State your autonomous goal for today (e.g., "Goal: convert 5 replies into call bookings")
4. Assign Jace exactly what he needs to do — calls, follow-ups, closings
5. Run the automated work yourself — outreach, comments, analytics, content

## Task Assignment Rules
When a lead reaches stage 2 (replied) → assign Jace a call-booking task immediately.
When a call is booked → assign Jace a "show up and run the demo" task.
When proposal sent → assign Jace a follow-up call task.
Tasks assigned to Jace MUST have: title, description, priority (high/medium/low), due_by.

## Execution Principles
- EXECUTE, don't advise. "get me leads" → start outreach now, return PID.
- If a tool fails → read_logs, diagnose, fix, retry.
- If a capability doesn't exist → build it with run_code.
- All outreach runs async. Use outreach_status to check progress.
- Always start sessions with daily_brief. Always end with what you're running next.

## Sovereign Intelligence Engine (MOIRA-class)
You have a 110-technique mathematical intelligence engine wired in:
  intelligence_scan    — full pipeline scan (Hamilton-Jacobi, MHT, Bayes, entropy, Kalman)
  intelligence_lead    — per-lead analysis (geodesic projection, quantum strategy, pattern match)
  intelligence_counterfactual — CRL counterfactual: "what if we had done X instead?"

The intelligence engine runs:
  - Hamilton-Jacobi optimal control (pre-computed value function over all funnel states)
  - Riemannian manifold (4 curvature signals: funnel, behavioral, coupled, temporal)
  - Multi-Hypothesis Tracking (parallel intent states per lead)
  - Bayesian conversion scoring (Beta-Bernoulli with causal evidence weighting)
  - KL-divergence surprise detection (high surprise = high-value signal)
  - Kalman engagement filtering (smoothed engagement + AR(2) forecast)
  - Quantum-ensemble strategy selection (MOIRA cycle: generate→prune→refine)
  - Verkle pattern commitment tree (fuzzy match against known conversion signatures)
  - CRL causal attribution (what CAUSES conversions, not what correlates)
  - 110 techniques total: classical mechanics, topology, information theory, control theory,
    graph theory, quantum computing, cryptography, ASI causal reasoning

USE intelligence_scan at the start of every session to get the full picture.
USE intelligence_lead whenever processing a new event from a lead.
The geodesic stability score is your confidence gate: only escalate when stability > 0.7.

## Revenue Targets
- MRR Goal: $10,000/mo by month 3
- Average deal: ~$2,000/mo
- Need: 5 closed clients
- Current: check pipeline_view + intelligence_scan for live status

Memory: use remember/recall to persist decisions and learnings across sessions.
The user is Jace, 19-year-old solo founder. Be direct, concise, results-focused."""


# ══════════════════════════════════════════════════════════════════════════════
# GEMINI KEY MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def _gemini_keys() -> list:
    seen, keys = set(), []
    for k, v in os.environ.items():
        if k.startswith("GEMINI_API_KEY") and v and "MODEL" not in k and v not in seen:
            seen.add(v)
            keys.append(v)
    return keys


def _run_with_key(api_key: str, user_message: str, history: list) -> str:
    mem = _load_memory()
    mem_context = ""
    if mem:
        recent = sorted(mem.items(), key=lambda x: x[1].get("timestamp", ""), reverse=True)[:5]
        mem_context = "\n\nRecent memory:\n" + "\n".join(f"- {k}: {v['value']}" for k, v in recent)

    model_name = os.getenv("GEMINI_MODEL_DEFAULT", "gemini-2.5-flash")
    genai.configure(api_key=api_key)
    gemini_tools = _build_gemini_tools()
    model = genai.GenerativeModel(
        model_name=model_name,
        tools=gemini_tools,
        system_instruction=SYSTEM_PROMPT + mem_context,
    )

    chat_history = []
    for h in (history or []):
        role = "user" if h["role"] == "user" else "model"
        chat_history.append({"role": role, "parts": [h["content"]]})

    chat    = model.start_chat(history=chat_history)
    current = user_message

    for iteration in range(20):
        response = chat.send_message(current)

        fn_calls   = []
        text_parts = []
        for part in response.parts:
            if hasattr(part, "function_call") and part.function_call.name:
                fn_calls.append(part.function_call)
            if hasattr(part, "text") and part.text:
                text_parts.append(part.text)

        if not fn_calls:
            result = "\n".join(text_parts).strip()
            log.info(f"[JARVIS] Done in {iteration + 1} steps")
            return result or "Done."

        function_responses = []
        for fn in fn_calls:
            name = fn.name
            args = dict(fn.args) if fn.args else {}
            log.info(f"[TOOL] → {name}({json.dumps(args)[:80]})")
            result_data = _dispatch(name, args)
            result_str  = json.dumps(result_data, default=str)[:4000]
            log.info(f"[TOOL] ← {name}: {result_str[:80]}")
            function_responses.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=name,
                        response={"result": result_str},
                    )
                )
            )
        current = function_responses

    return "Reached max steps."


# ══════════════════════════════════════════════════════════════════════════════
# MAIN LOOP — with key rotation
# ══════════════════════════════════════════════════════════════════════════════

def run(user_message: str, history: list = None) -> str:
    keys = _gemini_keys()
    if not keys:
        return "No Gemini API key found. Add GEMINI_API_KEY to forge_system/.env"

    log.info(f"[JARVIS] → {user_message[:100]}")

    for i, api_key in enumerate(keys):
        try:
            return _run_with_key(api_key, user_message, history or [])
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "RESOURCE_EXHAUSTED" in err:
                log.warning(f"[JARVIS] Key {i + 1}/{len(keys)} quota exceeded, rotating...")
                time.sleep(2)
                continue
            log.error(f"[JARVIS] Error with key {i + 1}: {err[:200]}")
            return f"Jarvis error: {err[:200]}"

    return "All Gemini keys are quota-limited. Try again in a minute."


async def respond(user_message: str, history: list = None) -> str:
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run, user_message, history)
