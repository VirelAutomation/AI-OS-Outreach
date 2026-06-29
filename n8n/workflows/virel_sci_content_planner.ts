import { workflow, trigger, node, expr, newCredential } from '@n8n/workflow-sdk';

const dailyPlanner = trigger({
  type: 'n8n-nodes-base.scheduleTrigger',
  version: 1.3,
  config: {
    name: 'Daily Strategy Trigger',
    position: [240, 320],
    parameters: {
      rule: {
        interval: [
          {
            field: 'days',
            daysInterval: 1,
            triggerAtHour: 9,
            triggerAtMinute: 0,
          },
        ],
      },
    },
  },
  output: [{}],
});

const buildContext = node({
  type: 'n8n-nodes-base.set',
  version: 3.4,
  config: {
    name: 'Build Growth Context',
    position: [520, 320],
    parameters: {
      mode: 'manual',
      includeOtherFields: true,
      assignments: {
        assignments: [
          { id: 'backend', name: 'backend_base_url', value: expr('{{ $env.FORGE_API_BASE_URL ?? "http://host.docker.internal:8000" }}'), type: 'string' },
          { id: 'jarvis_mode', name: 'jarvis_mode', value: expr('{{ $env.JARVIS_SCI_MODE ?? "autonomous" }}'), type: 'string' },
          { id: 'target', name: 'target_state', value: 'Publish high-conviction AI content that books qualified calls for Virel Automation.', type: 'string' },
          { id: 'niche', name: 'niche', value: 'service businesses', type: 'string' },
          { id: 'content_goal', name: 'content_goal', value: 'Show why AI systems are now mandatory and why Virel should be the operator of record.', type: 'string' },
          { id: 'hf_video', name: 'hf_video_endpoint', value: 'https://api-inference.huggingface.co/models/Wan-AI/Wan2.1-T2V-1.3B-Diffusers', type: 'string' },
          { id: 'hf_image', name: 'hf_image_endpoint', value: 'https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-dev', type: 'string' },
        ],
      },
    },
  },
  output: [{
    backend_base_url: 'http://host.docker.internal:8000',
    jarvis_mode: 'autonomous',
    target_state: 'Publish high-conviction AI content that books qualified calls for Virel Automation.',
    niche: 'service businesses',
    content_goal: 'Show why AI systems are now mandatory and why Virel should be the operator of record.',
    hf_video_endpoint: 'https://api-inference.huggingface.co/models/Wan-AI/Wan2.1-T2V-1.3B-Diffusers',
    hf_image_endpoint: 'https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-dev',
  }],
});

const runSciObjectives = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.4,
  config: {
    name: 'Run SCI Objectives',
    position: [820, 320],
    parameters: {
      method: 'POST',
      url: expr('{{ $json.backend_base_url + "/api/jarvis/objectives" }}'),
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ { founder_id: "jarvis-ceo", company_name: "Virel Automation", target_state: $json.target_state, founder_notes: ["Bias toward booked calls, not vanity reach", "Keep the message direct and commercial", "Train Jarvis to produce strategy that closes revenue, not vanity metrics"], company_constraints: ["Use Hugging Face for media generation", "Keep Instagram, Facebook, and X connected"], tasks_backlog: ["Need 7-day content runway", "Need repeatable why-us narrative", "Need CEO-level strategy brief for each content batch"], focus_areas: ["content strategy", "offer proof", "social distribution"], mode: $json.jarvis_mode, refresh_calendar: false } }}'),
      options: {
        response: {
          response: {
            neverError: true,
            responseFormat: 'json',
          },
        },
      },
    },
  },
  output: [{
    ok: true,
    objective_graph: {
      summary: 'Protect founder time and ship one compounding growth initiative.',
    },
  }],
});

const runCrlLearning = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.4,
  config: {
    name: 'Run CRL Learning',
    position: [1120, 320],
    parameters: {
      method: 'GET',
      url: expr('{{ $("Build Growth Context").item.json.backend_base_url + "/api/analytics/crl-learning" }}'),
      options: {
        response: {
          response: {
            neverError: true,
            responseFormat: 'json',
          },
        },
      },
    },
  },
  output: [{
    ok: true,
    mechanisms: [
      {
        cause: 'used_social_proof',
        description: 'Social proof improves conversion quality.',
      },
    ],
  }],
});

const runJarvisBrief = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.4,
  config: {
    name: 'Run Jarvis Brief',
    position: [1420, 440],
    parameters: {
      method: 'POST',
      url: expr('{{ $("Build Growth Context").item.json.backend_base_url + "/api/jarvis/brief" }}'),
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ { context: { target_state: $("Build Growth Context").item.json.target_state, niche: $("Build Growth Context").item.json.niche, content_goal: $("Build Growth Context").item.json.content_goal } } }}'),
      options: {
        response: {
          response: {
            neverError: true,
            responseFormat: 'json',
          },
        },
      },
    },
  },
  output: [{
    ok: true,
    brief: {
      headline: 'AI operators now outcompete manual teams.',
      priorities: [
        'Prove the revenue case for AI.',
        'Show strategy, not generic inspiration.',
        'Drive booked calls from every post.',
      ],
    },
  }],
});

