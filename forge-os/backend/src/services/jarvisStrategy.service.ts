/**
 * Jarvis Strategy Engine — Autonomous Planning & Experimentation
 *
 * This is the proactive brain of Jarvis. It does not wait to be asked.
 * It analyzes the full system state, generates strategies, runs A/B experiments
 * on hooks and DM techniques, identifies platform gaps, and allocates work between
 * itself and Jace. When something requires human action, it pushes to the human queue.
 *
 * L99 principle applied: contradiction-aware — every strategy must survive both
 * "what if the reply rate is 0?" and "what if Jace has no time today?"
 */

import { randomUUID } from 'node:crypto'
import { geminiApiKeyFor } from '../config/env.js'
import { callGeminiSimple } from '../lib/gemini.js'
import { writeAudit } from '../lib/auditLog.js'
import { getBestApproach, getLearningDigest, recordOutcome } from '../lib/crlLearning.js'
import {
  type HumanTask,
  type StrategyExperiment,
  getExperiments,
  getHumanTasks,
  pushHumanTask,
  saveExperiment,
} from '../lib/jarvisHumanQueue.js'
import { ProductionDataService } from './productionData.service.js'
import { CMOService } from './cmo.service.js'

const productionData = new ProductionDataService()
const cmo = new CMOService()

const COMPANY = 'Virel Automation'
const OFFER = 'AI lead generation and outreach automation'
const TARGET_INDUSTRIES = ['HVAC', 'Real Estate Agents', 'Digital Marketing Agencies', 'Interior Designers', 'Clinics', 'Med Spas', 'Online Coaches', 'Consultants']
const TARGET_CHANNELS = ['email', 'linkedin', 'instagram', 'tiktok', 'youtube_shorts', 'sms', 'x']

// Coach/consultant niches are best reached via Instagram DMs at 7–10pm their time.
// This is the highest-engagement window for personal-brand creators.
const EVENING_DM_NICHES = ['Online Coaches', 'Consultants']
const TARGET_PLATFORMS = ['apollo', 'apify', 'gmail', 'gemini', 'supabase', 'google_calendar', 'heygen', 'elevenlabs']

type DailyBriefSection = {
  title: string
  content: string
  urgency: 'critical' | 'high' | 'medium' | 'low'
  actionsForJarvis: string[]
  actionsForJace: string[]
}

export type DailyBrief = {
  id: string
  date: string
  headline: string
  overallStatus: 'on_track' | 'at_risk' | 'critical' | 'accelerating'
  sections: DailyBriefSection[]
  topPriorityForJace: string
  topPriorityForJarvis: string
  generatedAt: string
}

export type PlatformGap = {
  platform: string
  category: 'social_media' | 'outreach_tool' | 'content_creation' | 'analytics' | 'automation'
  reason: string
  estimatedImpact: 'high' | 'medium' | 'low'
  actionRequired: string
  costEstimate: string
  priority: 1 | 2 | 3
}

export type WeeklyPlan = {
  weekOf: string
  jarvisOwns: Array<{ day: string; tasks: string[] }>
  jaceOwns: Array<{ day: string; tasks: string[] }>
  experiments: Array<{ type: string; niche: string; platform: string; goal: string }>
  targets: { emailsToSend: number; leadsToEnrich: number; hooksToTest: number }
  generatedAt: string
}

// ── Utility ───────────────────────────────────────────────────────────────────

function stripJsonFence(text: string): string {
  const trimmed = text.trim()
  if (!trimmed.startsWith('```')) return trimmed
  const inner = trimmed.split('```')[1] ?? trimmed
  return inner.startsWith('json') ? inner.slice(4).trim() : inner.trim()
}

async function gemini(prompt: string, maxTokens = 1200, json = false): Promise<string> {
  const key = geminiApiKeyFor('jarvis')
  if (!key) return ''
  try {
    return await callGeminiSimple('jarvis', prompt, {
      temperature: 0.4,
      maxOutputTokens: maxTokens,
      ...(json ? { jsonMode: true } : {}),
    }) ?? ''
  } catch {
    return ''
  }
}

