import { geminiQueueStatus } from '../lib/gemini.js'
import { runtimeStore } from '../lib/runtimeStore.js'
import { checkSchemaReadiness } from '../lib/schemaReadiness.js'
import { OutreachService } from './outreach.service.js'

export type SpawnSystemInput = {
  businessArea: 'ceo' | 'cto' | 'cmo' | 'cfo' | 'lead_generation' | 'lead_management' | 'content' | 'analytics'
  objective: string
  maxAgents?: number
}

const executiveSystems = [
  { id: 'jarvis', name: 'Jarvis', role: 'CEO Orchestrator', scope: 'company-level routing, prioritization, decision synthesis' },
  { id: 'damien', name: 'Damien', role: 'CTO System', scope: 'API health, infrastructure, data integrity, failure investigation' },
  { id: 'noah', name: 'Noah', role: 'CMO System', scope: 'campaign strategy, copy testing, offer positioning' },
  { id: 'zoya', name: 'Zoya', role: 'CFO Analytics System', scope: 'MRR path, unit economics, revenue forecasting' },
  { id: 'devan', name: 'Devan', role: 'Lead Generation Head', scope: 'lead sourcing, Apify runs, enrichment, source quality' },
  { id: 'akhil', name: 'Akhil', role: 'Lead Management Head', scope: 'reply triage, CRM state, follow-ups, meeting handoff' },
  { id: 'king', name: 'King', role: 'AI Specialist', scope: 'evaluation, training data, agent quality, memory governance' },
]

const sciLayers = [
  'Sense: collect provider status, lead signals, campaign events, CRM movement, and revenue data.',
  'Causal: map each business goal into controllable levers such as leads sourced, emails sent, reply rate, booking rate, show rate, close rate, and MRR.',
  'Intervene: spawn bounded specialist systems with explicit tools, limits, approval rules, and rollback criteria.',
]

async function supabaseReadiness() {
  return checkSchemaReadiness()
}

export class CtoService {
  private outreach = new OutreachService()

  async systemReadiness() {
    const [outreachReadiness, supabase] = await Promise.all([
      this.outreach.readiness(),
      supabaseReadiness(),
    ])

    const providers = {
      ...outreachReadiness.providers,
      supabase,
    }

    const missing = Object.entries(providers)
      .filter(([, value]) => !value.ok)
      .map(([key, value]) => ({ provider: key, status: value.status, message: value.message }))

    return {
      ok: missing.length === 0,
      company: 'Virel Automation',
      offer: 'Lead Generation',
      targetIndustries: ['HVAC', 'Real Estate Agents', 'Digital Marketing Agencies'],
      targetMrr: 15000000,
      targetMonths: 7,
      providers,
      storage: runtimeStore.storage,
      queue: geminiQueueStatus(),
      missing,
    }
  }

  sciArchitecture() {
    return {
      ok: true,
      architecture: 'SCI',
      layers: sciLayers,
      executiveSystems,
      spawnPolicy: {
        defaultMaxAgentsPerSystem: 10,
        hardMaxAgentsPerRequest: 50,
        requiresApprovalFor: ['sending_email_batches', 'code_mutation', 'credential_changes', 'production_infrastructure_changes'],
        autonomousAllowedFor: ['readiness_checks', 'draft_generation', 'lead_scoring', 'analytics_summaries', 'follow_up_recommendations'],
      },
      businessLevers: [
        'qualified leads sourced per day',
        'approved drafts generated per day',
        'emails sent per inbox per day',
        'reply rate by industry',
        'meeting booking rate',
        'show rate',
        'close rate',
        'monthly recurring revenue',
      ],
    }
  }

  spawnPlan(input: SpawnSystemInput) {
    const maxAgents = Math.min(input.maxAgents ?? 10, 50)
    const owner = executiveSystems.find((system) => {
      if (input.businessArea === 'ceo') return system.id === 'jarvis'
      if (input.businessArea === 'cto') return system.id === 'damien'
      if (input.businessArea === 'cmo') return system.id === 'noah'
      if (input.businessArea === 'cfo' || input.businessArea === 'analytics') return system.id === 'zoya'
      if (input.businessArea === 'lead_generation') return system.id === 'devan'
      if (input.businessArea === 'lead_management') return system.id === 'akhil'
      return system.id === 'king'
    }) ?? executiveSystems[0]

    const agents = Array.from({ length: maxAgents }, (_, index) => ({
      id: `${owner.id}_agent_${index + 1}`,
      owner: owner.name,
      role: this.agentRoleFor(input.businessArea, index),
      objective: input.objective,
      status: 'planned',
    }))

    return {
      ok: true,
      owner,
      objective: input.objective,
      agents,
      guardrails: [
        'Every agent writes output to the run log before handoff.',
        'External API execution requires provider readiness.',
        'Email sending stays capped at 100 messages per Gmail account per day.',
        'Production code changes require explicit operator approval.',
      ],
    }
  }

  private agentRoleFor(area: SpawnSystemInput['businessArea'], index: number) {
    const roles: Record<SpawnSystemInput['businessArea'], string[]> = {
      ceo: ['priority analyst', 'decision synthesizer', 'risk reviewer', 'execution coordinator'],
      cto: ['provider checker', 'failure investigator', 'data integrity auditor', 'deployment reviewer'],
      cmo: ['segment strategist', 'copy analyst', 'offer tester', 'landing-page analyst'],
      cfo: ['MRR forecaster', 'unit economics analyst', 'goal gap analyst', 'revenue attribution analyst'],
      lead_generation: ['source scout', 'Apify run planner', 'lead quality scorer', 'enrichment reviewer'],
      lead_management: ['reply classifier', 'follow-up scheduler', 'CRM hygiene reviewer', 'meeting handoff agent'],
      content: ['hook researcher', 'proof asset planner', 'distribution planner', 'content performance analyst'],
      analytics: ['cohort analyst', 'funnel analyst', 'root integrity checker', 'experiment evaluator'],
    }
    const list = roles[area]
    return list[index % list.length]
  }
}
