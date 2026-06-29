"""
routers/events.py - Event logging and dashboard metrics.
"""

import logging
from fastapi import APIRouter
from database.supabase import db
from services.rating import compute_rating
from services.slack_notifier import notify_meeting_booked, notify_campaign_rating
from models.outreach import EventIn
from agents.lead_management_agent import triage_reply

router = APIRouter(prefix='/events', tags=['events'])
logger = logging.getLogger(__name__)


def _recompute_campaign(campaign_id: int, client):
    events = client.table('outreach.events').select('event_type').eq('campaign_id', campaign_id).execute().data
    counts = {'sent': 0, 'opened': 0, 'replied': 0, 'meeting_booked': 0, 'bounced': 0}
    for e in events:
        if e['event_type'] in counts:
            counts[e['event_type']] += 1
    campaign_res = client.table('outreach.campaigns').select('segment').eq('id', campaign_id).limit(1).execute()
    campaign_segment = campaign_res.data[0]['segment'] if campaign_res.data else None
    leads_count = (client.table('outreach.leads').select('id', count='exact').eq('industry', campaign_segment).execute().count or 100)
    rating = compute_rating(counts['sent'], counts['replied'], counts['meeting_booked'], counts['bounced'], leads_count)
    client.table('outreach.campaigns').update({
        'sent_count': counts['sent'],
        'opened_count': counts['opened'],
        'replied_count': counts['replied'],
        'meeting_count': counts['meeting_booked'],
        'bounced_count': counts['bounced'],
        'rating': rating.total,
    }).eq('id', campaign_id).execute()
    return rating


@router.post('/', summary='Log a campaign event and trigger campaign + lead-management updates')
async def log_event(event: EventIn):
    client = db()
    event_insert = client.table('outreach.events').insert(event.model_dump()).execute()
    event_row = event_insert.data[0] if event_insert.data else None
    rating = _recompute_campaign(event.campaign_id, client)

    status_map = {'replied': 'replied', 'meeting_booked': 'converted'}
    if event.event_type in status_map:
        client.table('outreach.leads').update({'status': status_map[event.event_type]}).eq('id', event.lead_id).execute()

    lead_management = None
    if event.event_type == 'replied' and event.metadata.get('reply_text'):
        try:
            lead_management = await triage_reply(
                campaign_id=event.campaign_id,
                lead_id=event.lead_id,
                reply_text=event.metadata.get('reply_text', ''),
                draft_id=event.draft_id,
                metadata={**event.metadata, 'event_id': event_row.get('id') if event_row else None},
            )
        except Exception as e:
            logger.warning('Akhil triage failed on reply event: %s', e)

    if event.event_type == 'meeting_booked':
        try:
            lead_res = client.table('outreach.leads').select('name, company').eq('id', event.lead_id).execute()
            campaign_res = client.table('outreach.campaigns').select('name').eq('id', event.campaign_id).execute()
            if lead_res.data and campaign_res.data:
                lead = lead_res.data[0]
                await notify_meeting_booked(lead['name'], lead['company'], campaign_res.data[0]['name'])
        except Exception as e:
            logger.warning('Slack meeting_booked notification failed: %s', e)

    if event.event_type == 'sent' and rating.total > 0:
        try:
            plan_res = (
                client.table('outreach.plans')
                .select('steps, start_date')
                .eq('campaign_id', event.campaign_id)
                .eq('status', 'active')
                .limit(1)
                .execute()
            )
            if plan_res.data:
                from datetime import datetime, timezone
                plan = plan_res.data[0]
                start_raw = plan.get('start_date')
                if start_raw:
                    start_date = datetime.fromisoformat(str(start_raw).replace('Z', '+00:00')).date()
                    day = (datetime.now(timezone.utc).date() - start_date).days + 1
                    if day in (7, 14):
                        campaign_res = client.table('outreach.campaigns').select('name').eq('id', event.campaign_id).execute()
                        if campaign_res.data:
                            await notify_campaign_rating(campaign_res.data[0]['name'], rating.total, rating.grade, rating.weakest_axis)
        except Exception as e:
            logger.warning('Slack rating checkpoint notification failed: %s', e)

    return {
        'logged': event.event_type,
        'campaign_rating': rating.total,
        'lead_management': lead_management,
    }


@router.get('/dashboard/', summary='Aggregate metrics across all active campaigns')
def get_dashboard():
    client = db()
    campaigns = client.table('outreach.campaigns').select('*').eq('status', 'active').execute().data
    if not campaigns:
        return {'message': 'No active campaigns', 'campaigns': []}
    summary = []
    for c in campaigns:
        total = c.get('total_leads') or 100
        r = compute_rating(c['sent_count'], c['replied_count'], c['meeting_count'], c['bounced_count'], total)
        summary.append({
            'id': c['id'],
            'name': c['name'],
            'segment': c['segment'],
            'sent': c['sent_count'],
            'replies': c['replied_count'],
            'meetings': c['meeting_count'],
            'rating': r.total,
            'grade': r.grade,
            'weakest_axis': r.weakest_axis,
        })
    summary.sort(key=lambda x: x['rating'], reverse=True)
    total_sent = sum(c['sent'] for c in summary)
    total_replies = sum(c['replies'] for c in summary)
    total_meetings = sum(c['meetings'] for c in summary)
    return {
        'active_campaigns': len(campaigns),
        'totals': {'sent': total_sent, 'replies': total_replies, 'meetings': total_meetings},
        'overall_reply_rate': round(total_replies / max(total_sent, 1) * 100, 1),
        'overall_conversion_rate': round(total_meetings / max(total_replies, 1) * 100, 1),
        'campaigns': summary,
    }
