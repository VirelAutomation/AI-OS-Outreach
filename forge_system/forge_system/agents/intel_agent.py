"""
agents/intel_agent.py â€” Intel AEI (Market & Company Intelligence).

Provides company research briefs, lead enrichment, and opportunity detection.
The Intel AEI acts as the system's research arm â€” it gathers context that
makes every other AEI smarter: better email personalization, better targeting,
better strategic decisions.

Currently uses Gemini's world knowledge for company research. When a Perplexity
or Serper API key is configured, it will supplement with real-time web data.
"""

import json
import logging

import google.generativeai as genai

from config import get_settings
from database.supabase import db
from models.asi import IntelBrief

logger = logging.getLogger(__name__)


async def research_company(company_name: str, industry: str = "") -> IntelBrief:
    """
    Generate a research brief on a company for lead targeting and personalization.

    Returns structured intelligence: pain points, decision maker profiles,
    the best hook angle for a cold email, and competitive context.
    Uses Gemini reasoning on its world knowledge. Cached to Supabase for 7 days.
    """
    client = db()

    # Check cache first â€” company research is stable over days
    try:
        cached = (
            client.table("jarvis.intel_briefings")
            .select("*")
            .eq("company", company_name)
            .gt("expires_at", "now()")
            .limit(1)
            .execute()
        )
        if cached.data:
            row = cached.data[0]
            logger.debug("Intel cache hit for %s", company_name)
            return IntelBrief(
                company=row["company"],
                industry=row["industry"],
                pain_points=row["pain_points"],
                decision_makers=row["decision_makers"],
                hook_angle=row["hook_angle"],
                competitive_context=row["competitive_context"],
            )
    except Exception:
        pass  # cache miss is fine â€” proceed to generate

    s = get_settings()
    genai.configure(api_key=s.gemini_key_for("devan"))
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""You are a B2B sales intelligence analyst. Research this company and return structured intelligence.

Company: {company_name}
Industry: {industry or "unknown â€” infer from company name/type"}

Return ONLY valid JSON, no markdown:
{{
  "pain_points": ["specific pain 1 for this company/industry", "specific pain 2", "specific pain 3"],
  "decision_makers": ["COO", "Head of Operations", "VP Engineering"],
  "hook_angle": "Single sentence â€” the most compelling cold email opener for this specific company",
  "competitive_context": "One sentence on what tools/processes they likely use that we could displace"
}}

Be specific to this company's likely situation. Avoid generic statements."""

    try:
        result = model.generate_content(prompt)
        raw = result.text.strip()
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip().rstrip("`").strip()
        data = json.loads(raw)
    except Exception as e:
        logger.error("Intel research parse error for %s: %s", company_name, e)
        data = {
            "pain_points": ["manual operational workflows", "scaling challenges", "data silos"],
            "decision_makers": ["COO", "Head of Operations", "Founder"],
            "hook_angle": f"Automate {company_name}'s most time-consuming operational workflows",
            "competitive_context": "Likely using manual processes or fragmented point solutions",
        }

    brief = IntelBrief(
        company=company_name,
        industry=industry,
        pain_points=data.get("pain_points", []),
        decision_makers=data.get("decision_makers", []),
        hook_angle=data.get("hook_angle", ""),
        competitive_context=data.get("competitive_context", ""),
    )

    # Cache to Supabase for 7 days
    try:
        client.table("jarvis.intel_briefings").insert({
            "company":             company_name,
            "industry":            industry,
            "pain_points":         brief.pain_points,
            "decision_makers":     brief.decision_makers,
            "hook_angle":          brief.hook_angle,
            "competitive_context": brief.competitive_context,
        }).execute()
    except Exception as e:
        logger.warning("Intel cache write failed for %s (non-critical): %s", company_name, e)

    logger.info("Intel brief generated for %s (%s)", company_name, industry)
    return brief


async def enrich_lead(lead_id: int) -> dict:
    """
    Enrich a lead with Intel AEI research and append findings to their notes.

    Fetches the lead, generates a company brief, and appends a structured
    Intel note to the lead's notes field for use by email_generator.py.
    """
    client = db()
    lead_res = client.table("outreach.leads").select("*").eq("id", lead_id).execute()
    if not lead_res.data:
        return {"error": "Lead not found", "lead_id": lead_id}

    lead = lead_res.data[0]
    brief = await research_company(lead["company"], lead.get("industry", ""))

    intel_note = (
        f"[INTEL] Pain: {brief.pain_points[0] if brief.pain_points else 'unknown'}. "
        f"Hook: {brief.hook_angle}. "
        f"DM: {', '.join(brief.decision_makers[:2]) if brief.decision_makers else 'unknown'}."
    )
    existing_notes = (lead.get("notes") or "").strip()
    updated_notes = f"{existing_notes}\n{intel_note}".strip() if existing_notes else intel_note

    client.table("outreach.leads").update({"notes": updated_notes}).eq("id", lead_id).execute()
    logger.info("Lead %d enriched: %s @ %s", lead_id, lead["name"], lead["company"])

    return {
        "lead_id":       lead_id,
        "enriched":      True,
        "brief":         brief.model_dump(),
        "notes_updated": True,
    }


async def bulk_enrich_leads(lead_ids: list[int]) -> dict:
    """Enrich multiple leads. Returns a summary of enriched vs failed."""
    enriched = failed = 0
    for lead_id in lead_ids:
        try:
            result = await enrich_lead(lead_id)
            if result.get("enriched"):
                enriched += 1
            else:
                failed += 1
        except Exception as e:
            logger.error("Bulk enrich failed for lead %d: %s", lead_id, e)
            failed += 1
    return {"enriched": enriched, "failed": failed, "total": len(lead_ids)}


async def identify_opportunities(segment: str) -> dict:
    """
    Identify current market opportunities and ideal targets in a segment.
    Returns an AI-generated opportunity brief for the Orchestrator.
    """
    s = get_settings()
    genai.configure(api_key=s.gemini_key_for("devan"))
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""You are a B2B market intelligence analyst specializing in {segment}.

Identify the top 3 current market opportunities for Virel Automation (an AI-powered operations automation company) targeting the {segment} sector.

Return ONLY valid JSON:
{{
  "opportunities": [
    {{
      "title": "Opportunity title",
      "why_now": "Why this is a hot opportunity right now (1-2 sentences)",
      "ideal_target": "Company type/size/role to target",
      "hook": "Best cold email hook for this opportunity"
    }}
  ],
  "market_summary": "2-sentence overview of the {segment} market's current pain landscape"
}}"""

    try:
        result = model.generate_content(prompt)
        raw = result.text.strip()
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip().rstrip("`").strip()
        return json.loads(raw)
    except Exception as e:
        logger.error("Opportunity identification failed for %s: %s", segment, e)
        return {"error": str(e), "segment": segment}

