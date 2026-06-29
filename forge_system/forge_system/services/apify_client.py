"""Thin Apify integration layer for lead sourcing and enrichment."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from config import get_settings

log = logging.getLogger('forge.apify')


def is_configured() -> bool:
    s = get_settings()
    return bool(s.apify_api_token and s.apify_default_actor_id)


def _normalize_industry(value: str | None, default_value: str | None = None) -> str | None:
    raw = (value or default_value or '').strip().lower()
    if raw in {'hvac', 'heating', 'cooling', 'heating and cooling'}:
        return 'hvac'
    if raw in {'real estate', 'real estate agents', 'real estate agent', 'realtor', 'realtors'}:
        return 'real_estate_agents'
    if raw in {'digital marketing', 'digital marketing agency', 'digital marketing agencies', 'marketing agency', 'marketing agencies'}:
        return 'digital_marketing_agencies'
    return raw or None


async def run_actor(input_payload: dict[str, Any], actor_id: str | None = None) -> dict[str, Any]:
    s = get_settings()
    actor = actor_id or s.apify_default_actor_id

    if not s.apify_api_token or not actor:
        return {
            'mode': 'offline',
            'status': 'not_configured',
            'message': 'Apify token or actor ID is missing.',
            'items': [],
        }

    url = f'https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items'
    params = {'token': s.apify_api_token}

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, params=params, json=input_payload)
            response.raise_for_status()
            items = response.json()
    except Exception as e:
        log.error('Apify actor run failed for %s: %s', actor, e)
        return {
            'mode': 'live',
            'status': 'error',
            'actor_id': actor,
            'message': str(e),
            'items': [],
        }

    log.info('Apify actor %s returned %s items', actor, len(items))
    return {
        'mode': 'live',
        'status': 'ok',
        'actor_id': actor,
        'items': items,
    }


async def provider_status(live: bool = False) -> dict:
    s = get_settings()
    base = {
        'configured': bool(s.apify_api_token),
        'default_actor_id': s.apify_default_actor_id or None,
    }
    if not live or not s.apify_api_token:
        base['status'] = 'configured' if base['configured'] else 'not_configured'
        return base

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get('https://api.apify.com/v2/users/me', params={'token': s.apify_api_token})
            response.raise_for_status()
            data = response.json().get('data', {})
        return {
            **base,
            'status': 'ready',
            'username': data.get('username'),
            'user_id': data.get('id'),
        }
    except Exception as e:
        return {**base, 'status': 'error', 'error': str(e)}


def normalize_to_leads(items: list[dict[str, Any]], defaults: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    defaults = defaults or {}
    leads: list[dict[str, Any]] = []

    for item in items:
        email = item.get('email') or item.get('workEmail') or item.get('businessEmail')
        company = item.get('company') or item.get('companyName') or item.get('organizationName')
        name = item.get('name') or item.get('fullName') or item.get('contactName')

        if not email or not company or not name:
            continue

        leads.append({
            'name': name,
            'company': company,
            'email': email,
            'role': item.get('title') or item.get('role'),
            'industry': _normalize_industry(item.get('industry'), defaults.get('industry')),
            'city': item.get('city') or defaults.get('city'),
            'phone': item.get('phone'),
            'source': 'apify',
            'notes': item.get('summary') or item.get('description') or '',
            'extra_data': item,
        })

    return leads