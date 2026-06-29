/**
 * Forge OS Background Scheduler
 *
 * Autonomous job runner that persists last-run state across restarts.
 * Jobs are fire-and-forget — failures are swallowed, never crash the server.
 * CRL learning informs which industries/segments get prioritised.
 *
 * Jobs:
 *   replySyncJob       — every 30 min: scan Gmail, classify replies, update CRL
 *   dailyBriefJob      — every 24hr: generate Jarvis daily brief + push urgent tasks
 *   leadBatchJob       — every 2hr: CRL-smart lead enrichment (rotates best industry)
 *   hookExperimentJob  — every 7d: run hook experiment for top priority industry
 *   meetingPrepJob     — every 6hr: detect upcoming meetings, push prep tasks to Jace
 *   jarvisProactiveJob — every 4hr: Jarvis checks pipeline state and self-assigns work
 *
 * Enable: NODE_ENV=production or ENABLE_SCHEDULER=true
 */

import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { env } from '../config/env.js'
import { writeAudit } from './auditLog.js'
import { emitEvent } from './eventBus.js'
import { pushHumanTask } from './jarvisHumanQueue.js'

// ── Scheduler State Persistence ───────────────────────────────────────────────

type JobState = {
  lastRunAt: string | null
  runCount: number
  errorCount: number
}

type SchedulerState = {
  jobs: Record<string, JobState>
  startedAt: string
}

const STATE_PATH = resolve(process.cwd(), 'data', 'scheduler-state.json')
let schedulerState: SchedulerState = { jobs: {}, startedAt: new Date().toISOString() }

async function loadSchedulerState(): Promise<void> {
  try {
    const raw = await readFile(STATE_PATH, 'utf8')
    const parsed = JSON.parse(raw) as Partial<SchedulerState>
    if (parsed.jobs && typeof parsed.jobs === 'object') {
      schedulerState.jobs = parsed.jobs
    }
  } catch { /* first run — no state file yet */ }
}

async function saveSchedulerState(): Promise<void> {
  try {
    await mkdir(resolve(process.cwd(), 'data'), { recursive: true })
    await writeFile(STATE_PATH, JSON.stringify(schedulerState, null, 2), 'utf8')
  } catch { /* non-fatal */ }
}

function getJobState(name: string): JobState {
  if (!schedulerState.jobs[name]) {
    schedulerState.jobs[name] = { lastRunAt: null, runCount: 0, errorCount: 0 }
  }
  return schedulerState.jobs[name]!
}

function shouldSkipDueToRecentRun(name: string, intervalMs: number): boolean {
  const state = getJobState(name)
  if (!state.lastRunAt) return false
  const elapsed = Date.now() - new Date(state.lastRunAt).getTime()
  // Skip if the job ran within 80% of its interval (prevents double-run on restart)
  return elapsed < intervalMs * 0.8
}

// ── Job Runner ────────────────────────────────────────────────────────────────

type Job = {
  name: string
  intervalMs: number
  run: () => Promise<void>
}

const jobs: Job[] = []
const timers: ReturnType<typeof setInterval>[] = []

async function safeRun(job: Job) {
  const jobState = getJobState(job.name)
  const start = Date.now()
  try {
    await job.run()
    jobState.lastRunAt = new Date().toISOString()
    jobState.runCount++
    await saveSchedulerState()
    emitEvent('scheduler_tick', { job: job.name, durationMs: Date.now() - start, runCount: jobState.runCount })
    writeAudit({
      actor: 'scheduler',
      action: 'job_run',
      purpose: job.name,
      result: 'ok',
      metadata: { durationMs: Date.now() - start, runCount: jobState.runCount },
    })
  } catch (error) {
    jobState.errorCount++
    await saveSchedulerState()
    const message = error instanceof Error ? error.message : String(error)
    writeAudit({
      actor: 'scheduler',
      action: 'job_error',
      purpose: job.name,
      result: 'error',
      metadata: { error: message, errorCount: jobState.errorCount },
    })
  }
}

// ── Job: Reply Sync ───────────────────────────────────────────────────────────

