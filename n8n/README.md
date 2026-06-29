# Virel Agentic Growth System

This folder holds the versioned n8n workflow source for the AI OS growth stack.

Workflows:

- `workflows/virel_business_intel_harvest.ts`
  - Webhook-driven business search intake.
  - Normalizes search-provider results into phone, email, website, and lead score rows.
  - Persists to the `virel_business_intel` n8n data table.

- `workflows/virel_sci_content_planner.ts`
  - Daily planner that pulls SCI and CRL context from FORGE.
  - Uses `api/jarvis/objectives`, `api/jarvis/brief`, `api/analytics/crl-learning`, and the CMO endpoints.
  - Queues Meta/X content into `virel_social_queue` and writes planning state into `virel_strategy_ledger`.
  - Calls both Hugging Face video and image endpoints so Jarvis can produce mixed-media queue items.

- `workflows/virel_social_publisher.ts`
  - Polls the social queue and publishes due items.
  - Uses the Meta Graph API for Instagram/Facebook and the X node for X posts.

Required n8n credentials:

- `Search Provider API Key`
  - `httpHeaderAuth`
  - Intended for Serper, Maps, Apify proxy, or another search source.

- `Hugging Face Token`
  - `httpBearerAuth`
  - Used for Hugging Face image/video generation calls.

- `Meta Page Token`
  - `facebookGraphApi`
  - Used by the Facebook Graph API node.

- `X OAuth2`
  - `twitterOAuth2Api`
  - Used by the X posting node.

Runtime assumptions:

- `FORGE_API_BASE_URL` is reachable from n8n. If unset, the workflow falls back to `http://host.docker.internal:8000`.
- `JARVIS_SCI_MODE` can override the planner mode. Default is `autonomous`.
- Existing backend endpoints remain:
  - `/api/jarvis/objectives`
  - `/api/jarvis/brief`
  - `/api/analytics/crl-learning`
  - `/api/cmo/research`
  - `/api/cmo/concepts`
  - `/api/cmo/script`

Known gap:

- The Hugging Face inference calls still need a public asset-hosting step if you want generated images/videos to be posted directly by Meta Graph. The current workflows assume a public `media_url` is available to the publisher.

Current Hugging Face defaults used in the workflow source:

- Image: `black-forest-labs/FLUX.1-dev`
- Video: `Wan-AI/Wan2.1-T2V-1.3B-Diffusers`

The n8n personal project used during creation was `Jace Daking <jacepersonalai@gmail.com>`.
