# FORGE Outreach OS Blueprint

## Core Goal

FORGE is an AI-led outreach and lead-handling operating system for Virel Automation.

Primary business objective:

- source leads
- enrich leads
- generate personalized cold emails
- send through Gmail
- route interested prospects to a landing page
- qualify them through Jarvis chat
- book calls
- store all signal data in Supabase
- analyze conversion by campaign, segment, landing page, and message pattern

## Key Principle

Generating the email and sourcing the email are different systems.

- Gemini creates the message
- Apify sources and enriches lead data
- Gmail sends
- Jarvis orchestrates
- Supabase stores the operating truth

## Lead Source Stack

### Preferred stack

1. Apify actor layer
2. company website scrape
3. contact pattern inference
4. optional verification pass
5. CRM insert

### Why Apify

Apify is suitable for:

- company discovery
- website extraction
- metadata scraping
- contact-page parsing
- LinkedIn-like enrichment where permitted by the actor flow

Apify alone is not a perfect email verifier. For serious deliverability, add one of:

- NeverBounce
- ZeroBounce
- Hunter verification
- Instantly verification

If that is not available yet, mark leads with `verification_status = unverified` and keep send volume low.

## Multi-System AI Org

### Jarvis

Top-level orchestrator.

Responsibilities:

- receives strategic commands
- delegates to specialist systems
- summarizes company state
- supervises automations
- approves or escalates high-risk actions

### CMO System

Own reasoning space for:

- ICP strategy
- segment planning
- campaign thesis
- subject line variation
- landing-page messaging
- content angle generation
- reply-rate diagnostics

### CTO System

Own reasoning space for:

- API health
- Gmail delivery health
- Supabase integrity
- Redis / queue health
- event logging correctness
- retry, rate-limit, and fail-fast policy
- analytics roots and data integrity

### CEO View

Human strategic cockpit.

Shows:

- pipeline
- cash impact
- campaign ranking
- booked meetings
- system health
- next best move

## Dashboard Information Architecture

### 1. CEO Overview

- revenue target
- weighted pipeline
- booked meetings
- hottest segment
- top campaign
- execution risk alerts

### 2. Jarvis Command

- full chat with Jarvis
- command input
- morning briefing
- strategy mode
- execution mode
- decision log

### 3. Automations

- create automation
- schedule tasks
- assign to Jarvis / CMO / CTO
- trigger conditions
- approval rules
- retry rules
- execution history

### 4. Outreach Pipeline

- lead source status
- enrichment queue
- draft review queue
- approved-to-send queue
- sent / replied / booked states

### 5. Campaign Control

- campaign builder
- plan timeline
- goal tracker
- rating engine
- subject test performance

### 6. CRM and Meetings

- all leads
- all companies
- status transitions
- booked calls
- no-show / converted / lost

### 7. Landing Page Intelligence

- page visits by campaign
- CTA click rate
- chatbot engagement
- meeting-book conversion
- vertical-specific page performance

### 8. Analytics

- reply rate by campaign
- meeting rate by industry
- message pattern performance
- subject line performance
- landing page conversion by segment
- sparse-Merkle / root checkpoint status

### 9. Content

- proof assets
- case studies
- landing-page copy blocks
- email angle library
- offer positioning notes

### 10. CTO Control Room

- Supabase health
- Gmail API health
- Gemini usage state
- Apify actor runs
- queue depth
- failed jobs
- retry history
- alert center

## Outreach Pipeline v1

1. Apify actor discovers or enriches company + contact data
2. lead record stored in Supabase
3. CMO System selects segment and campaign angle
4. Gemini drafts personalized email
5. human reviews draft
6. Gmail draft created
7. Gmail send executes
8. tracking link points to landing page with campaign + lead + draft identifiers
9. visitor lands on page
10. Jarvis / lead-intel alert created
11. chat qualifies visitor
12. meeting request stored
13. CRM + pipeline updated
14. analytics updated

## Required Keys

- Gemini API key
- Gmail OAuth client ID
- Gmail OAuth client secret
- Gmail refresh token
- Gmail sender address
- Supabase URL
- Supabase anon key
- Supabase service key
- direct Postgres URL if using pgvector-heavy workflows
- Redis / Upstash URL
- Redis token if separate
- Apify API token
- landing page base URL

## Immediate Build Priority

1. Apify ingestion service
2. lead enrichment and dedupe
3. Gemini personalization service
4. Gmail draft and send service
5. tracking-link event capture
6. landing-page lead alert
7. draft review queue UI
8. Jarvis command UI
9. automations UI