async function replySyncJob() {
  const { ReplySyncService } = await import('../services/replySync.service.js')
  const { recordOutcome } = await import('./crlLearning.js')

  const replySync = new ReplySyncService()
  const result = await replySync.syncRecentReplies(30)

  if (result.ok && Array.isArray(result.items)) {
    let positiveReplies = 0
    for (const item of result.items as Array<{ intent?: string; industry?: string }>) {
      const intent = item.intent
      if (intent === 'interested' || intent === 'meeting_intent') {
        void recordOutcome('outreach', 'reply_received', { channel: 'email', industry: item.industry })
        emitEvent('reply_received', { intent })
        positiveReplies++
      } else if (intent === 'unsubscribe') {
        void recordOutcome('outreach', 'unsubscribe', { channel: 'email' })
      } else if (intent === 'objection') {
        void recordOutcome('outreach', 'objection', { channel: 'email' })
      }
    }
    if (positiveReplies > 0) {
      emitEvent('pipeline_updated', { source: 'reply_sync', newReplies: positiveReplies })
    }
  }
}

// ── Job: Daily Brief ──────────────────────────────────────────────────────────

async function dailyBriefJob() {
  const { generateDailyBrief } = await import('../services/jarvisStrategy.service.js')
  const brief = await generateDailyBrief()

  emitEvent('brief_generated', {
    headline: brief.headline,
    status: brief.overallStatus,
    topPriorityForJace: brief.topPriorityForJace,
  })

  if (brief.overallStatus === 'critical' || brief.overallStatus === 'at_risk') {
    await pushHumanTask({
      title: `Urgent: ${brief.topPriorityForJace}`,
      description: `Daily brief status: ${brief.overallStatus.toUpperCase()}\n\n${brief.headline}\n\nJarvis is handling: ${brief.topPriorityForJarvis}`,
      category: 'feedback',
      priority: 1,
      createdBy: 'scheduler',
      payload: { briefStatus: brief.overallStatus, generatedAt: brief.generatedAt },
    })
  }
}

// ── Job: Lead Batch (CRL-smart) ───────────────────────────────────────────────

const TARGET_INDUSTRIES = [
  'HVAC', 'Real Estate Agents', 'Digital Marketing Agencies',
  'Interior Designers', 'Clinics', 'Med Spas',
  'Online Coaches', 'Consultants',
]

async function leadBatchJob() {
  const { OutreachService } = await import('../services/outreach.service.js')
  const { getLearningDigest } = await import('./crlLearning.js')

  const outreach = new OutreachService()

  // CRL-informed industry selection: pick the best performing industry, or rotate
  let targetIndustry = TARGET_INDUSTRIES[0]!
  try {
    const digest = await getLearningDigest()
    const topPatterns = (digest.topPatterns ?? []) as Array<{ key: string; avgReward: number; confidence: number }>

    // Find the highest-reward industry pattern from CRL data
    let bestReward = -Infinity
    for (const pattern of topPatterns) {
      const match = pattern.key.match(/^industry:(.+)$/)
      if (match?.[1] && TARGET_INDUSTRIES.includes(match[1]) && pattern.avgReward > bestReward && pattern.confidence > 0.1) {
        bestReward = pattern.avgReward
        targetIndustry = match[1]
      }
    }

    // If no CRL data yet, rotate by week
    if (bestReward === -Infinity) {
      const weekNum = Math.floor(Date.now() / (7 * 24 * 60 * 60 * 1000))
      targetIndustry = TARGET_INDUSTRIES[weekNum % TARGET_INDUSTRIES.length] ?? TARGET_INDUSTRIES[0]!
    }
  } catch { /* fallback to default */ }

  const apolloResult = await outreach.apolloSearch(targetIndustry, 5)
  const newLeads = Array.isArray(apolloResult.results) ? apolloResult.results.slice(0, 5) : []

  if (newLeads.length > 0) {
    await outreach.enrichAndDraft(newLeads)
    emitEvent('lead_enriched', { count: newLeads.length, source: 'apollo_scheduler', industry: targetIndustry })
    emitEvent('pipeline_updated', { source: 'lead_batch', newLeads: newLeads.length, industry: targetIndustry })
  }
}

// ── Job: Hook Experiment ──────────────────────────────────────────────────────

