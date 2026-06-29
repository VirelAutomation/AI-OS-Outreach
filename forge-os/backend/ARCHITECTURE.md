# FORGE OS Backend Architecture

## Goal

FORGE OS backend is a founder-facing AI operating system for:

- generating leads
- enriching leads
- personalizing outbound
- routing prospects to a landing page
- qualifying inbound visitors through Jarvis chat
- booking meetings
- turning booked meetings into CRM and pipeline records
- scoring campaign performance and revenue velocity

## Jarvis Role

Jarvis is the orchestrator, not a free-form superuser.

Jarvis can:

- read CRM state
- inspect campaign performance
- compute analytics roots
- personalize outreach drafts
- qualify inbound chat
- create booking requests
- recommend next actions

Jarvis should not:

- mutate critical records without policy checks
- send outbound blindly
- hold raw secrets in frontend runtime

## Domain Modules

### CRM

- prospects
- companies
- statuses
- lead source

### Outreach

- campaigns
- campaign steps
- events
- personalization
- Gmail send pipeline
- Apollo enrichment pipeline

### Meetings

- booking requests
- scheduled meetings
- outcomes

### Pipeline

- deals
- stage history
- weighted close values

### Analytics

- campaign scoring
- niche performance
- sparse-Merkle-style collection roots
- global root checkpoint

### Content

- case studies
- proof assets
- landing page copy blocks
- future content calendar

## Public Funnel

The public landing page should use:

- `POST /api/public/chat`
- `POST /api/public/bookings`

Flow:

1. visitor lands on page
2. chatbot qualifies them
3. chatbot routes qualified visitor into booking request
4. booking request becomes CRM record + meeting candidate
5. Jarvis surfaces it in founder dashboard

## Suggested Next Build Order

1. run `backend/supabase/schema.v1.sql`, then `backend/supabase/schema.v2.sql`
2. wire backend to Supabase admin key
3. replace mock CRM reads with real tables
4. connect public landing page chat to `/api/public/chat`
5. connect booking widget to `/api/public/bookings`
6. wire Jarvis frontend to `POST /api/jarvis`
7. add Gmail send pipeline
8. add Apollo enrichment pipeline
9. move analytics roots into persisted snapshots
