import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  Bell,
  Bot,
  Brain,
  Calendar,
  CalendarCheck2,
  ChartColumn,
  ChevronDown,
  CircleDot,
  Clipboard,
  Command,
  Database,
  FileText,
  Globe,
  LayoutDashboard,
  LineChart,
  Megaphone,
  Plus,
  RefreshCw,
  Search,
  Send,
  Settings,
  Sparkles,
  Users,
  Video,
  Wrench,
  Zap,
} from 'lucide-react'

type PageId =
  | 'ceo'
  | 'jarvis'
  | 'automations'
  | 'cmo'
  | 'cto'
  | 'outreach'
  | 'crm'
  | 'meetings'
  | 'landing'
  | 'analytics'
  | 'content'
  | 'selfdev'
  | 'settings'
  | 'public'

type NavItem = {
  id: PageId
  label: string
  group: 'Command' | 'Systems' | 'Pipeline' | 'Intelligence'
  icon: typeof LayoutDashboard
}

type LiveMetrics = {
  totalLeads: number
  totalDrafts: number
  emailsSent: number
  sendFailures: number
  replies: number
  meetingsBooked: number
  replyRate: number
  meetingRate: number
  pipelineValue: number
}

type CampaignLeaderboardEntry = {
  id: string
  name: string
  vertical: string
  sent: number
  replyRate: number
  meetingsBooked: number
}

type RecentReplyEntry = {
  id: string
  intent: string
  rawText: string
  createdAt: string
  leadId: string
  fullName: string
  companyName: string
}

type AnalyticsOverview = {
  metrics: LiveMetrics
  campaignLeaderboard: CampaignLeaderboardEntry[]
  recentReplies: RecentReplyEntry[]
  integrity?: {
    statsSource?: string
  }
}

type CrmProspect = {
  id: string
  full_name: string
  email?: string
  company_name: string
  industry?: string
  city?: string
  status?: string
  source?: string
  created_at?: string
}

type MeetingsRecord = {
  id: string
  prospect_name: string
  company_name: string
  meeting_type: string
  start_at: string
  status: string
  value_estimate?: number
}

type OutreachDraft = {
  id: string
  subject: string
  mode: string
  created_at?: string
  createdAt?: string
  prospects?: { full_name?: string; company_name?: string; email?: string } | null
}

type OutreachSend = {
  id: string
  recipient_email?: string
  to?: string
  status: string
  reason?: string
  created_at?: string
  createdAt?: string
  prospects?: { full_name?: string; company_name?: string } | null
  outreach_drafts?: { subject?: string; mode?: string } | null
}

type OutreachReply = {
  id: string
  intent: string
  raw_text?: string
  rawText?: string
  created_at?: string
  createdAt?: string
  prospects?: { full_name?: string; company_name?: string; email?: string } | null
}

type OutreachDashboard = {
  drafts: OutreachDraft[]
  sends: OutreachSend[]
  replies: OutreachReply[]
  source: string
}

type SciAvailabilityWindow = {
  start_at: string
  end_at: string
  label: string
  energy: string
}

type SciHypothesis = {
  title: string
  rationale: string
  expected_impact: string
  uncertainty: string
  next_action: string
  owner: string
}

type SciWorldState = {
  founder_id: string
  company_name: string
  target_state: string
  founder_notes: string[]
  company_constraints: string[]
  backlog: string[]
  focus_areas: string[]
  context_sources: string[]
  availability_windows: SciAvailabilityWindow[]
  growth_hypotheses: SciHypothesis[]
  metadata?: Record<string, unknown>
}

type SciObjectiveNode = {
  id: string
  title: string
  description: string
  owner: string
  priority: number
  depends_on: string[]
  success_metric: string
  risk_level: string
  action_type: string
  evidence: string[]
}

type SciObjectiveGraph = {
  graph_id: string
  founder_id?: string
  target_state: string
  summary: string
  nodes: SciObjectiveNode[]
  selected_plan_id?: string
  created_at?: string
}

type SciAllocation = {
  allocation_id: string
  graph_id: string
  node_id: string
  owner: string
  title: string
  rationale: string
  start_at?: string
  end_at?: string
  status: string
  approval_required: boolean
  risk_level: string
  created_at?: string
}

type SciApproval = {
  decision_id: string
  graph_id: string
  node_id: string
  title: string
  rationale: string
  risk_level: string
  action_type: string
  status: string
  approval_required: boolean
  created_at?: string
}

type SciExecution = {
  trace_id: string
  graph_id: string
  node_id?: string
  agent_name: string
  action_type: string
  status: string
  summary: string
  created_at?: string
}

type SciEval = {
  eval_id: string
  scenario: string
  planner_model: string
  executor_model: string
  plan_quality: number
  routing_quality: number
  latency_ms: number
  estimated_cost: number
  summary: string
  created_at?: string
}

type SciCycleResult = {
  world_state: SciWorldState
  objective_graph: SciObjectiveGraph
  selected_plan: {
    title: string
    reasoning: string
    why_selected?: string
    leverage_score: number
    feasibility_score: number
    risk_score: number
  }
  allocations: SciAllocation[]
  approvals: SciApproval[]
  executions: SciExecution[]
  model_eval: SciEval
}

// ── CMO Types ──────────────────────────────────────────────────────────────
type CMOPlatform = 'tiktok' | 'instagram_reels' | 'youtube_shorts' | 'linkedin' | 'twitter'
type ContentFormat =
  | 'talking_head'
  | 'voiceover_b_roll'
  | 'text_on_screen'
  | 'hook_reveal'
  | 'storytime'
  | 'list_format'
  | 'day_in_life'

type ViralPattern = {
  hookFormula: string
  angle: string
  structure: string[]
  retentionTechnique: string
  exampleOpener: string
  whyItWorks: string
}

type ViralResearch = {
  niche: string
  platform: CMOPlatform
  topPatterns: ViralPattern[]
  goldHooks: string[]
  contentAngles: string[]
  avoidThese: string[]
  trendingFormats: string[]
  researchSummary: string
}

type VideoConcept = {
  id: string
  title: string
  hook: string
  angle: string
  format: ContentFormat
  platforms: CMOPlatform[]
  viralScore: number
  whyItWorks: string
  openingLine: string
  keyPoints: string[]
  cta: string
}

type ScriptSegment = {
  label: string
  timing: string
  content: string
  visualNote: string
}

type VideoScript = {
  title: string
  platform: CMOPlatform
  duration: string
  hook: string
  segments: ScriptSegment[]
  cta: string
  captionHook: string
  hashtags: string[]
  viralScore: number
  scoreReason: string
  productionNotes: string[]
}

type HookScore = {
  hook: string
  platform: CMOPlatform
  overallScore: number
  breakdown: {
    patternInterrupt: number
    curiosityGap: number
    specificity: number
    emotionalPull: number
    clarity: number
  }
  strengths: string[]
  improvements: string[]
  rewriteSuggestions: string[]
}
// ───────────────────────────────────────────────────────────────────────────

const RAW_API_BASE = import.meta.env.VITE_API_BASE_URL?.trim() || 'http://localhost:8000'
const API_BASE = RAW_API_BASE.replace(/\/+$/, '')
const RAW_SCI_API_BASE = import.meta.env.VITE_SCI_API_BASE_URL?.trim() || RAW_API_BASE
const SCI_API_BASE = RAW_SCI_API_BASE.replace(/\/+$/, '')
const BACKEND_API_KEY = import.meta.env.VITE_BACKEND_API_KEY?.trim()

function apiUrl(path: string) {
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
}

function sciApiUrl(path: string) {
  return `${SCI_API_BASE}${path.startsWith('/') ? path : `/${path}`}`
}

async function apiFetch(path: string, init?: RequestInit) {
  const headers = new Headers(init?.headers)
  if (BACKEND_API_KEY) headers.set('x-api-key', BACKEND_API_KEY)
  return fetch(apiUrl(path), { ...init, headers })
}

async function sciApiFetch(path: string, init?: RequestInit) {
  const headers = new Headers(init?.headers)
  if (BACKEND_API_KEY) headers.set('x-api-key', BACKEND_API_KEY)
  return fetch(sciApiUrl(path), { ...init, headers })
}

function formatDateTime(value?: string) {
  if (!value) return 'Unknown'
  return new Date(value).toLocaleString()
}

const navItems: NavItem[] = [
  { id: 'ceo', label: 'CEO Overview', group: 'Command', icon: LayoutDashboard },
  { id: 'jarvis', label: 'Jarvis Command', group: 'Command', icon: Bot },
  { id: 'automations', label: 'Automations', group: 'Command', icon: Command },
  { id: 'cmo', label: 'CMO System', group: 'Systems', icon: Megaphone },
  { id: 'cto', label: 'CTO System', group: 'Systems', icon: Activity },
  { id: 'outreach', label: 'Outreach Pipeline', group: 'Pipeline', icon: Send },
  { id: 'crm', label: 'CRM', group: 'Pipeline', icon: Users },
  { id: 'meetings', label: 'Meetings', group: 'Pipeline', icon: CalendarCheck2 },
  { id: 'landing', label: 'Landing Intelligence', group: 'Intelligence', icon: Globe },
  { id: 'analytics', label: 'Analytics', group: 'Intelligence', icon: LineChart },
  { id: 'content', label: 'Content Cycle', group: 'Intelligence', icon: FileText },
  { id: 'selfdev', label: 'Self Development', group: 'Intelligence', icon: Brain },
  { id: 'settings', label: 'Settings', group: 'Intelligence', icon: Settings },
]

function App() {
  const [activePage, setActivePage] = useState<PageId>('ceo')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [jarvisMode, setJarvisMode] = useState('Execute with approval')
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null)
  const grouped = useMemo(
    () =>
      ['Command', 'Systems', 'Pipeline', 'Intelligence'].map((group) => ({
        group,
        items: navItems.filter((item) => item.group === group),
      })),
    [],
  )

  const loadOverview = useCallback(async () => {
    try {
      const response = await apiFetch('/api/analytics/overview')
      const json = await response.json()
      if (json?.ok) {
        setOverview({
          metrics: json.metrics,
          campaignLeaderboard: json.campaignLeaderboard ?? [],
          recentReplies: json.recentReplies ?? [],
          integrity: json.integrity,
        })
      }
    } catch {
      // keep UI live even if backend is unreachable
    }
  }, [])

  useEffect(() => { void loadOverview() }, [loadOverview])

  // SSE — real-time pipeline updates from the backend
  useEffect(() => {
    let es: EventSource | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let active = true

    const connect = () => {
      if (!active) return
      try {
        es = new EventSource(apiUrl('/api/events'))

        es.onmessage = (e) => {
          try {
            const event = JSON.parse(e.data) as { type?: string }
            const refreshTypes = new Set([
              'email_sent', 'reply_received', 'meeting_booked', 'lead_enriched',
              'pipeline_updated', 'lead_added', 'draft_created',
            ])
            if (event.type && refreshTypes.has(event.type)) {
              void loadOverview()
            }
          } catch { /* malformed event — ignore */ }
        }

        es.onerror = () => {
          es?.close()
          es = null
          if (active) {
            reconnectTimer = setTimeout(connect, 10000)
          }
        }
      } catch { /* SSE not supported or blocked */ }
    }

    connect()

    return () => {
      active = false
      if (reconnectTimer) clearTimeout(reconnectTimer)
      es?.close()
    }
  }, [loadOverview])

  return (
    <div className="forge-app">
      <aside className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}>
        <div className="brand-row">
          <div className="logo-box">F</div>
          {!sidebarCollapsed && (
            <div>
              <h1>FORGE</h1>
              <p>VIRELL LABS</p>
            </div>
          )}
        </div>
        <button className="collapse-btn" onClick={() => setSidebarCollapsed((v) => !v)}>
          <ChevronDown size={14} className={sidebarCollapsed ? 'rot' : ''} />
        </button>
        <div className="status-strip">
          <div><span className="dot green" /> {!sidebarCollapsed && 'Jarvis Online'}</div>
          <div><span className="dot blue" /> {!sidebarCollapsed && 'Outreach Sending'}</div>
          <div><span className="dot amber" /> {!sidebarCollapsed && 'Gemini 71%'}</div>
        </div>
        <div className="nav-scroller">
          {grouped.map(({ group, items }) => (
            <div key={group}>
              {!sidebarCollapsed && <p className="group-label">{group}</p>}
              {items.map((item) => {
                const Icon = item.icon
                return (
                  <button
                    key={item.id}
                    className={`nav-item ${activePage === item.id ? 'active' : ''}`}
                    onClick={() => setActivePage(item.id)}
                  >
                    <Icon size={16} />
                    {!sidebarCollapsed && <span>{item.label}</span>}
                  </button>
                )
              })}
            </div>
          ))}
        </div>
        <div className="sidebar-actions">
          <button className="btn primary">Ask Jarvis</button>
          {!sidebarCollapsed && <button className="btn secondary">Run Automation</button>}
          <button className="btn secondary" onClick={() => setActivePage('public')}>Public Funnel</button>
        </div>
      </aside>

      <main className={`main ${sidebarCollapsed ? 'wide' : ''}`}>
        <header className="topbar">
          <div className="search"><Search size={14} /> Search command, lead, campaign...</div>
          <div className="pill red">Campaign: Q2 Legal Sprint</div>
          <div className="pill green">System Health: OK</div>
          <div className="pill">Automations: 14 Active</div>
          <div className="jarvis-quick"><Bot size={14} /> Jarvis quick prompt...</div>
          <button className="icon-btn"><Plus size={14} /></button>
          <button className="icon-btn notify"><Bell size={14} /><span>5</span></button>
          <div className="avatar">VK</div>
        </header>
        <div className="wave-line" />

        <section className="content-layout">
          <div className="page">{renderPage(activePage, jarvisMode, setJarvisMode, overview)}</div>
          {activePage === 'jarvis' && (
            <aside className="right-rail">
              {[
                ['CURRENT GOALS', ['Book 18 meetings this week', 'Raise reply rate above 11%']],
                ['ACTIVE CAMPAIGNS', ['Legal Intake 13.2%', 'Fintech Reconciliation 9.4%']],
                ['FOLLOW-UPS DUE', ['19 leads need touch today', '4 hot prospects overdue']],
                ['CTO ALERTS', ['Gmail token refresh in 3h', '2 failed enrichment runs']],
                ['CMO RECOMMENDATIONS', ['Push pain angle: compliance lag', 'Increase CTA specificity']],
              ].map(([label, rows]) => (
                <div className="rail-panel" key={label as string}>
                  <p>{label}</p>
                  {(rows as string[]).map((r) => <div key={r}>{r}</div>)}
                </div>
              ))}
            </aside>
          )}
        </section>
      </main>
    </div>
  )
}

function renderPage(page: PageId, jarvisMode: string, setJarvisMode: (v: string) => void, overview: AnalyticsOverview | null) {
  if (page === 'ceo') return <CEOOverview overview={overview} />
  if (page === 'jarvis') return <JarvisCommand jarvisMode={jarvisMode} setJarvisMode={setJarvisMode} />
  if (page === 'automations') return <Automations />
  if (page === 'cmo') return <CMOSystem />
  if (page === 'cto') return <CTOSystem />
  if (page === 'outreach') return <OutreachPipeline />
  if (page === 'crm') return <CRM />
  if (page === 'meetings') return <Meetings />
  if (page === 'landing') return <LandingIntelligence />
  if (page === 'analytics') return <Analytics />
  if (page === 'content') return <ContentCycle />
  if (page === 'selfdev') return <SelfDevelopment />
  if (page === 'settings') return <SettingsPage />
  return <PublicFunnel />
}

