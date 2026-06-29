# FORGE INTELLIGENCE SYSTEM — CODEX BUILD PROMPT
# Paste this into Codex as your project system prompt.
# Review before pasting — sections marked FLAG FOR JF are notes for Jace to act on.
# ═══════════════════════════════════════════════════════════════════════════════


## WHAT YOU ARE BUILDING

You are completing and connecting the FORGE Intelligence System — a dual-purpose backend serving two products simultaneously:

**FORGE Outreach Agent** handles the full B2B cold email lifecycle for Aikiaa Ops Forge. It manages leads imported from Apollo or CSV, generates AI-personalised email drafts using Gemini, tracks campaign execution through a 14-day plan, logs every email event (sent, opened, replied, meeting booked, bounced), and computes a 0-100 campaign rating across four axes: reply rate (40%), conversion rate (35%), volume completion (15%), and deliverability (10%).

**Jarvis** is a domain-specialised AI assistant built on a fine-tuned Mistral-7B model. It maintains per-user long-term memory via vector embeddings (pgvector/HNSW), runs a continual learning pipeline that curates conversation data into HuggingFace training examples, and uses a segregation agent to score and filter training data before it reaches the model. Jarvis powers the Nimera product targeting real estate agents.

Both systems share one Supabase PostgreSQL database (two schemas: `outreach` and `jarvis`), one Upstash Redis instance for session state and caching, and one FastAPI backend.


## TECH STACK

The backend is Python 3.11+ with FastAPI and Uvicorn. The database is Supabase (PostgreSQL 15 with pgvector extension). The cache and message queue is Upstash Redis (accessed via redis-py with SSL). Email generation uses Google Gemini 1.5 Flash. Vector embeddings use Gemini's text-embedding-004 model (768 dimensions). Gmail API handles email draft creation. HuggingFace Hub stores trained model versions. Slack SDK handles meeting-booked notifications. All secrets are loaded from .env via pydantic-settings — never hardcoded.


## PROJECT STRUCTURE

Every file in the project has been scaffolded. Your job is to complete stubs, wire integrations, and ensure everything runs end-to-end.

```
forge_system/
├── main.py                         # FastAPI app — all routers mounted here
├── config.py                       # Pydantic settings — reads from .env
├── requirements.txt                # All Python dependencies
├── .env                            # NOT committed — see .env.example
│
├── database/
│   ├── supabase.py                 # db() and db_public() clients
│   └── redis_client.py             # All Redis key patterns — session, cache, stream, rate limit
│
├── models/
│   ├── outreach.py                 # Pydantic schemas: Lead, Campaign, Draft, Event, Rating
│   └── jarvis.py                   # Pydantic schemas: Message, Memory, Feedback, TrainingRun
│
├── routers/
│   ├── leads.py                    # CRUD + CSV import + status updates
│   ├── campaigns.py                # CRUD + plan generation + goals + AI draft generation
│   ├── drafts.py                   # CRUD + approve + send
│   ├── events.py                   # Event logging + dashboard
│   └── jarvis.py                   # Chat + WebSocket + memory + feedback + training pipeline
│
├── services/
│   ├── rating.py                   # COMPLETE — 4-axis rating engine with diagnostics
│   ├── email_generator.py          # COMPLETE — Gemini draft generation with ICP pain map
│   ├── segregation_agent.py        # COMPLETE — training data curation agent
│   ├── gmail.py                    # STUB — needs OAuth token exchange wired
│   ├── slack_notifier.py           # STUB — needs Slack bot token wired
│   └── notion.py                   # STUB — Notion database sync (low priority)
│
├── agents/
│   ├── jarvis_agent.py             # COMPLETE — full conversation loop with memory
│   └── forge_agent.py              # STUB — orchestration agent for campaign automation
│
├── utils/
│   └── embeddings.py               # COMPLETE — embed_text, retrieve_memories, store_memory
│
└── migrations/
    └── 001_full_schema.sql         # COMPLETE — run this in Supabase SQL Editor first
```