// ── Daily Brief ───────────────────────────────────────────────────────────────

export async function generateDailyBrief(): Promise<DailyBrief> {
  const [overview, learning, pendingTasks] = await Promise.all([
    productionData.analyticsOverview(),
    getLearningDigest(),
    getHumanTasks('pending'),
  ])

  const m = overview.metrics
  const id = `brief_${Date.now()}`
  const date = new Date().toLocaleDateString('en-AU', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })

  const fallback: DailyBrief = {
    id,
    date,
    headline: `Pipeline: ${m.emailsSent} sent, ${m.replies} replies (${m.replyRate.toFixed(1)}% rate), ${m.meetingsBooked} meetings. ${m.replyRate < 8 ? 'Reply rate needs work.' : 'Solid reply rate — scale volume.'}`,
    overallStatus: m.emailsSent === 0 ? 'critical' : m.replyRate < 5 ? 'at_risk' : m.replyRate < 12 ? 'on_track' : 'accelerating',
    sections: [
      {
        title: 'Outreach Pipeline',
        content: `${m.emailsSent} sent, ${m.replies} replies, ${m.meetingsBooked} meetings booked. Reply rate: ${m.replyRate.toFixed(1)}%.`,
        urgency: m.emailsSent < 10 ? 'critical' : m.replyRate < 8 ? 'high' : 'medium',
        actionsForJarvis: ['Enrich next batch of leads', 'Generate 5 smart personalized drafts'],
        actionsForJace: m.emailsSent < 20 ? ['Send at least 20 cold emails today'] : ['Review and approve pending drafts'],
      },
      {
        title: 'CRL Learning State',
        content: `${learning.totalEvents} outcomes tracked. Recent avg reward: ${learning.recentAvgReward}. Top patterns: ${learning.topPatterns.slice(0, 2).map((p: { key: string }) => p.key).join(', ') || 'insufficient data yet'}.`,
        urgency: learning.totalEvents < 5 ? 'high' : 'low',
        actionsForJarvis: ['Continue recording all email/reply outcomes to build pattern library'],
        actionsForJace: ['Respond to all pending inbox messages so CRL can classify intent'],
      },
      {
        title: 'Pending Human Tasks',
        content: `${pendingTasks.length} tasks queued for Jace. ${pendingTasks.filter((t) => t.priority === 1).length} are critical.`,
        urgency: pendingTasks.some((t) => t.priority === 1) ? 'critical' : pendingTasks.length > 3 ? 'high' : 'medium',
        actionsForJarvis: [],
        actionsForJace: pendingTasks.slice(0, 3).map((t) => t.title),
      },
    ],
    topPriorityForJace: m.emailsSent < 20 ? 'Send cold emails — pipeline is dry' : pendingTasks[0]?.title ?? 'Review Jarvis task queue',
    topPriorityForJarvis: 'Enrich leads and generate personalized drafts for Jace to send',
    generatedAt: new Date().toISOString(),
  }

  if (!geminiApiKeyFor('jarvis')) return fallback

  const prompt = `You are JARVIS generating a daily ops brief for Jace, 19yo founder of ${COMPANY}.
Company: ${COMPANY} | Offer: ${OFFER}
Target: $15M MRR in 7 months. Current MRR: $0.

LIVE METRICS:
- Leads: ${m.totalLeads} | Drafts: ${m.totalDrafts} | Sent: ${m.emailsSent} | Replies: ${m.replies} | Meetings: ${m.meetingsBooked} | Reply Rate: ${m.replyRate.toFixed(1)}%

CRL LEARNING:
- Total outcomes: ${learning.totalEvents} | Recent avg reward: ${learning.recentAvgReward}
- Top patterns: ${JSON.stringify(learning.topPatterns.slice(0, 3))}
- Worst patterns: ${JSON.stringify(learning.worstPatterns.slice(0, 2))}

PENDING JACE TASKS: ${pendingTasks.length} total, ${pendingTasks.filter((t) => t.priority === 1).length} critical
${pendingTasks.slice(0, 5).map((t) => `- [P${t.priority}] ${t.title}`).join('\n')}

Generate a direct, tactical daily brief. No fluff. Think like a senior ops director.
Return strict JSON:
{
  "headline": "one sentence status line",
  "overallStatus": "on_track|at_risk|critical|accelerating",
  "sections": [
    {
      "title": "section name",
      "content": "2-3 sentence assessment",
      "urgency": "critical|high|medium|low",
      "actionsForJarvis": ["action1", "action2"],
      "actionsForJace": ["action1", "action2"]
    }
  ],
  "topPriorityForJace": "single most important thing Jace must do today",
  "topPriorityForJarvis": "single most important thing Jarvis will execute autonomously today"
}`

  try {
    const text = await gemini(prompt, 1500, true)
    if (!text) return fallback
    const parsed = JSON.parse(stripJsonFence(text)) as Partial<DailyBrief>
    return {
      id,
      date,
      headline: parsed.headline ?? fallback.headline,
      overallStatus: parsed.overallStatus ?? fallback.overallStatus,
      sections: parsed.sections ?? fallback.sections,
      topPriorityForJace: parsed.topPriorityForJace ?? fallback.topPriorityForJace,
      topPriorityForJarvis: parsed.topPriorityForJarvis ?? fallback.topPriorityForJarvis,
      generatedAt: new Date().toISOString(),
    }
  } catch {
    return fallback
  }
}

