"""
agents/jarvis_agent.py

Jarvis intelligence loop + full dashboard tool access.
Tool intents are detected from the user's message before hitting Gemini.
If no tool matches, falls through to the normal Gemini conversation loop.
"""

import time
import hashlib
import asyncio
import re
import google.generativeai as genai

from database.supabase import db
from database.redis_client import (
    get_session, set_session, push_message, get_messages,
    get_cached_inference, cache_inference,
)
from utils.embeddings import embed_text, retrieve_memories
from models.jarvis import MessageIn, MessageOut
from config import get_settings
from agents import jarvis_tools as tools
from agents import jarvis_outreach as outreach
from agents import jarvis_strategic as strategic
from agents import jarvis_core as core

JARVIS_SYSTEM_PROMPT = """You are Jarvis, the central AI for Virel Automation.
Precise, direct, action-oriented. No filler.

You control the full outreach stack:

INSTAGRAM: run DMs, set limits, change niches, change follower range, check status, send followups
FACEBOOK: join groups, post in groups, DM members, check status
CONFIG: change any setting in real-time
DASHBOARD: leads, campaigns, analytics, Gmail drafts, automations

Just tell me what to do."""


# ═════════════════════════════════════════════════════════════════════════════
# Intent detection — checked BEFORE Gemini, in priority order
# ═════════════════════════════════════════════════════════════════════════════

def _num(text: str, default: int) -> int:
    m = re.search(r"\b(\d+)\b", text)
    return max(1, min(int(m.group(1)), 200)) if m else default