## WHAT IS COMPLETE (DO NOT REWRITE)

The following files contain production-ready logic. Read them for context but do not modify unless there is a bug:

`services/rating.py` — The four-axis rating formula, letter grade thresholds, per-axis diagnostics, and recommended actions are tuned and tested. Do not change the weight distribution (0.45/0.35/0.15/0.10).

`services/email_generator.py` — The ICP pain map for legal, ecommerce, and fintech segments is the core IP of the FORGE product. The prompt structure enforces the Straight Line method. Do not add placeholder fields or soften the tone instructions.

`agents/jarvis_agent.py` — The full conversation loop: Redis session → Redis message buffer → semantic memory retrieval → prompt construction → Gemini generation → inference cache → Supabase persistence → Redis update. Preserves the correct async flow.

`utils/embeddings.py` — embed_text checks Redis cache before every API call. This is a cost and latency control. Do not remove the cache check.

`database/redis_client.py` — All Redis key namespaces and TTLs are intentional. The TTL on session state (7200s), message buffer (86400s), and embedding cache (259200s) are calibrated to the product's usage patterns.

`migrations/001_full_schema.sql` — All tables, indexes (including the HNSW vector index and partial indexes), and Postgres functions are defined here. Run this exactly once in Supabase. Do not alter the schema without understanding the downstream index implications.


## WHAT NEEDS TO BE BUILT (YOUR JOB)

### Priority 1 — Required for basic operation

**`services/gmail.py`** must implement three functions:
- `create_draft(to_email, subject, body)` — creates a Gmail draft and returns the draft ID. Use the Gmail API v1 with OAuth2 credentials loaded from config (client_id, client_secret, refresh_token). The refresh token is obtained once via the OAuth flow and stored in .env permanently.
- `send_draft(gmail_draft_id)` — sends an existing Gmail draft by ID.
- `list_sent(limit)` — returns recent sent messages for sync.

Wire `create_draft` into `routers/drafts.py` at the `POST /drafts/` endpoint so that every saved draft is simultaneously created in Gmail. Store the returned `gmail_draft_id` on the database row.

**`services/slack_notifier.py`** must implement one function:
- `notify_meeting_booked(lead_name, company, campaign_name)` — posts a formatted Slack message to the configured channel ID using the Slack WebClient with the bot token from config.

Wire this into `routers/events.py` inside `log_event` when `event_type == "meeting_booked"`.

**`database/__init__.py`** and **`database/supabase.py __init__`** — add empty `__init__.py` files to `database/`, `models/`, `routers/`, `services/`, `agents/`, `utils/` so Python treats them as packages.

### Priority 2 — Required for Jarvis to work fully

**`agents/forge_agent.py`** should implement an orchestration function `run_campaign_cycle(campaign_id)` that: fetches the active plan, identifies which steps are due today based on the current date vs start_date, fetches the appropriate batch of leads, calls `generate_drafts_batch`, saves the drafts, and returns a summary. This is the automation layer that makes campaigns run without manual triggers.

**`routers/jarvis.py` training status endpoint** should be upgraded to use FastAPI's `StreamingResponse` with Server-Sent Events so the frontend can receive live training status updates. The current implementation returns only the latest run. Replace it with an async generator that polls `jarvis.training_runs` every 5 seconds and yields the status as SSE events.

### Priority 3 — Complete the stubs

**`services/notion.py`** — implement `sync_lead_to_notion(lead)` using the Notion API client. This writes a new page to the configured Notion database ID with lead properties. Called optionally from the leads router after a lead is created.

**`services/slack_notifier.py`** — add a second function `notify_campaign_rating(campaign_name, score, grade, weakest_axis)` for the Day 7 and Day 14 rating checkpoint notifications.


## CONVENTIONS — FOLLOW THESE THROUGHOUT