async function hookExperimentJob() {
  const { runHookExperiment } = await import('../services/jarvisStrategy.service.js')
  const { getLearningDigest } = await import('./crlLearning.js')

  // CRL-informed: pick lowest-confidence industry for the experiment (most to learn from)
  let targetIndustry = 'HVAC'
  try {
    const digest = await getLearningDigest()
    const topPatterns = (digest.topPatterns ?? []) as Array<{ key: string; avgReward: number; confidence: number }>
    const industryConfidences = new Map<string, number>()
    for (const p of topPatterns) {
      const match = p.key.match(/^industry:(.+)$/)
      if (match?.[1] && TARGET_INDUSTRIES.includes(match[1])) {
        industryConfidences.set(match[1], p.confidence)
      }
    }
    // Industries with no data or lowest confidence need experiments most
    let lowestConf = Infinity
    for (const ind of TARGET_INDUSTRIES) {
      const conf = industryConfidences.get(ind) ?? 0
      if (conf < lowestConf) { lowestConf = conf; targetIndustry = ind }
    }
  } catch { /* fallback */ }

  const platforms = ['tiktok', 'instagram_reels', 'linkedin'] as const
  const weekNum = Math.floor(Date.now() / (7 * 24 * 60 * 60 * 1000))
  const platform = platforms[weekNum % platforms.length] ?? 'tiktok'

  const experiment = await runHookExperiment({ niche: targetIndustry, platform, count: 5 })
  emitEvent('hook_experiment_complete', {
    niche: targetIndustry,
    platform,
    winner: experiment.winner,
    score: experiment.winnerScore,
  })
}

// ── Job: Meeting Prep ─────────────────────────────────────────────────────────

async function meetingPrepJob() {
  const { MeetingsService } = await import('../services/meetings.service.js')

  const meetings = new MeetingsService()
  const allMeetings = await meetings.listMeetings()

  // Find meetings in the next 24 hours that are confirmed
  const now = Date.now()
  const in24h = now + 24 * 60 * 60 * 1000

  const upcoming = (allMeetings as Array<{
    id: string; prospect_name?: string; company_name?: string;
    start_at?: string; meeting_type?: string; status?: string
  }>).filter((m) => {
    if (m.status === 'cancelled' || m.status === 'no_show') return false
    const startMs = m.start_at ? new Date(m.start_at).getTime() : 0
    return startMs > now && startMs < in24h
  })

  for (const meeting of upcoming) {
    const existingTasks = await import('./jarvisHumanQueue.js').then((m) => m.getHumanTasks('pending'))
    const alreadyQueued = existingTasks.some((t) => t.title.includes(meeting.prospect_name ?? '') && t.category === 'feedback')
    if (alreadyQueued) continue

    await pushHumanTask({
      title: `Prep for meeting: ${meeting.prospect_name ?? 'Prospect'} (${meeting.company_name ?? ''})`,
      description: `You have a ${meeting.meeting_type ?? 'call'} meeting scheduled within 24 hours.\n\nProspect: ${meeting.prospect_name}\nCompany: ${meeting.company_name}\nTime: ${meeting.start_at}\n\nJarvis will generate talking points. You need to: confirm the meeting, review the prospect's company, and have your offer ready.`,
      category: 'feedback',
      priority: 1,
      createdBy: 'scheduler',
      payload: { meetingId: meeting.id, startAt: meeting.start_at, prospectName: meeting.prospect_name },
    })

    emitEvent('meeting_booked', { prospectName: meeting.prospect_name, companyName: meeting.company_name, startAt: meeting.start_at })
  }
}

// ── Jobs: Instagram DM Windows ───────────────────────────────────────────────
// Three precise windows per the outreach strategy:
//   7–10pm IST → 10 DMs to US coaches/consultants
//   9am–1pm London → 8 DMs to UK HVAC firms
//   10am–12pm IST → 12 DMs to India digital marketing agencies

