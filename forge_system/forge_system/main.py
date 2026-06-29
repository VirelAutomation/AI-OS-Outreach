"""FORGE Intelligence System entry point."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routers import leads, campaigns, drafts, events, jarvis, sci
from routers import orchestrator, tools, automations, signals
from routers import analytics, outreach_router, crm, meetings, cmo, calendar_router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)

settings = get_settings()
_cors_env = settings.cors_allow_origins.strip()
if not _cors_env or _cors_env == '*':
    origins = ['*']
    allow_credentials = False
else:
    origins = [o.strip() for o in _cors_env.split(',') if o.strip()]
    allow_credentials = True

app = FastAPI(
    title='FORGE Intelligence System',
    description=(
        'Backend for FORGE Outreach Agent and Jarvis AI - Virel Automation\n\n'
        'ASI Architecture: 5 AEI specialists (FORGE, JARVIS, ANALYTICS, INTEL, OPS) '
        'coordinated by the central Orchestrator via the Nexus message bus.\n\n'
        'Quick start: POST /asi/command/ with any natural language business command.'
    ),
    version='2.0.0',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_credentials,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(leads.router)
app.include_router(campaigns.router)
app.include_router(drafts.router)
app.include_router(events.router)
app.include_router(jarvis.router)
app.include_router(sci.router)
app.include_router(orchestrator.router)
app.include_router(tools.router)
app.include_router(automations.router)
app.include_router(signals.router)
app.include_router(analytics.router)
app.include_router(outreach_router.router)
app.include_router(crm.router)
app.include_router(meetings.router)
app.include_router(cmo.router)
app.include_router(calendar_router.router)


@app.get('/', tags=['health'])
def root():
    return {
        'status': 'FORGE ASI online',
        'version': '2.0.0',
        'docs': '/docs',
        'aeis': ['forge', 'jarvis', 'analytics', 'intel', 'ops'],
        'asi_command': 'POST /asi/command/',
        'cors_allow_origins': origins,
        'allow_credentials': allow_credentials,
    }


@app.get('/health/', tags=['health'])
def health():
    return {'status': 'ok', 'environment': settings.app_env}
