"""Akhil - Lead Management Head runtime."""

import json
import logging
from datetime import datetime, timedelta, timezone

import google.generativeai as genai

from config import get_settings
from database.supabase import db

logger = logging.getLogger(__name__)


def _fallback_triage(reply_text: str) -> dict:
    text = (reply_text or '').lower()
    if any(token in text for token in ['unsubscribe', 'remove me', 'stop emailing']):
        return {
            'classification': 'unsubscribe',
            'status_after': 'dead',
            'confidence': 0.95,
            'summary': 'Prospect asked to stop contact.',
            'next_action': 'suppress_contact',
            'create_follow_up': False,
            'follow_up_days': 0,
            'priority': 'low',
        }
    if any(token in text for token in ['not interested', 'no thanks', 'no thank you']):
        return {
            'classification': 'not_interested',
            'status_after': 'dead',
            'confidence': 0.9,
            'summary': 'Prospect rejected the outreach.',
            'next_action': 'close_out',
            'create_follow_up': False,
            'follow_up_days': 0,
            'priority': 'low',
        }
    if any(token in text for token in ['book', 'schedule', 'let us talk', 'call tomorrow', 'meeting']):
        return {
            'classification': 'meeting_intent',
            'status_after': 'replied',
            'confidence': 0.88,
            'summary': 'Prospect shows call intent and needs quick scheduling follow-up.',
            'next_action': 'schedule_meeting',
            'create_follow_up': True,
            'follow_up_days': 1,
            'priority': 'high',
        }
    if any(token in text for token in ['later', 'next month', 'circle back', 'follow up']):
        return {
            'classification': 'not_now',
            'status_after': 'replied',
            'confidence': 0.82,
            'summary': 'Prospect did not reject, but requested delayed follow-up.',
            'next_action': 'schedule_follow_up',
            'create_follow_up': True,
            'follow_up_days': 7,
            'priority': 'medium',
        }
    if any(token in text for token in ['price', 'pricing', 'cost', 'how much', 'proposal']):
        return {
            'classification': 'pricing_objection',
            'status_after': 'replied',
            'confidence': 0.8,
            'summary': 'Prospect engaged and raised a pricing or proposal question.',
            'next_action': 'respond_with_clarity',
            'create_follow_up': True,
            'follow_up_days': 2,
            'priority': 'high',
        }
    if any(token in text for token in ['interested', 'sounds good', 'tell me more']):
        return {
            'classification': 'interested',
            'status_after': 'replied',
            'confidence': 0.8,
            'summary': 'Prospect is interested and should be actively worked.',
            'next_action': 'advance_conversation',
            'create_follow_up': True,
            'follow_up_days': 1,
            'priority': 'high',
        }
    return {
        'classification': 'neutral_reply',
        'status_after': 'replied',
        'confidence': 0.65,
        'summary': 'Prospect replied but intent is ambiguous.',
        'next_action': 'human_review_or_follow_up',
        'create_follow_up': True,
        'follow_up_days': 3,
        'priority': 'medium',
    }