async function igCoachDmJob() {
  const { isOutreachWindowOpen } = await import('./timezoneWindows.js')
  if (!isOutreachWindowOpen('igCoachesIST')) return

  const { getTodayCounters, incrementCounter, queueAction } = await import('./socialQueue.js')
  const today = await getTodayCounters()
  if (today.igCoachDms >= 10) return  // daily cap hit

  const {
    generateInstagramDmBatch,
    buildInstagramDmTaskDescription,
    detectNiche,
    auditSocialBatch,
  } = await import('../services/socialOutreach.service.js')

  const niche = detectNiche('coaches')
  const needed = 10 - today.igCoachDms
  const messages = await generateInstagramDmBatch(niche, needed)

  const description = buildInstagramDmTaskDescription(niche, 'US', needed, '7–10pm IST', messages)

  for (const m of messages) {
    await queueAction({
      platform: 'instagram',
      niche: 'coaches',
      region: 'US_Eastern',
      targetName: m.targetName,
      targetHandle: m.targetHandle,
      message: m.message,
      status: 'queued',
      scheduledFor: '19:00–22:00 IST',
    })
  }

  await incrementCounter('igCoachDms', needed)
  auditSocialBatch('instagram', niche, needed, '7–10pm IST coaches')
  emitEvent('pipeline_updated', { source: 'ig_coach_dm', niche: 'coaches', count: needed })

  await pushHumanTask({
    title: `[7–10pm IST] Send ${needed} Instagram DMs to US coaches NOW`,
    description,
    category: 'outreach_manual',
    priority: 1,
    createdBy: 'scheduler_ig_coach',
    payload: { niche: 'coaches', region: 'US', count: needed, window: '7–10pm IST' },
  })
}

async function igHvacLondonJob() {
  const { isOutreachWindowOpen } = await import('./timezoneWindows.js')
  if (!isOutreachWindowOpen('igHvacLondon')) return

  const { getTodayCounters, incrementCounter, queueAction } = await import('./socialQueue.js')
  const today = await getTodayCounters()
  if (today.igHvacDms >= 8) return

  const {
    generateInstagramDmBatch,
    buildInstagramDmTaskDescription,
    detectNiche,
    auditSocialBatch,
  } = await import('../services/socialOutreach.service.js')

  const niche = detectNiche('hvac')
  const needed = 8 - today.igHvacDms
  const messages = await generateInstagramDmBatch(niche, needed)

  const description = buildInstagramDmTaskDescription(niche, 'UK / London', needed, '9am–1pm London', messages)

  for (const m of messages) {
    await queueAction({
      platform: 'instagram',
      niche: 'hvac',
      region: 'London',
      targetName: m.targetName,
      message: m.message,
      status: 'queued',
      scheduledFor: '09:00–13:00 London',
    })
  }

  await incrementCounter('igHvacDms', needed)
  auditSocialBatch('instagram', niche, needed, '9am–1pm London HVAC')
  emitEvent('pipeline_updated', { source: 'ig_hvac_london', niche: 'hvac', count: needed })

  await pushHumanTask({
    title: `[London Morning] Send ${needed} Instagram DMs to UK HVAC firms NOW`,
    description,
    category: 'outreach_manual',
    priority: 1,
    createdBy: 'scheduler_ig_hvac',
    payload: { niche: 'hvac', region: 'UK', count: needed, window: '9am–1pm London' },
  })
}

async function igAgencyIndiaJob() {
  const { isOutreachWindowOpen } = await import('./timezoneWindows.js')
  if (!isOutreachWindowOpen('igAgencyIndia')) return

  const { getTodayCounters, incrementCounter, queueAction } = await import('./socialQueue.js')
  const today = await getTodayCounters()
  if (today.igAgencyDms >= 12) return

  const {
    generateInstagramDmBatch,
    buildInstagramDmTaskDescription,
    detectNiche,
    auditSocialBatch,
  } = await import('../services/socialOutreach.service.js')

  const niche = detectNiche('digital marketing agency')
  const needed = 12 - today.igAgencyDms
  const messages = await generateInstagramDmBatch(niche, needed)

  const description = buildInstagramDmTaskDescription(niche, 'India', needed, '10am–12pm IST', messages)

  for (const m of messages) {
    await queueAction({
      platform: 'instagram',
      niche: 'digital_marketing_agency',
      region: 'IST',
      targetName: m.targetName,
      message: m.message,
      status: 'queued',
      scheduledFor: '10:00–12:00 IST',
    })
  }

  await incrementCounter('igAgencyDms', needed)
  auditSocialBatch('instagram', niche, needed, '10am IST India agencies')
  emitEvent('pipeline_updated', { source: 'ig_agency_india', niche: 'digital_marketing_agency', count: needed })

  await pushHumanTask({
    title: `[10am IST] Send ${needed} Instagram DMs to India digital marketing agencies NOW`,
    description,
    category: 'outreach_manual',
    priority: 1,
    createdBy: 'scheduler_ig_agency',
    payload: { niche: 'digital_marketing_agency', region: 'India', count: needed, window: '10am–12pm IST' },
  })
}

