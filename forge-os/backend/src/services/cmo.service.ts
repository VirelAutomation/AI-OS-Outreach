import { randomUUID } from 'node:crypto'
import { geminiApiKeyFor } from '../config/env.js'
import { cmoArtifactStore } from '../lib/cmoArtifactStore.js'
import { callGeminiDetailed } from '../lib/gemini.js'

export type Platform = 'tiktok' | 'instagram_reels' | 'youtube_shorts' | 'linkedin' | 'twitter'
export type ContentFormat =
  | 'talking_head'
  | 'voiceover_b_roll'
  | 'text_on_screen'
  | 'hook_reveal'
  | 'storytime'
  | 'list_format'
  | 'day_in_life'

export type ViralPattern = {
  hookFormula: string
  angle: string
  structure: string[]
  retentionTechnique: string
  exampleOpener: string
  whyItWorks: string
}

export type ViralResearch = {
  niche: string
  platform: Platform
  topPatterns: ViralPattern[]
  goldHooks: string[]
  contentAngles: string[]
  avoidThese: string[]
  trendingFormats: string[]
  researchSummary: string
}

export type VideoConcept = {
  id: string
  title: string
  hook: string
  angle: string
  format: ContentFormat
  platforms: Platform[]
  viralScore: number
  whyItWorks: string
  openingLine: string
  keyPoints: string[]
  cta: string
}

export type ScriptSegment = {
  label: string
  timing: string
  content: string
  visualNote: string
}

