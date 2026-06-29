# FORGE System Environment Configuration

## Supabase Configuration
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_supabase_publishable_key
SUPABASE_SERVICE_KEY=your_supabase_service_role_key
DATABASE_URL=
```

## Redis Configuration
```
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=
```

## Company Settings
```
COMPANY_NAME=Virel Automation
PRIMARY_OFFER=Lead Generation
TARGET_VERTICALS=HVAC,Real Estate Agents,Digital Marketing Agencies
REVENUE_TARGET_MRR=15000000
REVENUE_TARGET_MONTHS=7
```

## Gemini AI Models (Google GenAI)
```
GEMINI_API_KEY=
GEMINI_MODEL_DEFAULT=gemini-1.5-flash
GEMINI_MODEL_REASONING=gemini-1.5-flash
GEMINI_MODEL_EMBEDDINGS=models/text-embedding-004

# Executive key assignments
# Jarvis   -> CEO / orchestrator
# Damien   -> CTO / systems
# Noah     -> CMO / outreach copy
# Zoya     -> CFO / analytics
# Devan    -> Lead generation
# Akhil    -> Lead management
# King     -> AI training / governance
GEMINI_API_KEY_JARVIS=
GEMINI_API_KEY_DAMIEN=
GEMINI_API_KEY_NOAH=
GEMINI_API_KEY_ZOYA=
GEMINI_API_KEY_DEVAN=
GEMINI_API_KEY_AKHIL=
GEMINI_API_KEY_KING=
```

## Gmail / Google OAuth Configuration
```
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
GMAIL_REFRESH_TOKEN=
GMAIL_SENDER_EMAIL=
GMAIL_DAILY_SEND_CAP_PER_ACCOUNT=100
GOOGLE_OAUTH_CLIENT_FILE=C:/Users/Marilyn/Downloads/AI OS/credentials/google-oauth-client.json
GOOGLE_SERVICE_ACCOUNT_FILE=C:/Users/Marilyn/Downloads/AI OS/credentials/google-service-account.json
```

## Slack Configuration
```
SLACK_BOT_TOKEN=
SLACK_CHANNEL_ID=
```

## Notion Configuration
```
NOTION_API_KEY=
NOTION_DATABASE_ID=
```

## Hugging Face Configuration
```
HF_TOKEN=
HF_REPO_ID=
HF_BASE_MODEL=mistralai/Mistral-7B-Instruct-v0.2
```

## Additional API Keys
```
ANTHROPIC_API_KEY=
APOLLO_API_KEY=
APIFY_API_TOKEN=
APIFY_DEFAULT_ACTOR_ID=
SERPER_API_KEY=
```