// ── Job: Facebook Group Posts ─────────────────────────────────────────────────
// Runs hourly. Checks which groups are at their optimal post time and
// generates a task with the exact posts to publish in each group.

async function fbGroupPostJob() {
  const { getGroupsDueForPosting, markGroupPosted } = await import('../services/facebookGroups.service.js')
  const { generateGroupPostPair, detectNiche, buildFacebookGroupPostTaskDescription } = await import('../services/socialOutreach.service.js')
  const { incrementCounter, queueAction } = await import('./socialQueue.js')

  const dueGroups = await getGroupsDueForPosting()
  if (dueGroups.length === 0) return

  // Generate content for each unique niche represented
  const niches = [...new Set(dueGroups.map((g) => g.niche))]
  const contentByNiche = new Map<string, { primary: string; alternate: string }>()
  for (const niche of niches) {
    contentByNiche.set(niche, await generateGroupPostPair(detectNiche(niche)))
  }

  const groupsWithTime = dueGroups.map((g) => ({
    name: g.name,
    country: g.country,
    postTime: `${new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })} ${g.region}`,
  }))

  const firstNicheContent = contentByNiche.values().next().value ?? { primary: '', alternate: '' }
  const description = buildFacebookGroupPostTaskDescription(groupsWithTime, firstNicheContent.primary, firstNicheContent.alternate)

  for (const group of dueGroups) {
    const content = contentByNiche.get(group.niche) ?? firstNicheContent
    await queueAction({
      platform: 'facebook_group',
      niche: group.niche,
      region: group.region,
      groupId: group.id,
      groupName: group.name,
      message: content.primary,
      status: 'queued',
      scheduledFor: `optimal:${group.region}`,
    })
    await markGroupPosted(group.id)
  }

  await incrementCounter('fbGroupPosts', dueGroups.length)
  emitEvent('pipeline_updated', { source: 'fb_group_posts', count: dueGroups.length })

  await pushHumanTask({
    title: `[Facebook Groups] Post in ${dueGroups.length} group(s) NOW — optimal time for their timezone`,
    description,
    category: 'outreach_manual',
    priority: 2,
    createdBy: 'scheduler_fb_groups',
    payload: { groupCount: dueGroups.length, groups: dueGroups.map((g) => g.name) },
  })
}

// ── Job: Facebook Comments ────────────────────────────────────────────────────
// Three sessions: morning (10/session), afternoon (10/session), evening (10/session) = 30/day

async function fbCommentJob() {
  const { isOutreachWindowOpen } = await import('./timezoneWindows.js')
  const inMorning = isOutreachWindowOpen('fbCommentMorning')
  const inAfternoon = isOutreachWindowOpen('fbCommentAfternoon')
  const inEvening = isOutreachWindowOpen('fbCommentEvening')
  if (!inMorning && !inAfternoon && !inEvening) return

  const { getTodayCounters, incrementCounter, queueAction } = await import('./socialQueue.js')
  const today = await getTodayCounters()
  if (today.fbComments >= 30) return  // daily cap

  const { generateCommentBatch, detectNiche, buildFacebookCommentTaskDescription } = await import('../services/socialOutreach.service.js')

  const sessionCount = 10
  const niche = detectNiche('digital_marketing_agency')  // rotate niche by session
  const comments = await generateCommentBatch(niche, sessionCount)

  await queueAction({
    platform: 'facebook_comment',
    niche: 'general',
    region: 'IST',
    message: comments.join('\n---\n'),
    status: 'queued',
    scheduledFor: inMorning ? 'morning' : inAfternoon ? 'afternoon' : 'evening',
  })

  await incrementCounter('fbComments', sessionCount)

  const windowLabel = inMorning ? 'Morning (10/30)' : inAfternoon ? 'Afternoon (20/30)' : 'Evening (30/30)'
  await pushHumanTask({
    title: `[Facebook Comments] ${windowLabel} — comment on 10 posts now`,
    description: buildFacebookCommentTaskDescription(niche, sessionCount, comments),
    category: 'outreach_manual',
    priority: 2,
    createdBy: 'scheduler_fb_comments',
    payload: { count: sessionCount, window: windowLabel },
  })
}

