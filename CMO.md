# FORGE OS — CMO System (Noah)

## Location

```
forge-os/
├── backend/
│   └── src/
│       ├── services/
│       │   └── cmo.service.ts        ← Core CMO AI engine
│       └── routes/
│           └── cmo.ts                ← REST API endpoints
└── src/
    └── App.tsx                       ← CMOSystem() component (UI)
```

---

## What Noah Does

Noah is the CMO of Forge OS. He is a multi-agent creative intelligence system wired to Gemini 2.5 Pro as his brain. His job is to research what goes viral, generate video concepts, write production-ready scripts, and score hooks — all for the specific niche and platform you give him.

### Capabilities

| Capability | Endpoint | What it produces |
|---|---|---|
| Viral Research | `POST /api/cmo/research` | Top viral patterns, gold hooks, content angles, trending formats, what to avoid |
| Concept Generator | `POST /api/cmo/concepts` | 6–8 video concepts with hook, angle, opening line, key points, viral score |
| Script Builder | `POST /api/cmo/script` | Full production script with per-segment timing, visual notes, caption hook, hashtags |
| Hook Scorer | `POST /api/cmo/hook/score` | 5-dimension virality score + 3 rewritten hook variations |
| Sub-agent Spawn | `POST /api/cmo/spawn` | Delegate to a specialist sub-agent (see below) |
| Status | `GET /api/cmo/status` | CMO health + capabilities (used by Jarvis for cross-system delegation) |

---

## Multi-Agent Architecture

Noah can spawn specialist sub-agents for focused tasks. Jarvis can instruct Noah to spawn these directly via `/api/cmo/spawn`.

### Noah's Sub-agents

| Sub-agent | ID | Responsibility |
|---|---|---|
| Subject Line Lab | `subject_line_lab` | Generates and A/B tests email subject lines for max open rate |
| Message Architect | `message_architect` | Builds cold outreach messaging frameworks for specific ICPs |
| Offer Positioner | `offer_positioner` | Frames the product offer for maximum perceived value |
| Landing CRO | `landing_cro` | Optimises landing page copy and structure for conversion |
| Content Angle Scout | `content_angle_scout` | Finds viral angles and trending hooks for the creator's niche |

### Jarvis → Noah Delegation

Jarvis (CEO orchestrator) can delegate CMO tasks by:
1. Calling `POST /api/cmo/spawn` with a `subAgent` and `goal`
2. Calling `GET /api/cmo/status` to check what Noah can do
3. Including `cmo` as an agent type in sovereign goal runs (`/api/jarvis/sovereign/goal`)

---

## API Stack Required

### Brain
| Service | Purpose | Key needed |
|---|---|---|
| **Google Gemini 2.5 Pro** | All AI generation — research, scripts, concepts, hook scoring | `GEMINI_API_KEY` |

### Database
| Service | Purpose | Key needed |
|---|---|---|
| **Supabase** | Store generated scripts, concepts, campaign history, viral research cache | `SUPABASE_URL`, `SUPABASE_SECRET_KEY` |

### Content Distribution (future)
| Service | Purpose | Key needed |
|---|---|---|
| **Later / Buffer API** | Schedule and publish generated content to social platforms | `LATER_API_KEY` or `BUFFER_ACCESS_TOKEN` |
| **Instagram Graph API** | Post Reels directly from Forge OS | `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_PAGE_ID` |
| **TikTok Content API** | Upload videos to TikTok | `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET` |
| **LinkedIn API** | Post to LinkedIn from Forge OS | `LINKEDIN_ACCESS_TOKEN` |

---

## Video & Image Generation Stack

Noah generates *scripts and concepts* — but to turn those scripts into actual videos and images, you need the following tools wired in. These are the recommended providers for each layer.

### Video Generation (Reels / Shorts / TikTok)

| Tool | What it does | Why it's the right pick |
|---|---|---|
| **Seedance (ByteDance)** | Text-to-video and image-to-video generation | Best motion quality for short-form viral content. Produces cinematic movement that looks native on Reels/TikTok. |
| **Runway Gen-4** | Text-to-video, video-to-video, background removal | High control over style and motion. Good for brand-consistent content. |
| **Kling AI** | High-quality video generation from text or image | Strong for product showcases and face-consistent character video |
| **Pika Labs** | Quick video generation, motion effects on stills | Fast turnaround, good for ugc-style and meme-adjacent content |
| **HeyGen** | AI avatar video — talking head from text script | Feed Noah's script directly → HeyGen renders a talking-head reel in your face/voice |

