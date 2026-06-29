"""
agents/orchestrator_agent.py - The ASI Orchestrator (Central Intelligence).

The Orchestrator is the meta-agent that coordinates all AEI specialists.
It does not execute campaigns, train models, or send emails - it decides
WHAT should happen strategically and delegates HOW to the specialist AEIs.

Executive layer:
- Jarvis (CEO)
- Damien (CTO)
- Noah (CMO)
- Zoya (CFO)
- Devan (Lead Generation Head)
- Akhil (Lead Management Head)
- King (AI Specialist / training governor)
"""

import json
import uuid
import logging
import time

import google.generativeai as genai

from agents.executive_registry import get_executive_status_map, get_specialist_agent_count
from config import get_settings
from models.asi import OrchestratorCommand, OrchestratorResponse
from utils.nexus import send_to_aei, broadcast_insight
from database.supabase import db

logger = logging.getLogger(__name__)

AEI_REGISTRY = {
    'forge': {
        'description': 'B2B outreach, cold email campaigns, lead management, draft generation, campaign automation',
        'capabilities': ['run_campaign_cycle', 'generate_drafts', 'get_campaign_rating', 'enrich_leads'],
        'triggers': ['campaign', 'email', 'lead', 'outreach', 'reply rate', 'cold email', 'draft'],
    },
    'jarvis': {
        'description': 'Conversational AI, long-term memory, knowledge management, executive reasoning, user queries',
        'capabilities': ['answer_question', 'store_memory', 'search_knowledge', 'generate_report'],
        'triggers': ['jarvis', 'memory', 'knowledge', 'question', 'chat', 'conversation', 'strategy'],
    },
    'analytics': {
        'description': 'Business intelligence, KPI tracking, campaign performance analysis, pipeline forecasting',
        'capabilities': ['analyze_campaign_performance', 'forecast_pipeline', 'generate_kpi_report', 'identify_trends'],
        'triggers': ['performance', 'analytics', 'metrics', 'kpi', 'forecast', 'trend', 'data', 'report'],
    },
    'intel': {
        'description': 'Market intelligence, competitor monitoring, lead enrichment, company research, industry analysis',
        'capabilities': ['research_company', 'enrich_lead', 'monitor_competitors', 'identify_opportunities'],
        'triggers': ['research', 'company', 'market', 'competitor', 'intel', 'enrich', 'industry', 'opportunity'],
    },
    'ops': {
        'description': 'Operations automation, scheduling, workflow management, resource allocation, system health',
        'capabilities': ['schedule_campaign_cycle', 'monitor_workflows', 'check_system_health', 'optimize_resources'],
        'triggers': ['schedule', 'automate', 'workflow', 'operations', 'health', 'system', 'optimize'],
    },
}

_ORCHESTRATOR_SYSTEM = """You are the FORGE ASI Orchestrator - the central intelligence governing the company.

You coordinate a network of specialized AEI agents and an executive speaker layer.

Executive speakers:
- Jarvis: CEO and final company operator
- Damien: CTO and reliability governor
- Noah: CMO and messaging strategist
- Zoya: CFO and analytics/goal owner
- Devan: Lead Generation Head and sourcing owner
- Akhil: Lead Management Head and CRM/reply owner
- King: AI Specialist, training governor, and memory/evaluation owner

AEI execution network:
- FORGE AEI: B2B outreach, cold email, lead management, campaign execution
- JARVIS AEI: conversational reasoning, long-term memory, executive dialogue
- ANALYTICS AEI: KPI tracking, performance analysis, forecasting
- INTEL AEI: company research, lead enrichment, competitor monitoring
- OPS AEI: operations automation, scheduling, workflow management, system health

When given a command:
1. Identify which business objectives are at stake
2. Determine which AEIs need to act and in what sequence
3. Assign specific, concrete tasks to each AEI
4. Synthesize your analysis into strategic insights
5. List the 2-3 most important next steps for the human

Be direct. Be specific. No padding. Think like a Chief of Staff who sees the whole board."""