const buildStrategyLedger = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Build Strategy Ledger',
    position: [1420, 180],
    parameters: {
      mode: 'runOnceForAllItems',
      language: 'javaScript',
      jsCode: "const sci = $('Run SCI Objectives').first().json;\nconst crl = $('Run CRL Learning').first().json;\nconst brief = $('Run Jarvis Brief').first().json;\nconst mechanism = (crl.mechanisms ?? [])[0] ?? {};\nreturn [{ json: {\n  strategy_id: `strategy-${$now.toMillis()}`,\n  target_state: $('Build Growth Context').first().json.target_state,\n  focus_area: 'content strategy',\n  contradiction: 'Need polished multi-platform content without slipping into generic AI fluff.',\n  recommended_move: brief.brief?.headline ?? sci.objective_graph?.summary ?? 'Publish proof-heavy operator content.',\n  counterfactual_path: mechanism.description ?? 'No CRL mechanism returned.',\n  owner: 'jarvis',\n  status: 'running',\n  approval_required: false,\n  review_at: $now.plus({ days: 1 }).toISO(),\n} }];",
    },
  },
  output: [{
    strategy_id: 'strategy-1',
    target_state: 'Publish high-conviction AI content that books qualified calls for Virel Automation.',
    focus_area: 'content strategy',
    contradiction: 'Need polished multi-platform content without slipping into generic AI fluff.',
    recommended_move: 'Protect founder time and ship one compounding growth initiative.',
    counterfactual_path: 'Social proof improves conversion quality.',
    owner: 'jarvis',
    status: 'running',
    approval_required: false,
    review_at: '2026-06-24T00:00:00.000Z',
  }],
});

const persistStrategyLedger = node({
  type: 'n8n-nodes-base.dataTable',
  version: 1.1,
  config: {
    name: 'Persist Strategy Ledger',
    position: [1720, 180],
    parameters: {
      resource: 'row',
      operation: 'upsert',
      dataTableId: {
        __rl: true,
        mode: 'id',
        value: '5DrQhKsQguX823Zr',
      },
      matchType: 'allConditions',
      filters: {
        conditions: [
          { keyName: 'strategy_id', condition: 'eq', keyValue: expr('{{ $json.strategy_id }}') },
        ],
      },
      columns: {
        mappingMode: 'defineBelow',
        value: {
          strategy_id: expr('{{ $json.strategy_id }}'),
          target_state: expr('{{ $json.target_state }}'),
          focus_area: expr('{{ $json.focus_area }}'),
          contradiction: expr('{{ $json.contradiction }}'),
          recommended_move: expr('{{ $json.recommended_move }}'),
          counterfactual_path: expr('{{ $json.counterfactual_path }}'),
          owner: expr('{{ $json.owner }}'),
          status: expr('{{ $json.status }}'),
          approval_required: expr('{{ $json.approval_required }}'),
          review_at: expr('{{ $json.review_at }}'),
        },
      },
    },
  },
  output: [{
    strategy_id: 'strategy-1',
    target_state: 'Publish high-conviction AI content that books qualified calls for Virel Automation.',
  }],
});

const researchHooks = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.4,
  config: {
    name: 'Research Hooks',
    position: [1420, 320],
    parameters: {
      method: 'POST',
      url: expr('{{ $("Build Growth Context").item.json.backend_base_url + "/api/cmo/research" }}'),
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ { niche: $("Build Growth Context").item.json.niche, platform: "instagram_reels" } }}'),
      options: {
        response: {
          response: {
            neverError: true,
            responseFormat: 'json',
          },
        },
      },
    },
  },
  output: [{
    ok: true,
    research: {
      goldHooks: ['This is what your business loses without AI'],
      trendingFormats: ['talking head'],
    },
  }],
});

const generateConcepts = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.4,
  config: {
    name: 'Generate Concepts',
    position: [1720, 320],
    parameters: {
      method: 'POST',
      url: expr('{{ $("Build Growth Context").item.json.backend_base_url + "/api/cmo/concepts" }}'),
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ { niche: $("Build Growth Context").item.json.niche, platform: "instagram_reels", count: 3, goal: $("Build Growth Context").item.json.content_goal, researchContext: $("Research Hooks").item.json.research } }}'),
      options: {
        response: {
          response: {
            neverError: true,
            responseFormat: 'json',
          },
        },
      },
    },
  },
  output: [{
    ok: true,
    concepts: [
      {
        id: 'concept-1',
        title: 'Why AI is now mandatory',
        hook: 'If your team still runs manually, you are already late.',
        openingLine: 'Most owners do not realize the margin they are leaking.',
      },
    ],
  }],
});

