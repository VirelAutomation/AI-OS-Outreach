"""
config.py - single source of truth for backend configuration.

Canonical behavior:
- Read `.env` from the project root first.
- Fall back to local package `.env` only for convenience.
- Fail fast when core infrastructure secrets are missing.
- Keep optional integrations disabled unless explicitly configured.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
ENV_FILES = (
    str(PROJECT_DIR / '.env'),
    str(PROJECT_DIR / '.env.local'),
    str(PACKAGE_DIR / '.env'),
    str(PACKAGE_DIR / '.env.local'),
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        extra='ignore',
        env_ignore_empty=True,
    )

    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str
    database_url: str
    redis_url: str
    redis_password: str = ''

    company_name: str = 'Virel Automation'
    revenue_target_mrr: int = 15000000
    revenue_target_months: int = 7

    gemini_api_key: str = ''
    gemini_model_default: str = 'gemini-2.0-flash'
    gemini_model_reasoning: str = 'gemini-2.0-flash'
    gemini_model_embeddings: str = 'models/text-embedding-004'

    gemini_api_key_jarvis: str = ''
    gemini_api_key_damien: str = ''
    gemini_api_key_noah: str = ''
    gemini_api_key_zoya: str = ''
    gemini_api_key_devan: str = ''
    gemini_api_key_akhil: str = ''
    gemini_api_key_king: str = ''

    gmail_client_id: str = ''
    gmail_client_secret: str = ''
    gmail_refresh_token: str = ''
    gmail_sender_email: str = ''
    gmail_daily_send_cap_per_account: int = 20
    google_calendar_id: str = 'primary'
    google_oauth_client_file: str = ''
    google_service_account_file: str = ''

    slack_bot_token: str = ''
    slack_channel_id: str = ''
    notion_api_key: str = ''
    notion_database_id: str = ''
    notion_architecture_page_id: str = ''

    hf_token: str = ''
    hf_repo_id: str = ''
    hf_base_model: str = 'mistralai/Mistral-7B-Instruct-v0.2'
    hf_space_id: str = ''
    anthropic_api_key: str = ''

    linear_api_key: str = ''
    linear_team_id: str = ''
    sentry_dsn: str = ''
    cloudflare_api_token: str = ''
    cloudflare_account_id: str = ''
    cloudflare_zone_id: str = ''

    apollo_api_key: str = ''
    apify_api_token: str = ''
    apify_default_actor_id: str = ''
    serper_api_key: str = ''
    perplexity_api_key: str = ''
    calendly_api_key: str = ''
    landing_page_base_url: str = ''

    cors_allow_origins: str = '*'
    app_env: str = 'development'
    api_secret_key: str = 'change-me-in-production'
    training_quality_threshold: float = 0.70
    training_batch_size: int = 100
    executive_spawn_limit: int = 4
    executive_spawn_depth_limit: int = 2

    @model_validator(mode='after')
    def validate_runtime_guardrails(self):
        if self.app_env.lower() == 'production' and self.api_secret_key == 'change-me-in-production':
            raise ValueError('API_SECRET_KEY must be set to a non-default value in production.')
        if not 0 <= self.training_quality_threshold <= 1:
            raise ValueError('TRAINING_QUALITY_THRESHOLD must be between 0 and 1.')
        if self.executive_spawn_limit < 0:
            raise ValueError('EXECUTIVE_SPAWN_LIMIT must be 0 or greater.')
        if self.executive_spawn_depth_limit < 0:
            raise ValueError('EXECUTIVE_SPAWN_DEPTH_LIMIT must be 0 or greater.')
        if self.revenue_target_mrr <= 0:
            raise ValueError('REVENUE_TARGET_MRR must be greater than 0.')
        if self.revenue_target_months <= 0:
            raise ValueError('REVENUE_TARGET_MONTHS must be greater than 0.')
        if not self.any_gemini_key_configured():
            raise ValueError('At least one Gemini API key must be configured.')
        return self

    def any_gemini_key_configured(self) -> bool:
        return any([
            self.gemini_api_key,
            self.gemini_api_key_jarvis,
            self.gemini_api_key_damien,
            self.gemini_api_key_noah,
            self.gemini_api_key_zoya,
            self.gemini_api_key_devan,
            self.gemini_api_key_akhil,
            self.gemini_api_key_king,
        ])

    def gemini_key_for(self, agent_name: str) -> str:
        alias = (agent_name or '').strip().lower().replace('-', '_').replace(' ', '_')
        alias_map = {
            'ceo': 'jarvis',
            'orchestrator': 'jarvis',
            'cto': 'damien',
            'ops': 'damien',
            'cmo': 'noah',
            'forge': 'noah',
            'cfo': 'zoya',
            'analytics': 'zoya',
            'intel': 'devan',
            'lead_generation': 'devan',
            'lead_management': 'akhil',
            'training': 'king',
            'memory': 'king',
        }
        normalized = alias_map.get(alias, alias)
        key_map = {
            'jarvis': self.gemini_api_key_jarvis,
            'damien': self.gemini_api_key_damien,
            'noah': self.gemini_api_key_noah,
            'zoya': self.gemini_api_key_zoya,
            'devan': self.gemini_api_key_devan,
            'akhil': self.gemini_api_key_akhil,
            'king': self.gemini_api_key_king,
        }
        return key_map.get(normalized) or self.gemini_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
