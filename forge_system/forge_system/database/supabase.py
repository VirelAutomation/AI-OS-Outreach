"""
database/supabase.py

Two clients, one module. The anon client respects Row Level Security
and is safe for user-facing operations. The service client bypasses
all security policies and is for internal agent/backend-only writes.

Never expose the service client to frontend routes.
"""

from functools import lru_cache
from supabase import create_client, Client
from config import get_settings


@lru_cache
def get_anon_client() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_anon_key)


@lru_cache
def get_service_client() -> Client:
    """
    Full admin access — bypasses Row Level Security.
    Use ONLY in server-side service and agent code.
    """
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_key)


# Convenience aliases — import these throughout the codebase
def db() -> Client:
    return get_service_client()


def db_public() -> Client:
    return get_anon_client()