// ── Job: Facebook DMs + Friend Requests ──────────────────────────────────────
// 4 DMs per day, 1 per session at DM1/2/3/4 windows. Each with a friend request.

async function fbDmJob() {
  const { isOutreachWindowOpen } = await import('./timezoneWindows.js')
  const inAnyWindow = (
    isOutreachWindowOpen('fbDm1') || isOutreachWindowOpen('fbDm2') ||
    isOutreachWindowOpen('fbDm3') || isOutreachWindowOpen('fbDm4')
  )
  if (!inAnyWindow) return

  const { getTodayCounters, incrementCounter, queueAction } = await import('./socialQueue.js')
  const today = await getTodayCounters()
  if (today.fbDms >= 4) return  // daily cap: 4 DMs

  const {
    generateFacebookDm,
    generateFriendRequestMessage,
    detectNiche,
    buildFacebookDmTaskDescription,
  } = await import('../services/socialOutreach.service.js')

  // Rotate niche by DM count
  const nicheRotation = ['coaches', 'consultants', 'digital_marketing_agency', 'hvac'] as const
  const nicheKey = nicheRotation[today.fbDms % 4] ?? 'coaches'
  const niche = detectNiche(nicheKey)

  const [dmMsg, friendMsg] = await Promise.all([
    generateFacebookDm(niche),
    generateFriendRequestMessage(niche),
  ])

  await queueAction({
    platform: 'facebook_dm',
    niche: nicheKey,
    region: 'IST',
    message: dmMsg,
    status: 'queued',
    scheduledFor: `fbDm${today.fbDms + 1}`,
  })
  await queueAction({
    platform: 'facebook_friend',
    niche: nicheKey,
    region: 'IST',
    message: friendMsg,
    status: 'queued',
    scheduledFor: `fbDm${today.fbDms + 1}`,
  })

  await incrementCounter('fbDms', 1)
  await incrementCounter('fbFriendRequests', 1)

  await pushHumanTask({
    title: `[Facebook DM #${today.fbDms + 1}] Send 1 DM + friend request to a ${nicheKey} owner`,
    description: buildFacebookDmTaskDescription(niche, dmMsg, friendMsg),
    category: 'outreach_manual',
    priority: 2,
    createdBy: 'scheduler_fb_dm',
    payload: { niche: nicheKey, dmNumber: today.fbDms + 1 },
  })
}

// ── Job: Evening Coach DM Window (legacy — now handled by igCoachDmJob) ───────
// Kept as a narrower evening-only fallback for the old 7-10pm IST timing.

async function eveningCoachDmJob() {
  const nowUtc = new Date()
  const hourUtc = nowUtc.getUTCHours()

  // 6pm–10pm US Eastern = 22:00–02:00 UTC (EST) or 23:00–03:00 UTC (EDT)
  // We use 22–03 UTC as the window to catch both EST and EDT
  const inWindow = hourUtc >= 22 || hourUtc < 3

  if (!inWindow) return

  const existingTasks = await (await import('./jarvisHumanQueue.js')).getHumanTasks('pending')
  const alreadySentToday = existingTasks.some((t) =>
    t.title.includes('Coach DM') &&
    t.createdAt.startsWith(new Date().toISOString().slice(0, 10)),
  )

  if (alreadySentToday) return

  // Get the winning DM opener from CRL if available
  const { getBestApproach } = await import('./crlLearning.js')
  const dmRec = await getBestApproach({ industry: 'Online Coaches', channel: 'instagram' }, ['pain-first', 'result-first', 'signal-first'], 'hookStyle').catch(() => ({ best: null, confidence: 0, reason: '' }))
  const winnerStyle = dmRec.best ?? 'pain-first'

  await pushHumanTask({
    title: `[Coach DM Window] Send 20 Instagram DMs to coaches NOW — it\'s 7–10pm for them`,
    description: `This is the highest-converting window for coaches and consultants on Instagram.\n\nTarget: Business coaches, life coaches, sales coaches with 1k–50k followers.\nOpener style: ${winnerStyle} (CRL confidence: ${(dmRec.confidence * 100).toFixed(0)}%)\n\nPain-first opener to use:\n"Hey [name] — I've been following your content. Most coaches in your position are getting engagement but the DMs never convert to calls. We automated that exact handoff for 3 coaches last month. Mind if I show you how it works in 2 mins?"\n\nGoal: 20 DMs tonight. Report back how many responded so Jarvis can learn.`,
    category: 'outreach_manual',
    priority: 1,
    createdBy: 'scheduler_evening_coach_dm',
    payload: {
      niche: 'Online Coaches',
      channel: 'instagram',
      recommendedStyle: winnerStyle,
      crlConfidence: dmRec.confidence,
      window: '7–10pm US Eastern',
    },
  })

  emitEvent('pipeline_updated', { source: 'evening_coach_dm_window', niche: 'Online Coaches', channel: 'instagram' })
}

