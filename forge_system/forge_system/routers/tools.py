"""
routers/tools.py — Gemini function calling schema endpoint.

Returns the tool schema that Gemini AI Studio needs for function calling.
This is the bridge between the AI Studio system prompt in FORGE_SYSTEM_PROMPT.md
and the live API — Gemini calls these functions by name to execute FORGE operations.

Add this to AI Studio: Tools → Add function → paste individual schemas from /tools/schema/.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/tools", tags=["Gemini Tools"])


@router.get("/schema/", summary="Return Gemini function calling schemas for AI Studio integration")
def get_tool_schema():
    """
    Returns all FORGE function declarations in the format Gemini AI Studio expects.
    In AI Studio: Tools section → Function declarations → add each entry individually.
    In the API: pass the `tools` list directly to the GenerativeModel constructor.
    """
    return {
        "tools": [
            {
                "name": "get_leads",
                "description": "Fetch leads filtered by industry, city, or status.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "industry": {"type": "string", "description": "legal | ecommerce | fintech"},
                        "city": {"type": "string"},
                        "status": {"type": "string", "description": "new | contacted | replied | converted | dead"},
                        "limit": {"type": "integer", "description": "Max results, default 100"},
                    },
                },
            },
            {
                "name": "get_campaign",
                "description": "Fetch a campaign's current state, metrics, rating, and goals.",
                "parameters": {
                    "type": "object",
                    "properties": {"campaign_id": {"type": "integer"}},
                    "required": ["campaign_id"],
                },
            },
            {
                "name": "create_campaign",
                "description": "Initialize a new campaign with segment, dates, and auto-created default goals.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "segment": {"type": "string", "description": "legal | ecommerce | fintech"},
                        "start_date": {"type": "string", "description": "ISO 8601 date"},
                        "end_date": {"type": "string", "description": "ISO 8601 date"},
                    },
                    "required": ["name", "segment"],
                },
            },
            {
                "name": "generate_plan",
                "description": "Generate a 14-day execution plan for a campaign with auto-calculated batch sizes.",
                "parameters": {
                    "type": "object",
                    "properties": {"campaign_id": {"type": "integer"}},
                    "required": ["campaign_id"],
                },
            },
            {
                "name": "get_plan",
                "description": "Get the active execution plan and each step's status for a campaign.",
                "parameters": {
                    "type": "object",
                    "properties": {"campaign_id": {"type": "integer"}},
                    "required": ["campaign_id"],
                },
            },
            {
                "name": "set_goals",
                "description": "Set or overwrite the goals for a campaign.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "campaign_id": {"type": "integer"},
                        "goals": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "goal_type": {"type": "string", "description": "meetings | replies | sent"},
                                    "target_value": {"type": "number"},
                                    "deadline": {"type": "string"},
                                },
                            },
                        },
                    },
                    "required": ["campaign_id", "goals"],
                },
            },
            {
                "name": "get_goals",
                "description": "Get goals and live progress percentages for a campaign.",
                "parameters": {
                    "type": "object",
                    "properties": {"campaign_id": {"type": "integer"}},
                    "required": ["campaign_id"],
                },
            },
            {
                "name": "get_drafts",
                "description": "List email drafts — filter by campaign or status (draft | approved | sent).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "campaign_id": {"type": "integer"},
                        "status": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                },
            },
            {
                "name": "approve_draft",
                "description": "Approve a draft for sending.",
                "parameters": {
                    "type": "object",
                    "properties": {"draft_id": {"type": "integer"}},
                    "required": ["draft_id"],
                },
            },
            {
                "name": "log_event",
                "description": "Log a campaign event: sent | opened | replied | meeting_booked | bounced. Automatically updates metrics and rating.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "campaign_id": {"type": "integer"},
                        "lead_id": {"type": "integer"},
                        "draft_id": {"type": "integer"},
                        "event_type": {"type": "string", "description": "sent | opened | replied | meeting_booked | bounced"},
                    },
                    "required": ["campaign_id", "lead_id", "event_type"],
                },
            },
            {
                "name": "get_campaign_rating",
                "description": "Get the computed rating (0-100), grade, weakest axis, diagnosis, and recommended action for a campaign.",
                "parameters": {
                    "type": "object",
                    "properties": {"campaign_id": {"type": "integer"}},
                    "required": ["campaign_id"],
                },
            },
            {
                "name": "get_dashboard",
                "description": "Get aggregate metrics across all active campaigns with per-campaign rating cards.",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "run_campaign_cycle",
                "description": "Run today's automated campaign step: identify due leads, generate AI drafts, save for human review.",
                "parameters": {
                    "type": "object",
                    "properties": {"campaign_id": {"type": "integer"}},
                    "required": ["campaign_id"],
                },
            },
            {
                "name": "orchestrate_command",
                "description": "Send a high-level business command to the ASI Orchestrator. It will route to the correct AEI specialists and return insights and next steps.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Natural language business command"},
                        "target_aei": {"type": "string", "description": "Optional: route to specific AEI — forge | jarvis | analytics | intel | ops"},
                    },
                    "required": ["command"],
                },
            },
            {
                "name": "research_company",
                "description": "Get an Intel AEI research brief on a company: pain points, decision makers, best hook angle.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "company_name": {"type": "string"},
                        "industry": {"type": "string"},
                    },
                    "required": ["company_name"],
                },
            },
            {
                "name": "get_ops_digest",
                "description": "Get the daily operations digest: system health, today's automation schedule, draft queue status, and 3 action bullets.",
                "parameters": {"type": "object", "properties": {}},
            },
        ]
    }
