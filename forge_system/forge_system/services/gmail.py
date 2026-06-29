"""Gmail API integration with explicit readiness and daily send caps."""

import asyncio
import base64
import logging
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from config import get_settings

logger = logging.getLogger(__name__)

_SCOPES = [
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
]


def _build_service():
    s = get_settings()
    creds = Credentials(
        token=None,
        refresh_token=s.gmail_refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=s.gmail_client_id,
        client_secret=s.gmail_client_secret,
        scopes=_SCOPES,
    )
    creds.refresh(Request())
    return build('gmail', 'v1', credentials=creds)


def _is_configured() -> bool:
    s = get_settings()
    return bool(s.gmail_refresh_token and s.gmail_client_id and s.gmail_client_secret and s.gmail_sender_email)


def _create_draft_sync(to_email: str, subject: str, body: str) -> str:
    s = get_settings()
    svc = _build_service()
    msg = MIMEMultipart('alternative')
    msg['To'] = to_email
    msg['From'] = s.gmail_sender_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
    draft = svc.users().drafts().create(userId='me', body={'message': {'raw': raw}}).execute()
    draft_id = draft['id']
    logger.info('Gmail draft created: %s -> %s', draft_id, to_email)
    return draft_id


def _count_sent_today_sync() -> int:
    svc = _build_service()
    date_token = datetime.now(timezone.utc).strftime('%Y/%m/%d')
    query = f'in:sent after:{date_token}'
    count = 0
    next_page_token = None
    while True:
        result = svc.users().messages().list(
            userId='me',
            q=query,
            maxResults=100,
            pageToken=next_page_token,
        ).execute()
        messages = result.get('messages', [])
        count += len(messages)
        next_page_token = result.get('nextPageToken')
        if not next_page_token:
            break
    return count


def _send_draft_sync(gmail_draft_id: str) -> dict:
    s = get_settings()
    sent_today = _count_sent_today_sync()
    if sent_today >= s.gmail_daily_send_cap_per_account:
        raise RuntimeError(f'daily_cap_reached:{sent_today}/{s.gmail_daily_send_cap_per_account}')
    svc = _build_service()
    result = svc.users().drafts().send(userId='me', body={'id': gmail_draft_id}).execute()
    logger.info('Gmail draft sent: %s -> message %s', gmail_draft_id, result.get('id'))
    return result


def _list_sent_sync(limit: int) -> list:
    svc = _build_service()
    result = svc.users().messages().list(userId='me', labelIds=['SENT'], maxResults=limit).execute()
    return result.get('messages', [])


def _provider_status_sync() -> dict:
    s = get_settings()
    sent_today = _count_sent_today_sync()
    return {
        'configured': True,
        'sender': s.gmail_sender_email,
        'daily_cap': s.gmail_daily_send_cap_per_account,
        'sent_today': sent_today,
        'remaining_today': max(s.gmail_daily_send_cap_per_account - sent_today, 0),
        'status': 'ready' if sent_today < s.gmail_daily_send_cap_per_account else 'cap_reached',
    }


async def create_draft(to_email: str, subject: str, body: str) -> str:
    if not _is_configured():
        logger.debug('Gmail not configured - skipping draft creation')
        return ''
    try:
        return await asyncio.to_thread(_create_draft_sync, to_email, subject, body)
    except Exception as e:
        logger.error('Gmail create_draft failed for %s: %s', to_email, e)
        return ''


async def send_draft(gmail_draft_id: str) -> dict:
    if not gmail_draft_id:
        return {'error': 'missing_gmail_draft_id'}
    if not _is_configured():
        return {'error': 'gmail_not_configured'}
    try:
        return await asyncio.to_thread(_send_draft_sync, gmail_draft_id)
    except Exception as e:
        logger.error('Gmail send_draft failed for %s: %s', gmail_draft_id, e)
        return {'error': str(e)}


async def list_sent(limit: int = 20) -> list:
    if not _is_configured():
        return []
    try:
        return await asyncio.to_thread(_list_sent_sync, limit)
    except Exception as e:
        logger.error('Gmail list_sent failed: %s', e)
        return []


async def provider_status(live: bool = False) -> dict:
    s = get_settings()
    base = {
        'configured': _is_configured(),
        'sender': s.gmail_sender_email or None,
        'daily_cap': s.gmail_daily_send_cap_per_account,
    }
    if not base['configured'] or not live:
        base['status'] = 'configured' if base['configured'] else 'not_configured'
        return base
    try:
        live_status = await asyncio.to_thread(_provider_status_sync)
        return live_status
    except Exception as e:
        return {**base, 'status': 'error', 'error': str(e)}