"""Email draft management."""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from database.supabase import db
from models.outreach import DraftIn, DraftUpdate
from services.gmail import create_draft as gmail_create_draft, send_draft as gmail_send_draft, provider_status as gmail_provider_status

router = APIRouter(prefix='/drafts', tags=['drafts'])
logger = logging.getLogger(__name__)


@router.post('/', summary='Save a draft manually and push it to Gmail')
async def create_draft(draft: DraftIn):
    client = db()
    lead_res = client.table('outreach.leads').select('email').eq('id', draft.lead_id).execute()
    lead_email = lead_res.data[0]['email'] if lead_res.data else ''

    gmail_draft_id = ''
    gmail_status = await gmail_provider_status(live=False)
    if lead_email and gmail_status.get('configured'):
        try:
            gmail_draft_id = await gmail_create_draft(lead_email, draft.subject, draft.body)
        except Exception as e:
            logger.warning('Gmail draft creation failed for lead %d: %s', draft.lead_id, e)

    payload = draft.model_dump()
    payload['gmail_draft_id'] = gmail_draft_id or None
    payload.setdefault('extra_data', {})
    payload['extra_data']['gmail_configured'] = gmail_status.get('configured', False)
    res = client.table('outreach.email_drafts').insert(payload).execute()
    return res.data[0]


@router.get('/', summary='List drafts by campaign or status')
def get_drafts(campaign_id: int = None, status: str = None, limit: int = 50):
    client = db()
    q = client.table('outreach.email_drafts').select('*')
    if campaign_id:
        q = q.eq('campaign_id', campaign_id)
    if status:
        q = q.eq('status', status)
    return {'total': len(q.execute().data), 'drafts': q.limit(limit).execute().data}


@router.put('/{draft_id}/', summary='Edit a draft or update its status')
def update_draft(draft_id: int, update: DraftUpdate):
    client = db()
    payload = {k: v for k, v in update.model_dump().items() if v is not None}
    if 'body' in payload or 'subject' in payload:
        current = client.table('outreach.email_drafts').select('version').eq('id', draft_id).execute()
        if current.data:
            payload['version'] = current.data[0]['version'] + 1
    res = client.table('outreach.email_drafts').update(payload).eq('id', draft_id).execute()
    if not res.data:
        raise HTTPException(404, 'Draft not found')
    return res.data[0]


@router.post('/{draft_id}/approve/', summary='Approve a draft for sending')
def approve_draft(draft_id: int):
    res = db().table('outreach.email_drafts').update({'status': 'approved'}).eq('id', draft_id).execute()
    if not res.data:
        raise HTTPException(404, 'Draft not found')
    return {'draft_id': draft_id, 'status': 'approved'}


@router.post('/{draft_id}/send/', summary='Send draft via Gmail and log the event only on success')
async def send_draft(draft_id: int):
    client = db()
    draft_res = client.table('outreach.email_drafts').select('*').eq('id', draft_id).execute()
    if not draft_res.data:
        raise HTTPException(404, 'Draft not found')
    draft = draft_res.data[0]

    if draft.get('status') not in {'approved', 'draft'}:
        raise HTTPException(409, f"Draft status '{draft.get('status')}' cannot be sent")
    if not draft.get('gmail_draft_id'):
        raise HTTPException(409, 'Draft has no Gmail draft ID. Create or refresh the Gmail draft first.')

    gmail_result = await gmail_send_draft(draft['gmail_draft_id'])
    if gmail_result.get('error'):
        raise HTTPException(502, f"Gmail send failed: {gmail_result['error']}")

    client.table('outreach.email_drafts').update({
        'status': 'sent',
        'sent_at': datetime.utcnow().isoformat(),
    }).eq('id', draft_id).execute()

    client.table('outreach.events').insert({
        'campaign_id': draft['campaign_id'],
        'lead_id': draft['lead_id'],
        'draft_id': draft_id,
        'event_type': 'sent',
        'metadata': {
            'gmail_message_id': gmail_result.get('id'),
            'gmail_thread_id': gmail_result.get('threadId'),
        },
    }).execute()

    return {'draft_id': draft_id, 'status': 'sent', 'gmail': gmail_result}