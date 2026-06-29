import { randomUUID } from 'node:crypto'
import { geminiApiKeyFor } from '../config/env.js'
import { callGeminiDetailed } from '../lib/gemini.js'
import { CMOService } from './cmo.service.js'
import {
  type JarvisAgentType,
  type JarvisTask,
  jarvisStateStore,
} from '../lib/jarvisStateStore.js'

type Intervention = {
  causal_node: string
  task: string
  agent_type: JarvisAgentType
  depends_on?: string[]
  priority?: number
  required_apis?: string[]
}

type CausalMap = {
  causal_analysis: string
  interventions: Intervention[]
}

type AgentDecision = {
  decision: 'execute' | 'spawn' | 'approval_required'
  result?: string
  subtasks?: Intervention[]
  code_request?: {
    system: string
    reason: string
    files: string[]
    required_apis: string[]
    approval_question: string
  }
}

type AgentRunResult = {
  task: string
  status: 'blocked' | 'approval_required' | 'done' | 'failed'
  result: unknown
  causalNode?: string
  children?: AgentRunResult[]
}

export type JarvisGoalInput = {
  goal: string
  mode?: 'advisory' | 'approval' | 'autonomous'
  maxDepth?: number
  maxAgents?: number
}

const allowedAgents: JarvisAgentType[] = ['orchestrator', 'outreach', 'research', 'ops', 'crm', 'content', 'analyst', 'cto', 'cmo', 'cfo', 'lead_generation', 'lead_management', 'human']

function now() {
  return new Date().toISOString()
}

function stripJsonFence(value: string) {
  const trimmed = value.trim()
  if (!trimmed.includes('```')) return trimmed
  const fenced = trimmed.split('```')[1] ?? trimmed
  return fenced.startsWith('json') ? fenced.slice(4).trim() : fenced.trim()
}

function safeAgentType(value: unknown): JarvisAgentType {
  return allowedAgents.includes(value as JarvisAgentType) ? (value as JarvisAgentType) : 'analyst'
}

export class JarvisSovereignService {
  private cmo = new CMOService()
  private activeAgents = new Set<string>()

  async receiveGoal(input: JarvisGoalInput) {
    const maxDepth = input.maxDepth ?? 3
    const maxAgents = input.maxAgents ?? 20
    const mode = input.mode ?? 'approval'
    const runId = randomUUID()
    const createdAt = now()

    await jarvisStateStore.saveRun({
      id: runId,
      goal: input.goal,
      status: 'running',
      mode,
      createdAt,
      updatedAt: createdAt,
    })

    const companyState = await jarvisStateStore.getCompanySnapshot()
    const causalMap = await this.decomposeWithSCI(input.goal, companyState)
    await this.log(runId, 'jarvis-core', runId, 'sci_decomposition', causalMap)

    const rootTask = await this.createTask({
      runId,
      goal: input.goal,
      agentType: 'orchestrator',
      depth: 0,
      parentId: null,
      causalNode: 'company_goal',
      priority: 0,
      dependsOn: [],
    })

    const results = await this.executeInterventions({
      runId,
      parentId: rootTask.id,
      depth: 1,
      maxDepth,
      maxAgents,
      mode,
      interventions: causalMap.interventions,
    })

    const synthesis = await this.synthesize(input.goal, causalMap, results)
    await jarvisStateStore.updateTask(rootTask.id, { status: 'done', result: synthesis })
    await jarvisStateStore.updateRun(runId, { status: 'done', synthesis })

    return {
      ok: true,
      runId,
      causalAnalysis: causalMap.causal_analysis,
      interventions: causalMap.interventions,
      results,
      synthesis,
    }
  }

  async setCompanyState(key: string, value: unknown) {
    return jarvisStateStore.setCompanyState(key, value)
  }

  async getStatus() {
    const state = await jarvisStateStore.getState()
    return {
      runs: state.runs.slice(-20).reverse(),
      tasks: state.tasks.slice(-100).reverse(),
      logs: state.logs.slice(-100).reverse(),
      companyState: state.companyState,
    }
  }