// ── Hook Experiment ───────────────────────────────────────────────────────────

export async function runHookExperiment(config: {
  niche: string
  platform: 'tiktok' | 'instagram_reels' | 'youtube_shorts' | 'linkedin' | 'twitter'
  count?: number
}): Promise<StrategyExperiment> {
  const count = Math.min(config.count ?? 5, 8)
  const expId = `exp_hook_${randomUUID().slice(0, 8)}`

  const experiment: StrategyExperiment = {
    id: expId,
    type: 'hook',
    niche: config.niche,
    platform: config.platform,
    status: 'running',
    variants: [],
    winner: null,
    winnerScore: 0,
    insight: '',
    createdAt: new Date().toISOString(),
  }
  await saveExperiment(experiment)

  // Generate hook variants using Gemini
  const hookGenPrompt = `Generate ${count} viral hook variants for ${COMPANY} targeting ${config.niche} business owners on ${config.platform.replace('_', ' ')}.
Offer: ${OFFER}.
Each hook must be under 15 words. Target: business owners who are losing leads due to slow follow-up.
Return strict JSON array of strings: ["hook1", "hook2", "hook3"]`

  let hooks: string[] = []
  try {
    const text = await gemini(hookGenPrompt, 600, true)
    if (text) {
      const parsed = JSON.parse(stripJsonFence(text))
      hooks = Array.isArray(parsed) ? parsed.slice(0, count).map(String) : []
    }
  } catch { /* use fallback hooks */ }

  if (hooks.length < 3) {
    hooks = [
      `How ${config.niche} owners are losing 40% of their leads (and don't know it)`,
      `I built an AI that books calls for ${config.niche} companies while they sleep`,
      `The 3-minute follow-up system that doubled our ${config.niche} client's revenue`,
      `Why your ${config.niche} leads go cold (and the fix takes 10 minutes)`,
      `This one change in follow-up speed is getting ${config.niche} owners 3x more meetings`,
    ].slice(0, count)
  }

  // Score each hook using CMO's hook scorer
  const scored = await Promise.all(hooks.map(async (hook) => {
    try {
      const scoreResult = await cmo.scoreHook(hook, config.platform)
      const score = (scoreResult as { score?: { viralityScore?: number; overallScore?: number } }).score?.viralityScore
        ?? (scoreResult as { score?: { viralityScore?: number; overallScore?: number } }).score?.overallScore
        ?? 50
      const viralityScore = (scoreResult as { score?: { viralityScore?: number } }).score?.viralityScore
      const clarity = (scoreResult as { score?: { clarity?: number } }).score?.clarity
      const hookStrength = (scoreResult as { score?: { hookStrength?: number } }).score?.hookStrength

      // Record in CRL
      void recordOutcome('noah', score >= 70 ? 'hook_scored_high' : 'hook_scored_low', {
        niche: config.niche,
        platform: config.platform,
      })

      return { text: hook, score, viralityScore, clarity, hookStrength }
    } catch {
      return { text: hook, score: 50 }
    }
  }))

  const sorted = scored.sort((a, b) => b.score - a.score)
  const winner = sorted[0]

  experiment.variants = sorted
  experiment.winner = winner.text
  experiment.winnerScore = winner.score
  experiment.status = 'complete'
  experiment.completedAt = new Date().toISOString()

  // Generate insight
  const topScore = winner.score
  const bottomScore = sorted[sorted.length - 1]?.score ?? 0
  experiment.insight = `Winner scored ${topScore} vs worst ${bottomScore} (spread: ${topScore - bottomScore}). ${topScore >= 75 ? 'Strong hook — deploy immediately.' : topScore >= 60 ? 'Decent hook — refine the angle.' : 'Low scores across the board — niche or platform angle needs rethink.'}`

  await saveExperiment(experiment)

  // Push winning hook as human task to use
  if (winner.score >= 60) {
    await pushHumanTask({
      title: `Use this winning hook in your next ${config.platform} post`,
      description: `Jarvis ran a ${count}-variant hook experiment for ${config.niche} on ${config.platform}. Winner scored ${winner.score}/100:\n\n"${winner.text}"\n\n${experiment.insight}`,
      category: 'content_record',
      priority: 2,
      createdBy: 'strategy_engine',
      payload: { hook: winner.text, score: winner.score, platform: config.platform, niche: config.niche },
    })
  }

  writeAudit({
    actor: 'jarvis',
    action: 'hook_experiment',
    purpose: `${config.niche}:${config.platform}`,
    result: 'ok',
    metadata: { winner: winner.text, score: winner.score, variants: sorted.length },
  })

  return experiment
}