async def execute_command(command: OrchestratorCommand) -> OrchestratorResponse:
    command_id = str(uuid.uuid4())[:12]
    start_ms = int(time.time() * 1000)
    s = get_settings()
    genai.configure(api_key=s.gemini_key_for('jarvis'))

    aei_context = '\n'.join(
        f"- {name.upper()} AEI: {info['description']}"
        for name, info in AEI_REGISTRY.items()
    )

    prompt = f"""{_ORCHESTRATOR_SYSTEM}

Available AEIs:
{aei_context}

Command from user: \"{command.command}\"
Additional context: {json.dumps(command.context) if command.context else 'none'}
Target AEI hint: {command.target_aei or 'none - you decide'}

Respond ONLY with valid JSON (no markdown, no explanation outside JSON):
{{
  \"analysis\": \"2-3 sentence strategic analysis of the business situation\",
  \"aeis_to_involve\": [\"forge\", \"analytics\"],
  \"tasks\": [
    {{\"aei\": \"forge\", \"task_type\": \"get_campaign_rating\", \"description\": \"Pull current rating for all active campaigns\"}},
    {{\"aei\": \"analytics\", \"task_type\": \"analyze_campaign_performance\", \"description\": \"Identify which axis is underperforming most\"}}
  ],
  \"insights\": [
    \"Insight 1 - specific, actionable observation\",
    \"Insight 2 - specific, actionable observation\"
  ],
  \"next_steps\": [
    \"Specific step 1 the team should take today\",
    \"Specific step 2\",
    \"Specific step 3\"
  ],
  \"response\": \"Direct 2-3 sentence answer to the command. Specific and action-oriented.\"
}}"""

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        result = model.generate_content(prompt)
        raw = result.text.strip()

        if '```' in raw:
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
            raw = raw.strip().rstrip('`').strip()

        parsed = json.loads(raw)

    except Exception as e:
        logger.error("Orchestrator parse error for command '%s': %s", command.command[:50], e)
        parsed = {
            'analysis': f'Processing error: {str(e)[:100]}',
            'aeis_to_involve': [],
            'tasks': [],
            'insights': ['Check orchestrator logs for details'],
            'next_steps': ['Retry the command with more specific context'],
            'response': 'I encountered an issue analyzing that command. Please check system logs.',
        }

    actions_taken = []
    for task in parsed.get('tasks', []):
        target = task.get('aei', 'forge')
        task_type = task.get('task_type', 'process')
        try:
            task_id = await send_to_aei(
                source='orchestrator',
                target=target,
                task_type=task_type,
                payload={
                    'description': task.get('description', ''),
                    'original_command': command.command,
                    'context': command.context,
                    'command_id': command_id,
                },
                priority=3,
            )
            actions_taken.append({
                'aei': target,
                'task_type': task_type,
                'task_id': task_id,
                'status': 'dispatched',
            })
        except Exception as e:
            logger.error('Nexus dispatch failed for %s/%s: %s', target, task_type, e)
            actions_taken.append({'aei': target, 'task_type': task_type, 'status': 'failed', 'error': str(e)})

    for insight in parsed.get('insights', []):
        try:
            await broadcast_insight('orchestrator', insight, priority=4)
        except Exception:
            pass

    latency = int(time.time() * 1000) - start_ms

    try:
        db().table('jarvis.orchestrator_commands').insert({
            'command_id': command_id,
            'user_id': command.user_id,
            'command': command.command,
            'response': parsed.get('response', ''),
            'actions': actions_taken,
            'insights': parsed.get('insights', []),
            'next_steps': parsed.get('next_steps', []),
            'aeis': parsed.get('aeis_to_involve', []),
            'confidence': 0.87,
        }).execute()
    except Exception as e:
        logger.warning('Orchestrator audit log failed (non-critical): %s', e)

    logger.info('Orchestrator: command %s - %d tasks dispatched in %dms', command_id, len(actions_taken), latency)

    return OrchestratorResponse(
        command_id=command_id,
        response=parsed.get('response', 'Command processed.'),
        actions_taken=actions_taken,
        aeis_involved=parsed.get('aeis_to_involve', []),
        insights=parsed.get('insights', []),
        next_steps=parsed.get('next_steps', []),
        confidence=0.87,
    )


async def get_system_status() -> dict:
    from utils.nexus import get_stream_length

    client = db()
    settings = get_settings()
    campaigns_res = client.table('outreach.campaigns').select('id', count='exact').eq('status', 'active').execute()
    active_campaigns = campaigns_res.count or 0

    aei_loads = {}
    for aei_name in AEI_REGISTRY:
        try:
            aei_loads[aei_name] = await get_stream_length(aei_name)
        except Exception:
            aei_loads[aei_name] = 0

    aeis = {}
    for name, info in AEI_REGISTRY.items():
        aeis[name] = {
            'status': 'active',
            'description': info['description'],
            'capabilities': info['capabilities'],
            'pending_tasks': aei_loads.get(name, 0),
        }

    return {
        'status': 'operational',
        'aeis': aeis,
        'executive_systems': get_executive_status_map(settings),
        'active_campaigns': active_campaigns,
        'orchestrator_version': '2.0.0',
        'asi_level': 'Executive-Coordinated AEI Network',
        'coordination_model': settings.gemini_model_reasoning,
        'aei_count': len(AEI_REGISTRY),
        'executive_count': 7,
        'specialist_agent_count': get_specialist_agent_count(),
    }