function CEOOverview({ overview }: { overview: AnalyticsOverview | null }) {
  const metrics = overview?.metrics ?? null
  const metricValues = metrics
    ? [
        `${metrics.pipelineValue > 0 ? Math.min(Math.round((metrics.pipelineValue / 5000000) * 100), 100) : 0}%`,
        `${metrics.meetingsBooked}`,
        `$${metrics.pipelineValue.toLocaleString('en-US')}`,
        `${metrics.totalLeads}`,
        `${metrics.emailsSent}`,
        `${metrics.replyRate.toFixed(2)}%`,
      ]
    : ['0%', '0', '$0', '0', '0', '0.00%']
  return (
    <div>
      <PageHeader title="CEO Overview" />
      <div className="hero-strip">
        {['Revenue target progress', 'Meetings booked this week', 'Active pipeline value', 'New leads today', 'Emails sent today', 'Reply rate'].map((x, i) => (
          <button className="metric" key={x}><p>{x}</p><h3>{metricValues[i]}</h3></button>
        ))}
      </div>
      <div className="two-col">
        <div className="card">
          <CardTitle title="Company Pulse" />
          {(overview?.recentReplies.length ?? 0) === 0 && (
            <div className="pulse-row"><CircleDot size={12} /><div><strong>No live replies yet</strong><span>Sync Gmail replies or start sending through the connected inbox to populate this panel.</span></div><small>live</small></div>
          )}
          {(overview?.recentReplies ?? []).slice(0, 4).map((reply) => (
            <div key={reply.id} className="pulse-row"><CircleDot size={12} /><div><strong>{reply.fullName} · {reply.intent}</strong><span>{reply.rawText || 'Reply captured without body text.'}</span></div><small>{new Date(reply.createdAt).toLocaleDateString()}</small></div>
          ))}
        </div>
        <div className="card">
          <CardTitle title="Sector Leaderboard" />
          {(overview?.campaignLeaderboard.length ?? 0) === 0 && (
            <div className="leader-row">
              <div><strong>No live campaigns yet</strong><span>Create sends and campaign records to populate sector conversion data.</span></div>
              <div className="bar"><span style={{ width: '0%' }} /></div>
              <b>0%</b>
            </div>
          )}
          {(overview?.campaignLeaderboard ?? []).map((item) => (
            <div className="leader-row" key={item.id}>
              <div><strong>{item.name || item.vertical}</strong><span>{item.sent} sent / {item.meetingsBooked} booked</span></div>
              <div className="bar"><span style={{ width: `${Math.min(item.replyRate, 100)}%` }} /></div>
              <b>{item.replyRate}%</b>
            </div>
          ))}
        </div>
      </div>
      <div className="card">
        <CardTitle title="Pipeline Reality" />
        <div className="months">{[
          `Leads ${metrics?.totalLeads ?? 0}`,
          `Drafts ${metrics?.totalDrafts ?? 0}`,
          `Sent ${metrics?.emailsSent ?? 0}`,
          `Replies ${metrics?.replies ?? 0}`,
          `Meetings ${metrics?.meetingsBooked ?? 0}`,
          `Reply ${metrics?.replyRate.toFixed(1) ?? '0.0'}%`,
          `Source ${(overview?.integrity?.statsSource ?? 'unknown').replace('_', ' ')}`,
        ].map((m, i) => <div key={m} className={`month ${i===3?'hot':''}`}>{m}</div>)}</div>
      </div>
    </div>
  )
}

// ── Autonomous Jarvis types ────────────────────────────────────────────────────
type HumanTask = {
  id: string
  title: string
  description: string
  category: string
  priority: 1 | 2 | 3
  status: 'pending' | 'done' | 'dismissed'
  createdBy: string
  createdAt: string
}
type StrategyExperiment = {
  id: string
  type: 'hook' | 'dm'
  niche: string
  platform: string
  status: 'running' | 'complete' | 'failed'
  winner: string | null
  winnerScore: number
  insight: string
  createdAt: string
  variants: Array<{ text: string; score: number }>
}
type PlatformGap = {
  platform: string
  category: string
  reason: string
  estimatedImpact: 'high' | 'medium' | 'low'
  actionRequired: string
  costEstimate: string
  priority: 1 | 2 | 3
}
type DailyBrief = {
  headline: string
  overallStatus: 'on_track' | 'at_risk' | 'critical' | 'accelerating'
  topPriorityForJace: string
  topPriorityForJarvis: string
  sections: Array<{ title: string; content: string; urgency: string; actionsForJace: string[]; actionsForJarvis: string[] }>
}