  async recordApproval(taskId: string, approved: boolean, note?: string) {
    const task = await jarvisStateStore.updateTask(taskId, {
      status: approved ? 'pending' : 'blocked',
      result: JSON.stringify({
        approval: approved ? 'approved' : 'rejected',
        note: note ?? '',
        recordedAt: now(),
      }),
    })

    if (task) {
      await this.log(task.runId, 'operator', task.id, approved ? 'approval_granted' : 'approval_rejected', {
        note: note ?? '',
      })
    }

    return task
  }

  private async decomposeWithSCI(goal: string, companyState: Record<string, unknown>): Promise<CausalMap> {
    const fallback: CausalMap = {
      causal_analysis:
        'Goal decomposed into causal interventions across target selection, build capability, lead generation, execution, and measurement.',
      interventions: [
        {
          causal_node: 'target_revenue_path',
          task: 'Define the numerical path from current state to the next revenue target, including lead, email, meeting, and close-rate assumptions.',
          agent_type: 'analyst',
          priority: 1,
        },
        {
          causal_node: 'lead_generation_system',
          task: 'Design and improve the lead generation system, including required data sources, enrichment, scoring, and handoff to outreach.',
          agent_type: 'cto',
          priority: 2,
          required_apis: ['Apify', 'Gemini', 'Gmail'],
        },
        {
          causal_node: 'marketing_message_system',
          task: 'Use Noah CMO to define the campaign positioning, subject-line logic, landing-page promise, and offer angle for Virel Automation lead generation.',
          agent_type: 'cmo',
          priority: 3,
          required_apis: ['Gemini', 'Supabase'],
        },
        {
          causal_node: 'qualified_target_supply',
          task: 'Find and qualify target accounts for the selected segments.',
          agent_type: 'research',
          priority: 6,
        },
        {
          causal_node: 'lead_management_system',
          task: 'Design the reply triage, follow-up, meeting handoff, and CRM state movement for Akhil lead management.',
          agent_type: 'lead_management',
          priority: 5,
          required_apis: ['Gmail', 'Supabase'],
        },
        {
          causal_node: 'outbound_execution',
          task: 'Turn qualified targets into personalized outreach drafts and a controlled sending plan.',
          agent_type: 'outreach',
          priority: 6,
        },
      ],
    }

    if (!geminiApiKeyFor('jarvis')) return fallback

    const prompt = [
      'You are JARVIS SCI, a sovereign causal intelligence engine for a solo founder.',
      'Think in interventions, not generic tasks.',
      'Agent types allowed: orchestrator, outreach, research, ops, crm, content, analyst, cto, cmo, cfo, lead_generation, lead_management, human.',
      'Return strict JSON with keys: causal_analysis, interventions.',
      'Each intervention must include: causal_node, task, agent_type, depends_on, priority, required_apis.',
      '',
      `COMPANY_STATE: ${JSON.stringify(companyState)}`,
      `GOAL: ${goal}`,
    ].join('\n')

    try {
      const text = await this.gemini(prompt, 1800, true)
      const parsed = JSON.parse(stripJsonFence(text)) as CausalMap
      return {
        causal_analysis: parsed.causal_analysis || fallback.causal_analysis,
        interventions: (parsed.interventions || fallback.interventions).map((item, index) => ({
          causal_node: item.causal_node || `node_${index + 1}`,
          task: item.task,
          agent_type: safeAgentType(item.agent_type),
          depends_on: item.depends_on ?? [],
          priority: item.priority ?? index + 1,
          required_apis: item.required_apis ?? [],
        })).filter((item) => item.task),
      }
    } catch {
      return fallback
    }
  }

  private async executeInterventions(input: {
    runId: string
    parentId: string
    depth: number
    maxDepth: number
    maxAgents: number
    mode: 'advisory' | 'approval' | 'autonomous'
    interventions: Intervention[]
  }): Promise<AgentRunResult[]> {
    const sorted = [...input.interventions].sort((a, b) => (a.priority ?? 99) - (b.priority ?? 99))
    const independent = sorted.filter((item) => !item.depends_on?.length)
    const dependent = sorted.filter((item) => item.depends_on?.length)

    const parallel: AgentRunResult[] = await Promise.all(
      independent.map((item) => this.runSingleIntervention({ ...input, intervention: item })),
    )

    const sequential: AgentRunResult[] = []
    for (const item of dependent) {
      sequential.push(await this.runSingleIntervention({ ...input, intervention: item }))
    }

    return [...parallel, ...sequential]
  }