const splitConcepts = node({
  type: 'n8n-nodes-base.splitOut',
  version: 1,
  config: {
    name: 'Split Concepts',
    position: [2020, 320],
    parameters: {
      fieldToSplitOut: 'concepts',
      include: 'allOtherFields',
      options: {
        destinationFieldName: 'concept',
      },
    },
  },
  output: [{
    concept: {
      id: 'concept-1',
      title: 'Why AI is now mandatory',
      hook: 'If your team still runs manually, you are already late.',
      openingLine: 'Most owners do not realize the margin they are leaking.',
    },
    ok: true,
  }],
});

const generateScripts = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.4,
  config: {
    name: 'Generate Script',
    position: [2320, 320],
    parameters: {
      method: 'POST',
      url: expr('{{ $("Build Growth Context").item.json.backend_base_url + "/api/cmo/script" }}'),
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ { concept: $json.concept.title, hook: $json.concept.hook, platform: "instagram_reels", niche: $("Build Growth Context").item.json.niche, goal: $("Build Growth Context").item.json.content_goal } }}'),
      options: {
        response: {
          response: {
            neverError: true,
            responseFormat: 'json',
          },
        },
      },
    },
  },
  output: [{
    ok: true,
    script: {
      title: 'Why AI is now mandatory',
      hook: 'If your team still runs manually, you are already late.',
      cta: 'Book a call with Virel.',
      captionHook: 'AI is not optional anymore.',
      segments: [
        { content: 'Owners are wasting hours on manual follow-up.' },
      ],
    },
  }],
});

const queueVideoJob = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.4,
  config: {
    name: 'Queue Hugging Face Video Job',
    position: [2620, 320],
    parameters: {
      method: 'POST',
      url: expr('{{ $("Build Growth Context").item.json.hf_video_endpoint }}'),
      authentication: 'genericCredentialType',
      genericAuthType: 'httpBearerAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ { inputs: ($json.script.hook + " " + $json.script.captionHook), parameters: { num_frames: 81, guidance_scale: 6 } } }}'),
      options: {
        response: {
          response: {
            neverError: true,
            responseFormat: 'json',
          },
        },
      },
    },
    credentials: {
      httpBearerAuth: newCredential('Hugging Face Token'),
    },
  },
  output: [{
    asset_url: 'https://huggingface.co/generated/video-asset.mp4',
  }],
});

const queueImageJob = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.4,
  config: {
    name: 'Queue Hugging Face Image Job',
    position: [2920, 320],
    parameters: {
      method: 'POST',
      url: expr('{{ $("Build Growth Context").item.json.hf_image_endpoint }}'),
      authentication: 'genericCredentialType',
      genericAuthType: 'httpBearerAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ { inputs: ($("Generate Script").item.json.script.hook + " " + $("Generate Script").item.json.script.captionHook + " cinematic social image"), parameters: { guidance_scale: 4.5, num_inference_steps: 28 } } }}'),
      options: {
        response: {
          response: {
            neverError: true,
            responseFormat: 'json',
          },
        },
      },
    },
    credentials: {
      httpBearerAuth: newCredential('Hugging Face Token'),
    },
  },
  output: [{
    asset_url: 'https://huggingface.co/generated/image-asset.png',
  }],
});