// ── DM Experiment ─────────────────────────────────────────────────────────────

export async function runDmExperiment(config: {
  industry: string
  channel: 'linkedin' | 'instagram' | 'sms' | 'x'
  hookStyles?: Array<'pain-first' | 'result-first' | 'signal-first'>
}): Promise<StrategyExperiment> {
  const styles = config.hookStyles ?? ['pain-first', 'result-first', 'signal-first']
  const expId = `exp_dm_${randomUUID().slice(0, 8)}`

  const experiment: StrategyExperiment = {
    id: expId,
    type: 'dm',
    niche: config.industry,
    platform: config.channel,
    status: 'running',
    variants: [],
    winner: null,
    winnerScore: 0,
    insight: '',
    createdAt: new Date().toISOString(),
  }
  await saveExperiment(experiment)

  // Generate DM variants using CMO research + Gemini scoring
  const prompt = `You are a DM conversion expert. Score these ${config.channel} DM hook styles for ${config.industry} business owners.
For each style, write a 2-sentence opener and score it 0-100 for likely positive response.

Styles to test: ${styles.join(', ')}
Company: ${COMPANY} | Offer: ${OFFER}
Target: ${config.industry} owner who loses leads due to slow follow-up

Return strict JSON:
[
  { "style": "pain-first", "opener": "...", "score": 75, "reasoning": "..." },
  { "style": "result-first", "opener": "...", "score": 68, "reasoning": "..." },
  { "style": "signal-first", "opener": "...", "score": 81, "reasoning": "..." }
]`

  let variants = experiment.variants

  try {
    const text = await gemini(prompt, 900, true)
    if (text) {
      const parsed = JSON.parse(stripJsonFence(text)) as Array<{ style: string; opener: string; score: number; reasoning?: string }>
      variants = parsed.map((p) => ({
        text: `[${p.style}] ${p.opener}`,
        score: p.score,
        hookStrength: p.score,
      }))

      // Record in CRL
      for (const v of variants) {
        void recordOutcome('outreach', v.score >= 70 ? 'hook_scored_high' : 'hook_scored_low', {
          channel: config.channel,
          industry: config.industry,
          hookStyle: v.text.split(']')[0]?.replace('[', '').trim(),
        })
      }
    }
  } catch { /* use empty variants */ }

  if (variants.length === 0) {
    variants = styles.map((style) => ({
      text: `[${style}] Jarvis generated DM variant (Gemini offline — add key to score)`,
      score: 50,
    }))
  }

  const sorted = variants.sort((a, b) => b.score - a.score)
  const winner = sorted[0]

  experiment.variants = sorted
  experiment.winner = winner.text
  experiment.winnerScore = winner.score
  experiment.status = 'complete'
  experiment.completedAt = new Date().toISOString()
  experiment.insight = `Best ${config.channel} approach for ${config.industry}: ${winner.text.split(']')[0]?.replace('[', '') ?? 'unknown'} style (score: ${winner.score}). ${winner.score >= 70 ? 'Deploy this opener immediately.' : 'Scores are low — refine the pain point angle.'}`

  await saveExperiment(experiment)

  await pushHumanTask({
    title: `Send 20 ${config.channel} DMs using the winning opener angle`,
    description: `Jarvis tested ${styles.length} DM styles for ${config.industry} on ${config.channel}. Winner (${winner.score}/100):\n\n${winner.text}\n\nSend 20 DMs today using this opener. Report back how many responded.`,
    category: 'outreach_manual',
    priority: winner.score >= 70 ? 1 : 2,
    createdBy: 'strategy_engine',
    payload: { winner: winner.text, score: winner.score, channel: config.channel, industry: config.industry, allVariants: sorted },
  })

  writeAudit({
    actor: 'jarvis',
    action: 'dm_experiment',
    purpose: `${config.industry}:${config.channel}`,
    result: 'ok',
    metadata: { winner: winner.text, score: winner.score },
  })

  return experiment
}