def _campaign_ref(text: str) -> str:
    """Extract a campaign name or id from message."""
    m = re.search(r"campaign\s+['\"]?([^'\"]+?)['\"]?\s*(campaign)?$", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # fall back: any quoted string
    m = re.search(r"['\"](.+?)['\"]", text)
    return m.group(1) if m else ""


async def _dispatch_tool(text: str) -> str | None:
    """
    Full intent classifier — checked before Gemini.
    Priority: outreach ops > config changes > dashboard tools > Gemini.
    """
    t = text.lower()

    # ════════════════════════════════════════════════════
    # INSTAGRAM OUTREACH
    # ════════════════════════════════════════════════════

    # Run IG outreach
    if re.search(r"(run|start|launch|send|do|fire).{0,25}(ig|instagram|dms?)\b", t) or \
       re.search(r"\b(ig|instagram).{0,20}(run|start|outreach|dms?)\b", t):
        limit  = _num(text, 20)
        region = "india" if "india" in t else "us" if "us" in t or "america" in t else "auto"
        return await outreach.ig_run(region=region, limit=limit)

    if re.search(r"ig.{0,10}(status|stats?)|instagram.{0,10}(status|stats?)|how many.{0,15}ig", t):
        return outreach.ig_status()

    if re.search(r"ig.{0,15}follow.?up|instagram.{0,15}follow.?up|send.{0,10}follow.?up", t):
        return outreach.ig_followups()

    if re.search(r"check.{0,15}repl|scan.{0,15}inbox|ig.{0,15}repl", t):
        return outreach.ig_check_replies()

    # ════════════════════════════════════════════════════
    # FACEBOOK OUTREACH
    # ════════════════════════════════════════════════════

    if re.search(r"(join|find).{0,20}(facebook|fb).{0,20}groups?", t) or \
       re.search(r"(facebook|fb).{0,20}(join|find).{0,20}groups?", t):
        niche = _extract_niche(t)
        return await outreach.fb_join(niche)

    if re.search(r"(post|write|make).{0,20}(facebook|fb|groups?)|fb.{0,15}post", t):
        niche = _extract_niche(t)
        return await outreach.fb_post(niche)

    if re.search(r"(dm|message|outreach).{0,20}(facebook|fb|group.{0,10}member)|fb.{0,15}dm", t):
        niche = _extract_niche(t)
        return await outreach.fb_dm(niche)

    if re.search(r"fb.{0,10}(status|stats?)|facebook.{0,10}(status|stats?)", t):
        return outreach.fb_status()

    if re.search(r"(run|start|do).{0,15}(facebook|fb).{0,15}(outreach|all)|fb.{0,10}all", t):
        niche = _extract_niche(t)
        await outreach.fb_join(niche)
        return await outreach.fb_post(niche)

    # ════════════════════════════════════════════════════
    # CONFIG CHANGES
    # ════════════════════════════════════════════════════

    # DM / post limits
    if re.search(r"set.{0,20}(ig|instagram).{0,20}limit|ig.{0,10}limit.{0,10}to|send.{0,10}\d+.{0,10}dms?", t):
        n = _num(text, 20)
        return outreach.set_ig_limit(n)

    if re.search(r"set.{0,20}(fb|facebook).{0,20}(dm|message).{0,10}limit", t):
        n = _num(text, 20)
        return outreach.set_fb_dm_limit(n)

    if re.search(r"set.{0,20}(fb|facebook).{0,20}post.{0,10}limit", t):
        n = _num(text, 20)
        return outreach.set_fb_post_limit(n)

    # Follower range
    if re.search(r"(follower|followers?).{0,20}(range|between|from)|target.{0,20}\d+.{0,10}follower", t):
        nums = re.findall(r"\b(\d+)\b", text)
        if len(nums) >= 2:
            return outreach.set_follower_range(int(nums[0]), int(nums[1]))
        elif nums:
            return outreach.set_follower_range(200, int(nums[0]))

    # Region
    if re.search(r"(switch|change|set).{0,20}(region|country|target).{0,20}(india|us|america)", t) or \
       re.search(r"target.{0,15}(india|us|america|united states)", t):
        region = "india" if "india" in t else "us"
        return outreach.set_ig_region(region)

    # Niche changes
    if re.search(r"(add|remove|change|set|target).{0,20}(niche|industry|type).{0,30}(us|america|india)", t) or \
       re.search(r"(only|just).{0,15}(hvac|med.?spa|coach|realtor|agency|agencies)", t):
        niches = []
        if "hvac" in t:          niches.append("hvac")
        if "med spa" in t or "medspa" in t: niches.append("med spa")
        if "coach" in t:         niches.append("coach")
        if "realtor" in t or "real estate" in t: niches.append("realtor")
        if "marketing" in t or "agenc" in t: niches.append("digital marketing agency")
        if "interior" in t:      niches.append("interior designer")
        if niches:
            if "india" in t:
                return outreach.set_india_niches(niches)
            return outreach.set_us_niches(niches)

    # Enable/disable
    if re.search(r"(disable|pause|stop|turn off).{0,15}instagram", t):
        return outreach.toggle_ig(False)
    if re.search(r"(enable|resume|turn on).{0,15}instagram", t):
        return outreach.toggle_ig(True)
    if re.search(r"(disable|pause|stop|turn off).{0,15}(facebook|fb)", t):
        return outreach.toggle_fb(False)
    if re.search(r"(enable|resume|turn on).{0,15}(facebook|fb)", t):
        return outreach.toggle_fb(True)

    # ════════════════════════════════════════════════════
    # STATUS & LOGS
    # ════════════════════════════════════════════════════

    if re.search(r"show.{0,10}config|current.{0,10}config|what.{0,15}set(tings?)?", t):
        return outreach.show_config()

    if re.search(r"(full|all|everything).{0,10}status|how.{0,15}(doing|performing|going)\??$", t):
        return outreach.full_status()

    if re.search(r"show.{0,10}(ig|instagram).{0,10}log|ig.{0,10}log", t):
        return outreach.show_log("ig", 25)

    if re.search(r"show.{0,10}(fb|facebook).{0,10}log|fb.{0,10}log", t):
        return outreach.show_log("fb", 25)

    # ════════════════════════════════════════════════════
    # DASHBOARD TOOLS (campaigns, leads, email, analytics)
    # ════════════════════════════════════════════════════

    if re.search(r"(analytics|dashboard|overview).{0,20}summar", t) and \
       not re.search(r"ig|instagram|fb|facebook", t):
        return tools.get_analytics_summary()

    if re.search(r"list\s+campaigns?|show\s+campaigns?|all\s+campaigns?", t):
        return tools.list_campaigns("active" if "active" in t else None)

    if re.search(r"campaign\s+stats?|how.{0,10}campaign", t):
        return tools.get_campaign_stats(_campaign_ref(text) or "1")

    if re.search(r"create\s+campaign", t):
        name_m = re.search(r"(?:called?|named?)\s+['\"]?([^'\"]+?)['\"]?", text, re.IGNORECASE)
        seg_m  = re.search(r"for\s+([a-z ]+?)$", text, re.IGNORECASE)
        return tools.create_campaign(
            name_m.group(1).strip() if name_m else "New Campaign",
            seg_m.group(1).strip()  if seg_m  else "general",
        )

    if re.search(r"(list|show|how many)\s+leads?", t):
        ind_m = re.search(r"(?:for|in)\s+([a-z &]+?)(?:\s+leads?)?$", text, re.IGNORECASE)
        ind   = ind_m.group(1).strip() if ind_m else None
        if re.search(r"how many|count", t):
            return tools.get_lead_count(ind)
        return tools.list_leads(industry=ind, limit=_num(text, 20))

    if re.search(r"gmail\s*status|email\s*status", t):
        return await tools.gmail_status()

    if re.search(r"(generate|write|create).{0,10}(email|drafts?)", t) and "campaign" in t:
        return await tools.generate_email_drafts(_campaign_ref(text) or "1", _num(text, 10))

    if re.search(r"send.{0,10}(email|drafts?|outreach)", t) and not re.search(r"ig|fb|dm", t):
        return await tools.send_email_drafts(_campaign_ref(text) or "1", _num(text, 10))

    if re.search(r"(list|show)\s+automations?", t):
        return tools.list_automations()

    if re.search(r"recent\s+events?|what.{0,10}happened", t):
        return tools.get_recent_events()

    return None   # no tool matched → Gemini handles it


def _extract_niche(t: str) -> str | None:
    if "hvac"    in t: return "hvac"
    if "med spa" in t or "medspa" in t: return "med spa"
    if "coach"   in t: return "coach"
    return None


# ═════════════════════════════════════════════════════════════════════════════
# Main respond loop
# ═════════════════════════════════════════════════════════════════════════════

async def respond(message: MessageIn) -> MessageOut:
    start_ms = int(time.time() * 1000)
    s = get_settings()
    genai.configure(api_key=s.gemini_key_for("jarvis"))

    # ── Core: everything routes through Jarvis Core (Claude + tools) ─────────
    # Fast-path: outreach commands still hit the regex dispatcher for speed
    tool_result = await _dispatch_tool(message.content)
    if tool_result is not None:
        response_text = tool_result
        latency = int(time.time() * 1000) - start_ms
        await push_message(message.session_id, {"role": "user", "content": message.content})
        await push_message(message.session_id, {"role": "assistant", "content": response_text})
        return MessageOut(
            session_id=message.session_id,
            response=response_text,
            model_version="tool",
            latency_ms=latency,
            memory_retrieved=0,
        )

    # Everything else → Jarvis Core (Claude agentic, 50+ tools, truly universal)
    history      = await get_messages(message.session_id)
    chat_history = [{"role": h["role"], "content": h["content"]} for h in history[-8:]]
    response_text = await core.respond(message.content, chat_history)
    latency = int(time.time() * 1000) - start_ms
    await push_message(message.session_id, {"role": "user",      "content": message.content})
    await push_message(message.session_id, {"role": "assistant", "content": response_text})
    return MessageOut(
        session_id=message.session_id,
        response=response_text,
        model_version="claude-sonnet-4-6-core",
        latency_ms=latency,
        memory_retrieved=0,
    )