export type VideoScript = {
  title: string
  platform: Platform
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

export type HookScore = {
  hook: string
  platform: Platform
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

// CMO spawn registry — sub-agents Noah can delegate to
export type CMOSubAgent =
  | 'subject_line_lab'
  | 'message_architect'
  | 'offer_positioner'
  | 'landing_cro'
  | 'content_angle_scout'

export type CMOTask = {
  id: string
  subAgent: CMOSubAgent
  goal: string
  status: 'pending' | 'running' | 'done' | 'failed'
  result?: string
  createdAt: string
}

function stripJsonFence(value: string) {
  const trimmed = value.trim()
  if (!trimmed.includes('```')) return trimmed
  const fenced = trimmed.split('```')[1] ?? trimmed
  return fenced.startsWith('json') ? fenced.slice(4).trim() : fenced.trim()
}

const FALLBACK_PATTERNS: ViralPattern[] = [
  {
    hookFormula: '"I [did painful thing] for [X time] so you don\'t have to — here\'s what actually works."',
    angle: 'Sacrifice + Value Transfer',
    structure: ['Hook 0–3s', 'Setup tension 3–8s', 'Rapid value delivery 8–45s', 'Loop/CTA 45–60s'],
    retentionTechnique: 'Curiosity gap — promise payoff in hook, deliver fast, then loop back to it',
    exampleOpener: 'I spent 6 months testing every cold outreach method. This one booked 47 meetings.',
    whyItWorks: 'Positions creator as audience proxy. You did the work, they get the shortcut. Extremely high save and share intent.',
  },
  {
    hookFormula: '"The [industry] secret nobody talks about — and why it matters for you."',
    angle: 'Insider Knowledge / Contrarian',
    structure: ['Provocative hook 0–3s', 'Build credibility 3–10s', 'Drop the insight 10–45s', 'CTA 45–60s'],
    retentionTechnique: 'Information exclusivity — viewers watch to get access to something they think is hidden',
    exampleOpener: 'The outbound strategy booking me 18 meetings a week — nobody in my industry is talking about it.',
    whyItWorks: 'Triggers FOMO and positions creator as an insider. High comment and save rate.',
  },
  {
    hookFormula: '"[Specific number] reasons why [common belief] is killing your [result]."',
    angle: 'Myth Busting / Reframe',
    structure: ['Bold claim hook', 'Agitate the pain', 'Numbered reveals with proof', 'CTA'],
    retentionTechnique: 'List format with numbered reveals — viewers watch for each number',
    exampleOpener: '3 reasons why sending more emails is actually destroying your reply rate.',
    whyItWorks: 'Challenges existing beliefs, forces engagement and comment debate.',
  },
  {
    hookFormula: '"I went from [bad state] to [good state] in [short timeframe]. Here\'s the exact system."',
    angle: 'Transformation Story with Proof',
    structure: ['State the transformation hook', 'Establish before state', 'Reveal the system', 'Proof + CTA'],
    retentionTechnique: 'Before/after contrast creates aspiration — viewers want to reach the after state',
    exampleOpener: 'I went from 0 to 22 booked meetings in 14 days. Here\'s the exact system I used.',
    whyItWorks: 'Specific numbers + timeframe creates credibility. Aspiration drives watch time.',
  },
  {
    hookFormula: '"Stop doing [common thing]. [Specific alternative] is what actually works."',
    angle: 'Contrarian + Direct Fix',
    structure: ['Interrupt with stop command', 'Call out the mistake', 'Present alternative', 'Proof + CTA'],
    retentionTechnique: 'The word "stop" is a pattern interrupt — instantly feels urgent and relevant',
    exampleOpener: 'Stop writing long cold emails. 3-sentence emails are converting at 4x the rate right now.',
    whyItWorks: 'Directly challenges what viewers are doing, making it personally relevant. Very high share rate.',
  },
]

const FALLBACK_HOOKS = [
  'I booked [X] meetings in [timeframe] without [common painful thing]. Here\'s exactly how.',
  'Stop doing [common advice]. Do this instead — it\'s converting at [X]x the rate.',
  'The [role/method] strategy that got me [specific result] in [timeframe]. No one talks about this.',
  'Nobody told me this when I started [thing]. I had to figure it out after losing [cost].',
  'If you\'re a [ICP] and you\'re not doing this, you\'re leaving [result] on the table every month.',
  'I tested [X number] [things] so you don\'t have to. Here\'s the only one that actually works.',
  'The truth about [common topic] that [industry people] don\'t want you to know.',
  '[Controversial statement about their current approach]. Here\'s the proof — and I\'m not taking it back.',
]

const FALLBACK_ANGLES = [
  'Transformation Story — before/after with specific numbers and short timeframe',
  'Process Reveal — step-by-step of a system that works, shown in real time',
  'Failure Autopsy — what went wrong, why, and what the lesson is worth',
  'Contrarian Take — argue against popular advice with data or lived proof',
  'Day-in-the-Life — real-time execution of a system (document, don\'t create)',
  'Hot Take + Defense — bold controversial claim then immediately defend it with evidence',
]

export class CMOService {
  // Multi-agent task registry — CMO can spawn sub-agents
  private activeTasks = new Map<string, CMOTask>()

  async researchViralTrends(niche: string, platform: Platform): Promise<ViralResearch> {
    const fallback: ViralResearch = {
      niche,
      platform,
      topPatterns: FALLBACK_PATTERNS,
      goldHooks: FALLBACK_HOOKS,
      contentAngles: FALLBACK_ANGLES,
      avoidThese: [
        'Opening with "In today\'s video..." or "Hey guys, welcome back" — you\'ve lost them in 0.5s',
        'Vague hooks with no specific number, result, or claim attached',
        'Over-produced content that looks too polished — authenticity outperforms production on short-form',
        'Asking for too many actions in CTA — pick one: save, comment, or follow. Not all three.',
      ],
      trendingFormats: [
        'POV-style talking head with on-screen text callouts for key numbers',
        'Screen recording + raw voiceover — walkthroughs, system reveals',
        'Split-screen before/after with overlaid stats',
        'Raw phone footage with authentic delivery — no ring light, no studio',
      ],
      researchSummary:
        'Viral content rewards specificity, speed, and authenticity. The hook must work in 1.5 seconds. Information density and insider angles outperform polished production. The creator who wins gives the viewer a shortcut they feel they couldn\'t get anywhere else.',
    }

    if (!geminiApiKeyFor('noah')) {
      cmoArtifactStore.save('research', fallback)
      return fallback
    }

    const prompt = `You are Noah, CMO of Forge OS — a world-class viral content strategist who has studied 100,000+ viral videos.

Research what makes content go viral in the "${niche}" niche on ${platform.replace(/_/g, ' ')}.

Think like: MrBeast's retention team, Alex Hormozi's content lab, and the top growth hackers in the creator economy.
Base your research on real viral patterns: hooks that stop the scroll, structures that hold retention, angles that get shared.

Return strict JSON (no markdown) with this exact shape:
{
  "topPatterns": [
    {
      "hookFormula": "fill-in-the-blank formula with [brackets]",
      "angle": "name of the angle",
      "structure": ["step 1 with timing", "step 2"],
      "retentionTechnique": "specific psychological technique",
      "exampleOpener": "exact example opener for this niche",
      "whyItWorks": "psychology + data reasoning"
    }
  ],
  "goldHooks": ["ready-to-use hook with [brackets] for variables"],
  "contentAngles": ["angle name — psychological reasoning"],
  "avoidThese": ["specific mistake and why it kills performance"],
  "trendingFormats": ["format description specific to this niche and platform"],
  "researchSummary": "3-4 sentence viral formula for this niche+platform"
}

Requirements:
- 5 topPatterns minimum, all niche-specific
- 8 goldHooks (fill-in-the-blank, immediately usable)
- 6 contentAngles with psychological reasoning
- 4 avoidThese (common mistakes that kill virality in this specific niche)
- 4 trendingFormats specific to ${platform.replace(/_/g, ' ')} right now
- researchSummary: the single viral formula for ${niche} on ${platform.replace(/_/g, ' ')}

Niche: ${niche}
Platform: ${platform}`

    try {
      const text = await this.gemini(prompt, 3500, true)
      const parsed = JSON.parse(stripJsonFence(text)) as Partial<ViralResearch>
      const researchResult = {
        niche,
        platform,
        topPatterns: parsed.topPatterns?.length ? parsed.topPatterns : fallback.topPatterns,
        goldHooks: parsed.goldHooks?.length ? parsed.goldHooks : fallback.goldHooks,
        contentAngles: parsed.contentAngles?.length ? parsed.contentAngles : fallback.contentAngles,
        avoidThese: parsed.avoidThese?.length ? parsed.avoidThese : fallback.avoidThese,
        trendingFormats: parsed.trendingFormats?.length ? parsed.trendingFormats : fallback.trendingFormats,
        researchSummary: parsed.researchSummary ?? fallback.researchSummary,
      }
      cmoArtifactStore.save('research', researchResult)
      return researchResult
    } catch {
      return fallback
    }
  }

  async generateConcepts(input: {
    niche: string
    platform: Platform
    count: number
    goal?: string
    researchContext?: Partial<ViralResearch>
  }): Promise<VideoConcept[]> {
    const count = Math.min(Math.max(input.count, 1), 8)

    if (!geminiApiKeyFor('noah')) {
      const concepts = this.fallbackConcepts(input.niche, input.platform, count)
      cmoArtifactStore.save('concepts', { niche: input.niche, platform: input.platform, concepts })
      return concepts
    }

    const contextBlock = input.researchContext
      ? `\nViral research context for this niche:\n${JSON.stringify(
          { goldHooks: input.researchContext.goldHooks, contentAngles: input.researchContext.contentAngles, trendingFormats: input.researchContext.trendingFormats },
          null,
          2,
        )}`
      : ''

    const prompt = `You are Noah, CMO of Forge OS — a world-class viral content strategist.

Generate ${count} high-virality video concepts for the "${input.niche}" niche on ${input.platform.replace(/_/g, ' ')}.
${input.goal ? `Creator goal: ${input.goal}` : ''}${contextBlock}

Each concept must be immediately executable: specific hook, angle, key points, and CTA.
viralScore is 1–100 based on hook strength, shareability, and retention potential. Be honest — not everything is a 90.

Return strict JSON array (no markdown):
[
  {
    "title": "concept title",
    "hook": "exact first words spoken or shown on screen — must hit in under 1.5 seconds",
    "angle": "name of the viral angle being used",
    "format": "talking_head|voiceover_b_roll|text_on_screen|hook_reveal|storytime|list_format|day_in_life",
    "platforms": ["tiktok", "instagram_reels"],
    "viralScore": 85,
    "whyItWorks": "specific psychological and structural reasoning",
    "openingLine": "exact first sentence spoken on camera",
    "keyPoints": ["point 1", "point 2", "point 3"],
    "cta": "specific call to action"
  }
]

Niche: ${input.niche}
Platform: ${input.platform}
Count: ${count}`

    try {
      const text = await this.gemini(prompt, 4000, true)
      const parsed = JSON.parse(stripJsonFence(text)) as VideoConcept[]
      const concepts = parsed.slice(0, count).map((c, i) => ({
        id: randomUUID(),
        title: c.title ?? `Concept ${i + 1}`,
        hook: c.hook ?? '',
        angle: c.angle ?? '',
        format: (c.format ?? 'talking_head') as ContentFormat,
        platforms: Array.isArray(c.platforms) ? c.platforms : [input.platform],
        viralScore: typeof c.viralScore === 'number' ? Math.min(100, Math.max(0, c.viralScore)) : 70,
        whyItWorks: c.whyItWorks ?? '',
        openingLine: c.openingLine ?? '',
        keyPoints: Array.isArray(c.keyPoints) ? c.keyPoints : [],
        cta: c.cta ?? '',
      }))
      cmoArtifactStore.save('concepts', { niche: input.niche, platform: input.platform, concepts })
      return concepts
    } catch {
      return this.fallbackConcepts(input.niche, input.platform, count)
    }
  }

  async generateScript(input: {
    concept: string
    hook: string
    platform: Platform
    niche: string
    duration?: string
    goal?: string
  }): Promise<VideoScript> {
    const duration =
      input.duration ??
      ({ youtube_shorts: '60s', tiktok: '45s', instagram_reels: '30s', linkedin: '60s', twitter: '30s' }[
        input.platform
      ] ??
        '45s')

    if (!geminiApiKeyFor('noah')) {
      const script = this.fallbackScript(input, duration)
      cmoArtifactStore.save('script', { niche: input.niche, platform: input.platform, script })
      return script
    }

    const prompt = `You are Noah, CMO of Forge OS — a world-class viral video scriptwriter.

Write a production-ready script engineered to go viral. Every word must earn its place.

Platform: ${input.platform.replace(/_/g, ' ')}
Niche: ${input.niche}
Target duration: ${duration}
Concept: ${input.concept}
Hook: ${input.hook}
${input.goal ? `Creator goal: ${input.goal}` : ''}

Script rules:
- Hook must land in the FIRST 1.5 SECONDS — no welcome, no intro, no fluff
- Every segment must create a reason to keep watching
- Use pattern interrupts every 7–10 seconds (cuts, text overlays, zoom, tonal shift)
- End with a strong loop back to the hook OR a hard CTA (pick one)
- viralScore: honest 1–100 based on hook strength, retention structure, and CTA clarity

Return strict JSON (no markdown):
{
  "title": "video title / working title",
  "platform": "${input.platform}",
  "duration": "${duration}",
  "hook": "exact hook text — the first 1.5 seconds",
  "segments": [
    {
      "label": "Hook",
      "timing": "0–3s",
      "content": "exact words spoken",
      "visualNote": "camera direction or b-roll instruction"
    }
  ],
  "cta": "exact call to action text",
  "captionHook": "caption/thumbnail hook — different from the video hook, for feed discovery",
  "hashtags": ["hashtag1", "hashtag2"],
  "viralScore": 82,
  "scoreReason": "1-2 sentences on what makes this strong or what limits it",
  "productionNotes": ["production tip 1", "production tip 2"]
}

Include segments for: Hook, Setup/Tension, Value Block 1, Value Block 2, Pattern Interrupt, CTA.`

    try {
      const text = await this.gemini(prompt, 4500, true)
      const parsed = JSON.parse(stripJsonFence(text)) as VideoScript
      const script = {
        title: parsed.title ?? input.concept,
        platform: input.platform,
        duration: parsed.duration ?? duration,
        hook: parsed.hook ?? input.hook,
        segments: Array.isArray(parsed.segments) ? parsed.segments : [],
        cta: parsed.cta ?? 'Follow for more.',
        captionHook: parsed.captionHook ?? input.hook,
        hashtags: Array.isArray(parsed.hashtags) ? parsed.hashtags : [],
        viralScore: typeof parsed.viralScore === 'number' ? Math.min(100, Math.max(0, parsed.viralScore)) : 70,
        scoreReason: parsed.scoreReason ?? '',
        productionNotes: Array.isArray(parsed.productionNotes) ? parsed.productionNotes : [],
      }
      cmoArtifactStore.save('script', { niche: input.niche, platform: input.platform, script })
      return script
    } catch {
      return this.fallbackScript(input, duration)
    }
  }

  async scoreHook(hook: string, platform: Platform): Promise<HookScore> {
    if (!geminiApiKeyFor('noah')) {
      const score = this.fallbackHookScore(hook, platform)
      cmoArtifactStore.save('hook_score', score)
      return score
    }

    const prompt = `You are Noah, CMO — a viral hook specialist who has analysed 100,000+ video openings.

Score this hook for virality on ${platform.replace(/_/g, ' ')}:
"${hook}"

Score each dimension 0–100:
- patternInterrupt: Does it physically stop a scroll? Does it feel different from everything around it?
- curiosityGap: Does it create a MUST-watch-to-find-out tension?
- specificity: Is it specific enough to feel credible, real, and not generic?
- emotionalPull: Does it trigger a real emotion — fear, curiosity, aspiration, anger, or relief?
- clarity: Is the topic crystal clear in under 1.5 seconds?

overallScore = weighted average (curiosityGap 30%, patternInterrupt 25%, emotionalPull 20%, specificity 15%, clarity 10%)

Return strict JSON (no markdown):
{
  "overallScore": 75,
  "breakdown": {
    "patternInterrupt": 70,
    "curiosityGap": 80,
    "specificity": 75,
    "emotionalPull": 72,
    "clarity": 85
  },
  "strengths": ["specific strength 1", "specific strength 2"],
  "improvements": ["specific actionable improvement 1", "specific actionable improvement 2"],
  "rewriteSuggestions": [
    "rewritten version 1 — higher patternInterrupt",
    "rewritten version 2 — stronger curiosityGap",
    "rewritten version 3 — more specific result"
  ]
}`

    try {
      const text = await this.gemini(prompt, 1500, true)
      const parsed = JSON.parse(stripJsonFence(text)) as HookScore
      const score = {
        hook,
        platform,
        overallScore: typeof parsed.overallScore === 'number' ? Math.min(100, Math.max(0, parsed.overallScore)) : 50,
        breakdown: parsed.breakdown ?? {
          patternInterrupt: 50,
          curiosityGap: 50,
          specificity: 50,
          emotionalPull: 50,
          clarity: 50,
        },
        strengths: Array.isArray(parsed.strengths) ? parsed.strengths : [],
        improvements: Array.isArray(parsed.improvements) ? parsed.improvements : [],
        rewriteSuggestions: Array.isArray(parsed.rewriteSuggestions) ? parsed.rewriteSuggestions : [],
      }
      cmoArtifactStore.save('hook_score', score)
      return score
    } catch {
      return this.fallbackHookScore(hook, platform)
    }
  }

  // Spawn a CMO sub-agent task (called by Jarvis orchestrator)
  async spawnSubAgent(subAgent: CMOSubAgent, goal: string): Promise<CMOTask> {
    const task: CMOTask = {
      id: randomUUID(),
      subAgent,
      goal,
      status: 'running',
      createdAt: new Date().toISOString(),
    }
    this.activeTasks.set(task.id, task)

    try {
      const result = await this.runSubAgent(subAgent, goal)
      task.status = 'done'
      task.result = result
    } catch (error) {
      task.status = 'failed'
      task.result = error instanceof Error ? error.message : String(error)
    }

    cmoArtifactStore.save('sub_agent_task', task)
    return task
  }

  getActiveTasks(): CMOTask[] {
    return [...this.activeTasks.values()]
  }

  getArtifactStatus() {
    return cmoArtifactStore.status()
  }

  getArtifacts(limit = 50) {
    return cmoArtifactStore.latest(limit)
  }

  private async runSubAgent(subAgent: CMOSubAgent, goal: string): Promise<string> {
    const personas: Record<CMOSubAgent, string> = {
      subject_line_lab: 'You are the Subject Line Lab — a specialist who generates and A/B tests email subject lines for maximum open rate.',
      message_architect: 'You are the Message Architect — a specialist who builds cold outreach messaging frameworks for specific ICPs.',
      offer_positioner: 'You are the Offer Positioner — a specialist who frames the product offer for maximum perceived value in specific markets.',
      landing_cro: 'You are the Landing CRO — a specialist who optimises landing page copy and structure for conversion.',
      content_angle_scout: 'You are the Content Angle Scout — a specialist who finds viral content angles and trending hooks for the creator\'s niche.',
    }

    if (!geminiApiKeyFor('noah')) {
      return `${subAgent} completed: ${goal} — [Gemini API key required for live execution]`
    }

    const prompt = `${personas[subAgent]}

Your task: ${goal}

Return a clear, actionable result. Be specific. No fluff.`

    return this.gemini(prompt, 1200, false)
  }

  private fallbackConcepts(niche: string, platform: Platform, count: number): VideoConcept[] {
    const all: VideoConcept[] = [
      {
        id: randomUUID(),
        title: 'How I Generated 47 Qualified Leads in 7 Days With AI',
        hook: 'I used AI to generate 47 qualified leads last week. Nobody\'s talking about this method.',
        angle: 'Process Reveal + Proof',
        format: 'talking_head',
        platforms: [platform],
        viralScore: 87,
        whyItWorks: 'Specific number + short timeframe + insider secret formula. High save and share intent from the ICP.',
        openingLine: 'Last week I ran an experiment. I used AI to generate 47 qualified leads in 7 days — here\'s the exact system.',
        keyPoints: ['What the AI workflow does', 'The exact prompt structure', 'How to replicate it in under an hour'],
        cta: 'Save this. You\'ll want to come back to it.',
      },
      {
        id: randomUUID(),
        title: 'Stop Sending Cold Emails Like This (Do This Instead)',
        hook: 'Stop. Before you send that cold email, watch this — I\'ve reviewed 10,000+ cold emails and here\'s what makes me reply.',
        angle: 'Contrarian + Authority Proof',
        format: 'list_format',
        platforms: [platform],
        viralScore: 84,
        whyItWorks: '"Stop" is a pattern interrupt. Authority claim creates credibility. Immediately personal for anyone running outreach.',
        openingLine: 'Stop sending cold emails like this. Here are the 3 mistakes killing your reply rate.',
        keyPoints: ['Mistake 1: Too long', 'Mistake 2: About you, not them', 'The 3-sentence formula that works'],
        cta: 'Comment your niche — I\'ll tell you your biggest email mistake.',
      },
      {
        id: randomUUID(),
        title: 'Day in the Life Running a $50K/Month Outbound System',
        hook: 'A day in the life of running an outbound system doing $50K a month.',
        angle: 'Day-in-Life + Aspiration',
        format: 'day_in_life',
        platforms: [platform],
        viralScore: 81,
        whyItWorks: 'Aspirational number + behind-the-scenes access + document-don\'t-create format performs well on all short-form platforms.',
        openingLine: '7AM. First thing I do: check the overnight outreach report.',
        keyPoints: ['Morning system review', 'How I handle replies', 'Approving the afternoon send batch'],
        cta: 'Follow for the full system breakdown.',
      },
      {
        id: randomUUID(),
        title: 'The Email That Books Meetings Every Time (Copy This)',
        hook: 'This exact email has a 23% reply rate. Copy it word for word.',
        angle: 'Template Reveal',
        format: 'text_on_screen',
        platforms: [platform],
        viralScore: 91,
        whyItWorks: 'Permission to copy is the strongest CTA hook there is. Specific % creates immediate credibility. Save rate goes through the roof.',
        openingLine: 'This exact 3-sentence email has a 23% reply rate. Here it is.',
        keyPoints: ['Show the email on screen', 'Explain why each line works', 'The one variation for each ICP'],
        cta: 'Save this. Then send it today.',
      },
      {
        id: randomUUID(),
        title: 'I Failed at Outreach for 6 Months — Here\'s What Changed',
        hook: 'I spent 6 months sending cold emails with basically zero results. Then one thing changed everything.',
        angle: 'Failure Autopsy',
        format: 'storytime',
        platforms: [platform],
        viralScore: 78,
        whyItWorks: 'Vulnerability hook earns trust. The "one thing changed" creates a strong pull to watch through to the reveal.',
        openingLine: 'For 6 months I was sending 100 cold emails a day and getting maybe 1 reply a week.',
        keyPoints: ['What I was doing wrong', 'The insight that shifted everything', 'The new approach and results'],
        cta: 'Tell me what\'s not working in your outreach — I read every comment.',
      },
      {
        id: randomUUID(),
        title: 'The Truth About Reply Rates Nobody Talks About',
        hook: 'Industry "experts" say 3% reply rate is good. That\'s a lie — and here\'s the proof.',
        angle: 'Contrarian Hot Take + Defence',
        format: 'hook_reveal',
        platforms: [platform],
        viralScore: 85,
        whyItWorks: 'Calling out "experts" is a proven controversy hook. Immediately creates a debate in the comments section which drives algorithm reach.',
        openingLine: 'Everyone in sales is lying to you about reply rates.',
        keyPoints: ['What a real benchmark looks like', 'Why 3% is a broken standard', 'How to hit 12%+ consistently'],
        cta: 'If you disagree, comment why — let\'s debate it.',
      },
      {
        id: randomUUID(),
        title: '5 Cold Email Frameworks That Actually Convert in 2025',
        hook: '5 cold email frameworks that are converting right now — I\'ve tested every one of these.',
        angle: 'List Format with Proof',
        format: 'list_format',
        platforms: [platform],
        viralScore: 80,
        whyItWorks: 'Listicle with proof keeps viewers watching for each item. "Right now" creates immediacy. "I\'ve tested" creates authority.',
        openingLine: '5 cold email frameworks I\'ve personally tested — ranked from worst to best.',
        keyPoints: ['Framework 1 (weakest)', 'Framework 3 (middle)', 'Framework 5 (the winner with stats)'],
        cta: 'Save this list. Which one are you going to test first?',
      },
      {
        id: randomUUID(),
        title: 'How to Build a Lead Generation Machine in 30 Minutes',
        hook: 'I\'m going to show you how to build a lead gen machine in 30 minutes — for free.',
        angle: 'How-To + Specificity + Access',
        format: 'voiceover_b_roll',
        platforms: [platform],
        viralScore: 83,
        whyItWorks: '"For free" + "30 minutes" + "machine" is a 3-benefit hook. Walkthroughs have highest save rate of any format on short-form.',
        openingLine: 'Open a blank Google Sheet. This is your lead gen machine.',
        keyPoints: ['Step 1: Data structure', 'Step 2: Enrichment layer', 'Step 3: Outreach trigger'],
        cta: 'Save this and build it today.',
      },
    ]
    return all.slice(0, count)
  }

  private fallbackScript(
    input: { concept: string; hook: string; platform: Platform; niche: string },
    duration: string,
  ): VideoScript {
    return {
      title: input.concept,
      platform: input.platform,
      duration,
      hook: input.hook,
      segments: [
        {
          label: 'Hook',
          timing: '0–3s',
          content: input.hook,
          visualNote: 'Direct to camera, high energy. No intro. Start mid-sentence if needed.',
        },
        {
          label: 'Setup / Tension',
          timing: '3–10s',
          content: 'Here\'s what most people get wrong about this — and it\'s costing them every day.',
          visualNote: 'Stay on camera or cut to screen recording. Add on-screen text callout.',
        },
        {
          label: 'Value Block 1',
          timing: '10–25s',
          content: '[First key insight with a specific number or result attached]',
          visualNote: 'B-roll or on-screen text for the key stat. Zoom or cut for energy.',
        },
        {
          label: 'Pattern Interrupt',
          timing: '25–30s',
          content: 'And here\'s the part nobody talks about...',
          visualNote: 'Hard cut, zoom in, or change of scene. Break the visual monotony.',
        },
        {
          label: 'Value Block 2',
          timing: '30–42s',
          content: '[The counterintuitive insight — the thing that actually changes outcomes]',
          visualNote: 'Return to camera. Slower pace here — let the insight land.',
        },
        {
          label: 'CTA',
          timing: '42–' + duration,
          content: 'Save this so you don\'t forget it. And follow — I post the full system every week.',
          visualNote: 'Direct to camera, softer energy. Smile.',
        },
      ],
      cta: 'Save this. Follow for more.',
      captionHook: `The ${input.niche} method no one's talking about 👇`,
      hashtags: ['#business', '#entrepreneur', '#contentcreator', '#growthhacking', '#marketing'],
      viralScore: 70,
      scoreReason: 'Noah Gemini key not configured — running in offline mode. Add GEMINI_API_KEY_NOAH for AI-generated scripts.',
      productionNotes: [
        'Film in one take for authenticity — edits are fine but raw energy is the goal',
        'No background music under your voice — let the words do the work',
        'Burn-in captions — 85% of viewers watch on mute',
        'First frame matters as much as the hook — make it visual',
      ],
    }
  }

  private fallbackHookScore(hook: string, platform: Platform): HookScore {
    return {
      hook,
      platform,
      overallScore: 62,
      breakdown: { patternInterrupt: 55, curiosityGap: 65, specificity: 60, emotionalPull: 60, clarity: 75 },
      strengths: ['Clear topic — viewer knows what they\'re getting', 'Conversational tone fits short-form'],
      improvements: [
        'Add a specific number or result to build instant credibility',
        'Create a stronger curiosity gap — what is the one thing they\'ll miss if they scroll away?',
        'Lead with the most surprising or counterintuitive element',
      ],
      rewriteSuggestions: [
        `I tested [specific method] for 30 days straight. The result surprised me.`,
        `Stop [common thing they do]. Here's what actually works instead.`,
        `[Specific result] in [short timeframe]. Zero [common barrier]. Here's exactly how.`,
      ],
    }
  }

  private async gemini(prompt: string, maxOutputTokens: number, jsonMode: boolean): Promise<string> {
    const result = await callGeminiDetailed({
      role: 'noah',
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: {
        temperature: 0.7,
        maxOutputTokens,
        ...(jsonMode ? { responseMimeType: 'application/json' } : {}),
      },
    })
    return result.text
  }
}