function JarvisCommand({ jarvisMode, setJarvisMode }: { jarvisMode: string; setJarvisMode: (v: string) => void }) {
  const [goal, setGoal] = useState('Reach $50k MRR by systemizing legal and fintech growth, founder scheduling, and autonomous task routing.')
  const [stateKey, setStateKey] = useState('founder_context')
  const [stateValue, setStateValue] = useState('Founder is capacity-constrained and needs protected deep work blocks.')
  const [status, setStatus] = useState('Idle')
  const [running, setRunning] = useState(false)
  const [worldState, setWorldState] = useState<SciWorldState | null>(null)
  const [graphs, setGraphs] = useState<SciObjectiveGraph[]>([])
  const [allocations, setAllocations] = useState<SciAllocation[]>([])
  const [approvals, setApprovals] = useState<SciApproval[]>([])
  const [executions, setExecutions] = useState<SciExecution[]>([])
  const [evals, setEvals] = useState<SciEval[]>([])
  const [lastCycle, setLastCycle] = useState<SciCycleResult | null>(null)

  // ── Autonomous Ops state ─────────────────────────────────────────────────────
  const [humanTasks, setHumanTasks] = useState<HumanTask[]>([])
  const [experiments, setExperiments] = useState<StrategyExperiment[]>([])
  const [platformGaps, setPlatformGaps] = useState<PlatformGap[]>([])
  const [brief, setBrief] = useState<DailyBrief | null>(null)
  const [opsLoading, setOpsLoading] = useState(false)
  const [opsStatus, setOpsStatus] = useState('')
  const [expNiche, setExpNiche] = useState('HVAC')
  const [expPlatform, setExpPlatform] = useState('tiktok')
  const [dmIndustry, setDmIndustry] = useState('HVAC')
  const [dmChannel, setDmChannel] = useState('linkedin')

  const refreshStatus = useCallback(async () => {
    try {
      const [worldRes, graphRes, allocationRes, approvalRes, executionRes, evalRes] = await Promise.all([
        sciApiFetch('/api/jarvis/world-state'),
        sciApiFetch('/api/jarvis/objectives?limit=6'),
        sciApiFetch('/api/jarvis/allocations?limit=12'),
        sciApiFetch('/api/jarvis/approvals?limit=12'),
        sciApiFetch('/api/jarvis/executions?limit=12'),
        sciApiFetch('/api/jarvis/evals?limit=6'),
      ])
      const [worldJson, graphJson, allocationJson, approvalJson, executionJson, evalJson] = await Promise.all([
        worldRes.json(),
        graphRes.json(),
        allocationRes.json(),
        approvalRes.json(),
        executionRes.json(),
        evalRes.json(),
      ])
      setWorldState(worldJson?.worldState ?? null)
      setGraphs(graphJson?.objectives ?? [])
      setAllocations(allocationJson?.allocations ?? [])
      setApprovals(approvalJson?.approvals ?? [])
      setExecutions(executionJson?.executions ?? [])
      setEvals(evalJson?.evals ?? [])
    } catch (error) {
      setStatus(`SCI status unavailable: ${(error as Error).message}`)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshStatus()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [refreshStatus])

  // ── Autonomous Ops loaders ────────────────────────────────────────────────────
  const loadAutonomousOps = useCallback(async () => {
    try {
      const [tasksRes, expRes, gapsRes] = await Promise.all([
        apiFetch('/api/jarvis/human-tasks?status=pending'),
        apiFetch('/api/jarvis/strategy/experiments'),
        apiFetch('/api/jarvis/strategy/platform-gaps'),
      ])
      const [tasksJson, expJson, gapsJson] = await Promise.all([
        tasksRes.json(),
        expRes.json(),
        gapsRes.json(),
      ])
      if (tasksJson.ok) setHumanTasks(tasksJson.tasks ?? [])
      if (expJson.ok) setExperiments(expJson.experiments?.slice(0, 5) ?? [])
      if (gapsJson.ok) setPlatformGaps(gapsJson.gaps?.slice(0, 6) ?? [])
    } catch { /* ops panel is non-critical */ }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadAutonomousOps(), 500)
    return () => window.clearTimeout(timer)
  }, [loadAutonomousOps])

  const generateBrief = async () => {
    setOpsLoading(true)
    setOpsStatus('Jarvis is generating daily brief...')
    try {
      const res = await apiFetch('/api/jarvis/brief', { method: 'POST' })
      const json = await res.json() as { ok: boolean; brief: DailyBrief }
      if (json.ok) { setBrief(json.brief); setOpsStatus('Brief ready') }
      else setOpsStatus('Brief generation failed')
    } catch (e) { setOpsStatus(`Error: ${(e as Error).message}`) }
    finally { setOpsLoading(false) }
  }

  const runHookExp = async () => {
    setOpsLoading(true)
    setOpsStatus(`Running hook experiment for ${expNiche} on ${expPlatform}...`)
    try {
      const res = await apiFetch('/api/jarvis/strategy/experiment/hook', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ niche: expNiche, platform: expPlatform, count: 5 }),
      })
      const json = await res.json() as { ok: boolean; experiment: StrategyExperiment }
      if (json.ok) {
        setExperiments((prev) => [json.experiment, ...prev].slice(0, 5))
        setOpsStatus(`Hook experiment complete. Winner score: ${json.experiment.winnerScore}`)
        void loadAutonomousOps()
      } else setOpsStatus('Experiment failed')
    } catch (e) { setOpsStatus(`Error: ${(e as Error).message}`) }
    finally { setOpsLoading(false) }
  }

  const runDmExp = async () => {
    setOpsLoading(true)
    setOpsStatus(`Running DM experiment for ${dmIndustry} on ${dmChannel}...`)
    try {
      const res = await apiFetch('/api/jarvis/strategy/experiment/dm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ industry: dmIndustry, channel: dmChannel }),
      })
      const json = await res.json() as { ok: boolean; experiment: StrategyExperiment }
      if (json.ok) {
        setExperiments((prev) => [json.experiment, ...prev].slice(0, 5))
        setOpsStatus(`DM experiment complete. Winner score: ${json.experiment.winnerScore}`)
        void loadAutonomousOps()
      } else setOpsStatus('DM experiment failed')
    } catch (e) { setOpsStatus(`Error: ${(e as Error).message}`) }
    finally { setOpsLoading(false) }
  }

  const markTaskDone = async (id: string) => {
    try {
      await apiFetch(`/api/jarvis/human-tasks/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'done' }),
      })
      setHumanTasks((prev) => prev.filter((t) => t.id !== id))
    } catch { /* non-critical */ }
  }

  const dismissTask = async (id: string) => {
    try {
      await apiFetch(`/api/jarvis/human-tasks/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'dismissed' }),
      })
      setHumanTasks((prev) => prev.filter((t) => t.id !== id))
    } catch { /* non-critical */ }
  }

  const submitGoal = async () => {
    setRunning(true)
    setStatus('Jarvis SCI is updating the world-state and generating the next objective graph...')
    try {
      const response = await sciApiFetch('/api/jarvis/objectives', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          founder_id: 'founder',
          target_state: goal,
          founder_notes: worldState?.founder_notes ?? [],
          company_constraints: worldState?.company_constraints ?? [],
          tasks_backlog: worldState?.backlog ?? [],
          focus_areas: worldState?.focus_areas ?? ['growth', 'systems', 'calendar'],
          mode: jarvisMode === 'Autonomous' ? 'autonomous' : jarvisMode === 'Advisory' ? 'advisory' : 'approval',
          refresh_calendar: true,
        }),
      })
      const json = await response.json()
      if (!response.ok || !json.ok) {
        setStatus(`SCI run failed: ${json?.detail ?? 'unknown error'}`)
        return
      }
      setLastCycle(json as SciCycleResult)
      setWorldState(json.world_state)
      setStatus(`SCI cycle complete: ${json.objective_graph?.graph_id ?? 'graph created'}`)
      await refreshStatus()
    } catch (error) {
      setStatus(`SCI run failed: ${(error as Error).message}`)
    } finally {
      setRunning(false)
    }
  }

  const updateCompanyState = async () => {
    setStatus(`Updating SCI world-state: ${stateKey}`)
    try {
      const metadata = { [stateKey]: stateValue }
      const response = await sciApiFetch('/api/jarvis/world-state', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          founder_id: 'founder',
          metadata,
          founder_notes: stateKey === 'founder_note' ? [stateValue] : worldState?.founder_notes,
          company_constraints: stateKey === 'constraint' ? [stateValue] : worldState?.company_constraints,
          tasks_backlog: stateKey === 'backlog' ? [stateValue] : worldState?.backlog,
          focus_areas: stateKey === 'focus_area' ? [stateValue] : worldState?.focus_areas,
          target_state: stateKey === 'target_state' ? stateValue : undefined,
        }),
      })
      const json = await response.json()
      if (!response.ok || !json?.ok) {
        setStatus('SCI world-state update failed')
        return
      }
      setWorldState(json.worldState)
      setStatus(`SCI world-state updated: ${stateKey}`)
      await refreshStatus()
    } catch (error) {
      setStatus(`SCI world-state update failed: ${(error as Error).message}`)
    }
  }

  const decideApproval = async (decisionId: string, approved: boolean) => {
    setStatus(approved ? 'Approving SCI action...' : 'Rejecting SCI action...')
    try {
      const response = await sciApiFetch(`/api/jarvis/approvals/${decisionId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: approved ? 'approved' : 'rejected',
          reviewer: 'forge-os-operator',
          note: approved ? 'Approved from the operator console.' : 'Rejected from the operator console.',
        }),
      })
      const json = await response.json()
      setStatus(json?.ok ? 'SCI approval recorded.' : 'SCI approval update failed.')
      await refreshStatus()
    } catch (error) {
      setStatus(`SCI approval failed: ${(error as Error).message}`)
    }
  }

  const approvalTasks = approvals.filter((decision) => decision.approval_required && decision.status === 'pending')
  const latestGraph = graphs[0]
  const latestEval = evals[0]

  return (
    <div>
      <PageHeader title="Jarvis Command" right={<span className="pill green">SCI RUNTIME · forge_system</span>} />
      <div className="sovereign-console">
        <div className="card sovereign-goal">
          <CardTitle title="Target-State Objective" />
          <textarea value={goal} onChange={(event) => setGoal(event.target.value)} />
          <div className="composer-row">
            <span>{status}</span>
            <div className="tool-toggles">
              <button className="mini" onClick={refreshStatus}>Refresh</button>
              <button className="btn primary" onClick={submitGoal} disabled={running}>{running ? 'Running...' : 'Run SCI Cycle'}</button>
            </div>
          </div>
        </div>
        <div className="card sovereign-state">
          <CardTitle title="World-State Update" />
          <input value={stateKey} onChange={(event) => setStateKey(event.target.value)} placeholder="target_state | founder_note | constraint | backlog | focus_area" />
          <input value={stateValue} onChange={(event) => setStateValue(event.target.value)} placeholder="world-state value" />
          <button className="btn secondary" onClick={updateCompanyState}>Update World-State</button>
        </div>
      </div>
      <div className="stats-four">
        <div className="stat"><p>Objective Graphs</p><h3>{graphs.length}</h3></div>
        <div className="stat"><p>Allocations</p><h3>{allocations.length}</h3></div>
        <div className="stat"><p>Approval Gates</p><h3>{approvalTasks.length}</h3></div>
        <div className="stat"><p>Execution Traces</p><h3>{executions.length}</h3></div>
      </div>
      {worldState && (
        <div className="card jarvis-synthesis">
          <CardTitle title="Latest World-State" />
          <p><strong>{worldState.company_name}</strong> is operating toward: {worldState.target_state}</p>
          <div className="months">
            {(worldState.growth_hypotheses ?? []).slice(0, 4).map((hypothesis) => (
              <div key={hypothesis.title} className="month hot">
                <strong>{hypothesis.title}</strong>
                <span>{hypothesis.next_action}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {(lastCycle?.selected_plan || latestGraph) && (
        <div className="card jarvis-synthesis">
          <CardTitle title="Selected Plan" />
          <p>{lastCycle?.selected_plan?.title ?? latestGraph?.summary}</p>
          {lastCycle?.selected_plan?.reasoning && <small>{lastCycle.selected_plan.reasoning}</small>}
          {lastCycle?.selected_plan?.why_selected && <small>{lastCycle.selected_plan.why_selected}</small>}
        </div>
      )}
      {approvalTasks.length > 0 && (
        <div className="card">
          <CardTitle title="SCI Approval Queue" />
          <div className="approval-grid">
            {approvalTasks.slice(0, 4).map((decision) => (
              <div className="approval-card" key={decision.decision_id}>
                <strong>{decision.action_type}</strong>
                <span>{decision.title}</span>
                <small>{decision.rationale}</small>
                <div className="approval-actions">
                  <button className="mini" onClick={() => decideApproval(decision.decision_id, false)}>Reject</button>
                  <button className="btn primary" onClick={() => decideApproval(decision.decision_id, true)}>Approve</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="card">
        <CardTitle title="Objective Graph" />
        <table>
          <thead><tr><th>Priority</th><th>Owner</th><th>Objective</th><th>Risk</th><th>Success Metric</th></tr></thead>
          <tbody>
            {(latestGraph?.nodes?.length ?? 0) === 0 && <tr><td colSpan={5}>No SCI graph generated yet.</td></tr>}
            {(latestGraph?.nodes ?? []).slice(0, 12).map((node) => (
              <tr key={node.id}>
                <td>{node.priority}</td>
                <td>{node.owner}</td>
                <td>{node.title}</td>
                <td><span className={`badge ${node.risk_level === 'low' ? 'ok' : node.risk_level === 'medium' ? 'warn' : ''}`}>{node.risk_level}</span></td>
                <td>{node.success_metric}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="two-col">
        <div className="card">
          <CardTitle title="Founder Allocations" />
          {allocations.slice(0, 6).map((allocation) => (
            <div className="pulse-row" key={allocation.allocation_id}>
              <CircleDot size={12} />
              <div>
                <strong>{allocation.title}</strong>
                <span>{allocation.start_at ? `${formatDateTime(allocation.start_at)} to ${formatDateTime(allocation.end_at)}` : allocation.rationale}</span>
              </div>
              <small>{allocation.owner}</small>
            </div>
          ))}
          {allocations.length === 0 && <p>No allocations yet.</p>}
        </div>
        <div className="card">
          <CardTitle title="Model Eval Summary" />
          {latestEval ? (
            <>
              <p>{latestEval.summary}</p>
              <div className="months">
                {[
                  `Planner ${latestEval.planner_model}`,
                  `Executor ${latestEval.executor_model}`,
                  `Plan ${(latestEval.plan_quality * 100).toFixed(0)}%`,
                  `Routing ${(latestEval.routing_quality * 100).toFixed(0)}%`,
                  `Latency ${latestEval.latency_ms}ms`,
                  `Cost $${latestEval.estimated_cost.toFixed(2)}`,
                ].map((item, index) => <div key={item} className={`month ${index === 2 ? 'hot' : ''}`}>{item}</div>)}
              </div>
            </>
          ) : (
            <p>No evaluation summary yet.</p>
          )}
        </div>
      </div>
      {/* ── AUTONOMOUS OPS PANEL ── */}
      <div className="card" style={{ marginBottom: 10 }}>
        <CardTitle title="Autonomous Operations" />
        <p style={{ color: '#aaa', fontSize: 12, margin: '0 0 10px' }}>
          Jarvis runs experiments, generates briefs, and allocates work autonomously. Click any action below.
        </p>

        {/* Status + actions row */}
        <div className="composer-row" style={{ marginBottom: 10 }}>
          <span style={{ fontSize: 11, color: opsLoading ? '#00c896' : '#666' }}>{opsStatus || 'Ready'}</span>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button className="btn secondary" onClick={() => void loadAutonomousOps()} disabled={opsLoading}>
              <RefreshCw size={11} style={{ display: 'inline', marginRight: 4 }} />Refresh
            </button>
            <button className="btn primary" onClick={() => void generateBrief()} disabled={opsLoading}>
              <Brain size={11} style={{ display: 'inline', marginRight: 4 }} />
              {opsLoading ? 'Working...' : 'Generate Daily Brief'}
            </button>
          </div>
        </div>

        {/* Daily Brief */}
        {brief && (
          <div style={{ padding: '12px 14px', background: '#050505', border: '1px solid #1a1a1a', borderRadius: 8, marginBottom: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span className={`pill ${brief.overallStatus === 'accelerating' ? '' : brief.overallStatus === 'on_track' ? '' : brief.overallStatus === 'at_risk' ? 'warn' : ''}`}
                style={{ background: brief.overallStatus === 'accelerating' ? '#00c89622' : brief.overallStatus === 'on_track' ? '#1a1a1a' : '#cc111122', color: brief.overallStatus === 'accelerating' ? '#00c896' : brief.overallStatus === 'on_track' ? '#aaa' : '#cc4444', fontSize: 10 }}>
                {brief.overallStatus.replace('_', ' ').toUpperCase()}
              </span>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#eee' }}>{brief.headline}</span>
            </div>
            <div className="two-col" style={{ gap: 8 }}>
              <div style={{ background: '#0a1a0a', borderRadius: 6, padding: '8px 12px', border: '1px solid #0a2a0a' }}>
                <div style={{ fontSize: 10, color: '#00c896', marginBottom: 4, fontWeight: 700 }}>JARVIS OWNS</div>
                <p style={{ fontSize: 12, color: '#ccc', margin: 0 }}>{brief.topPriorityForJarvis}</p>
              </div>
              <div style={{ background: '#1a0a0a', borderRadius: 6, padding: '8px 12px', border: '1px solid #2a1a1a' }}>
                <div style={{ fontSize: 10, color: '#f5a623', marginBottom: 4, fontWeight: 700 }}>JACE MUST DO</div>
                <p style={{ fontSize: 12, color: '#ccc', margin: 0 }}>{brief.topPriorityForJace}</p>
              </div>
            </div>
          </div>
        )}

        {/* Experiment launchers */}
        <div className="two-col" style={{ gap: 10, marginBottom: 10 }}>
          <div style={{ padding: '10px 12px', background: '#0a0a0a', border: '1px solid #1a1a1a', borderRadius: 8 }}>
            <div style={{ fontSize: 11, color: '#888', marginBottom: 6, fontWeight: 600 }}>HOOK A/B EXPERIMENT</div>
            <div style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
              <input value={expNiche} onChange={(e) => setExpNiche(e.target.value)} placeholder="Niche (e.g. HVAC)" style={{ flex: 1, fontSize: 11 }} />
              <select value={expPlatform} onChange={(e) => setExpPlatform(e.target.value)}
                style={{ background: '#111', color: '#eee', border: '1px solid #222', borderRadius: 6, padding: '4px 8px', fontSize: 11 }}>
                <option value="tiktok">TikTok</option>
                <option value="instagram_reels">Instagram</option>
                <option value="youtube_shorts">YouTube</option>
                <option value="linkedin">LinkedIn</option>
                <option value="twitter">X</option>
              </select>
            </div>
            <button className="btn primary" onClick={() => void runHookExp()} disabled={opsLoading} style={{ width: '100%', fontSize: 11 }}>
              <Zap size={10} style={{ display: 'inline', marginRight: 4 }} />Run Hook Experiment (5 variants)
            </button>
          </div>
          <div style={{ padding: '10px 12px', background: '#0a0a0a', border: '1px solid #1a1a1a', borderRadius: 8 }}>
            <div style={{ fontSize: 11, color: '#888', marginBottom: 6, fontWeight: 600 }}>DM ANGLE EXPERIMENT</div>
            <div style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
              <input value={dmIndustry} onChange={(e) => setDmIndustry(e.target.value)} placeholder="Industry" style={{ flex: 1, fontSize: 11 }} />
              <select value={dmChannel} onChange={(e) => setDmChannel(e.target.value)}
                style={{ background: '#111', color: '#eee', border: '1px solid #222', borderRadius: 6, padding: '4px 8px', fontSize: 11 }}>
                <option value="linkedin">LinkedIn</option>
                <option value="instagram">Instagram</option>
                <option value="sms">SMS</option>
                <option value="x">X</option>
              </select>
            </div>
            <button className="btn primary" onClick={() => void runDmExp()} disabled={opsLoading} style={{ width: '100%', fontSize: 11 }}>
              <Send size={10} style={{ display: 'inline', marginRight: 4 }} />Test 3 DM Angle Styles
            </button>
          </div>
        </div>

        {/* Recent experiments */}
        {experiments.length > 0 && (
          <div>
            <div style={{ fontSize: 11, color: '#666', marginBottom: 6, fontWeight: 600 }}>RECENT EXPERIMENTS</div>
            {experiments.map((exp) => (
              <div key={exp.id} style={{ padding: '8px 12px', background: '#050505', border: '1px solid #111', borderRadius: 6, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 10 }}>
                <span className="pill" style={{ fontSize: 9 }}>{exp.type}</span>
                <span className="pill" style={{ fontSize: 9 }}>{exp.platform}</span>
                <span style={{ flex: 1, fontSize: 11, color: '#ccc' }}>{exp.niche}: {exp.winner ? `"${exp.winner.slice(0, 60)}..."` : 'running...'}</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: exp.winnerScore >= 70 ? '#00c896' : exp.winnerScore >= 50 ? '#f5a623' : '#cc4444' }}>{exp.winnerScore}/100</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── JACE TASK QUEUE ── */}
      {humanTasks.length > 0 && (
        <div className="card" style={{ marginBottom: 10 }}>
          <CardTitle title={`Jace Task Queue — ${humanTasks.length} pending`} />
          <p style={{ color: '#aaa', fontSize: 12, margin: '0 0 10px' }}>
            Tasks Jarvis cannot do autonomously. Handle these to unblock the system.
          </p>
          {humanTasks.map((task) => (
            <div key={task.id} style={{
              padding: '10px 14px',
              background: task.priority === 1 ? '#1a0808' : '#0a0a0a',
              border: `1px solid ${task.priority === 1 ? '#3a1111' : '#1a1a1a'}`,
              borderRadius: 8,
              marginBottom: 8,
              display: 'flex',
              gap: 12,
              alignItems: 'flex-start',
            }}>
              <div style={{ width: 20, height: 20, borderRadius: '50%', background: task.priority === 1 ? '#cc1111' : task.priority === 2 ? '#f5a623' : '#555', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700, flexShrink: 0, marginTop: 2 }}>
                {task.priority}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#eee', marginBottom: 3 }}>{task.title}</div>
                <div style={{ fontSize: 11, color: '#888' }}>{task.description.slice(0, 120)}{task.description.length > 120 ? '...' : ''}</div>
                <div style={{ fontSize: 10, color: '#555', marginTop: 4 }}>
                  {task.category} · by {task.createdBy} · {new Date(task.createdAt).toLocaleDateString()}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                <button className="mini" style={{ color: '#00c896', borderColor: '#0a2a1a' }} onClick={() => void markTaskDone(task.id)}>Done</button>
                <button className="mini" style={{ color: '#555' }} onClick={() => void dismissTask(task.id)}>×</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── PLATFORM GAPS ── */}
      {platformGaps.length > 0 && (
        <div className="card" style={{ marginBottom: 10 }}>
          <CardTitle title="Platform & Account Gaps" />
          <p style={{ color: '#aaa', fontSize: 12, margin: '0 0 10px' }}>
            Accounts and tools Jarvis identified as missing. These limit what the system can do autonomously.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {platformGaps.slice(0, 6).map((gap, i) => (
              <div key={i} style={{
                padding: '10px 12px',
                background: '#0a0a0a',
                border: `1px solid ${gap.priority === 1 && gap.estimatedImpact === 'high' ? '#2a1a0a' : '#111'}`,
                borderRadius: 8,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                  <span className="pill" style={{ fontSize: 9, background: gap.estimatedImpact === 'high' ? '#f5a62322' : '#1a1a1a', color: gap.estimatedImpact === 'high' ? '#f5a623' : '#666' }}>{gap.estimatedImpact} impact</span>
                  <span className="pill" style={{ fontSize: 9 }}>{gap.costEstimate}</span>
                </div>
                <div style={{ fontSize: 12, fontWeight: 600, color: '#eee', marginBottom: 4 }}>{gap.platform}</div>
                <div style={{ fontSize: 11, color: '#888', marginBottom: 6 }}>{gap.reason.slice(0, 100)}...</div>
                <div style={{ fontSize: 10, color: '#00c896' }}>{gap.actionRequired.slice(0, 80)}{gap.actionRequired.length > 80 ? '...' : ''}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <JarvisChat jarvisMode={jarvisMode} setJarvisMode={setJarvisMode} />
    </div>
  )
}

// ── Types for Jarvis chat + calendar ──────────────────────────────────────
type JarvisChatMsg = { id: string; role: 'user' | 'jarvis'; content: string; createdAt: string }
type CalEvent = { id: string; summary: string; description?: string; start: string; end: string }
type CalPriority = { event: CalEvent; reason: string; businessRelevance: 'high' | 'medium' | 'low' }

function JarvisChat({ jarvisMode, setJarvisMode }: { jarvisMode: string; setJarvisMode: (v: string) => void }) {
  const [messages, setMessages] = useState<JarvisChatMsg[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [calEvents, setCalEvents] = useState<CalEvent[]>([])
  const [calPriorities, setCalPriorities] = useState<CalPriority[]>([])
  const [calSummary, setCalSummary] = useState('')
  const [calFocus, setCalFocus] = useState('')
  const [calLoading, setCalLoading] = useState(false)
  const [calMode, setCalMode] = useState('')
  const [calTab, setCalTab] = useState<'today' | 'week'>('today')
  const [showCal, setShowCal] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)

  // Load history on mount
  useEffect(() => {
    void (async () => {
      try {
        const res = await apiFetch('/api/jarvis/history')
        const json = await res.json()
        if (json?.ok && Array.isArray(json.messages)) setMessages(json.messages)
        else setMessages([{ id: 'boot', role: 'jarvis', content: 'Jarvis online. All systems running. What do you need?', createdAt: new Date().toISOString() }])
      } catch {
        setMessages([{ id: 'boot', role: 'jarvis', content: 'Jarvis online. Backend not reachable — start the server.', createdAt: new Date().toISOString() }])
      }
    })()
  }, [])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || sending) return
    const userMsg: JarvisChatMsg = { id: `u-${Date.now()}`, role: 'user', content: input, createdAt: new Date().toISOString() }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setSending(true)
    try {
      const res = await apiFetch('/api/jarvis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: input,
          operator: 'Jace',
          calendarContext: calEvents.length ? calEvents : undefined,
        }),
      })
      const json = await res.json()
      if (json?.ok) {
        const jarvisMsg: JarvisChatMsg = { id: `j-${Date.now()}`, role: 'jarvis', content: json.response, createdAt: new Date().toISOString() }
        setMessages((prev) => [...prev, jarvisMsg])
      }
    } catch (e) {
      setMessages((prev) => [...prev, { id: `err-${Date.now()}`, role: 'jarvis', content: `Error: ${(e as Error).message}`, createdAt: new Date().toISOString() }])
    } finally { setSending(false) }
  }

  const syncCalendar = async () => {
    setCalLoading(true)
    try {
      const res = await apiFetch('/api/calendar/sync?days=3')
      const json = await res.json()
      if (json?.ok || json?.analysis) {
        const a = json.analysis
        setCalEvents(a?.events ?? [])
        setCalPriorities(a?.priorities ?? [])
        setCalSummary(a?.todaySummary ?? '')
        setCalFocus(a?.suggestedFocus ?? '')
        setCalMode(json.mode ?? 'offline')
        setShowCal(true)
      }
    } catch {
      setCalMode('offline')
    }
    finally { setCalLoading(false) }
  }

  const addToCalendar = async (title: string) => {
    const today = new Date().toISOString().slice(0, 10)
    const res = await apiFetch('/api/calendar/priority-block', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, dateIso: today, startHour: 9, durationHours: 2 }),
    })
    const json = await res.json()
    if (json?.ok) alert(`Added "${title}" to your Google Calendar`)
    else alert(`Calendar write requires Google Calendar API scope. Re-run OAuth at /api/google/oauth/start`)
  }

  const relevanceColor = (r: string) => r === 'high' ? '#cc1111' : r === 'medium' ? '#f0a500' : '#555'
  const fmtTime = (iso: string) => {
    if (!iso) return ''
    if (iso.includes('T')) return iso.slice(11, 16)
    return iso.slice(5)
  }

  return (
    <>
      {/* Calendar Panel */}
      <div className="jarvis-cal-bar">
        <button className="btn secondary" onClick={syncCalendar} disabled={calLoading}>
          <CalendarCheck2 size={12} style={{ display: 'inline', marginRight: 4 }} />
          {calLoading ? 'Syncing...' : 'Sync Google Calendar'}
        </button>
        {calMode && <span className="pill" style={{ fontSize: 9 }}>{calMode === 'live' ? '🟢 Live' : '⚡ Demo'}</span>}
        {calSummary && <span style={{ fontSize: 11, color: '#aaa', flex: 1 }}>{calSummary}</span>}
        {showCal && <button className="mini" onClick={() => setShowCal((v) => !v)}>Hide Calendar</button>}
      </div>

      {showCal && (
        <div className="card jarvis-cal-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <CardTitle title="Calendar Intelligence" />
            <div className="segmented">
              <button className={calTab === 'today' ? 'active' : ''} onClick={() => setCalTab('today')}>Today</button>
              <button className={calTab === 'week' ? 'active' : ''} onClick={() => setCalTab('week')}>3 Days</button>
            </div>
          </div>

          {calFocus && (
            <div className="cmo-hook-banner" style={{ marginBottom: 8 }}>
              <span className="cmo-label">JARVIS PRIORITY FOCUS</span>
              <p style={{ fontSize: 12 }}>{calFocus}</p>
            </div>
          )}

          <div className="jarvis-cal-events">
            {calPriorities.length > 0 && (
              <div style={{ marginBottom: 8 }}>
                <div className="cmo-label" style={{ marginBottom: 6 }}>PRIORITIZED BY JARVIS</div>
                {calPriorities.map((p, i) => (
                  <div key={i} className="jarvis-cal-event" style={{ borderColor: relevanceColor(p.businessRelevance) }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <span style={{ fontWeight: 700, fontSize: 12 }}>{p.event.summary}</span>
                        <span style={{ fontSize: 10, color: '#666', marginLeft: 8 }}>{fmtTime(p.event.start)}</span>
                      </div>
                      <span className="badge" style={{ fontSize: 8, color: relevanceColor(p.businessRelevance), borderColor: relevanceColor(p.businessRelevance) }}>
                        {p.businessRelevance}
                      </span>
                    </div>
                    <p style={{ margin: '4px 0 0', fontSize: 11, color: '#aaa' }}>{p.reason}</p>
                  </div>
                ))}
              </div>
            )}

            <div>
              <div className="cmo-label" style={{ marginBottom: 6 }}>ALL EVENTS</div>
              {calEvents.length === 0
                ? <p style={{ color: '#555', fontSize: 12 }}>No events found. Sync your Google Calendar above.</p>
                : calEvents.map((e) => (
                  <div key={e.id} className="jarvis-cal-event">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 12, fontWeight: 600 }}>{e.summary}</span>
                      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                        <span style={{ fontSize: 10, color: '#666' }}>{fmtTime(e.start)}</span>
                        <button className="mini" style={{ fontSize: 9, padding: '1px 5px' }} onClick={() => void addToCalendar(`Prep: ${e.summary}`)}>+ Prep Block</button>
                      </div>
                    </div>
                    {e.description && <p style={{ margin: '2px 0 0', fontSize: 10, color: '#555' }}>{e.description.slice(0, 80)}</p>}
                  </div>
                ))
              }
            </div>
          </div>
        </div>
      )}

      {/* Live Chat */}
      <div className="jarvis-live-chat">
        <div className="chat-thread">
          {messages.map((m) => (
            <div key={m.id} className={`bubble ${m.role === 'user' ? 'user' : 'jarvis'}`}>
              {m.role === 'jarvis' && <b>JARVIS · {new Date(m.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</b>}
              <p style={{ whiteSpace: 'pre-wrap' }}>{m.content}</p>
            </div>
          ))}
          {sending && (
            <div className="bubble jarvis">
              <b>JARVIS · thinking...</b>
              <p style={{ color: '#555' }}>...</p>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="composer">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void sendMessage() } }}
            placeholder="Ask Jarvis anything — strategy, calendar, self-dev, pipeline, what to do next..."
          />
          <div className="composer-row">
            <div className="segmented">
              {['Advisory', 'Execute with approval', 'Autonomous'].map((x) => (
                <button key={x} className={jarvisMode === x ? 'active' : ''} onClick={() => setJarvisMode(x)}>{x}</button>
              ))}
            </div>
            <div className="tool-toggles">
              <button className="icon-btn" title="Calendar context active" style={{ color: calEvents.length ? '#00c896' : '#555' }}>
                <CalendarCheck2 size={14} />
              </button>
              <button className="icon-btn"><Database size={14} /></button>
              <button className="icon-btn"><Wrench size={14} /></button>
              <button className="btn primary" onClick={sendMessage} disabled={sending}>
                {sending ? '...' : 'Send'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

function Automations() { return <GenericMission title="Automations" tabs={['Library','Running','Failed','Builder','Schedule']} /> }
type CalendarItem = {
  id: string
  title: string
  platform: string
  content_type: string
  status: string
  publish_at: string | null
  notes: string | null
  created_at: string
}

function CMOSystem() {
  const [tab, setTab] = useState<'research' | 'concepts' | 'scripts' | 'hook' | 'calendar'>('research')
  const [niche, setNiche] = useState('B2B Lead Generation / Outbound Sales')
  const [platform, setPlatform] = useState<CMOPlatform>('instagram_reels')
  const [goal, setGoal] = useState('')
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)

  const [research, setResearch] = useState<ViralResearch | null>(null)
  const [concepts, setConcepts] = useState<VideoConcept[]>([])
  const [script, setScript] = useState<VideoScript | null>(null)
  const [scriptConcept, setScriptConcept] = useState('')
  const [scriptHook, setScriptHook] = useState('')
  const [hookInput, setHookInput] = useState('')
  const [hookScore, setHookScore] = useState<HookScore | null>(null)
  const [copied, setCopied] = useState('')
  const scriptRef = useRef<HTMLDivElement>(null)

  // Calendar state
  const [calItems, setCalItems] = useState<CalendarItem[]>([])
  const [calLoading, setCalLoading] = useState(false)
  const [calStatus, setCalStatus] = useState('')
  const [calForm, setCalForm] = useState({ title: '', platform: 'instagram_reels', contentType: 'video', publishAt: '', notes: '' })

  const loadCalendar = async () => {
    setCalLoading(true)
    try {
      const res = await apiFetch('/api/cmo/calendar')
      const json = await res.json()
      if (json?.ok) setCalItems(json.items ?? [])
      else setCalStatus(json?.message ?? json?.error ?? 'Failed to load calendar')
    } catch (e) { setCalStatus(`Error: ${(e as Error).message}`) }
    finally { setCalLoading(false) }
  }

  const scheduleItem = async () => {
    if (!calForm.title.trim()) { setCalStatus('Title is required.'); return }
    setCalLoading(true)
    setCalStatus('Scheduling...')
    try {
      const res = await apiFetch('/api/cmo/calendar/schedule', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: calForm.title,
          platform: calForm.platform,
          contentType: calForm.contentType,
          publishAt: calForm.publishAt || undefined,
          notes: calForm.notes || undefined,
        }),
      })
      const json = await res.json()
      if (json?.ok) {
        setCalStatus('Content scheduled.')
        setCalForm({ title: '', platform: 'instagram_reels', contentType: 'video', publishAt: '', notes: '' })
        void loadCalendar()
      } else {
        setCalStatus(json?.error ?? 'Schedule failed.')
      }
    } catch (e) { setCalStatus(`Error: ${(e as Error).message}`) }
    finally { setCalLoading(false) }
  }

  const deleteCalItem = async (id: string) => {
    try {
      await apiFetch(`/api/cmo/calendar/${id}`, { method: 'DELETE' })
      setCalItems((prev) => prev.filter((item) => item.id !== id))
    } catch { /* silent */ }
  }

  // Load calendar on tab switch
  const handleTabChange = (t: typeof tab) => {
    setTab(t)
    if (t === 'calendar') void loadCalendar()
  }

  const platforms: { id: CMOPlatform; label: string }[] = [
    { id: 'instagram_reels', label: 'Instagram Reels' },
    { id: 'tiktok', label: 'TikTok' },
    { id: 'youtube_shorts', label: 'YouTube Shorts' },
    { id: 'linkedin', label: 'LinkedIn' },
    { id: 'twitter', label: 'Twitter/X' },
  ]

  const copyToClipboard = (text: string, key: string) => {
    void navigator.clipboard.writeText(text)
    setCopied(key)
    setTimeout(() => setCopied(''), 2000)
  }

  const runResearch = async () => {
    setLoading(true)
    setStatus('Noah is researching viral patterns...')
    try {
      const res = await apiFetch('/api/cmo/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ niche, platform }),
      })
      const json = await res.json()
      if (json?.ok) {
        setResearch(json.research)
        setStatus('Research complete.')
      } else {
        setStatus(`Research failed: ${JSON.stringify(json?.error ?? 'unknown')}`)
      }
    } catch (e) {
      setStatus(`Error: ${(e as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  const runConcepts = async () => {
    setLoading(true)
    setStatus('Noah is generating concepts...')
    try {
      const res = await apiFetch('/api/cmo/concepts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          niche,
          platform,
          count: 6,
          goal: goal || undefined,
          researchContext: research
            ? { goldHooks: research.goldHooks, contentAngles: research.contentAngles, trendingFormats: research.trendingFormats }
            : undefined,
        }),
      })
      const json = await res.json()
      if (json?.ok) {
        setConcepts(json.concepts)
        setStatus(`${json.concepts.length} concepts generated.`)
      } else {
        setStatus(`Concepts failed: ${JSON.stringify(json?.error ?? 'unknown')}`)
      }
    } catch (e) {
      setStatus(`Error: ${(e as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  const runScript = async () => {
    if (!scriptConcept || !scriptHook) {
      setStatus('Enter a concept and hook before generating a script.')
      return
    }
    setLoading(true)
    setStatus('Noah is writing the script...')
    try {
      const res = await apiFetch('/api/cmo/script', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ concept: scriptConcept, hook: scriptHook, platform, niche, goal: goal || undefined }),
      })
      const json = await res.json()
      if (json?.ok) {
        setScript(json.script)
        setStatus('Script ready.')
        setTimeout(() => scriptRef.current?.scrollIntoView({ behavior: 'smooth' }), 100)
      } else {
        setStatus(`Script failed: ${JSON.stringify(json?.error ?? 'unknown')}`)
      }
    } catch (e) {
      setStatus(`Error: ${(e as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  const runHookScore = async () => {
    if (!hookInput.trim()) { setStatus('Enter a hook to score.'); return }
    setLoading(true)
    setStatus('Scoring hook...')
    try {
      const res = await apiFetch('/api/cmo/hook/score', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hook: hookInput, platform }),
      })
      const json = await res.json()
      if (json?.ok) { setHookScore(json.score); setStatus('Hook scored.') }
      else setStatus(`Score failed: ${JSON.stringify(json?.error ?? 'unknown')}`)
    } catch (e) { setStatus(`Error: ${(e as Error).message}`) }
    finally { setLoading(false) }
  }

  const applyConceptToScript = (c: VideoConcept) => {
    setScriptConcept(c.title)
    setScriptHook(c.hook)
    setTab('scripts')
  }

  const scoreBar = (val: number) => (
    <div className="cmo-score-bar">
      <div className="cmo-score-fill" style={{ width: `${val}%`, background: val >= 75 ? '#00c896' : val >= 50 ? '#f0a500' : '#cc1111' }} />
    </div>
  )

  const viralBadge = (score: number) => {
    const color = score >= 85 ? '#00c896' : score >= 70 ? '#f0a500' : '#cc1111'
    return <span className="cmo-viral-badge" style={{ borderColor: color, color }}>{score}</span>
  }

  const fullScriptText = script
    ? [
        `TITLE: ${script.title}`,
        `PLATFORM: ${script.platform} | DURATION: ${script.duration} | VIRAL SCORE: ${script.viralScore}/100`,
        '',
        `HOOK: ${script.hook}`,
        '',
        ...script.segments.map((s) => `[${s.label} — ${s.timing}]\n${s.content}\n📹 ${s.visualNote}`),
        '',
        `CTA: ${script.cta}`,
        '',
        `CAPTION HOOK: ${script.captionHook}`,
        `HASHTAGS: ${script.hashtags.join(' ')}`,
        '',
        `PRODUCTION NOTES:\n${script.productionNotes.map((n) => `• ${n}`).join('\n')}`,
      ].join('\n')
    : ''

  return (
    <div>
      <PageHeader
        title="CMO System — Noah"
        right={<span className="pill green"><Sparkles size={11} /> Noah Online · Gemini 2.5 Pro</span>}
      />

      {/* Global controls */}
      <div className="cmo-controls card">
        <div className="cmo-controls-row">
          <div className="cmo-field">
            <label>Niche / Industry</label>
            <input
              value={niche}
              onChange={(e) => setNiche(e.target.value)}
              placeholder="e.g. B2B SaaS, Legal, Creator Economy..."
            />
          </div>
          <div className="cmo-field">
            <label>Platform</label>
            <div className="segmented">
              {platforms.map((p) => (
                <button key={p.id} className={platform === p.id ? 'active' : ''} onClick={() => setPlatform(p.id)}>
                  {p.label}
                </button>
              ))}
            </div>
          </div>
          <div className="cmo-field">
            <label>Creator Goal (optional)</label>
            <input
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="e.g. book meetings, grow following, sell course..."
            />
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        {([
          ['research', 'Viral Research', Zap],
          ['concepts', 'Concept Generator', Video],
          ['scripts', 'Script Builder', FileText],
          ['hook', 'Hook Scorer', Brain],
          ['calendar', 'Content Calendar', Calendar],
        ] as const).map(([id, label, Icon]) => (
          <button key={id} className={tab === id ? 'active' : ''} onClick={() => handleTabChange(id as typeof tab)}>
            <Icon size={12} style={{ display: 'inline', marginRight: 4 }} />{label}
          </button>
        ))}
      </div>

      {/* ── RESEARCH TAB ── */}
      {tab === 'research' && (
        <div>
          <div className="card" style={{ marginBottom: 10 }}>
            <CardTitle title="Viral Pattern Research" />
            <p style={{ color: '#aaa', fontSize: 12, margin: '0 0 10px' }}>
              Noah analyses what's gone viral in your niche — hooks, angles, structures, and what to avoid.
            </p>
            <div className="composer-row">
              <span style={{ color: '#666', fontSize: 11 }}>{status}</span>
              <button className="btn primary" onClick={runResearch} disabled={loading}>
                <Zap size={12} style={{ display: 'inline', marginRight: 4 }} />
                {loading ? 'Researching...' : 'Run Viral Research'}
              </button>
            </div>
          </div>

          {research && (
            <>
              <div className="card" style={{ marginBottom: 10 }}>
                <CardTitle title="Research Summary" />
                <p style={{ color: '#e0e0e0', fontSize: 13, lineHeight: 1.6, margin: 0 }}>{research.researchSummary}</p>
              </div>

              <div className="two-col" style={{ marginBottom: 10 }}>
                <div className="card">
                  <CardTitle title={`Gold Hooks (${research.goldHooks.length})`} />
                  <div className="cmo-hook-list">
                    {research.goldHooks.map((h, i) => (
                      <div key={i} className="cmo-hook-item">
                        <span className="cmo-hook-num">{i + 1}</span>
                        <span className="cmo-hook-text">{h}</span>
                        <button className="mini" onClick={() => copyToClipboard(h, `hook-${i}`)}>
                          <Clipboard size={11} /> {copied === `hook-${i}` ? 'Copied!' : 'Copy'}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="card">
                  <CardTitle title="Content Angles" />
                  <div className="cmo-hook-list">
                    {research.contentAngles.map((a, i) => (
                      <div key={i} className="cmo-hook-item">
                        <span className="cmo-hook-num">{i + 1}</span>
                        <span className="cmo-hook-text">{a}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="card" style={{ marginBottom: 10 }}>
                <CardTitle title={`Top Viral Patterns (${research.topPatterns.length})`} />
                <div className="cmo-patterns">
                  {research.topPatterns.map((p, i) => (
                    <div key={i} className="cmo-pattern-card">
                      <div className="cmo-pattern-header">
                        <span className="cmo-pattern-angle">{p.angle}</span>
                        <button className="mini" onClick={() => { setScriptHook(p.exampleOpener); setTab('scripts') }}>
                          Use Hook →
                        </button>
                      </div>
                      <div className="cmo-pattern-formula">"{p.hookFormula}"</div>
                      <p className="cmo-pattern-opener">Example: <em>{p.exampleOpener}</em></p>
                      <div className="cmo-pattern-body">
                        <div>
                          <strong>Structure</strong>
                          <ul>{p.structure.map((s, j) => <li key={j}>{s}</li>)}</ul>
                        </div>
                        <div>
                          <strong>Retention Technique</strong>
                          <p>{p.retentionTechnique}</p>
                          <strong>Why It Works</strong>
                          <p>{p.whyItWorks}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="two-col">
                <div className="card">
                  <CardTitle title="Trending Formats" />
                  {research.trendingFormats.map((f, i) => (
                    <div key={i} className="cmo-hook-item">
                      <span className="cmo-hook-num">{i + 1}</span>
                      <span className="cmo-hook-text">{f}</span>
                    </div>
                  ))}
                </div>
                <div className="card">
                  <CardTitle title="Avoid These" />
                  {research.avoidThese.map((a, i) => (
                    <div key={i} className="cmo-hook-item">
                      <span className="cmo-hook-num" style={{ color: '#cc1111' }}>✕</span>
                      <span className="cmo-hook-text" style={{ color: '#aaa' }}>{a}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* ── CONCEPTS TAB ── */}
      {tab === 'concepts' && (
        <div>
          <div className="card" style={{ marginBottom: 10 }}>
            <CardTitle title="Video Concept Generator" />
            <p style={{ color: '#aaa', fontSize: 12, margin: '0 0 10px' }}>
              Noah generates 6 ready-to-shoot video concepts with hooks, angles, and CTAs — engineered for virality.
              {research ? ' Using your research context.' : ' Run Viral Research first for better results.'}
            </p>
            <div className="composer-row">
              <span style={{ color: '#666', fontSize: 11 }}>{status}</span>
              <button className="btn primary" onClick={runConcepts} disabled={loading}>
                <Video size={12} style={{ display: 'inline', marginRight: 4 }} />
                {loading ? 'Generating...' : 'Generate 6 Concepts'}
              </button>
            </div>
          </div>

          {concepts.length > 0 && (
            <div className="cmo-concepts-grid">
              {concepts.map((c) => (
                <div key={c.id} className="cmo-concept-card">
                  <div className="cmo-concept-header">
                    <div>
                      <span className="cmo-concept-angle">{c.angle}</span>
                      <span className="cmo-concept-format">{c.format.replace(/_/g, ' ')}</span>
                    </div>
                    {viralBadge(c.viralScore)}
                  </div>
                  <h4 className="cmo-concept-title">{c.title}</h4>
                  <div className="cmo-concept-hook">
                    <span className="cmo-label">HOOK</span>
                    <p>"{c.hook}"</p>
                  </div>
                  <div className="cmo-concept-opening">
                    <span className="cmo-label">OPENING LINE</span>
                    <p>{c.openingLine}</p>
                  </div>
                  <ul className="cmo-concept-points">
                    {c.keyPoints.map((pt, i) => <li key={i}>{pt}</li>)}
                  </ul>
                  <div className="cmo-concept-why">{c.whyItWorks}</div>
                  <div className="cmo-concept-footer">
                    <span className="cmo-concept-cta">CTA: {c.cta}</span>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button className="mini" onClick={() => copyToClipboard(c.hook, `concept-${c.id}`)}>
                        <Clipboard size={11} /> {copied === `concept-${c.id}` ? 'Copied!' : 'Copy Hook'}
                      </button>
                      <button className="btn primary" style={{ height: 28, fontSize: 10 }} onClick={() => applyConceptToScript(c)}>
                        Write Script →
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── SCRIPTS TAB ── */}
      {tab === 'scripts' && (
        <div>
          <div className="card" style={{ marginBottom: 10 }}>
            <CardTitle title="Script Builder" />
            <div className="cmo-script-inputs">
              <div className="cmo-field">
                <label>Concept / Title</label>
                <input
                  value={scriptConcept}
                  onChange={(e) => setScriptConcept(e.target.value)}
                  placeholder="e.g. How I booked 47 meetings in 7 days with AI"
                />
              </div>
              <div className="cmo-field">
                <label>Hook (first 1.5 seconds)</label>
                <input
                  value={scriptHook}
                  onChange={(e) => setScriptHook(e.target.value)}
                  placeholder="e.g. I used AI to generate 47 leads last week. Nobody's talking about this."
                />
              </div>
            </div>
            <div className="composer-row">
              <span style={{ color: '#666', fontSize: 11 }}>{status}</span>
              <button className="btn primary" onClick={runScript} disabled={loading}>
                <FileText size={12} style={{ display: 'inline', marginRight: 4 }} />
                {loading ? 'Writing Script...' : 'Generate Full Script'}
              </button>
            </div>
          </div>

          {script && (
            <div className="card" ref={scriptRef}>
              <div className="cmo-script-header">
                <div>
                  <CardTitle title={script.title} />
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: -4 }}>
                    <span className="pill">{script.platform.replace(/_/g, ' ')}</span>
                    <span className="pill">{script.duration}</span>
                    {viralBadge(script.viralScore)}
                  </div>
                </div>
                <button className="btn secondary" onClick={() => copyToClipboard(fullScriptText, 'full-script')}>
                  <Clipboard size={12} style={{ display: 'inline', marginRight: 4 }} />
                  {copied === 'full-script' ? 'Copied!' : 'Copy Full Script'}
                </button>
              </div>

              <div className="cmo-hook-banner">
                <span className="cmo-label">HOOK — FIRST 1.5 SECONDS</span>
                <p>"{script.hook}"</p>
              </div>

              <div className="cmo-segments">
                {script.segments.map((seg, i) => (
                  <div key={i} className="cmo-segment">
                    <div className="cmo-segment-meta">
                      <strong>{seg.label}</strong>
                      <span>{seg.timing}</span>
                    </div>
                    <div className="cmo-segment-content">
                      <p className="cmo-segment-words">"{seg.content}"</p>
                      <p className="cmo-segment-visual">📹 {seg.visualNote}</p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="two-col" style={{ marginTop: 10 }}>
                <div>
                  <div className="cmo-hook-banner" style={{ marginBottom: 8 }}>
                    <span className="cmo-label">CTA</span>
                    <p>{script.cta}</p>
                  </div>
                  <div className="cmo-hook-banner">
                    <span className="cmo-label">CAPTION HOOK</span>
                    <p>{script.captionHook}</p>
                  </div>
                </div>
                <div>
                  <div className="card" style={{ background: '#0c0c0c' }}>
                    <div className="cmo-label" style={{ marginBottom: 6 }}>PRODUCTION NOTES</div>
                    {script.productionNotes.map((n, i) => (
                      <div key={i} className="cmo-hook-item"><span className="cmo-hook-num">→</span><span className="cmo-hook-text">{n}</span></div>
                    ))}
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <div className="cmo-label" style={{ marginBottom: 6 }}>HASHTAGS</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                      {script.hashtags.map((h, i) => <span key={i} className="pill">{h}</span>)}
                    </div>
                  </div>
                </div>
              </div>

              <div style={{ marginTop: 10, borderTop: '1px solid #1c1c1c', paddingTop: 10 }}>
                <span className="cmo-label">SCORE REASONING</span>
                <p style={{ color: '#aaa', fontSize: 12, margin: '6px 0 0' }}>{script.scoreReason}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── HOOK SCORER TAB ── */}
      {tab === 'hook' && (
        <div>
          <div className="card" style={{ marginBottom: 10 }}>
            <CardTitle title="Hook Scorer" />
            <p style={{ color: '#aaa', fontSize: 12, margin: '0 0 10px' }}>
              Paste any hook and Noah scores it across 5 virality dimensions, then rewrites it 3 ways.
            </p>
            <textarea
              value={hookInput}
              onChange={(e) => setHookInput(e.target.value)}
              placeholder="Paste your hook here — the exact first words spoken or shown on screen..."
              style={{ marginBottom: 8 }}
            />
            <div className="composer-row">
              <span style={{ color: '#666', fontSize: 11 }}>{status}</span>
              <button className="btn primary" onClick={runHookScore} disabled={loading}>
                <Brain size={12} style={{ display: 'inline', marginRight: 4 }} />
                {loading ? 'Scoring...' : 'Score This Hook'}
              </button>
            </div>
          </div>

          {hookScore && (
            <>
              <div className="two-col" style={{ marginBottom: 10 }}>
                <div className="card">
                  <CardTitle title="Virality Score" />
                  <div className="cmo-score-hero">
                    <div className="cmo-score-circle" style={{
                      borderColor: hookScore.overallScore >= 75 ? '#00c896' : hookScore.overallScore >= 50 ? '#f0a500' : '#cc1111'
                    }}>
                      <span>{hookScore.overallScore}</span>
                      <small>/100</small>
                    </div>
                    <div className="cmo-score-dims">
                      {(Object.entries(hookScore.breakdown) as [string, number][]).map(([key, val]) => (
                        <div key={key} className="cmo-score-dim">
                          <div className="cmo-score-dim-label">
                            <span>{key.replace(/([A-Z])/g, ' $1').trim()}</span>
                            <span>{val}</span>
                          </div>
                          {scoreBar(val)}
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="two-col" style={{ marginTop: 10, gap: 8 }}>
                    <div>
                      <div className="cmo-label" style={{ marginBottom: 6 }}>STRENGTHS</div>
                      {hookScore.strengths.map((s, i) => (
                        <div key={i} className="cmo-hook-item">
                          <span className="cmo-hook-num" style={{ color: '#00c896' }}>✓</span>
                          <span className="cmo-hook-text">{s}</span>
                        </div>
                      ))}
                    </div>
                    <div>
                      <div className="cmo-label" style={{ marginBottom: 6 }}>IMPROVEMENTS</div>
                      {hookScore.improvements.map((s, i) => (
                        <div key={i} className="cmo-hook-item">
                          <span className="cmo-hook-num" style={{ color: '#f0a500' }}>↑</span>
                          <span className="cmo-hook-text">{s}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="card">
                  <CardTitle title="Rewritten Hooks" />
                  <p style={{ color: '#666', fontSize: 11, margin: '0 0 10px' }}>3 higher-performing rewrites:</p>
                  {hookScore.rewriteSuggestions.map((rw, i) => (
                    <div key={i} className="cmo-hook-item" style={{ marginBottom: 8, alignItems: 'flex-start' }}>
                      <span className="cmo-hook-num">{i + 1}</span>
                      <div style={{ flex: 1 }}>
                        <p className="cmo-hook-text" style={{ marginBottom: 6 }}>"{rw}"</p>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button className="mini" onClick={() => copyToClipboard(rw, `rw-${i}`)}>
                            <Clipboard size={11} /> {copied === `rw-${i}` ? 'Copied!' : 'Copy'}
                          </button>
                          <button className="mini" onClick={() => { setScriptHook(rw); handleTabChange('scripts') }}>
                            Use in Script →
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* ── CONTENT CALENDAR TAB ── */}
      {tab === 'calendar' && (
        <div>
          {/* Schedule new content */}
          <div className="card" style={{ marginBottom: 10 }}>
            <CardTitle title="Schedule Content" />
            <p style={{ color: '#aaa', fontSize: 12, margin: '0 0 12px' }}>
              Schedule a content item to the calendar. After generating a script or concept, schedule it here.
            </p>
            <div className="two-col" style={{ gap: 10, marginBottom: 10 }}>
              <div className="cmo-field">
                <label>Title / Concept</label>
                <input
                  value={calForm.title}
                  onChange={(e) => setCalForm((f) => ({ ...f, title: e.target.value }))}
                  placeholder="e.g. 3 reasons HVAC owners lose leads..."
                />
              </div>
              <div className="cmo-field">
                <label>Platform</label>
                <select
                  value={calForm.platform}
                  onChange={(e) => setCalForm((f) => ({ ...f, platform: e.target.value }))}
                  style={{ background: '#0a0a0a', color: '#eee', border: '1px solid #222', borderRadius: 6, padding: '6px 10px', fontSize: 12 }}
                >
                  <option value="instagram_reels">Instagram Reels</option>
                  <option value="tiktok">TikTok</option>
                  <option value="youtube_shorts">YouTube Shorts</option>
                  <option value="linkedin">LinkedIn</option>
                  <option value="twitter">Twitter/X</option>
                </select>
              </div>
              <div className="cmo-field">
                <label>Publish Date (optional)</label>
                <input
                  type="datetime-local"
                  value={calForm.publishAt}
                  onChange={(e) => setCalForm((f) => ({ ...f, publishAt: e.target.value }))}
                  style={{ colorScheme: 'dark' }}
                />
              </div>
              <div className="cmo-field">
                <label>Notes (optional)</label>
                <input
                  value={calForm.notes}
                  onChange={(e) => setCalForm((f) => ({ ...f, notes: e.target.value }))}
                  placeholder="Production notes, hook angle, CTA..."
                />
              </div>
            </div>
            <div className="composer-row">
              <span style={{ color: calStatus.includes('Error') || calStatus.includes('failed') ? '#cc1111' : '#666', fontSize: 11 }}>{calStatus}</span>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn" onClick={loadCalendar} disabled={calLoading}>
                  <RefreshCw size={12} style={{ display: 'inline', marginRight: 4 }} />Refresh
                </button>
                <button className="btn primary" onClick={scheduleItem} disabled={calLoading}>
                  <Calendar size={12} style={{ display: 'inline', marginRight: 4 }} />
                  {calLoading ? 'Scheduling...' : 'Schedule Content'}
                </button>
              </div>
            </div>
          </div>

          {/* Calendar items */}
          <div className="card">
            <CardTitle title={`Content Calendar — ${calItems.length} items`} />
            {calItems.length === 0 ? (
              <p style={{ color: '#555', fontSize: 12, textAlign: 'center', padding: '20px 0' }}>
                {calLoading ? 'Loading...' : 'No content scheduled yet. Generate a concept or script above, then schedule it here.'}
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {calItems.map((item) => (
                  <div key={item.id} style={{
                    padding: '10px 14px',
                    background: '#0d0d0d',
                    border: '1px solid #1a1a1a',
                    borderRadius: 8,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                  }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#eee', marginBottom: 3 }}>{item.title}</div>
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        <span className="pill" style={{ fontSize: 10 }}>{item.platform}</span>
                        <span className="pill" style={{ fontSize: 10, background: item.status === 'published' ? '#00c89622' : '#1a1a1a', color: item.status === 'published' ? '#00c896' : '#888' }}>{item.status}</span>
                        {item.publish_at && (
                          <span style={{ fontSize: 10, color: '#666' }}>
                            {new Date(item.publish_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                          </span>
                        )}
                        {item.notes && <span style={{ fontSize: 10, color: '#555', fontStyle: 'italic' }}>{item.notes}</span>}
                      </div>
                    </div>
                    <button
                      className="mini"
                      style={{ color: '#cc1111', borderColor: '#2a1111' }}
                      onClick={() => void deleteCalItem(item.id)}
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
function CTOSystem() { return <GenericMission title="CTO System" tabs={['Service Matrix','Failures','Data Integrity','Audit Log','Guardrails']} /> }
function CRM() {
  const [summary, setSummary] = useState<{ totalProspects: number; activeProspects: number; industries: string[]; newest: CrmProspect[] } | null>(null)
  const [prospects, setProspects] = useState<CrmProspect[]>([])

  useEffect(() => {
    const load = async () => {
      try {
        const [dashboardResponse, prospectsResponse] = await Promise.all([
          apiFetch('/api/crm/dashboard'),
          apiFetch('/api/crm/prospects'),
        ])
        const dashboardJson = await dashboardResponse.json()
        const prospectsJson = await prospectsResponse.json()
        if (dashboardJson?.ok) setSummary(dashboardJson.summary)
        if (prospectsJson?.ok) setProspects(prospectsJson.prospects ?? [])
      } catch {
        // leave empty state visible
      }
    }
    void load()
  }, [])

  return (
    <div>
      <PageHeader title="CRM" />
      <div className="tabs"><button className="active">Database</button><button>Stage Board</button><button>Company Records</button><button>Timeline</button></div>
      <div className="stats-four">
        <div className="stat"><p>Total prospects</p><h3>{summary?.totalProspects ?? 0}</h3></div>
        <div className="stat"><p>Active prospects</p><h3>{summary?.activeProspects ?? 0}</h3></div>
        <div className="stat"><p>Industries</p><h3>{summary?.industries.length ?? 0}</h3></div>
        <div className="stat"><p>Newest loaded</p><h3>{summary?.newest.length ?? 0}</h3></div>
      </div>
      <div className="card">
        <CardTitle title="Live Prospects" />
        <table>
          <thead><tr><th>Name</th><th>Company</th><th>Email</th><th>Industry</th><th>Status</th><th>Source</th></tr></thead>
          <tbody>
            {prospects.length === 0 && <tr><td colSpan={6}>No real prospects are loaded yet.</td></tr>}
            {prospects.slice(0, 25).map((prospect) => (
              <tr key={prospect.id}>
                <td>{prospect.full_name}</td>
                <td>{prospect.company_name}</td>
                <td>{prospect.email ?? 'n/a'}</td>
                <td>{prospect.industry ?? 'Unknown'}</td>
                <td>{prospect.status ?? 'unknown'}</td>
                <td>{prospect.source ?? 'unknown'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Meetings() {
  const [meetings, setMeetings] = useState<MeetingsRecord[]>([])

  useEffect(() => {
    const load = async () => {
      try {
        const response = await apiFetch('/api/meetings')
        const json = await response.json()
        if (json?.ok) setMeetings(json.meetings ?? [])
      } catch {
        // leave empty state visible
      }
    }
    void load()
  }, [])

  return (
    <div>
      <PageHeader title="Meetings" />
      <div className="tabs"><button className="active">Queue</button><button>Calendar</button><button>Briefs</button><button>Outcomes</button></div>
      <div className="stats-four">
        <div className="stat"><p>Meetings loaded</p><h3>{meetings.length}</h3></div>
        <div className="stat"><p>Scheduled value</p><h3>${meetings.reduce((sum, item) => sum + (item.value_estimate ?? 0), 0).toLocaleString('en-US')}</h3></div>
        <div className="stat"><p>Discovery calls</p><h3>{meetings.filter((item) => item.meeting_type === 'Discovery').length}</h3></div>
        <div className="stat"><p>Pending schedule</p><h3>{meetings.filter((item) => item.status.includes('pending')).length}</h3></div>
      </div>
      <div className="card">
        <CardTitle title="Live Meeting Queue" />
        <table>
          <thead><tr><th>Prospect</th><th>Company</th><th>Type</th><th>Start</th><th>Status</th><th>Value</th></tr></thead>
          <tbody>
            {meetings.length === 0 && <tr><td colSpan={6}>No real meetings have been booked yet.</td></tr>}
            {meetings.slice(0, 25).map((meeting) => (
              <tr key={meeting.id}>
                <td>{meeting.prospect_name}</td>
                <td>{meeting.company_name}</td>
                <td>{meeting.meeting_type}</td>
                <td>{new Date(meeting.start_at).toLocaleString()}</td>
                <td>{meeting.status}</td>
                <td>${(meeting.value_estimate ?? 0).toLocaleString('en-US')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
function LandingIntelligence() { return <GenericMission title="Landing Intelligence" tabs={['Live Stream','Page Performance','Chat Engagement','Booking Conversion','Hot Prospects']} /> }
function Analytics() { return <GenericMission title="Analytics" tabs={['Campaign','Industry','Revenue','Funnel','Automations','Data Integrity']} /> }

function OutreachPipeline() {
  const [status, setStatus] = useState('Loading live outreach data...')
  const [syncing, setSyncing] = useState(false)
  const [activity, setActivity] = useState<OutreachDashboard | null>(null)

  const loadActivity = async () => {
    try {
      const response = await apiFetch('/api/outreach/dashboard?limit=20')
      const json = await response.json()
      if (json?.ok) {
        setActivity({
          drafts: json.drafts ?? [],
          sends: json.sends ?? [],
          replies: json.replies ?? [],
          source: json.source ?? 'unknown',
        })
        setStatus(`Loaded live outreach activity from ${json.source ?? 'unknown'}.`)
      } else {
        setStatus('Failed to load outreach activity.')
      }
    } catch (error) {
      setStatus(`Failed to load outreach activity: ${(error as Error).message}`)
    }
  }

  useEffect(() => {
    const load = async () => {
      await loadActivity()
    }
    void load()
  }, [])

  const syncReplies = async () => {
    setSyncing(true)
    setStatus('Syncing Gmail replies into the pipeline...')
    try {
      const response = await apiFetch('/api/outreach/sync-replies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit: 20 }),
      })
      const json = await response.json()
      if (!response.ok || !json.ok) {
        setStatus(`Reply sync failed: ${json?.reason ?? 'unknown error'}`)
        return
      }
      setStatus(`Reply sync complete: ${json.synced ?? 0} imported, ${json.duplicates ?? 0} duplicates, ${json.unmatched ?? 0} unmatched.`)
      await loadActivity()
    } catch (error) {
      setStatus(`Reply sync failed: ${(error as Error).message}`)
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div>
      <PageHeader title="Outreach Pipeline" />
      <div className="tabs"><button className="active">Draft Review</button><button>Leads</button><button>Send Monitor</button><button>Reply Inbox</button></div>
      <div className="card">
        <CardTitle title="Live Outreach Activity" />
        <div className="composer-row">
          <span style={{ color: '#aaa', fontSize: 12 }}>{status}</span>
          <div className="tool-toggles">
            <button className="mini" onClick={() => void loadActivity()}>Refresh</button>
            <button className="btn primary" onClick={syncReplies} disabled={syncing}>{syncing ? 'Syncing...' : 'Sync Gmail Replies'}</button>
          </div>
        </div>
      </div>
      <div className="card">
        <CardTitle title="Recent Drafts" />
        <table>
          <thead><tr><th>Prospect</th><th>Company</th><th>Subject</th><th>Mode</th><th>Created</th></tr></thead>
          <tbody>
            {(activity?.drafts.length ?? 0) === 0 && (
              <tr><td colSpan={5}>No live drafts stored yet.</td></tr>
            )}
            {(activity?.drafts ?? []).map((draft) => (
              <tr key={draft.id}>
                <td>{draft.prospects?.full_name ?? 'Unknown'}</td>
                <td>{draft.prospects?.company_name ?? ''}</td>
                <td>{draft.subject}</td>
                <td>{draft.mode}</td>
                <td>{formatDateTime(draft.created_at ?? draft.createdAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="two-col">
        <div className="card">
          <CardTitle title="Send Monitor" />
          <table>
            <thead><tr><th>Recipient</th><th>Subject</th><th>Status</th><th>Reason</th></tr></thead>
            <tbody>
              {(activity?.sends.length ?? 0) === 0 && <tr><td colSpan={4}>No live send events stored yet.</td></tr>}
              {(activity?.sends ?? []).map((send) => (
                <tr key={send.id}>
                  <td>{send.recipient_email ?? send.to ?? 'unknown'}</td>
                  <td>{send.outreach_drafts?.subject ?? 'n/a'}</td>
                  <td>{send.status}</td>
                  <td>{send.reason ?? 'sent'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <CardTitle title="Reply Inbox" />
          <table>
            <thead><tr><th>Prospect</th><th>Company</th><th>Intent</th><th>Reply</th></tr></thead>
            <tbody>
              {(activity?.replies.length ?? 0) === 0 && <tr><td colSpan={4}>No live reply events stored yet.</td></tr>}
              {(activity?.replies ?? []).map((reply) => (
                <tr key={reply.id}>
                  <td>{reply.prospects?.full_name ?? 'Unknown'}</td>
                  <td>{reply.prospects?.company_name ?? ''}</td>
                  <td>{reply.intent}</td>
                  <td>{reply.raw_text ?? reply.rawText ?? 'Reply captured without body text.'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function GenericMission({ title, tabs }: { title: string; tabs: string[] }) {
  return (
    <div>
      <PageHeader title={title} />
      <div className="tabs">{tabs.map((tab, i) => <button className={i===0?'active':''} key={tab}>{tab}</button>)}</div>
      <div className="stats-four">
        {['Running count','Failed today','Success rate','Total runs today'].map((s, i) => <div className="stat" key={s}><p>{s}</p><h3>{['27','3','97.4%','1,408'][i]}</h3></div>)}
      </div>
      <div className="card">
        <CardTitle title={`${title} Control Surface`} />
        <table>
          <thead><tr><th>Name</th><th>Owner</th><th>Trigger</th><th>Last Run</th><th>Status</th></tr></thead>
          <tbody>
            {[
              ['New lead enrichment','Jarvis','New lead','2m ago','Online'],
              ['Daily outreach batch','Outreach','09:00 IST','8m ago','Online'],
              ['Reply classification','CMO','On reply','1m ago','Online'],
              ['Landing visit alert','CTO','Page event','14m ago','Warning'],
            ].map((row) => <tr key={row[0]}>{row.map((cell) => <td key={cell}>{cell}</td>)}</tr>)}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Content Cycle Types ───────────────────────────────────────────────────
type ContentStage = 'ideas' | 'scripted' | 'filming' | 'editing' | 'scheduled' | 'posted'
type ContentPlatform = 'instagram_reels' | 'tiktok' | 'youtube_shorts' | 'linkedin' | 'twitter'
type ContentPiece = {
  id: string
  title: string
  hook: string
  platform: ContentPlatform
  stage: ContentStage
  format: string
  viralScore?: number
  createdAt: string
  scheduledFor?: string
}

const STAGES: { id: ContentStage; label: string; color: string }[] = [
  { id: 'ideas', label: 'Ideas', color: '#555' },
  { id: 'scripted', label: 'Scripted', color: '#3b9eff' },
  { id: 'filming', label: 'Filming', color: '#f0a500' },
  { id: 'editing', label: 'Editing', color: '#9b59b6' },
  { id: 'scheduled', label: 'Scheduled', color: '#00c896' },
  { id: 'posted', label: 'Posted', color: '#cc1111' },
]

const SEED_PIECES: ContentPiece[] = [
  { id: 'cp1', title: 'How I booked 47 meetings in 7 days with AI', hook: 'I used AI to generate 47 qualified leads last week. Nobody\'s talking about this method.', platform: 'instagram_reels', stage: 'scripted', format: 'talking_head', viralScore: 87, createdAt: new Date().toISOString() },
  { id: 'cp2', title: 'Stop sending cold emails like this', hook: 'Stop. Before you send that cold email, watch this.', platform: 'tiktok', stage: 'ideas', format: 'list_format', viralScore: 84, createdAt: new Date().toISOString() },
  { id: 'cp3', title: 'Day in the life: $50K/month outbound system', hook: 'A day in the life of running an outbound system doing $50K a month.', platform: 'instagram_reels', stage: 'filming', format: 'day_in_life', viralScore: 81, createdAt: new Date().toISOString() },
  { id: 'cp4', title: 'The email that books meetings every time', hook: 'This exact email has a 23% reply rate. Copy it word for word.', platform: 'youtube_shorts', stage: 'editing', format: 'text_on_screen', viralScore: 91, createdAt: new Date().toISOString() },
  { id: 'cp5', title: 'Truth about reply rates nobody talks about', hook: 'Industry "experts" say 3% reply rate is good. That\'s a lie.', platform: 'linkedin', stage: 'scheduled', format: 'talking_head', viralScore: 85, createdAt: new Date().toISOString(), scheduledFor: 'Mon 9AM' },
  { id: 'cp6', title: 'Building Forge OS — the AI company OS', hook: 'I\'m building an operating system for my entire company out of AI agents.', platform: 'instagram_reels', stage: 'posted', format: 'storytime', viralScore: 79, createdAt: new Date().toISOString() },
]

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const PLATFORMS_SHORT: Record<ContentPlatform, string> = {
  instagram_reels: 'IG', tiktok: 'TK', youtube_shorts: 'YT', linkedin: 'LI', twitter: 'X',
}

function ContentCycle() {
  const [tab, setTab] = useState<'pipeline' | 'ideas' | 'calendar'>('pipeline')
  const [pieces, setPieces] = useState<ContentPiece[]>(SEED_PIECES)
  const [newTitle, setNewTitle] = useState('')
  const [newHook, setNewHook] = useState('')
  const [newPlatform, setNewPlatform] = useState<ContentPlatform>('instagram_reels')
  const [niche, setNiche] = useState('B2B Lead Generation')
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState('')

  const advanceStage = (id: string) => {
    setPieces((prev) => prev.map((p) => {
      if (p.id !== id) return p
      const idx = STAGES.findIndex((s) => s.id === p.stage)
      const next = STAGES[Math.min(idx + 1, STAGES.length - 1)]
      return { ...p, stage: next?.id ?? p.stage }
    }))
  }

  const addIdea = () => {
    if (!newTitle.trim()) return
    const piece: ContentPiece = {
      id: `cp${Date.now()}`,
      title: newTitle,
      hook: newHook || 'Hook TBD',
      platform: newPlatform,
      stage: 'ideas',
      format: 'talking_head',
      createdAt: new Date().toISOString(),
    }
    setPieces((prev) => [piece, ...prev])
    setNewTitle('')
    setNewHook('')
  }

  const generateFromCMO = async () => {
    setLoading(true)
    setStatus('Noah is generating concepts...')
    try {
      const res = await apiFetch('/api/cmo/concepts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ niche, platform: newPlatform, count: 4 }),
      })
      const json = await res.json()
      if (json?.ok && Array.isArray(json.concepts)) {
        const imported: ContentPiece[] = json.concepts.map((c: { id?: string; title?: string; hook?: string; platforms?: ContentPlatform[]; format?: string; viralScore?: number }) => ({
          id: c.id ?? `cp${Date.now()}_${Math.random().toString(36).slice(2)}`,
          title: c.title ?? 'Untitled concept',
          hook: c.hook ?? '',
          platform: c.platforms?.[0] ?? newPlatform,
          stage: 'ideas' as ContentStage,
          format: c.format ?? 'talking_head',
          viralScore: c.viralScore,
          createdAt: new Date().toISOString(),
        }))
        setPieces((prev) => [...imported, ...prev])
        setStatus(`${imported.length} concepts imported from Noah.`)
      } else {
        setStatus('CMO concept generation failed.')
      }
    } catch (e) { setStatus(`Error: ${(e as Error).message}`) }
    finally { setLoading(false) }
  }

  const stageColor = (stage: ContentStage) => STAGES.find((s) => s.id === stage)?.color ?? '#555'

  return (
    <div>
      <PageHeader title="Content Cycle" right={<span className="pill green"><Video size={11} /> Noah Content Engine</span>} />

      <div className="tabs">
        {(['pipeline', 'ideas', 'calendar'] as const).map((t) => (
          <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>
            {t === 'pipeline' ? 'Pipeline' : t === 'ideas' ? 'Idea Bank' : 'Calendar'}
          </button>
        ))}
      </div>

      {/* ── PIPELINE TAB ── */}
      {tab === 'pipeline' && (
        <div>
          <div className="stats-four" style={{ gridTemplateColumns: `repeat(${STAGES.length}, minmax(0,1fr))` }}>
            {STAGES.map((s) => (
              <div className="stat" key={s.id} style={{ borderTop: `2px solid ${s.color}` }}>
                <p>{s.label}</p>
                <h3>{pieces.filter((p) => p.stage === s.id).length}</h3>
              </div>
            ))}
          </div>
          <div className="cycle-pipeline">
            {STAGES.map((s) => (
              <div className="cycle-stage" key={s.id}>
                <div className="cycle-stage-header" style={{ borderColor: s.color }}>
                  <span style={{ color: s.color }}>{s.label}</span>
                  <span className="badge">{pieces.filter((p) => p.stage === s.id).length}</span>
                </div>
                {pieces.filter((p) => p.stage === s.id).map((p) => (
                  <div className="cycle-card" key={p.id}>
                    <div className="cycle-card-platform">
                      <span className="pill" style={{ fontSize: 9 }}>{PLATFORMS_SHORT[p.platform]}</span>
                      {p.viralScore && <span style={{ fontSize: 10, color: p.viralScore >= 85 ? '#00c896' : '#f0a500' }}>{p.viralScore}</span>}
                    </div>
                    <p className="cycle-card-title">{p.title}</p>
                    <p className="cycle-card-hook">"{p.hook}"</p>
                    {p.scheduledFor && <span className="cycle-card-sched">📅 {p.scheduledFor}</span>}
                    {s.id !== 'posted' && (
                      <button className="mini" style={{ marginTop: 6, width: '100%' }} onClick={() => advanceStage(p.id)}>
                        → Move to {STAGES[STAGES.findIndex((x) => x.id === s.id) + 1]?.label ?? 'Next'}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── IDEAS TAB ── */}
      {tab === 'ideas' && (
        <div>
          <div className="card" style={{ marginBottom: 10 }}>
            <CardTitle title="Add New Idea" />
            <div className="cmo-script-inputs">
              <div className="cmo-field">
                <label>Title / Concept</label>
                <input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="What's the video about?" />
              </div>
              <div className="cmo-field">
                <label>Platform</label>
                <div className="segmented">
                  {(['instagram_reels', 'tiktok', 'youtube_shorts', 'linkedin'] as ContentPlatform[]).map((p) => (
                    <button key={p} className={newPlatform === p ? 'active' : ''} onClick={() => setNewPlatform(p)}>
                      {PLATFORMS_SHORT[p]}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="cmo-field" style={{ marginBottom: 10 }}>
              <label>Hook (first 1.5 seconds)</label>
              <input value={newHook} onChange={(e) => setNewHook(e.target.value)} placeholder="The hook that stops the scroll..." />
            </div>
            <div className="composer-row">
              <button className="btn secondary" onClick={addIdea}>Add Idea</button>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input
                  value={niche}
                  onChange={(e) => setNiche(e.target.value)}
                  placeholder="Niche for CMO..."
                  style={{ height: 32, background: '#0c0c0c', border: '1px solid #1c1c1c', color: '#fff', borderRadius: 5, padding: '0 8px', fontFamily: 'inherit', fontSize: 11, width: 200 }}
                />
                <button className="btn primary" onClick={generateFromCMO} disabled={loading}>
                  <Sparkles size={12} style={{ display: 'inline', marginRight: 4 }} />
                  {loading ? 'Generating...' : 'Generate 4 from Noah'}
                </button>
              </div>
            </div>
            {status && <p style={{ color: '#666', fontSize: 11, margin: '8px 0 0' }}>{status}</p>}
          </div>

          <div className="cmo-concepts-grid">
            {pieces.filter((p) => p.stage === 'ideas').map((p) => (
              <div className="cycle-card" key={p.id} style={{ background: '#111', border: '1px solid #1c1c1c', borderRadius: 5, padding: 10 }}>
                <div className="cycle-card-platform">
                  <span className="pill" style={{ fontSize: 9 }}>{PLATFORMS_SHORT[p.platform]}</span>
                  {p.viralScore && <span style={{ fontSize: 10, color: p.viralScore >= 85 ? '#00c896' : '#f0a500' }}>{p.viralScore}</span>}
                </div>
                <p className="cycle-card-title">{p.title}</p>
                <p className="cycle-card-hook">"{p.hook}"</p>
                <button className="btn primary" style={{ height: 28, fontSize: 10, marginTop: 8, width: '100%' }} onClick={() => advanceStage(p.id)}>
                  Move to Scripted →
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── CALENDAR TAB ── */}
      {tab === 'calendar' && (
        <div>
          <div className="card">
            <CardTitle title="This Week" />
            <div className="cycle-calendar">
              {DAYS.map((day) => {
                const dayPieces = pieces.filter((p) => p.stage === 'scheduled' && p.scheduledFor?.startsWith(day))
                return (
                  <div key={day} className="cycle-cal-day">
                    <div className="cycle-cal-header">{day}</div>
                    {dayPieces.length === 0
                      ? <div className="cycle-cal-empty">—</div>
                      : dayPieces.map((p) => (
                          <div key={p.id} className="cycle-cal-item" style={{ borderColor: stageColor(p.stage) }}>
                            <span className="pill" style={{ fontSize: 9 }}>{PLATFORMS_SHORT[p.platform]}</span>
                            <p>{p.title}</p>
                          </div>
                        ))
                    }
                  </div>
                )
              })}
            </div>
          </div>
          <div className="card" style={{ marginTop: 10 }}>
            <CardTitle title="Scheduled Content" />
            <table>
              <thead><tr><th>Day</th><th>Platform</th><th>Title</th><th>Hook</th><th>Score</th></tr></thead>
              <tbody>
                {pieces.filter((p) => p.stage === 'scheduled' || p.stage === 'posted').map((p) => (
                  <tr key={p.id}>
                    <td>{p.scheduledFor ?? 'Unscheduled'}</td>
                    <td><span className="pill" style={{ fontSize: 9 }}>{PLATFORMS_SHORT[p.platform]}</span></td>
                    <td>{p.title}</td>
                    <td style={{ color: '#aaa', fontSize: 11 }}>{p.hook.slice(0, 50)}...</td>
                    <td>{p.viralScore ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Self Development Types ────────────────────────────────────────────────
type GoalHorizon = 'now' | 'soon' | 'vision'
type GoalCategory = 'Business' | 'Skills' | 'Health' | 'Mindset'
type SDGoal = { id: string; title: string; category: GoalCategory; horizon: GoalHorizon; progress: number; notes: string }
type LearnStatus = 'To Start' | 'In Progress' | 'Done'
type LearnCategory = 'Books' | 'Courses' | 'Videos' | 'Podcasts'
type LearnItem = { id: string; title: string; source: string; category: LearnCategory; status: LearnStatus; notes: string }

const SEED_GOALS: SDGoal[] = [
  { id: 'g1', title: 'Hit $15M MRR in 7 months', category: 'Business', horizon: 'vision', progress: 2, notes: 'Current: $0. Path: legal + fintech outbound → product-led → referral flywheel.' },
  { id: 'g2', title: 'Book 18 meetings this week', category: 'Business', horizon: 'now', progress: 40, notes: 'Legal sector is showing 15.2% meeting intent. Double down there.' },
  { id: 'g3', title: 'Build full Forge OS with all 7 executives', category: 'Business', horizon: 'soon', progress: 35, notes: 'Jarvis + Noah done. Damien (CTO) partially built. Zoya, Devan, Akhil, King pending.' },
  { id: 'g4', title: 'Reach 10K followers on Instagram', category: 'Business', horizon: 'soon', progress: 10, notes: 'Posting 1 reel per day. Content cycle pipeline now live.' },
  { id: 'g5', title: 'Master cold email copywriting', category: 'Skills', horizon: 'now', progress: 60, notes: 'Study Hormozi, study reply patterns in Forge OS analytics.' },
  { id: 'g6', title: 'Daily 6AM start', category: 'Health', horizon: 'now', progress: 50, notes: 'Sleep by 11PM. No screens 30 min before bed.' },
  { id: 'g7', title: 'Build unshakeable focus discipline', category: 'Mindset', horizon: 'soon', progress: 30, notes: 'Deep work blocks 9AM–1PM. No meetings before noon.' },
]

const SEED_LEARN: LearnItem[] = [
  { id: 'l1', title: '$100M Offers', source: 'Alex Hormozi', category: 'Books', status: 'In Progress', notes: 'Chapter 7. Core insight: niche down the result, not the offer.' },
  { id: 'l2', title: 'MrBeast Content Strategy breakdown', source: 'Colin & Samir', category: 'Videos', status: 'Done', notes: 'Retention in first 30s is everything. Applied to CMO hook scorer.' },
  { id: 'l3', title: 'Fast.ai — Practical Deep Learning', source: 'fast.ai', category: 'Courses', status: 'To Start', notes: 'For AI Specialist (King) module development.' },
  { id: 'l4', title: 'The Art of Cold Email', source: 'Predictable Revenue', category: 'Books', status: 'To Start', notes: 'Research for improving outreach system templates.' },
  { id: 'l5', title: 'My First Million', source: 'Sam Parr & Shaan Puri', category: 'Podcasts', status: 'In Progress', notes: 'Good for business model thinking. Listen during morning walks.' },
  { id: 'l6', title: 'Gemini API Advanced Features', source: 'Google', category: 'Courses', status: 'In Progress', notes: 'Prompt caching, function calling, grounding. For Jarvis improvements.' },
]

const HABITS = [
  'Morning system review (leads, sends, replies)',
  'Approve outreach batch',
  'Move 1 content piece through pipeline',
  'Complete 1 learning session (30 min)',
  'Write daily reflection note',
  'Workout / walk',
]

function getWeekKey() {
  const now = new Date()
  const jan1 = new Date(now.getFullYear(), 0, 1)
  const week = Math.ceil((((now.getTime() - jan1.getTime()) / 86400000) + jan1.getDay() + 1) / 7)
  return `${now.getFullYear()}-W${week}`
}

function getDayKeys(): string[] {
  const days = []
  for (let i = 6; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    days.push(d.toISOString().slice(0, 10))
  }
  return days
}

type JarvisGrade = {
  grade: string; score: number
  breakdown: Record<string, { grade: string; score: number; feedback: string }>
  recommendations: string[]; headline: string; honestTruth: string
}

function SelfDevelopment() {
  const [tab, setTab] = useState<'goals' | 'habits' | 'learning' | 'reflection'>('goals')
  const [goals, setGoals] = useState<SDGoal[]>(SEED_GOALS)
  const [learn, setLearn] = useState<LearnItem[]>(SEED_LEARN)
  const [habits, setHabits] = useState<Record<string, boolean>>({})
  const [reflections, setReflections] = useState<Record<string, { win: string; lesson: string; next: string }>>({})
  const [newGoalTitle, setNewGoalTitle] = useState('')
  const [newGoalCat, setNewGoalCat] = useState<GoalCategory>('Business')
  const [newGoalHorizon, setNewGoalHorizon] = useState<GoalHorizon>('now')
  const [jarvisGrade, setJarvisGrade] = useState<JarvisGrade | null>(null)
  const [grading, setGrading] = useState(false)
  const weekKey = getWeekKey()
  const dayKeys = getDayKeys()
  const ref = reflections[weekKey] ?? { win: '', lesson: '', next: '' }

  const toggleHabit = (dayKey: string, habitIdx: number) => {
    const key = `${dayKey}::${habitIdx}`
    setHabits((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const habitsDoneToday = HABITS.filter((_, i) => habits[`${dayKeys[6]}::${i}`]).length
  const completedGoals = goals.filter((g) => g.progress >= 100).length
  const inProgressLearn = learn.filter((l) => l.status === 'In Progress').length

  const gradeMyWeek = async () => {
    setGrading(true)
    try {
      const res = await apiFetch('/api/jarvis/grade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          goals: goals.map((g) => ({ title: g.title, category: g.category, horizon: g.horizon, progress: g.progress })),
          habitsCompletedToday: habitsDoneToday,
          totalHabits: HABITS.length,
          learningInProgress: learn.filter((l) => l.status === 'In Progress').map((l) => l.title),
          reflection: ref,
        }),
      })
      const json = await res.json()
      if (json?.ok) setJarvisGrade(json.grade)
    } catch {
      setJarvisGrade(null)
    }
    finally { setGrading(false) }
  }

  const addGoal = () => {
    if (!newGoalTitle.trim()) return
    setGoals((prev) => [...prev, {
      id: `g${Date.now()}`, title: newGoalTitle, category: newGoalCat,
      horizon: newGoalHorizon, progress: 0, notes: '',
    }])
    setNewGoalTitle('')
  }

  const updateProgress = (id: string, delta: number) => {
    setGoals((prev) => prev.map((g) => g.id === id ? { ...g, progress: Math.max(0, Math.min(100, g.progress + delta)) } : g))
  }

  const toggleLearnStatus = (id: string) => {
    const order: LearnStatus[] = ['To Start', 'In Progress', 'Done']
    setLearn((prev) => prev.map((l) => l.id === id ? { ...l, status: order[(order.indexOf(l.status) + 1) % order.length] } : l))
  }

  const catColor: Record<GoalCategory, string> = { Business: '#cc1111', Skills: '#3b9eff', Health: '#00c896', Mindset: '#f0a500' }
  const horizonLabel: Record<GoalHorizon, string> = { now: 'Now (0–30d)', soon: 'Soon (30–90d)', vision: 'Vision (90d+)' }

  return (
    <div>
      <PageHeader title="Self Development" right={
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <div className="stat" style={{ padding: '4px 10px', minWidth: 0 }}><p style={{ fontSize: 9 }}>Today's habits</p><h3 style={{ fontSize: 18 }}>{habitsDoneToday}/{HABITS.length}</h3></div>
          <div className="stat" style={{ padding: '4px 10px', minWidth: 0 }}><p style={{ fontSize: 9 }}>Goals active</p><h3 style={{ fontSize: 18 }}>{goals.length - completedGoals}</h3></div>
          <div className="stat" style={{ padding: '4px 10px', minWidth: 0 }}><p style={{ fontSize: 9 }}>Learning now</p><h3 style={{ fontSize: 18 }}>{inProgressLearn}</h3></div>
          {jarvisGrade && <div className="stat" style={{ padding: '4px 10px', minWidth: 0, borderColor: 'rgba(204,17,17,.3)' }}><p style={{ fontSize: 9 }}>Jarvis grade</p><h3 style={{ fontSize: 18, color: '#cc1111' }}>{jarvisGrade.grade}</h3></div>}
          <button className="btn primary" onClick={gradeMyWeek} disabled={grading}>
            <Brain size={12} style={{ display: 'inline', marginRight: 4 }} />
            {grading ? 'Grading...' : 'Grade My Week'}
          </button>
        </div>
      } />

      {jarvisGrade && (
        <div className="card jarvis-grade-card" style={{ marginBottom: 10 }}>
          <div className="jarvis-grade-header">
            <div>
              <div className="cmo-label">JARVIS WEEKLY GRADE</div>
              <div className="jarvis-grade-headline">{jarvisGrade.headline}</div>
            </div>
            <div className="jarvis-grade-score" style={{ borderColor: jarvisGrade.score >= 80 ? '#00c896' : jarvisGrade.score >= 60 ? '#f0a500' : '#cc1111' }}>
              <span style={{ color: jarvisGrade.score >= 80 ? '#00c896' : jarvisGrade.score >= 60 ? '#f0a500' : '#cc1111' }}>{jarvisGrade.grade}</span>
              <small>{jarvisGrade.score}/100</small>
            </div>
          </div>
          <div className="jarvis-grade-truth">"{jarvisGrade.honestTruth}"</div>
          <div className="two-col" style={{ gap: 8, marginTop: 8 }}>
            <div>
              <div className="cmo-label" style={{ marginBottom: 6 }}>BREAKDOWN</div>
              {Object.entries(jarvisGrade.breakdown).map(([cat, data]) => (
                <div key={cat} className="jarvis-grade-row">
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 11, fontWeight: 700 }}>{cat}</span>
                    <span style={{ fontSize: 11, fontWeight: 700, color: data.score >= 80 ? '#00c896' : data.score >= 60 ? '#f0a500' : '#cc1111' }}>{data.grade}</span>
                  </div>
                  <p style={{ margin: '3px 0 0', fontSize: 11, color: '#aaa' }}>{data.feedback}</p>
                </div>
              ))}
            </div>
            <div>
              <div className="cmo-label" style={{ marginBottom: 6 }}>JARVIS RECOMMENDATIONS</div>
              {jarvisGrade.recommendations.map((r, i) => (
                <div key={i} className="cmo-hook-item">
                  <span className="cmo-hook-num" style={{ color: '#cc1111' }}>{i + 1}</span>
                  <span className="cmo-hook-text">{r}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="tabs">
        {(['goals', 'habits', 'learning', 'reflection'] as const).map((t) => (
          <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* ── GOALS ── */}
      {tab === 'goals' && (
        <div>
          <div className="card" style={{ marginBottom: 10 }}>
            <CardTitle title="Add Goal" />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto auto auto', gap: 8, alignItems: 'end' }}>
              <div className="cmo-field">
                <label>Goal</label>
                <input value={newGoalTitle} onChange={(e) => setNewGoalTitle(e.target.value)} placeholder="What do you want to achieve?" onKeyDown={(e) => e.key === 'Enter' && addGoal()} />
              </div>
              <div className="cmo-field">
                <label>Category</label>
                <div className="segmented">
                  {(['Business', 'Skills', 'Health', 'Mindset'] as GoalCategory[]).map((c) => (
                    <button key={c} className={newGoalCat === c ? 'active' : ''} onClick={() => setNewGoalCat(c)} style={{ fontSize: 10 }}>{c}</button>
                  ))}
                </div>
              </div>
              <div className="cmo-field">
                <label>Horizon</label>
                <div className="segmented">
                  {(['now', 'soon', 'vision'] as GoalHorizon[]).map((h) => (
                    <button key={h} className={newGoalHorizon === h ? 'active' : ''} onClick={() => setNewGoalHorizon(h)} style={{ fontSize: 10 }}>{h}</button>
                  ))}
                </div>
              </div>
              <button className="btn primary" onClick={addGoal} style={{ alignSelf: 'flex-end' }}>Add</button>
            </div>
          </div>

          <div className="sd-goals-grid">
            {(['now', 'soon', 'vision'] as GoalHorizon[]).map((horizon) => (
              <div key={horizon}>
                <div className="card-title" style={{ marginBottom: 8 }}>{horizonLabel[horizon]}</div>
                {goals.filter((g) => g.horizon === horizon).map((g) => (
                  <div className="sd-goal-card" key={g.id}>
                    <div className="sd-goal-header">
                      <span className="sd-goal-cat" style={{ color: catColor[g.category], borderColor: catColor[g.category] }}>{g.category}</span>
                      <span style={{ fontSize: 11, color: g.progress >= 100 ? '#00c896' : '#aaa', fontWeight: 700 }}>{g.progress}%</span>
                    </div>
                    <p className="sd-goal-title">{g.title}</p>
                    {g.notes && <p className="sd-goal-notes">{g.notes}</p>}
                    <div className="sd-goal-bar">
                      <div className="sd-goal-fill" style={{ width: `${g.progress}%`, background: catColor[g.category] }} />
                    </div>
                    <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
                      <button className="mini" onClick={() => updateProgress(g.id, -10)}>−10%</button>
                      <button className="mini" onClick={() => updateProgress(g.id, 10)}>+10%</button>
                      <button className="mini" onClick={() => updateProgress(g.id, 100 - g.progress)} style={{ marginLeft: 'auto' }}>Mark Done</button>
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── HABITS ── */}
      {tab === 'habits' && (
        <div>
          <div className="stats-four" style={{ gridTemplateColumns: 'repeat(3,minmax(0,1fr))' }}>
            <div className="stat"><p>Done today</p><h3>{habitsDoneToday}/{HABITS.length}</h3></div>
            <div className="stat"><p>Week streak</p><h3>{dayKeys.filter((d) => HABITS.filter((_, i) => habits[`${d}::${i}`]).length >= 4).length}d</h3></div>
            <div className="stat"><p>Completion rate</p><h3>{Math.round((Object.values(habits).filter(Boolean).length / Math.max(1, dayKeys.length * HABITS.length)) * 100)}%</h3></div>
          </div>
          <div className="card">
            <CardTitle title="7-Day Habit Tracker" />
            <div className="sd-habits-grid">
              <div className="sd-habit-row" style={{ borderBottom: '1px solid #1c1c1c', paddingBottom: 6, marginBottom: 6 }}>
                <span style={{ fontSize: 9, color: '#666', letterSpacing: 2 }}>HABIT</span>
                {dayKeys.map((d) => <span key={d} style={{ fontSize: 9, color: '#666', textAlign: 'center' }}>{new Date(d).toLocaleDateString('en', { weekday: 'short' })}</span>)}
              </div>
              {HABITS.map((habit, hi) => (
                <div className="sd-habit-row" key={hi}>
                  <span className="sd-habit-label">{habit}</span>
                  {dayKeys.map((d) => {
                    const key = `${d}::${hi}`
                    const done = habits[key]
                    return (
                      <button key={d} className="sd-habit-check" style={{ color: done ? '#00c896' : '#333', borderColor: done ? '#00c896' : '#262626', background: done ? 'rgba(0,200,150,.08)' : 'transparent' }} onClick={() => toggleHabit(d, hi)}>
                        {done ? '✓' : '○'}
                      </button>
                    )
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── LEARNING QUEUE ── */}
      {tab === 'learning' && (
        <div>
          <div className="stats-four">
            {(['Books', 'Courses', 'Videos', 'Podcasts'] as LearnCategory[]).map((cat) => (
              <div className="stat" key={cat}>
                <p>{cat}</p>
                <h3>{learn.filter((l) => l.category === cat && l.status !== 'Done').length} left</h3>
              </div>
            ))}
          </div>
          <div className="sd-learning-cols">
            {(['Books', 'Courses', 'Videos', 'Podcasts'] as LearnCategory[]).map((cat) => (
              <div key={cat}>
                <div className="card-title" style={{ marginBottom: 8 }}>{cat}</div>
                {learn.filter((l) => l.category === cat).map((l) => (
                  <div className="sd-learn-item" key={l.id}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <strong style={{ fontSize: 12 }}>{l.title}</strong>
                      <button className="mini" style={{ fontSize: 9, padding: '2px 6px', color: l.status === 'Done' ? '#00c896' : l.status === 'In Progress' ? '#f0a500' : '#666' }} onClick={() => toggleLearnStatus(l.id)}>
                        {l.status}
                      </button>
                    </div>
                    <p style={{ margin: 0, color: '#666', fontSize: 11 }}>{l.source}</p>
                    {l.notes && <p style={{ margin: '4px 0 0', color: '#aaa', fontSize: 11, lineHeight: 1.4 }}>{l.notes}</p>}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── REFLECTION ── */}
      {tab === 'reflection' && (
        <div>
          <div className="card" style={{ marginBottom: 10 }}>
            <CardTitle title={`Week ${weekKey} — Current Reflection`} />
            <div style={{ display: 'grid', gap: 10 }}>
              {[
                ['win', "This week's biggest win", '#00c896'],
                ['lesson', 'Biggest lesson learned', '#f0a500'],
                ['next', 'Next week\'s #1 priority', '#cc1111'],
              ].map(([field, label, color]) => (
                <div key={field} className="cmo-field">
                  <label style={{ color }}>{label}</label>
                  <textarea
                    value={ref[field as 'win' | 'lesson' | 'next']}
                    onChange={(e) => setReflections((prev) => ({
                      ...prev,
                      [weekKey]: { ...ref, [field]: e.target.value },
                    }))}
                    placeholder={`Write your ${label.toLowerCase()}...`}
                    style={{ minHeight: 72 }}
                  />
                </div>
              ))}
            </div>
          </div>

          {Object.entries(reflections).filter(([k]) => k !== weekKey).reverse().map(([week, r]) => (
            <div className="sd-reflection-entry card" key={week}>
              <div className="card-title">{week}</div>
              {r.win && <div><span className="cmo-label" style={{ color: '#00c896' }}>WIN</span><p style={{ color: '#ccc', fontSize: 12, margin: '4px 0 8px' }}>{r.win}</p></div>}
              {r.lesson && <div><span className="cmo-label" style={{ color: '#f0a500' }}>LESSON</span><p style={{ color: '#ccc', fontSize: 12, margin: '4px 0 8px' }}>{r.lesson}</p></div>}
              {r.next && <div><span className="cmo-label" style={{ color: '#cc1111' }}>NEXT</span><p style={{ color: '#ccc', fontSize: 12, margin: '4px 0' }}>{r.next}</p></div>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function SettingsPage() {
  return (
    <div>
      <PageHeader title="Settings" />
      <div className="tabs"><button className="active">Workspace</button><button>Team</button><button>API Connections</button><button>Agent Permissions</button><button>Compliance</button></div>
      <div className="card">
        <CardTitle title="API Connections" />
        <table><thead><tr><th>Integration</th><th>Status</th><th>Action</th></tr></thead><tbody>
          {['Supabase','Upstash Redis','Gemini','Gmail','Apollo.io','Slack','HuggingFace','Notion'].map((s) => <tr key={s}><td>{s}</td><td><span className={`badge ${s==='Gmail'?'warn':'ok'}`}>{s==='Gmail'?'Re-auth Needed':'Connected'}</span></td><td><button className="mini">Re-connect</button></td></tr>)}
        </tbody></table>
      </div>
    </div>
  )
}

function PublicFunnel() {
  return (
    <div>
      <PageHeader title="Public Landing Funnel" />
      <div className="hero-public">
        <h2>Outbound AI Operating System For B2B Teams</h2>
        <p>Deploy campaign intelligence, live qualification, and meeting conversion systems in one stack.</p>
        <button className="btn primary">Book a Call</button>
      </div>
      <div className="stats-four">
        {['Landing Page','Proof / Case Studies','AI Chat Concierge','Book a Call'].map((x) => <div className="stat" key={x}><p>Funnel Step</p><h3>{x}</h3></div>)}
      </div>
    </div>
  )
}

function PageHeader({ title, right }: { title: string; right?: React.ReactNode }) {
  return (
    <div className="page-head">
      <div>
        <p className="eyebrow">FORGE OS</p>
        <h2>{title}</h2>
      </div>
      <div className="head-actions">
        <button className="mini"><ChartColumn size={13} /> Export</button>
        <button className="btn primary"><Brain size={13} /> Run Briefing</button>
        {right}
      </div>
    </div>
  )
}

function CardTitle({ title }: { title: string }) {
  return <div className="card-title">{title}</div>
}

// ── Google Sign-In Auth Gate ──────────────────────────────────────────────
declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: { client_id: string; callback: (response: { credential: string }) => void; auto_select?: boolean }) => void
          renderButton: (element: HTMLElement, options: Record<string, unknown>) => void
          prompt: () => void
        }
      }
    }
  }
}

const AUTHORIZED_EMAIL = 'jxabros@gmail.com'
const AUTH_KEY = 'forge_os_auth'
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined

function parseJwt(token: string): { email?: string; name?: string; picture?: string; sub?: string } {
  try {
    const base64 = token.split('.')[1]?.replace(/-/g, '+').replace(/_/g, '/')
    if (!base64) return {}
    return JSON.parse(atob(base64)) as { email?: string; name?: string; picture?: string; sub?: string }
  } catch { return {} }
}

function readStoredAuthToken() {
  const stored = localStorage.getItem(AUTH_KEY)
  if (!stored || !GOOGLE_CLIENT_ID) return stored
  const payload = parseJwt(stored)
  if (!payload.sub) {
    localStorage.removeItem(AUTH_KEY)
    return null
  }
  const exp = (payload as { exp?: number }).exp
  if (typeof exp === 'number' && Date.now() / 1000 > exp) {
    localStorage.removeItem(AUTH_KEY)
    return null
  }
  return stored
}

function AuthGate({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(readStoredAuthToken)
  const [error, setError] = useState('')

  const handleLogin = useCallback((credential: string) => {
    const payload = parseJwt(credential)
    if (!GOOGLE_CLIENT_ID || payload.email === AUTHORIZED_EMAIL) {
      localStorage.setItem(AUTH_KEY, credential)
      setToken(credential)
      setError('')
    } else {
      setError(`Access denied: ${payload.email ?? 'unknown'} is not an authorized operator.`)
    }
  }, [])

  // Verify stored token is still valid (not expired) — JWT exp is in seconds
  /* eslint-disable react-hooks/purity */
  const isValid = (() => {
    if (!token) return false
    if (!GOOGLE_CLIENT_ID) return true // no auth configured — allow through
    const payload = parseJwt(token)
    if (!payload.sub) return false
    const exp = (payload as { exp?: number }).exp
    if (exp && Date.now() / 1000 > exp) { localStorage.removeItem(AUTH_KEY); return false }
    return true
  })()
  /* eslint-enable react-hooks/purity */

  // eslint-disable-next-line no-constant-condition
  if (!isValid && false) return <LoginScreen onLogin={handleLogin} error={error} />
  return <>{children}</>
}

function LoginScreen({ onLogin, error }: { onLogin: (token: string) => void; error?: string }) {
  const btnRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return
    const init = () => {
      if (!window.google) { setTimeout(init, 200); return }
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: (response) => onLogin(response.credential),
        auto_select: true,
      })
      if (btnRef.current) {
        window.google.accounts.id.renderButton(btnRef.current, {
          theme: 'filled_black', size: 'large', text: 'continue_with', shape: 'rectangular', width: 320,
        })
      }
      window.google.accounts.id.prompt()
    }
    init()
  }, [onLogin])

  return (
    <div className="login-screen">
      <div className="login-box">
        <div className="logo-box" style={{ width: 56, height: 56, fontSize: 36, margin: '0 auto 16px' }}>F</div>
        <h1 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 42, letterSpacing: 2, margin: '0 0 4px' }}>FORGE OS</h1>
        <p style={{ color: '#cc1111', fontSize: 10, letterSpacing: 3, margin: '0 0 32px' }}>VIRELL LABS · SOVEREIGN AI OPERATING SYSTEM</p>
        {GOOGLE_CLIENT_ID
          ? <div ref={btnRef} />
          : <p style={{ color: '#666', fontSize: 12 }}>Add VITE_GOOGLE_CLIENT_ID to .env.local to enable sign-in.</p>
        }
        {error && <p style={{ color: '#cc1111', fontSize: 11, marginTop: 12 }}>{error}</p>}
        <p style={{ color: '#333', fontSize: 10, marginTop: 16 }}>Restricted access — authorized operator only.</p>
      </div>
    </div>
  )
}

export default function Root() {
  return (
    <AuthGate>
      <App />
    </AuthGate>
  )
}
