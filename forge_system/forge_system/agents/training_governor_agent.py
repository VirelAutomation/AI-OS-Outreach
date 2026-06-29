"""King - training and evaluation governor."""

import json
import logging
import uuid
from datetime import datetime, timezone

import google.generativeai as genai

from agents.executive_registry import get_executive_status_map
from config import get_settings
from database.supabase import db
from services.segregation_agent import run_segregation_cycle

logger = logging.getLogger(__name__)


async def get_training_readiness(domain_tags: list[str] | None = None, min_quality: float | None = None, max_examples: int | None = None) -> dict:
    settings = get_settings()
    client = db()
    threshold = min_quality if min_quality is not None else settings.training_quality_threshold

    q = client.table('jarvis.training_examples').select('*').eq('processed', False).gte('quality_score', threshold)
    if domain_tags:
        q = q.in_('domain_tag', domain_tags)
    rows = q.order('quality_score', desc=True).limit(max_examples or settings.training_batch_size).execute().data or []

    avg_quality = round(sum((row.get('quality_score') or 0) for row in rows) / len(rows), 3) if rows else 0.0
    latest_run = (
        client.table('jarvis.training_runs')
        .select('*')
        .order('created_at', desc=True)
        .limit(1)
        .execute()
        .data
    )
    return {
        'company_name': settings.company_name,
        'target_mrr': settings.revenue_target_mrr,
        'target_months': settings.revenue_target_months,
        'eligible_examples': len(rows),
        'avg_quality_score': avg_quality,
        'threshold': threshold,
        'domain_tags': domain_tags or ['all'],
        'last_training_run': latest_run[0] if latest_run else None,
        'recommended_batch_size': min(len(rows), max_examples or settings.training_batch_size),
    }


async def evaluate_executive_systems() -> dict:
    settings = get_settings()
    client = db()
    registry = get_executive_status_map(settings)
    evaluations = []

    for executive_id, detail in registry.items():
        score = 1.0
        findings = []

        if not detail['gemini_key_configured']:
            score -= 0.5
            findings.append('missing_gemini_key')
        if executive_id == 'noah' and not (settings.gmail_client_id and settings.gmail_client_secret and settings.gmail_refresh_token):
            score -= 0.2
            findings.append('gmail_not_ready')
        if executive_id == 'devan' and not settings.apify_api_token:
            score -= 0.2
            findings.append('apify_not_ready')
        if executive_id in {'jarvis', 'damien', 'zoya', 'king'} and not settings.supabase_url:
            score -= 0.2
            findings.append('supabase_not_ready')

        score = round(max(score, 0.0), 2)
        verdict = 'healthy' if score >= 0.85 else 'degraded' if score >= 0.6 else 'at_risk'
        summary = f"{detail['speaker_name']} ({detail['title']}) is {verdict}. Findings: {', '.join(findings) if findings else 'none'}."

        row = {
            'agent_name': executive_id,
            'executive_owner': 'king',
            'evaluation_type': 'executive_readiness',
            'score': score,
            'verdict': verdict,
            'summary': summary,
            'payload': {
                'findings': findings,
                'specialist_count': detail['specialist_count'],
            },
        }
        evaluations.append(row)
        try:
            client.table('jarvis.agent_evaluations').insert(row).execute()
        except Exception as e:
            logger.warning('Agent evaluation log failed for %s: %s', executive_id, e)

    return {'evaluations': evaluations}


async def run_governance_cycle(limit: int = 500, domain_tags: list[str] | None = None, min_quality: float | None = None, max_examples: int | None = None) -> dict:
    settings = get_settings()
    client = db()
    run_id = f'king-{uuid.uuid4().hex[:12]}'
    started_at = datetime.now(timezone.utc)

    segregation_summary = await run_segregation_cycle(limit=limit)
    readiness = await get_training_readiness(domain_tags=domain_tags, min_quality=min_quality, max_examples=max_examples)
    evaluations = await evaluate_executive_systems()

    governance_summary = {
        'run_id': run_id,
        'segregation_summary': segregation_summary,
        'readiness': readiness,
        'evaluations_logged': len(evaluations['evaluations']),
    }

    try:
        genai.configure(api_key=settings.gemini_key_for('king'))
        model = genai.GenerativeModel(settings.gemini_model_reasoning)
        prompt = f"""You are King, AI Specialist at {settings.company_name}.
Summarize this governance cycle in 2 short sentences for the executive team.

Data:
{json.dumps(governance_summary)}"""
        governance_summary['executive_summary'] = model.generate_content(prompt).text.strip()
    except Exception as e:
        logger.warning('King governance summary generation failed: %s', e)
        governance_summary['executive_summary'] = 'Governance cycle completed. Review readiness and evaluation findings.'

    try:
        client.table('jarvis.training_governance_runs').insert({
            'run_id': run_id,
            'governor': 'king',
            'scope': {
                'limit': limit,
                'domain_tags': domain_tags or ['all'],
                'min_quality': min_quality if min_quality is not None else settings.training_quality_threshold,
                'max_examples': max_examples,
            },
            'segregation_summary': segregation_summary,
            'readiness_summary': {
                'eligible_examples': readiness['eligible_examples'],
                'avg_quality_score': readiness['avg_quality_score'],
                'recommended_batch_size': readiness['recommended_batch_size'],
            },
            'status': 'completed',
            'started_at': started_at.isoformat(),
            'completed_at': datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        logger.warning('Training governance run log failed: %s', e)

    return governance_summary