All database operations go through the service layer. Routers call service functions; service functions call `db()`. Routers never call `db()` directly. This is already partially broken in the router stubs for brevity — refactor to the correct pattern if you see it.

Every router function has a clear docstring explaining what it does, its inputs, its outputs, and which service it delegates to.

All async operations use `async def` and `await`. Supabase's Python client is synchronous — wrap blocking calls in `asyncio.to_thread()` if you need to call them from an async context without blocking the event loop.

The `.env` file is never committed. An `.env.example` file with all keys and empty values must exist at the project root. Create it if it is missing.

Error handling: every endpoint that touches the database must handle the case where the resource is not found and raise `HTTPException(404)`. Every endpoint that creates a resource must check for duplicates and raise `HTTPException(409)`.

Logging: use Python's standard `logging` module. Every significant operation (campaign created, draft generated, event logged, segregation cycle run) must emit an INFO log. Errors must emit an ERROR log with the exception.


## DATABASE MIGRATION — RUN FIRST

Before writing any code, run `migrations/001_full_schema.sql` in the Supabase SQL Editor (Dashboard → SQL Editor → New query → paste → Run). This creates both schemas, all tables, all indexes including the HNSW vector index and the partial indexes, and the three Postgres functions (`match_memories`, `bump_memory_access`, `next_sequence`). The application will fail to start if these do not exist.

After running the migration, verify in the Supabase Table Editor that you can see tables under both the `outreach` and `jarvis` schemas.


## API ENDPOINT REFERENCE

These are all currently implemented endpoints. Use these as the contract when building the frontend or connecting integrations.

```
GET  /                              Health check
GET  /health/

# Leads
POST /leads/                        Create single lead
POST /leads/batch/                  Bulk JSON import
POST /leads/import-csv/             CSV file upload
GET  /leads/                        List with filters (industry, city, status)
PUT  /leads/{id}/status/            Update lead status

# Campaigns
POST /campaigns/                    Create campaign + default goals
GET  /campaigns/                    List campaigns
GET  /campaigns/{id}/               Campaign detail
GET  /campaigns/{id}/rating/        Computed rating + diagnosis
POST /campaigns/{id}/plans/         Generate 14-day plan
GET  /campaigns/{id}/plans/         Get active plan
PUT  /campaigns/{id}/plans/steps/{n}/ Mark step complete
POST /campaigns/{id}/goals/         Set goals
GET  /campaigns/{id}/goals/         Goal progress
POST /campaigns/{id}/drafts/generate/ AI bulk draft generation

# Drafts
POST /drafts/                       Save draft manually
GET  /drafts/                       List by campaign or status
PUT  /drafts/{id}/                  Edit draft
POST /drafts/{id}/approve/          Approve for sending
POST /drafts/{id}/send/             Mark sent + log event

# Events
POST /events/                       Log event (updates metrics + rating)
GET  /events/dashboard/             Aggregate across all active campaigns

# Jarvis
POST /jarvis/chat/                  Send message, get response
WS   /jarvis/chat/ws/{session_id}   WebSocket real-time chat
POST /jarvis/memory/                Store a long-term memory
POST /jarvis/memory/search/         Semantic memory search
GET  /jarvis/memory/{user_id}/      List user memories
DELETE /jarvis/memory/{id}/         Delete a memory
POST /jarvis/feedback/              Submit feedback on a response
POST /jarvis/training/segregate/    Manually trigger segregation cycle
GET  /jarvis/training/examples/     List curated training examples
GET  /jarvis/training/runs/         Training run history
GET  /jarvis/training/status/       Latest training run status (upgrade to SSE)
```