  private async runSingleIntervention(input: {
    runId: string
    parentId: string
    depth: number
    maxDepth: number
    maxAgents: number
    mode: 'advisory' | 'approval' | 'autonomous'
    intervention: Intervention
  }): Promise<AgentRunResult> {
    if (this.activeAgents.size >= input.maxAgents) {
      return { task: input.intervention.task, status: 'blocked', result: 'Agent resource gate reached.' }
    }

    const task = await this.createTask({
      runId: input.runId,
      goal: input.intervention.task,
      agentType: safeAgentType(input.intervention.agent_type),
      depth: input.depth,
      parentId: input.parentId,
      causalNode: input.intervention.causal_node,
      priority: input.intervention.priority ?? 99,
      dependsOn: input.intervention.depends_on ?? [],
    })

    await jarvisStateStore.updateTask(task.id, { status: 'running' })
    const agentId = randomUUID()
    this.activeAgents.add(agentId)

    try {
      const decision = await this.runAgent(task, input.maxDepth, input.mode, input.intervention.required_apis ?? [])
      await this.log(input.runId, agentId, task.id, 'agent_decision', decision)

      if (decision.decision === 'approval_required') {
        await jarvisStateStore.updateTask(task.id, { status: 'approval_required', result: JSON.stringify(decision.code_request ?? decision) })
        return { task: task.goal, status: 'approval_required', result: decision.code_request ?? decision, causalNode: task.causalNode }
      }

      if (decision.decision === 'spawn' && input.depth < input.maxDepth && decision.subtasks?.length) {
        const children: AgentRunResult[] = await this.executeInterventions({
          runId: input.runId,
          parentId: task.id,
          depth: input.depth + 1,
          maxDepth: input.maxDepth,
          maxAgents: input.maxAgents,
          mode: input.mode,
          interventions: decision.subtasks,
        })
        const result: string = JSON.stringify(children)
        await jarvisStateStore.updateTask(task.id, { status: 'done', result })
        return { task: task.goal, status: 'done', result, children, causalNode: task.causalNode }
      }

      const result = decision.result ?? 'Agent completed without detailed output.'
      await jarvisStateStore.updateTask(task.id, { status: 'done', result })
      return { task: task.goal, status: 'done', result, causalNode: task.causalNode }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      await jarvisStateStore.updateTask(task.id, { status: 'failed', result: message })
      return { task: task.goal, status: 'failed', result: message, causalNode: task.causalNode }
    } finally {
      this.activeAgents.delete(agentId)
    }
  }

  private async runAgent(task: JarvisTask, maxDepth: number, mode: 'advisory' | 'approval' | 'autonomous', requiredApis: string[]): Promise<AgentDecision> {
    if (task.agentType === 'cto') {
      return this.runCtoAgent(task, mode, requiredApis)
    }

    if (task.agentType === 'cmo') {
      return this.runCmoAgent(task)
    }

    const fallback: AgentDecision = {
      decision: 'execute',
      result: `${task.agentType} agent completed planning for: ${task.goal}`,
    }

    if (!geminiApiKeyFor('jarvis')) return fallback

    const prompt = [
      `You are the ${task.agentType.toUpperCase()} agent inside JARVIS.`,
      `Task: ${task.goal}`,
      `Depth: ${task.depth}/${maxDepth}`,
      `Mode: ${mode}`,
      'Decide whether to execute directly, spawn subtasks, or request approval.',
      'Return strict JSON: { "decision": "execute|spawn|approval_required", "result": string, "subtasks": [...] }.',
      'At max depth, execute directly. Max 4 subtasks.',
    ].join('\n')

    try {
      const text = await this.gemini(prompt, 1200, true)
      const parsed = JSON.parse(stripJsonFence(text)) as AgentDecision
      return {
        decision: parsed.decision ?? 'execute',
        result: parsed.result,
        subtasks: parsed.subtasks?.slice(0, 4).map((item, index) => ({
          causal_node: item.causal_node || `${task.causalNode ?? 'node'}_${index + 1}`,
          task: item.task,
          agent_type: safeAgentType(item.agent_type),
          depends_on: item.depends_on ?? [],
          priority: item.priority ?? index + 1,
          required_apis: item.required_apis ?? [],
        })),
      }
    } catch {
      return fallback
    }
  }