async def triage_reply(campaign_id: int, lead_id: int, reply_text: str, draft_id: int | None = None, metadata: dict | None = None) -> dict:
    client = db()
    settings = get_settings()
    metadata = metadata or {}

    lead_res = client.table('outreach.leads').select('*').eq('id', lead_id).execute()
    lead = lead_res.data[0] if lead_res.data else None
    if not lead:
        return {'error': 'lead_not_found', 'lead_id': lead_id}

    campaign_res = client.table('outreach.campaigns').select('*').eq('id', campaign_id).execute()
    campaign = campaign_res.data[0] if campaign_res.data else None
    if not campaign:
        return {'error': 'campaign_not_found', 'campaign_id': campaign_id}

    before_status = lead.get('status', 'new')
    triage = _fallback_triage(reply_text)

    try:
        genai.configure(api_key=settings.gemini_key_for('akhil'))
        model = genai.GenerativeModel(settings.gemini_model_reasoning)
        prompt = f"""You are Akhil, Lead Management Head at {settings.company_name}.

Your job is to classify a reply from a prospect and decide the next action so the company moves toward {settings.revenue_target_mrr} MRR in {settings.revenue_target_months} months.

Lead:
- Name: {lead.get('name')}
- Company: {lead.get('company')}
- Role: {lead.get('role')}
- Industry: {lead.get('industry')}
- Current status: {before_status}
- Campaign: {campaign.get('name')}

Reply text:
{reply_text}

Return ONLY valid JSON:
{{
  "classification": "meeting_intent | interested | pricing_objection | technical_objection | not_now | referral | unsubscribe | not_interested | neutral_reply",
  "status_after": "replied | converted | dead",
  "confidence": 0.0,
  "summary": "One sentence on what the reply means.",
  "next_action": "One concrete next action.",
  "create_follow_up": true,
  "follow_up_days": 1,
  "priority": "high | medium | low"
}}"""
        result = model.generate_content(prompt)
        raw = result.text.strip()
        if '```' in raw:
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
            raw = raw.strip().rstrip('`').strip()
        parsed = json.loads(raw)
        triage = {
            'classification': parsed.get('classification', triage['classification']),
            'status_after': parsed.get('status_after', triage['status_after']),
            'confidence': float(parsed.get('confidence', triage['confidence'])),
            'summary': parsed.get('summary', triage['summary']),
            'next_action': parsed.get('next_action', triage['next_action']),
            'create_follow_up': bool(parsed.get('create_follow_up', triage['create_follow_up'])),
            'follow_up_days': int(parsed.get('follow_up_days', triage['follow_up_days'])),
            'priority': parsed.get('priority', triage['priority']),
        }
    except Exception as e:
        logger.warning('Akhil AI triage failed for lead %s: %s', lead_id, e)

    note_line = f"[AKHIL] {triage['classification']}: {triage['summary']} Next: {triage['next_action']}"
    current_notes = (lead.get('notes') or '').strip()
    updated_notes = f"{current_notes}\n{note_line}".strip() if current_notes else note_line

    client.table('outreach.leads').update({
        'status': triage['status_after'],
        'notes': updated_notes,
    }).eq('id', lead_id).execute()

    action_row = None
    follow_up_row = None

    try:
        action_insert = client.table('outreach.lead_management_actions').insert({
            'lead_id': lead_id,
            'campaign_id': campaign_id,
            'event_id': metadata.get('event_id'),
            'executive_name': 'akhil',
            'classification': triage['classification'],
            'status_before': before_status,
            'status_after': triage['status_after'],
            'summary': triage['summary'],
            'next_action': triage['next_action'],
            'confidence': triage['confidence'],
            'payload': {
                'reply_text': reply_text,
                'draft_id': draft_id,
                'metadata': metadata,
            },
        }).execute()
        action_row = action_insert.data[0] if action_insert.data else None
    except Exception as e:
        logger.warning('Lead management action log failed for lead %s: %s', lead_id, e)

    if triage['create_follow_up'] and triage['status_after'] != 'dead':
        due_at = datetime.now(timezone.utc) + timedelta(days=max(triage['follow_up_days'], 0))
        try:
            follow_insert = client.table('outreach.follow_up_tasks').insert({
                'lead_id': lead_id,
                'campaign_id': campaign_id,
                'owner_executive': 'akhil',
                'reason': triage['next_action'],
                'due_at': due_at.isoformat(),
                'priority': triage['priority'],
                'status': 'open',
                'payload': {
                    'classification': triage['classification'],
                    'reply_text': reply_text,
                    'draft_id': draft_id,
                },
            }).execute()
            follow_up_row = follow_insert.data[0] if follow_insert.data else None
        except Exception as e:
            logger.warning('Follow-up task creation failed for lead %s: %s', lead_id, e)

    return {
        'lead_id': lead_id,
        'campaign_id': campaign_id,
        'classification': triage['classification'],
        'status_before': before_status,
        'status_after': triage['status_after'],
        'confidence': triage['confidence'],
        'summary': triage['summary'],
        'next_action': triage['next_action'],
        'follow_up_task': follow_up_row,
        'action_log': action_row,
    }


async def get_follow_up_queue(limit: int = 50) -> dict:
    client = db()
    rows = (
        client.table('outreach.follow_up_tasks')
        .select('*')
        .eq('status', 'open')
        .order('due_at')
        .limit(limit)
        .execute()
        .data
    )
    return {
        'open_tasks': len(rows),
        'tasks': rows,
    }


async def get_lead_management_digest() -> dict:
    client = db()
    queue = await get_follow_up_queue(limit=20)
    open_tasks = queue['open_tasks']
    replied_count = client.table('outreach.leads').select('id', count='exact').eq('status', 'replied').execute().count or 0
    converted_count = client.table('outreach.leads').select('id', count='exact').eq('status', 'converted').execute().count or 0
    dead_count = client.table('outreach.leads').select('id', count='exact').eq('status', 'dead').execute().count or 0

    recent_actions = []
    try:
        recent_actions = (
            client.table('outreach.lead_management_actions')
            .select('*')
            .order('created_at', desc=True)
            .limit(10)
            .execute()
            .data
        )
    except Exception:
        recent_actions = []

    return {
        'open_follow_ups': open_tasks,
        'lead_status_totals': {
            'replied': replied_count,
            'converted': converted_count,
            'dead': dead_count,
        },
        'queue': queue['tasks'],
        'recent_actions': recent_actions,
    }