const buildQueueItems = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Build Queue Items',
    position: [2920, 320],
    parameters: {
      mode: 'runOnceForAllItems',
      language: 'javaScript',
      jsCode: "const sci = $('Run SCI Objectives').first().json;\nconst crl = $('Run CRL Learning').first().json;\nconst brief = $('Run Jarvis Brief').first().json;\nconst mechanisms = (crl.mechanisms ?? []).slice(0, 2).map((item) => item.description ?? item.cause ?? '').filter(Boolean);\nconst posts = [];\nfor (const item of $input.all()) {\n  const script = item.json.script ?? {};\n  const title = script.title ?? 'AI systems now win';\n  const hook = script.hook ?? 'AI is already deciding the next market leaders.';\n  const scriptText = (script.segments ?? []).map((segment) => segment.content ?? '').join(' ');\n  const caption = `${script.captionHook ?? hook}\\n\\n${script.cta ?? 'Book a strategy call with Virel.'}`;\n  const imageUrl = item.json.asset_url ?? item.json.url ?? '';\n  const videoUrl = $('Queue Hugging Face Video Job').item.json.asset_url ?? $('Queue Hugging Face Video Job').item.json.url ?? imageUrl;\n  const useVideo = Boolean(videoUrl);\n  const contentId = `content-${Date.now()}-${Math.floor(Math.random() * 100000)}`;\n  posts.push({\n    content_id: `${contentId}-ig`,\n    platform: 'instagram',\n    title,\n    hook,\n    script_text: scriptText,\n    caption,\n    media_prompt: `${hook} ${scriptText}`,\n    media_url: useVideo ? videoUrl : imageUrl,\n    is_video: useVideo,\n    status: 'ready',\n    publish_at: $now.plus({ hours: 2 }).toISO(),\n    approval_required: false,\n  });\n  posts.push({\n    content_id: `${contentId}-fb`,\n    platform: 'facebook',\n    title,\n    hook,\n    script_text: scriptText,\n    caption,\n    media_prompt: `${hook} ${scriptText}`,\n    media_url: useVideo ? videoUrl : imageUrl,\n    is_video: useVideo,\n    status: 'ready',\n    publish_at: $now.plus({ hours: 2 }).toISO(),\n    approval_required: false,\n  });\n}\nposts.push({\n  content_id: `content-x-${Date.now()}`,\n  platform: 'x',\n  title: 'Why AI is mandatory now',\n  hook: 'Most businesses are still trying to outrun manual work with more manual work.',\n  script_text: [\n    brief.brief?.headline ?? sci.objective_graph?.summary ?? 'Jarvis wants a harder strategic operating system.',\n    ...(brief.brief?.priorities ?? []).slice(0, 2),\n    mechanisms.join(' | ') || 'Use counterfactual proof and social proof together.',\n    'AI is not a feature. It is now the operating layer for growth, sales, and follow-up.',\n    'Virel builds the system, not just the post.'\n  ].filter(Boolean).join(' '),\n  caption: 'AI is now a mandatory operating system. Businesses that wait will subsidize competitors that automate. Virel builds the actual machinery.',\n  media_prompt: 'Minimal proof-driven image for a CEO strategy post about AI urgency.',\n  media_url: $input.first()?.json.asset_url ?? '',\n  is_video: false,\n  status: 'ready',\n  publish_at: $now.plus({ hours: 3 }).toISO(),\n  approval_required: false,\n});\nreturn posts.map((json) => ({ json }));",
    },
  },
  output: [{
    content_id: 'content-ig-1',
    platform: 'instagram',
    title: 'Why AI is now mandatory',
    hook: 'If your team still runs manually, you are already late.',
    script_text: 'Owners are wasting hours on manual follow-up.',
    caption: 'AI is not optional anymore.',
    media_prompt: 'If your team still runs manually, you are already late.',
    media_url: 'https://huggingface.co/generated/video-asset.mp4',
    is_video: true,
    status: 'ready',
    publish_at: '2026-06-23T12:00:00.000Z',
    approval_required: false,
  }],
});

const persistSocialQueue = node({
  type: 'n8n-nodes-base.dataTable',
  version: 1.1,
  config: {
    name: 'Persist Social Queue',
    position: [3220, 320],
    parameters: {
      resource: 'row',
      operation: 'upsert',
      dataTableId: {
        __rl: true,
        mode: 'id',
        value: '8PRuj7rfE2FDYkzR',
      },
      matchType: 'allConditions',
      filters: {
        conditions: [
          { keyName: 'content_id', condition: 'eq', keyValue: expr('{{ $json.content_id }}') },
          { keyName: 'platform', condition: 'eq', keyValue: expr('{{ $json.platform }}') },
        ],
      },
      columns: {
        mappingMode: 'defineBelow',
        value: {
          content_id: expr('{{ $json.content_id }}'),
          platform: expr('{{ $json.platform }}'),
          title: expr('{{ $json.title }}'),
          hook: expr('{{ $json.hook }}'),
          script_text: expr('{{ $json.script_text }}'),
          caption: expr('{{ $json.caption }}'),
          media_prompt: expr('{{ $json.media_prompt }}'),
          media_url: expr('{{ $json.media_url }}'),
          is_video: expr('{{ $json.is_video }}'),
          status: expr('{{ $json.status }}'),
          publish_at: expr('{{ $json.publish_at }}'),
          approval_required: expr('{{ $json.approval_required }}'),
        },
      },
    },
  },
  output: [{
    content_id: 'content-ig-1',
    platform: 'instagram',
  }],
});

export default workflow('virel-sci-content-planner', 'Virel - SCI Content Planner')
  .add(dailyPlanner)
  .to(buildContext)
  .to(runSciObjectives)
  .to(runCrlLearning)
  .to(runJarvisBrief)
  .to(researchHooks)
  .to(generateConcepts)
  .to(splitConcepts)
  .to(generateScripts)
  .to(queueVideoJob)
  .to(queueImageJob)
  .to(buildQueueItems)
  .to(persistSocialQueue)
  .add(runCrlLearning)
  .to(runJarvisBrief)
  .to(buildStrategyLedger)
  .to(persistStrategyLedger);
