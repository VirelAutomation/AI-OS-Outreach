"""Generate cold-email drafts for the current Virel Automation offer."""

from typing import Optional

import google.generativeai as genai

from config import get_settings


ICP_PAIN_MAP = {
    'hvac': {
        'pains': [
            'the owner relies on referrals and inconsistent ad spend, so the pipeline swings month to month',
            'technicians stay busy, but the calendar is not predictably filled with high-quality booked jobs',
            'follow-up on old inquiries and estimate requests is inconsistent, so revenue leaks after first contact',
        ],
        'tone': 'direct, practical, local-business aware. Focus on booked jobs, estimate volume, and calendar consistency.',
        'outcomes': 'more booked service calls, more estimate requests, steadier lead flow each month',
    },
    'real_estate_agents': {
        'pains': [
            'lead flow depends too heavily on platform churn, referrals, and manual follow-up',
            'agents waste time chasing low-intent prospects instead of consistently speaking to motivated sellers or buyers',
            'the pipeline gets thin between deals because outreach and nurture are not systemized',
        ],
        'tone': 'sharp, opportunity-driven, focused on listings, buyer intent, and calendar density.',
        'outcomes': 'more inbound seller conversations, more qualified buyer calls, more consistent pipeline month to month',
    },
    'digital_marketing_agencies': {
        'pains': [
            'growth depends on founder-led sales and sporadic referrals instead of a repeatable acquisition engine',
            'the team delivers well, but new business generation is inconsistent and hard to forecast',
            'cold outreach and follow-up are too manual to produce steady qualified calls each month',
        ],
        'tone': 'commercial, performance-oriented, focused on qualified calls, pipeline predictability, and client acquisition.',
        'outcomes': 'more qualified discovery calls, steadier agency pipeline, more new-client conversations each month',
    },
}


def _build_prompt(lead: dict, segment: str, custom_instructions: Optional[str] = None) -> str:
    settings = get_settings()
    pain_context = ICP_PAIN_MAP.get(segment, ICP_PAIN_MAP['digital_marketing_agencies'])
    pains_text = '\n'.join(f'- {p}' for p in pain_context['pains'])

    return f"""You are Noah, the CMO system at {settings.company_name}.

Offer: {settings.primary_offer}
Core promise: we help businesses get more leads per month through a structured outbound and follow-up system.

Generate ONE personalized cold email for this lead. Follow every rule exactly.

LEAD DATA:
Name: {lead.get('name', 'there')}
Company: {lead.get('company', '')}
Role: {lead.get('role', 'decision maker')}
City: {lead.get('city', '')}
Industry: {segment}
Notes: {lead.get('notes', 'none')}

SEGMENT PAIN POINTS (reference the most relevant one, do not list all):
{pains_text}

TONE: {pain_context['tone']}
OUTCOMES TO REFERENCE: {pain_context['outcomes']}

RULES - follow all of them without exception:
1. Subject line: specific hook, 8 words maximum, no generic sales phrasing.
2. Opener: one sentence referencing something specific to their role or business type.
3. Pain: 1-2 sentences naming the exact lead-generation problem in present tense.
4. Bridge: one sentence connecting that pain to {settings.company_name}'s lead-generation system. Describe outcomes, not features.
5. CTA: one sentence, one ask only - either a reply or a 15-minute call.
6. Sign-off: 'Jace / {settings.company_name}'
7. No placeholders.
8. No robotic AI language. Write like a smart operator, not a template machine.
9. Keep the body concise. No paragraph should exceed 2 sentences.

{f'ADDITIONAL INSTRUCTIONS: {custom_instructions}' if custom_instructions else ''}

OUTPUT FORMAT - return only this:
Subject: [subject line]

[email body]
"""


async def generate_draft(lead: dict, segment: str, custom_instructions: Optional[str] = None) -> dict:
    settings = get_settings()
    genai.configure(api_key=settings.gemini_key_for('noah'))
    model = genai.GenerativeModel(settings.gemini_model_default)

    prompt = _build_prompt(lead, segment, custom_instructions)
    response = model.generate_content(prompt)
    raw = response.text.strip()

    lines = raw.split('\n')
    subject = ''
    body_lines = []
    parsing_body = False

    for line in lines:
        if line.startswith('Subject:'):
            subject = line.replace('Subject:', '').strip()
        elif subject and line.strip() == '' and not parsing_body:
            parsing_body = True
        elif parsing_body:
            body_lines.append(line)

    body = '\n'.join(body_lines).strip()

    if not subject or not body:
        parts = raw.split('\n\n', 1)
        subject = parts[0].replace('Subject:', '').strip() if parts else 'Lead generation idea'
        body = parts[1].strip() if len(parts) > 1 else raw

    return {'subject': subject, 'body': body}


async def generate_drafts_batch(leads: list[dict], segment: str, custom_instructions: Optional[str] = None) -> list[dict]:
    results = []
    for lead in leads:
        try:
            draft = await generate_draft(lead, segment, custom_instructions)
            results.append({
                'lead_id': lead.get('id'),
                'subject': draft['subject'],
                'body': draft['body'],
                'status': 'generated',
            })
        except Exception as e:
            results.append({
                'lead_id': lead.get('id'),
                'status': 'failed',
                'error': str(e),
            })
    return results