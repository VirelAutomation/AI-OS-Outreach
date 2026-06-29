"""Public funnel and sourcing signal endpoints."""

from datetime import datetime
import logging

from fastapi import APIRouter

from database.supabase import db
from models.automation import LandingVisitIn, ChatSignalIn, BookingSignalIn, ApifyRunIn
from services.apify_client import run_actor, normalize_to_leads, provider_status as apify_provider_status
from services.gmail import provider_status as gmail_provider_status

router = APIRouter(prefix='/signals', tags=['signals'])
log = logging.getLogger('forge.signals')


@router.get('/providers/readiness/', summary='Provider readiness for Gmail and Apify')
async def provider_readiness(live: bool = False):
    return {
        'gmail': await gmail_provider_status(live=live),
        'apify': await apify_provider_status(live=live),
    }


@router.post('/landing-visit/', summary='Capture a landing-page visit from an outreach link')
def capture_landing_visit(payload: LandingVisitIn):
    client = db()
    res = client.table('outreach.page_visits').insert({
        'campaign_id': payload.campaign_id,
        'lead_id': payload.lead_id,
        'draft_id': payload.draft_id,
        'visitor_email': payload.visitor_email,
        'visitor_name': payload.visitor_name,
        'company_name': payload.company_name,
        'page_url': payload.page_url,
        'referrer': payload.referrer,
        'utm_source': payload.utm_source,
        'utm_campaign': payload.utm_campaign,
        'metadata': payload.metadata,
    }).execute()

    client.table('outreach.events').insert({
        'campaign_id': payload.campaign_id,
        'lead_id': payload.lead_id,
        'draft_id': payload.draft_id,
        'event_type': 'landing_visit',
        'metadata': {
            'page_url': payload.page_url,
            'visitor_email': payload.visitor_email,
            **payload.metadata,
        },
    }).execute()

    log.info('Landing visit captured for lead=%s campaign=%s', payload.lead_id, payload.campaign_id)
    return res.data[0]


@router.post('/chat/', summary='Capture Jarvis chatbot engagement from the landing page')
def capture_chat_signal(payload: ChatSignalIn):
    client = db()
    res = client.table('outreach.chat_signals').insert({
        'session_id': payload.session_id,
        'campaign_id': payload.campaign_id,
        'lead_id': payload.lead_id,
        'message': payload.message,
        'sentiment': payload.sentiment,
        'qualified': payload.qualified,
        'metadata': payload.metadata,
    }).execute()

    client.table('outreach.events').insert({
        'campaign_id': payload.campaign_id,
        'lead_id': payload.lead_id,
        'event_type': 'chat_engaged',
        'metadata': {
            'session_id': payload.session_id,
            'qualified': payload.qualified,
            **payload.metadata,
        },
    }).execute()

    return res.data[0]


@router.post('/booking/', summary='Capture a booked call from the landing page')
def capture_booking_signal(payload: BookingSignalIn):
    from services.rating import compute_rating

    client = db()
    res = client.table('outreach.booking_signals').insert({
        'campaign_id': payload.campaign_id,
        'lead_id': payload.lead_id,
        'name': payload.name,
        'email': payload.email,
        'company': payload.company,
        'booking_time': payload.booking_time.isoformat(),
        'source': payload.source,
        'metadata': payload.metadata,
    }).execute()

    client.table('outreach.events').insert({
        'campaign_id': payload.campaign_id,
        'lead_id': payload.lead_id,
        'event_type': 'meeting_booked',
        'metadata': {
            'booking_time': payload.booking_time.isoformat(),
            'source': payload.source,
            **payload.metadata,
        },
    }).execute()

    if payload.lead_id:
        client.table('outreach.leads').update({'status': 'converted'}).eq('id', payload.lead_id).execute()

    if payload.campaign_id:
        campaign_res = client.table('outreach.campaigns').select('*').eq('id', payload.campaign_id).limit(1).execute()
        if campaign_res.data:
            campaign = campaign_res.data[0]
            events = client.table('outreach.events').select('event_type').eq('campaign_id', payload.campaign_id).execute().data
            counts = {'sent': 0, 'opened': 0, 'replied': 0, 'meeting_booked': 0, 'bounced': 0}
            for event in events:
                event_type = event.get('event_type')
                if event_type in counts:
                    counts[event_type] += 1
            leads_count = (client.table('outreach.leads').select('id', count='exact').eq('industry', campaign.get('segment')).execute().count or 100)
            rating = compute_rating(counts['sent'], counts['replied'], counts['meeting_booked'], counts['bounced'], leads_count)
            client.table('outreach.campaigns').update({
                'sent_count': counts['sent'],
                'opened_count': counts['opened'],
                'replied_count': counts['replied'],
                'meeting_count': counts['meeting_booked'],
                'bounced_count': counts['bounced'],
                'rating': rating.total,
            }).eq('id', payload.campaign_id).execute()

    return res.data[0]


@router.post('/apify/run/', summary='Run Apify, normalize results, and persist deduped leads')
async def apify_run(payload: ApifyRunIn):
    actor_input = {
        'search': payload.search_term,
        'industry': payload.industry,
        'city': payload.city,
        'startUrls': [{'url': str(url)} for url in payload.start_urls],
        'maxItems': payload.max_items,
    }

    result = await run_actor(actor_input, actor_id=payload.actor_id)
    items = result.get('items', [])
    leads = normalize_to_leads(items, defaults={'industry': payload.industry, 'city': payload.city})

    client = db()
    created = 0
    skipped = 0
    persisted = []

    for lead in leads:
        existing = client.table('outreach.leads').select('id,email').eq('email', lead['email']).limit(1).execute()
        if existing.data:
            skipped += 1
            persisted.append({'status': 'skipped', 'lead': existing.data[0]})
            continue
        insert = client.table('outreach.leads').insert(lead).execute()
        if insert.data:
            created += 1
            persisted.append({'status': 'created', 'lead': insert.data[0]})

    run_insert = client.table('outreach.source_runs').insert({
        'source_type': 'apify',
        'status': result.get('status', 'unknown'),
        'search_term': payload.search_term,
        'industry': payload.industry,
        'city': payload.city,
        'raw_count': len(items),
        'normalized_count': len(leads),
        'payload': actor_input,
        'response_snapshot': {
            'mode': result.get('mode'),
            'actor_id': result.get('actor_id'),
            'created': created,
            'skipped': skipped,
            'message': result.get('message'),
        },
        'completed_at': datetime.utcnow().isoformat(),
    }).execute()

    return {
        'run': run_insert.data[0] if run_insert.data else None,
        'count': len(leads),
        'created': created,
        'skipped': skipped,
        'mode': result.get('mode', 'offline'),
        'status': result.get('status', 'unknown'),
        'message': result.get('message'),
        'leads': persisted,
    }