  private async runCmoAgent(task: JarvisTask): Promise<AgentDecision> {
    const goal = [
      'CMO task from Jarvis SCI graph:',
      task.goal,
      'Company: Virel Automation.',
      'Offer: Lead Generation.',
      'Target industries: HVAC, Real Estate Agents, Digital Marketing Agencies.',
    ].join('\n')
    const result = await this.cmo.spawnSubAgent('message_architect', goal)
    return {
      decision: 'execute',
      result: JSON.stringify(result),
    }
  }
  private async runCtoAgent(task: JarvisTask, mode: 'advisory' | 'approval' | 'autonomous', requiredApis: string[]): Promise<AgentDecision> {
    const request = {
      system: task.goal,
      reason: 'CTO changes can touch code, infrastructure, credentials, or external APIs, so they require explicit operator approval before execution.',
      files: [
        'backend/src/routes/*',
        'backend/src/services/*',
        'backend/src/lib/*',
        'src/App.tsx',
      ],
      required_apis: requiredApis.length ? requiredApis : ['Gemini'],
      approval_question: `Approve CTO to design and implement code for: ${task.goal}`,
    }

    if (mode !== 'autonomous') {
      return { decision: 'approval_required', code_request: request }
    }

    return {
      decision: 'execute',
      result: `CTO generated an implementation plan for ${task.goal}. Autonomous code mutation is disabled in this backend v1; execution should occur through the Codex workspace with audit review.`,
      code_request: request,
    }
  }

  private async synthesize(goal: string, causalMap: CausalMap, results: unknown[]) {
    const fallback = [
      `Goal: ${goal}`,
      `Causal read: ${causalMap.causal_analysis}`,
      'Jarvis created a bounded task graph and assigned work to specialist agents.',
      'CTO tasks that require code or APIs are gated for approval.',
    ].join(' ')

    if (!geminiApiKeyFor('jarvis')) return fallback

    try {
      return await this.gemini(
        [
          'You are Jarvis, CEO/orchestrator. Summarize this run in under 180 words.',
          'State what was decided, what is blocked on Jace, and the next highest-leverage move.',
          `GOAL: ${goal}`,
          `CAUSAL_MAP: ${JSON.stringify(causalMap)}`,
          `RESULTS: ${JSON.stringify(results)}`,
        ].join('\n'),
        900,
        false,
      )
    } catch {
      return fallback
    }
  }

  private async createTask(input: {
    runId: string
    goal: string
    agentType: JarvisAgentType
    depth: number
    parentId: string | null
    causalNode?: string
    priority: number
    dependsOn: string[]
  }) {
    const ts = now()
    const task: JarvisTask = {
      id: randomUUID(),
      runId: input.runId,
      goal: input.goal,
      agentType: input.agentType,
      depth: input.depth,
      parentId: input.parentId,
      status: 'pending',
      causalNode: input.causalNode,
      priority: input.priority,
      dependsOn: input.dependsOn,
      createdAt: ts,
      updatedAt: ts,
    }
    return jarvisStateStore.saveTask(task)
  }

  private async log(runId: string, agentId: string, taskId: string, event: string, payload: unknown) {
    return jarvisStateStore.log({
      id: randomUUID(),
      runId,
      agentId,
      taskId,
      event,
      payload,
      ts: now(),
    })
  }

  private async gemini(prompt: string, maxOutputTokens: number, jsonMode: boolean) {
    const result = await callGeminiDetailed({
      role: 'jarvis',
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: {
        temperature: 0.35,
        maxOutputTokens,
        ...(jsonMode ? { responseMimeType: 'application/json' } : {}),
      },
    })
    return result.text
  }
}