// ── Platform Gap Analysis ─────────────────────────────────────────────────────

export async function analyzePlatformGaps(configuredCredentials: string[] = []): Promise<PlatformGap[]> {
  const learning = await getLearningDigest()

  const allGaps: PlatformGap[] = []

  // Apollo — lead enrichment
  if (!configuredCredentials.includes('apollo')) {
    allGaps.push({
      platform: 'Apollo.io',
      category: 'outreach_tool',
      reason: 'Apollo is the highest-yield B2B contact database. Without it, lead sourcing is manual and slow. Starts at $49/mo for 1,200 exports.',
      estimatedImpact: 'high',
      actionRequired: 'Sign up at apollo.io, get your API key, add APOLLO_API_KEY to backend/.env.local',
      costEstimate: '$49–$99/mo',
      priority: 1,
    })
  }

  // LinkedIn — primary B2B channel
  if (!configuredCredentials.includes('linkedin_premium')) {
    allGaps.push({
      platform: 'LinkedIn Premium / Sales Navigator',
      category: 'outreach_tool',
      reason: 'Decision makers in HVAC, real estate, and agencies are most reachable on LinkedIn. Sales Navigator gives 50 InMails/mo and advanced search.',
      estimatedImpact: 'high',
      actionRequired: 'Upgrade LinkedIn to Premium Business or Sales Navigator. Connect profile to Jarvis DM workflow.',
      costEstimate: '$99–$170/mo',
      priority: 1,
    })
  }

  // TikTok Business — content reach
  if (!configuredCredentials.includes('tiktok_business')) {
    allGaps.push({
      platform: 'TikTok Business Account',
      category: 'social_media',
      reason: 'Organic content on TikTok targeting business owners (HVAC, real estate) can generate inbound leads at zero cost. Noah (CMO) is already generating scripts — just no posting channel.',
      estimatedImpact: 'medium',
      actionRequired: 'Create a TikTok Business account for Virel Automation. Download Noah\'s generated scripts and start posting 3x/week.',
      costEstimate: 'Free',
      priority: 2,
    })
  }

  // Instagram Business
  if (!configuredCredentials.includes('instagram_business')) {
    allGaps.push({
      platform: 'Instagram Business Account',
      category: 'social_media',
      reason: 'Interior designers, med spas, and clinics are heavy Instagram users. Reels + DMs can generate warm leads from inbound content.',
      estimatedImpact: 'medium',
      actionRequired: 'Create or convert Instagram to Business account. Run Noah\'s Reels scripts as content. Wire DMs to CRM.',
      costEstimate: 'Free',
      priority: 2,
    })
  }

  // HeyGen — video creation
  if (!configuredCredentials.includes('heygen')) {
    allGaps.push({
      platform: 'HeyGen (AI Video)',
      category: 'content_creation',
      reason: 'HeyGen lets Jarvis turn Noah\'s scripts into AI avatar videos automatically, removing the need to record. Massive content velocity unlock.',
      estimatedImpact: 'high',
      actionRequired: 'Sign up at heygen.com, create an avatar, add HEYGEN_API_KEY to .env.local',
      costEstimate: '$24–$89/mo',
      priority: 2,
    })
  }

  // Instantly.ai or Lemlist — email infrastructure
  if (!configuredCredentials.includes('email_warmup')) {
    allGaps.push({
      platform: 'Email Warmup Tool (Instantly.ai or Lemlist)',
      category: 'outreach_tool',
      reason: 'Without email warmup, cold outreach from Gmail will land in spam after 50 sends. A warmup tool keeps deliverability above 90%.',
      estimatedImpact: 'high',
      actionRequired: 'Sign up for Instantly.ai or Lemlist, connect Gmail, start warming. Do not send cold emails without this.',
      costEstimate: '$30–$99/mo',
      priority: 1,
    })
  }

  // Google My Business — local signals for HVAC outreach
  if (!configuredCredentials.includes('google_ads')) {
    allGaps.push({
      platform: 'Google Ads Account',
      category: 'analytics',
      reason: 'For HVAC and clinic clients, running retargeting pixels on the Forge OS landing page can close inbound leads faster. Also enables Jace to run client campaigns.',
      estimatedImpact: 'low',
      actionRequired: 'Create a Google Ads account at ads.google.com. No spend needed — just the account for pixel access.',
      costEstimate: 'Free (account), ads optional',
      priority: 3,
    })
  }

  // Omni Socials — social scheduling
  if (!configuredCredentials.includes('omni_socials')) {
    allGaps.push({
      platform: 'Social Scheduling (Omni Socials / Buffer)',
      category: 'automation',
      reason: 'Noah generates content but has no auto-publish path. A scheduling tool lets Jarvis queue posts for Jace\'s approval and publish automatically.',
      estimatedImpact: 'medium',
      actionRequired: 'Create an Omni Socials or Buffer account, connect TikTok + Instagram, wire to Noah\'s content calendar.',
      costEstimate: '$0–$18/mo',
      priority: 2,
    })
  }

  // Coach/consultant specific gaps — these niches live on Instagram, not LinkedIn
  allGaps.push({
    platform: 'Instagram DM Outreach (Coaches & Consultants)',
    category: 'outreach_tool',
    reason: 'Online coaches and consultants are most reachable via Instagram DMs at 7–10pm their timezone. They check DMs in the evening after content posting. This was your highest-converting channel in the old outreach system.',
    estimatedImpact: 'high',
    actionRequired: 'Run DM campaigns on Instagram targeting coaches (business, life, sales coaches) between 7–10pm. Use the pain-first opener: "I noticed you\'re posting consistently but your CTA is getting ignored — want to see what we fixed for [similar coach]?" Aim for 20 DMs/night.',
    costEstimate: 'Free (manual) or $50–200/mo with automation tool',
    priority: 1,
  })

  // Sort by priority then impact
  const impactOrder = { high: 0, medium: 1, low: 2 }
  allGaps.sort((a, b) => a.priority - b.priority || impactOrder[a.estimatedImpact] - impactOrder[b.estimatedImpact])

  // Auto-push critical gaps as human tasks
  const criticalGaps = allGaps.filter((g) => g.priority === 1 && g.estimatedImpact === 'high')
  for (const gap of criticalGaps) {
    const existing = await getHumanTasks('pending')
    const alreadyQueued = existing.some((t) => t.title.includes(gap.platform))
    if (!alreadyQueued) {
      await pushHumanTask({
        title: `Set up ${gap.platform}`,
        description: `${gap.reason}\n\nAction: ${gap.actionRequired}\nCost: ${gap.costEstimate}`,
        category: 'account_setup',
        priority: 1,
        createdBy: 'platform_gap_analyzer',
        payload: gap,
      })
    }
  }

  // Factor in CRL learning — if a channel pattern has high reward, mention it
  const topPatterns = (learning.topPatterns ?? []) as Array<{ key: string; avgReward: number; confidence: number }>
  for (const pattern of topPatterns) {
    if (pattern.avgReward > 0.5 && pattern.confidence > 0.3) {
      const note = `CRL data: pattern "${pattern.key}" has avg reward ${pattern.avgReward} with ${pattern.confidence} confidence — double down on this.`
      allGaps.unshift({
        platform: `Exploit pattern: ${pattern.key}`,
        category: 'outreach_tool',
        reason: note,
        estimatedImpact: 'high',
        actionRequired: 'Jarvis will automatically prioritize this pattern in next outreach batch.',
        costEstimate: 'Free',
        priority: 1,
      })
    }
  }

  return allGaps.slice(0, 12)
}