// ── Job: Jarvis Proactive Loop ────────────────────────────────────────────────
// Every 4 hours, Jarvis autonomously checks state and self-assigns work.
// This is the "thinking without being asked" engine.

async function jarvisProactiveJob() {
  const { getHumanTasks, getHumanQueueSummary } = await import('./jarvisHumanQueue.js')
  const { ProductionDataService } = await import('../services/productionData.service.js')

  const productionData = new ProductionDataService()
  const [overview, summary, pendingTasks] = await Promise.all([
    productionData.analyticsOverview(),
    getHumanQueueSummary(),
    getHumanTasks('pending'),
  ])

  const m = overview.metrics

  // Rule 1: If no emails sent in 24h and no pending critical tasks — push a task
  const criticalTaskExists = pendingTasks.some((t) => t.priority === 1 && t.category === 'outreach_manual')
  if (m.emailsSent < 5 && !criticalTaskExists) {
    await pushHumanTask({
      title: 'Cold outreach pipeline is dry — send emails NOW',
      description: `JARVIS PROACTIVE ALERT: Only ${m.emailsSent} emails have been sent. The pipeline will stall without outreach volume.\n\nJarvis has enriched leads. Your job: go to Outreach → Batch Send and send at least 30 emails today.\n\nEvery day without outreach = 0 revenue progress.`,
      category: 'outreach_manual',
      priority: 1,
      createdBy: 'jarvis_proactive',
      payload: { emailsSent: m.emailsSent, trigger: 'low_volume' },
    })
    emitEvent('pipeline_updated', { source: 'jarvis_proactive', alert: 'low_email_volume' })
  }

  // Rule 2: If reply rate is > 10% — scale volume, push task to Jace
  if (m.replyRate > 10 && m.emailsSent > 20) {
    const scaleTaskExists = pendingTasks.some((t) => t.title.includes('scale') || t.title.includes('volume'))
    if (!scaleTaskExists) {
      await pushHumanTask({
        title: `Reply rate ${m.replyRate.toFixed(1)}% — SCALE NOW. Double daily send volume.`,
        description: `Your reply rate is ${m.replyRate.toFixed(1)}% — above the 10% benchmark. This is the moment to pour fuel on the fire.\n\nJarvis is enriching 2x more leads per batch. You need to: increase daily sends from ~${Math.round(m.emailsSent)} to ${Math.round(m.emailsSent * 2)} this week.\n\nWhen you have strong reply rates, scale fast before algo changes or list fatigue sets in.`,
        category: 'strategy_approval',
        priority: 1,
        createdBy: 'jarvis_proactive',
        payload: { replyRate: m.replyRate, currentSent: m.emailsSent, trigger: 'high_reply_rate' },
      })
    }
  }

  // Rule 3: If meetings booked — push a follow-up / close task
  if (m.meetingsBooked > 0) {
    const followUpExists = pendingTasks.some((t) => t.title.includes('close') || t.title.includes('follow'))
    if (!followUpExists) {
      await pushHumanTask({
        title: `${m.meetingsBooked} meeting(s) booked — prep your close and send contract`,
        description: `You have ${m.meetingsBooked} meetings. Jarvis has no access to close the deal — that's you.\n\nBefore each meeting:\n1. Review the prospect's company website\n2. Prepare the pain point story\n3. Have a price anchor ready ($2k/mo–$5k/mo)\n4. Send a contract within 2 hours of the meeting if they say yes`,
        category: 'outreach_manual',
        priority: 1,
        createdBy: 'jarvis_proactive',
        payload: { meetingsBooked: m.meetingsBooked, trigger: 'meetings_pending_close' },
      })
    }
  }

  // Summary event — tells the dashboard Jarvis just checked in
  emitEvent('pipeline_updated', {
    source: 'jarvis_proactive',
    pendingTasks: summary.pendingTasks,
    criticalTasks: summary.criticalTasks,
    checkedAt: new Date().toISOString(),
  })
}

