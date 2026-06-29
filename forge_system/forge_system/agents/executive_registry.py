"""Executive multi-agent registry for the FORGE operating system."""

from copy import deepcopy

EXECUTIVE_SYSTEMS = {
    'jarvis': {
        'speaker_name': 'Jarvis',
        'title': 'CEO',
        'mission': 'Company-wide orchestration, strategic direction, and final executive judgment.',
        'owns': ['orchestrator', 'executive_briefing', 'strategy', 'cross-system delegation'],
        'specialists': [
            'chief_of_staff',
            'board_briefing_analyst',
            'priority_router',
            'risk_sentinel',
        ],
    },
    'damien': {
        'speaker_name': 'Damien',
        'title': 'CTO',
        'mission': 'Reliability, runtime health, integrations, security posture, and automation safety.',
        'owns': ['ops', 'system_health', 'provider_readiness', 'runtime_guardrails'],
        'specialists': [
            'api_sentinel',
            'queue_watcher',
            'credential_guard',
            'deploy_watchdog',
            'incident_triage',
        ],
    },
    'noah': {
        'speaker_name': 'Noah',
        'title': 'CMO',
        'mission': 'Messaging, campaign architecture, subject lines, hooks, and landing-page conversion strategy.',
        'owns': ['campaign_strategy', 'email_copy', 'landing_copy', 'offer_positioning'],
        'specialists': [
            'subject_line_lab',
            'message_architect',
            'offer_positioner',
            'landing_cro',
            'content_angle_scout',
        ],
    },
    'zoya': {
        'speaker_name': 'Zoya',
        'title': 'CFO',
        'mission': 'Revenue intelligence, pipeline economics, goal tracking, and performance analytics.',
        'owns': ['analytics', 'forecasting', 'goal_tracking', 'financial_signaling'],
        'specialists': [
            'forecast_engine',
            'reply_rate_analyst',
            'pipeline_value_monitor',
            'attribution_analyst',
        ],
    },
    'devan': {
        'speaker_name': 'Devan',
        'title': 'Lead Generation Head',
        'mission': 'Lead sourcing, company research, enrichment quality, and outbound list generation.',
        'owns': ['apify_sourcing', 'research', 'enrichment', 'target_discovery'],
        'specialists': [
            'source_hunter',
            'company_researcher',
            'enrichment_scorer',
            'segment_builder',
            'target_quality_auditor',
        ],
    },
    'akhil': {
        'speaker_name': 'Akhil',
        'title': 'Lead Management Head',
        'mission': 'Lead-state progression, reply triage, meeting readiness, and CRM discipline.',
        'owns': ['crm_progression', 'reply_triage', 'follow_up', 'meeting_handling'],
        'specialists': [
            'reply_classifier',
            'crm_steward',
            'follow_up_scheduler',
            'meeting_preparer',
            'handoff_manager',
        ],
    },
    'king': {
        'speaker_name': 'King',
        'title': 'AI Specialist',
        'mission': 'Training governance, memory quality, evaluation, and logging all learning signals to Supabase.',
        'owns': ['training', 'memory', 'evaluation', 'agent_quality_control'],
        'specialists': [
            'memory_librarian',
            'embedding_guard',
            'training_curator',
            'eval_judge',
            'label_auditor',
            'policy_trainer',
        ],
    },
}

EXECUTIVE_ORDER = ['jarvis', 'damien', 'noah', 'zoya', 'devan', 'akhil', 'king']


def get_specialist_agent_count() -> int:
    return sum(len(meta['specialists']) for meta in EXECUTIVE_SYSTEMS.values())


def get_executive_status_map(settings) -> dict:
    result = {}
    for executive_id in EXECUTIVE_ORDER:
        meta = deepcopy(EXECUTIVE_SYSTEMS[executive_id])
        result[executive_id] = {
            'executive_id': executive_id,
            'speaker_name': meta['speaker_name'],
            'title': meta['title'],
            'mission': meta['mission'],
            'owns': meta['owns'],
            'specialists': meta['specialists'],
            'specialist_count': len(meta['specialists']),
            'spawn_capable': True,
            'spawn_limit': settings.executive_spawn_limit,
            'spawn_depth_limit': settings.executive_spawn_depth_limit,
            'gemini_key_configured': bool(settings.gemini_key_for(executive_id)),
            'training_governor': 'king' if executive_id != 'king' else 'self',
            'reports_to': None if executive_id == 'jarvis' else 'jarvis',
        }
    return result


def get_executive_detail(executive_id: str, settings) -> dict | None:
    executive_id = (executive_id or '').strip().lower()
    statuses = get_executive_status_map(settings)
    detail = statuses.get(executive_id)
    if not detail:
        return None

    if executive_id == 'jarvis':
        detail['delegates_to'] = ['damien', 'noah', 'zoya', 'devan', 'akhil', 'king']
    elif executive_id == 'king':
        detail['delegates_to'] = []
        detail['trains'] = ['jarvis', 'damien', 'noah', 'zoya', 'devan', 'akhil']
    else:
        detail['delegates_to'] = ['king']

    detail['governance'] = {
        'requires_logging_to_supabase': True,
        'spawn_capable': True,
        'spawn_limit': settings.executive_spawn_limit,
        'spawn_depth_limit': settings.executive_spawn_depth_limit,
    }
    return detail