// ── Weekly Plan ───────────────────────────────────────────────────────────────

export async function generateWeeklyPlan(): Promise<WeeklyPlan> {
  const [overview, learning, pendingTasks, experiments] = await Promise.all([
    productionData.analyticsOverview(),
    getLearningDigest(),
    getHumanTasks('pending'),
    getExperiments(),
  ])

  const m = overview.metrics
  const weekOf = new Date().toLocaleDateString('en-AU', { weekday: undefined, year: 'numeric', month: 'long', day: 'numeric' })

  const fallbackPlan: WeeklyPlan = {
    weekOf,
    jarvisOwns: [
      { day: 'Monday', tasks: ['Enrich 20 new leads via Apollo', 'Generate personalized drafts for HVAC segment', 'Score 5 new hook variants'] },
      { day: 'Tuesday', tasks: ['Sync Gmail replies', 'Update CRL with all outcomes', 'Run DM experiment on LinkedIn for real estate'] },
      { day: 'Wednesday', tasks: ['Generate CMO concepts for TikTok', 'Enrich 20 more leads for agency segment', 'Analyze reply patterns from this week'] },
      { day: 'Thursday', tasks: ['Run DM experiment on Instagram for med spas', 'Generate weekly brief', 'Update CRM with meeting outcomes'] },
      { day: 'Friday', tasks: ['Generate next week plan', 'CRL digest report', 'Synthesize top 3 lessons from this week'] },
    ],
    jaceOwns: [
      { day: 'Monday', tasks: ['Send 30 approved cold emails', 'Check pending LinkedIn connection requests'] },
      { day: 'Tuesday', tasks: ['Post 1 TikTok/Reel from Noah\'s scripts', 'Reply to all interested email threads'] },
      { day: 'Wednesday', tasks: ['Record 1 hook video if HeyGen unavailable', 'Follow up with any meeting no-shows'] },
      { day: 'Thursday', tasks: ['Send 30 more cold emails', 'Complete any pending account setup tasks'] },
      { day: 'Friday', tasks: ['Review CRL week digest', 'Decide next week\'s target industry priority'] },
    ],
    experiments: [
      { type: 'hook', niche: 'HVAC', platform: 'tiktok', goal: 'Find highest-converting TikTok hook for HVAC pain point' },
      { type: 'dm', niche: 'Real Estate Agents', platform: 'linkedin', goal: 'Test 3 LinkedIn DM angles for real estate agents' },
      { type: 'hook', niche: 'Med Spas', platform: 'instagram_reels', goal: 'Find best Reels hook for med spa owners' },
    ],
    targets: {
      emailsToSend: Math.max(60, m.emailsSent + 40),
      leadsToEnrich: 50,
      hooksToTest: 15,
    },
    generatedAt: new Date().toISOString(),
  }

  if (!geminiApiKeyFor('jarvis')) return fallbackPlan

  const prompt = `You are JARVIS generating a tactical weekly plan for ${COMPANY}.
Current: ${m.emailsSent} emails sent, ${m.replies} replies, ${m.meetingsBooked} meetings, ${m.replyRate.toFixed(1)}% reply rate.
Pending Jace tasks: ${pendingTasks.length}. Recent experiments: ${experiments.slice(0, 3).map((e) => `${e.type}:${e.niche}:winner score ${e.winnerScore}`).join(', ') || 'none yet'}.
CRL data: ${learning.totalEvents} events, avg reward ${learning.recentAvgReward}. Top patterns: ${learning.topPatterns.slice(0, 2).map((p: { key: string }) => p.key).join(', ')}.

Create a split-ownership weekly plan. Jarvis handles all AI/data tasks. Jace handles sending, recording, manual outreach, and approvals.
Be specific and realistic. Consider Jace is 19, solo, has limited time.

Return strict JSON:
{
  "jarvisOwns": [{ "day": "Monday", "tasks": ["task1", "task2"] }],
  "jaceOwns": [{ "day": "Monday", "tasks": ["task1", "task2"] }],
  "experiments": [{ "type": "hook|dm", "niche": "industry", "platform": "platform", "goal": "..." }],
  "targets": { "emailsToSend": 80, "leadsToEnrich": 50, "hooksToTest": 15 }
}`

  try {
    const text = await gemini(prompt, 1800, true)
    if (!text) return fallbackPlan
    const parsed = JSON.parse(stripJsonFence(text)) as Partial<WeeklyPlan>
    return {
      weekOf,
      jarvisOwns: parsed.jarvisOwns ?? fallbackPlan.jarvisOwns,
      jaceOwns: parsed.jaceOwns ?? fallbackPlan.jaceOwns,
      experiments: parsed.experiments ?? fallbackPlan.experiments,
      targets: parsed.targets ?? fallbackPlan.targets,
      generatedAt: new Date().toISOString(),
    }
  } catch {
    return fallbackPlan
  }
}