## ══════════════════════════════════════════════════════
## FLAG FOR JF — FRONTEND REQUIREMENTS
## ══════════════════════════════════════════════════════
##
## The following frontend components need to be built to connect
## with the backend. The backend endpoints are ready. These are
## the UI components that do not yet exist.
##
## CRITICAL (needed for day-one use):
##
## 1. CAMPAIGN DASHBOARD PAGE
##    Connect to: GET /events/dashboard/
##    Displays: active campaign count, total sent/replies/meetings,
##    overall reply rate, per-campaign rating cards with grade badges
##    (S/A/B/C/F colour coded), weakest axis indicator per card.
##
## 2. DRAFT REVIEW QUEUE
##    Connect to: GET /drafts/?status=draft, PUT /drafts/{id}/, POST /drafts/{id}/approve/
##    This is the most important UI in the whole system. Shows each generated
##    draft with the lead's name, company, subject line, and body. Jace reviews,
##    edits inline, approves or rejects. Bulk approve button for when a batch
##    looks good. This is where AI-generated content gets human review before
##    it touches a real inbox.
##
## 3. LEAD IMPORT PAGE
##    Connect to: POST /leads/import-csv/, POST /leads/batch/
##    File drag-and-drop for CSV upload. Paste-as-JSON option. Preview table
##    showing the first 5 rows before import is confirmed. Import result
##    summary (X created, Y skipped as duplicates).
##
## 4. CAMPAIGN BUILDER
##    Connect to: POST /campaigns/, POST /campaigns/{id}/goals/, POST /campaigns/{id}/plans/
##    Three-step form: (1) name and segment selection, (2) goal configuration
##    with editable targets, (3) confirm and launch which calls all three
##    endpoints in sequence. Show the generated plan after launch.
##
## IMPORTANT (needed for Jarvis to be usable):
##
## 5. JARVIS CHAT WINDOW
##    Connect to: WS /jarvis/chat/ws/{session_id}
##    Standard chat UI with user bubbles on the right, Jarvis on the left.
##    Session ID generated client-side (UUID). Shows memory_retrieved count
##    as a subtle indicator when memories influenced the response.
##
## 6. MEMORY BROWSER
##    Connect to: GET /jarvis/memory/{user_id}/, DELETE /jarvis/memory/{id}/,
##    POST /jarvis/memory/search/
##    Table view of all stored memories with type, importance score, access count.
##    Search bar that calls the semantic search endpoint. Delete button per row.
##
## LOWER PRIORITY (can be deferred):
##
## 7. TRAINING PIPELINE STATUS PAGE
##    Connect to: GET /jarvis/training/runs/, GET /jarvis/training/status/ (SSE)
##    Shows training run history with status badges, example count, validation
##    loss, model version. Live status indicator for the current run using SSE.
##
## 8. GOAL PROGRESS CARDS
##    Connect to: GET /campaigns/{id}/goals/
##    Per-campaign goal tracker with progress bars. On Track (green) /
##    At Risk (amber) / Behind (red) status labels.
##
## 9. PLAN TIMELINE
##    Connect to: GET /campaigns/{id}/plans/, PUT /campaigns/{id}/plans/steps/{n}/
##    Visual 14-day timeline with each step, its batch size, and a checkbox
##    to mark it done. Shows current day highlighted.
##
## ══════════════════════════════════════════════════════


## BUILD ORDER

If you are starting from scratch, execute in this order to always have a running state:

1. Create all `__init__.py` files in every package directory.
2. Create `.env.example` with all keys from config.py listed with empty values.
3. Run `migrations/001_full_schema.sql` in Supabase.
4. Verify `pip install -r requirements.txt` completes without errors.
5. Run `uvicorn main:app --reload` and confirm `GET /` returns the health check.
6. Implement `services/gmail.py` and wire it into the drafts router.
7. Implement `services/slack_notifier.py` and wire it into the events router.
8. Test the full lead → campaign → draft → event → rating loop end to end.
9. Test Jarvis chat via `POST /jarvis/chat/` with a test session.
10. Run segregation manually via `POST /jarvis/training/segregate/` and verify examples appear.