// ── Scheduler Lifecycle ───────────────────────────────────────────────────────

export async function initScheduler() {
  const shouldRun = env.NODE_ENV === 'production' || env.ENABLE_SCHEDULER === true
  if (!shouldRun) return

  // Load persisted state before scheduling so we know when each job last ran
  await loadSchedulerState()
  schedulerState.startedAt = new Date().toISOString()

  jobs.push(
    { name: 'reply_sync',       intervalMs: 30 * 60 * 1000,           run: replySyncJob },
    { name: 'daily_brief',      intervalMs: 24 * 60 * 60 * 1000,      run: dailyBriefJob },
    { name: 'lead_batch',       intervalMs: 2 * 60 * 60 * 1000,       run: leadBatchJob },
    { name: 'hook_experiment',  intervalMs: 7 * 24 * 60 * 60 * 1000,  run: hookExperimentJob },
    { name: 'meeting_prep',        intervalMs: 6 * 60 * 60 * 1000,    run: meetingPrepJob },
    { name: 'jarvis_proactive',    intervalMs: 4 * 60 * 60 * 1000,    run: jarvisProactiveJob },
    { name: 'evening_coach_dm',    intervalMs: 1 * 60 * 60 * 1000,    run: eveningCoachDmJob },
    // ── Social outreach windows (run every 30min — window checks are internal) ──
    { name: 'ig_coach_dm',         intervalMs: 30 * 60 * 1000,        run: igCoachDmJob },
    { name: 'ig_hvac_london',      intervalMs: 30 * 60 * 1000,        run: igHvacLondonJob },
    { name: 'ig_agency_india',     intervalMs: 30 * 60 * 1000,        run: igAgencyIndiaJob },
    { name: 'fb_group_posts',      intervalMs: 60 * 60 * 1000,        run: fbGroupPostJob },
    { name: 'fb_comments',         intervalMs: 2 * 60 * 60 * 1000,    run: fbCommentJob },
    { name: 'fb_dms',              intervalMs: 4 * 60 * 60 * 1000,    run: fbDmJob },
  )

  for (const job of jobs) {
    // If the job ran recently (within 80% of its interval), skip the startup run
    const skipStartup = shouldSkipDueToRecentRun(job.name, job.intervalMs)

    if (!skipStartup) {
      // Stagger startup: 5–45 seconds to avoid thundering herd
      const startDelay = 5000 + Math.random() * 40000
      setTimeout(() => void safeRun(job), startDelay)
    }

    // Always register the interval for future runs
    timers.push(setInterval(() => void safeRun(job), job.intervalMs))
  }

  writeAudit({
    actor: 'scheduler',
    action: 'init',
    purpose: 'background_jobs_started',
    result: 'ok',
    metadata: { jobs: jobs.map((j) => j.name), env: env.NODE_ENV, persistedState: Object.keys(schedulerState.jobs) },
  })
}

export function stopScheduler() {
  for (const timer of timers) clearInterval(timer)
  timers.length = 0
}

export function getSchedulerStatus() {
  return jobs.map(({ name, intervalMs }) => {
    const state = getJobState(name)
    return {
      name,
      intervalMs,
      lastRunAt: state.lastRunAt,
      runCount: state.runCount,
      errorCount: state.errorCount,
      nextRunIn: state.lastRunAt
        ? Math.max(0, intervalMs - (Date.now() - new Date(state.lastRunAt).getTime()))
        : null,
    }
  })
}