// ── CRL Strategy Recommendation ───────────────────────────────────────────────

export async function getStrategyRecommendation(industry?: string, channel?: string): Promise<{
  recommendedHookStyle: { best: string | null; confidence: number; reason: string }
  recommendedChannel: { best: string | null; confidence: number; reason: string }
  summary: string
}> {
  const [hookRec, channelRec] = await Promise.all([
    getBestApproach(
      { industry: industry ?? 'HVAC', channel: channel ?? 'email' },
      ['pain-first', 'result-first', 'signal-first'],
      'hookStyle',
    ),
    getBestApproach(
      { industry: industry ?? 'HVAC' },
      TARGET_CHANNELS,
      'channel',
    ),
  ])

  const hasData = hookRec.confidence > 0.1 || channelRec.confidence > 0.1

  return {
    recommendedHookStyle: hookRec,
    recommendedChannel: channelRec,
    summary: hasData
      ? `For ${industry ?? 'your target industries'}: Use ${hookRec.best ?? 'pain-first'} hook style (confidence: ${(hookRec.confidence * 100).toFixed(0)}%) via ${channelRec.best ?? 'email'} (confidence: ${(channelRec.confidence * 100).toFixed(0)}%).`
      : `Not enough CRL data yet. Run more outreach and experiments — Jarvis needs at least 10 outcomes per pattern to be confident.`,
  }
}
