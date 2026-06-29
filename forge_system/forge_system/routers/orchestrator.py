"""
routers/orchestrator.py - ASI Orchestrator and AEI network endpoints.
"""

from fastapi import APIRouter, HTTPException

from agents.executive_registry import get_executive_detail, get_executive_status_map, get_specialist_agent_count
from agents.lead_management_agent import triage_reply, get_follow_up_queue, get_lead_management_digest
from agents.orchestrator_agent import execute_command, get_system_status
from agents.analytics_agent import analyze_campaign_performance, forecast_pipeline, generate_kpi_report
from agents.intel_agent import research_company, enrich_lead, bulk_enrich_leads, identify_opportunities
from agents.ops_agent import check_system_health, get_campaign_schedule, monitor_draft_queue, generate_ops_digest
from agents.forge_agent import run_campaign_cycle, get_campaign_summary
from agents.training_governor_agent import get_training_readiness, run_governance_cycle, evaluate_executive_systems
from config import get_settings
from models.asi import OrchestratorCommand, ResearchRequest
from models.executive import ReplyTriageIn, GovernanceRunIn

router = APIRouter(prefix='/asi', tags=['ASI Orchestrator'])


@router.get('/', summary='ASI system overview and AEI network status')
async def asi_overview():
    return await get_system_status()


@router.get('/executives/', summary='Executive speaker systems and their specialist pools')
async def executive_registry():
    settings = get_settings()
    return {
        'company_name': settings.company_name,
        'target_mrr': settings.revenue_target_mrr,
        'target_months': settings.revenue_target_months,
        'executives': get_executive_status_map(settings),
        'specialist_agent_count': get_specialist_agent_count(),
        'spawn_limit': settings.executive_spawn_limit,
        'spawn_depth_limit': settings.executive_spawn_depth_limit,
    }


@router.get('/executives/{executive_id}/', summary='Single executive speaker system detail')
async def executive_detail(executive_id: str):
    detail = get_executive_detail(executive_id, get_settings())
    if not detail:
        raise HTTPException(404, f'Executive system {executive_id} not found')
    return detail


@router.get('/health/', summary='OPS AEI system health check')
async def system_health():
    return await check_system_health()


@router.post('/command/', summary='Issue a high-level command to the ASI Orchestrator')
async def orchestrate(command: OrchestratorCommand):
    return await execute_command(command)


@router.get('/analytics/', summary='Analytics AEI - full campaign performance report')
async def analytics_overview():
    return await analyze_campaign_performance()


@router.get('/analytics/{campaign_id}/', summary='Analytics AEI - deep analysis of one campaign')
async def campaign_analysis(campaign_id: int):
    return await analyze_campaign_performance(campaign_id)


@router.get('/analytics/{campaign_id}/forecast/', summary='Analytics AEI - pipeline forecast')
async def pipeline_forecast(campaign_id: int):
    return await forecast_pipeline(campaign_id)


@router.get('/analytics/kpi/report/', summary='Analytics AEI - cross-campaign KPI snapshot')
async def kpi_report():
    return await generate_kpi_report()


@router.post('/intel/research/', summary='Intel AEI - company research brief')
async def company_research(req: ResearchRequest):
    brief = await research_company(req.company_name, req.industry)
    return brief.model_dump()


@router.post('/intel/enrich/{lead_id}/', summary='Intel AEI - enrich a lead with company research')
async def lead_enrichment(lead_id: int):
    return await enrich_lead(lead_id)


@router.post('/intel/enrich/bulk/', summary='Intel AEI - bulk enrich multiple leads')
async def bulk_lead_enrichment(lead_ids: list[int]):
    return await bulk_enrich_leads(lead_ids)


@router.get('/intel/opportunities/{segment}/', summary='Intel AEI - market opportunities in a segment')
async def market_opportunities(segment: str):
    return await identify_opportunities(segment)


@router.get('/ops/schedule/', summary='OPS AEI - today\'s campaign automation schedule')
async def ops_schedule():
    return await get_campaign_schedule()


@router.get('/ops/queue/', summary='OPS AEI - draft review queue status')
async def ops_queue():
    return await monitor_draft_queue()


@router.get('/ops/digest/', summary='OPS AEI - daily operations digest')
async def ops_digest():
    return await generate_ops_digest()


@router.post('/forge/campaigns/{campaign_id}/cycle/', summary='FORGE AEI - run today\'s campaign cycle')
async def campaign_cycle(campaign_id: int):
    return await run_campaign_cycle(campaign_id)


@router.get('/forge/campaigns/{campaign_id}/summary/', summary='FORGE AEI - rich campaign snapshot')
async def campaign_snapshot(campaign_id: int):
    return await get_campaign_summary(campaign_id)


@router.post('/lead-management/triage-reply/', summary='Akhil - classify a lead reply and create follow-up actions')
async def lead_management_triage(payload: ReplyTriageIn):
    return await triage_reply(
        campaign_id=payload.campaign_id,
        lead_id=payload.lead_id,
        reply_text=payload.reply_text,
        draft_id=payload.draft_id,
        metadata=payload.metadata,
    )


@router.get('/lead-management/follow-ups/', summary='Akhil - follow-up queue')
async def lead_management_followups(limit: int = 50):
    return await get_follow_up_queue(limit=limit)


@router.get('/lead-management/digest/', summary='Akhil - lead management digest')
async def lead_management_digest():
    return await get_lead_management_digest()


@router.get('/training/readiness/', summary='King - training readiness snapshot')
async def training_readiness(domain_tag: str | None = None, min_quality: float | None = None, max_examples: int | None = None):
    domain_tags = [domain_tag] if domain_tag else None
    return await get_training_readiness(domain_tags=domain_tags, min_quality=min_quality, max_examples=max_examples)


@router.post('/training/governance/', summary='King - run governance cycle over training and executive readiness')
async def training_governance(payload: GovernanceRunIn):
    return await run_governance_cycle(
        limit=payload.limit,
        domain_tags=payload.domain_tags,
        min_quality=payload.min_quality,
        max_examples=payload.max_examples,
    )


@router.get('/training/evaluations/', summary='King - evaluate executive system readiness')
async def training_evaluations():
    return await evaluate_executive_systems()