### Image Generation (Thumbnails / Stills / Ads)

| Tool | What it does | Why it's the right pick |
|---|---|---|
| **Midjourney v7** | Highest quality image generation | Best for brand visuals, thumbnails, offer graphics |
| **Ideogram 3** | Text-in-image generation | Best for thumbnail text overlays and on-screen text visuals |
| **Adobe Firefly** | Brand-safe image generation with style matching | Good for consistent brand visuals across a content calendar |
| **Stable Diffusion (SDXL / Flux)** | Self-hosted image generation | No per-image cost. Run on your own GPU for volume production. |
| **Higgs Field** | Image + video gen with workspace management | Already wired into Claude's MCP — can generate assets from within Forge OS directly |

### Audio / Voice (for Voiceover Scripts)

| Tool | What it does | Why it's the right pick |
|---|---|---|
| **ElevenLabs** | AI voice cloning + text-to-speech | Clone your own voice and narrate Noah's scripts automatically |
| **Murf AI** | Studio-quality AI voices | Good for professional voiceovers without cloning |
| **Suno / Udio** | AI music generation | Background music for reels that isn't copyright-flagged |

### Editing & Post-Production

| Tool | What it does | Why it's the right pick |
|---|---|---|
| **CapCut API** | Programmatic video editing, auto-captions, templates | Best for auto-captioning Noah's scripts at scale |
| **Descript** | AI-powered video editing via transcript | Edit video like a doc — great for talking head content |
| **Opus Clip** | Auto-clip long video into short-form content | Feed a long video → Opus finds the viral moments → outputs Reels/Shorts |

---

## Recommended Full Stack for Viral Content Production

```
Noah (CMO) generates:
  → Script + Hook + Concept + Visual Notes

Then feeds into:
  → HeyGen (talking head video from script)
  → ElevenLabs (voice clone for voiceover scripts)
  → Seedance or Runway (cinematic b-roll from visual notes)
  → Ideogram (thumbnail with text)
  → CapCut (auto-captions burned in)
  → Later/Buffer (scheduled posting to Reels + TikTok + LinkedIn)
```

---

## How to Add Keys

Add these to `forge-os/backend/.env.local`:

```env
# Already there — fill these in:
GEMINI_API_KEY=your_gemini_key_here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SECRET_KEY=your_supabase_service_role_key

# Add when ready:
HEYGEN_API_KEY=
ELEVENLABS_API_KEY=
RUNWAY_API_KEY=
SEEDANCE_API_KEY=
LATER_API_KEY=
INSTAGRAM_ACCESS_TOKEN=
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
```

---

## Jarvis ↔ Noah Communication Protocol

When Jarvis receives a goal that involves content, marketing, or messaging, it routes to Noah via the `cmo` agent type. Here's how it works:

1. **Jarvis decomposes the goal** via `/api/jarvis/sovereign/goal`
2. If an intervention has `agent_type: "cmo"`, Jarvis routes to Noah
3. Noah's sub-agents execute the task and return a result
4. Results feed back into Jarvis's task graph and synthesis

### Example Jarvis instruction to Noah:
```json
POST /api/cmo/spawn
{
  "subAgent": "content_angle_scout",
  "goal": "Find the 3 highest-virality content angles for the legal niche on Instagram Reels this week"
}
```

---

## Current Status

| Component | Status |
|---|---|
| cmo.service.ts | Built — Gemini-powered, offline fallback included |
| cmo.ts routes | Built — 6 endpoints registered |
| CMOSystem UI | Built — 4 tabs: Research, Concepts, Scripts, Hook Scorer |
| Jarvis integration | Protocol defined — spawn endpoint live |
| Video generation | Not yet wired — see stack above |
| Content scheduling | Not yet wired — Later/Buffer APIs needed |
| Supabase persistence | Not yet wired — scripts/concepts currently in-memory |

---

## Next Steps for CMO

1. **Add `GEMINI_API_KEY`** to `backend/.env.local` — unlocks all AI features
2. **Wire HeyGen** → feed Noah's scripts directly into video generation
3. **Wire ElevenLabs** → auto-narrate voiceover scripts
4. **Persist to Supabase** → store generated concepts and scripts so they survive restarts
5. **Add content calendar** → schedule concepts across platforms via Later/Buffer API
6. **Wire Seedance or Runway** → generate b-roll from Noah's visual notes per script segment
