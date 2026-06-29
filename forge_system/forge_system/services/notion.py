"""
services/notion.py — Notion database sync (optional integration).

Writes lead records to a Notion database after creation so the team has a
live CRM view alongside the FORGE backend. Called optionally from leads router.
Silently skips if notion_api_key or notion_database_id are not set.
"""

import logging
from notion_client import Client
from config import get_settings

logger = logging.getLogger(__name__)


def _client() -> Client:
    return Client(auth=get_settings().notion_api_key)


def _is_configured() -> bool:
    s = get_settings()
    return bool(s.notion_api_key and s.notion_database_id)


async def sync_lead_to_notion(lead: dict) -> dict:
    """
    Create a Notion page for a lead in the configured database.

    Maps FORGE lead fields to Notion properties. Non-configured fields
    (role, city, industry) fall back to empty strings to avoid Notion
    validation errors on missing select options.

    Returns the created page metadata or {"skipped": True} if unconfigured.
    """
    if not _is_configured():
        logger.debug("Notion not configured — skipping lead sync for %s", lead.get("email"))
        return {"skipped": True}

    s = get_settings()
    properties = {
        "Name":     {"title":     [{"text": {"content": lead.get("name", "")}}]},
        "Company":  {"rich_text": [{"text": {"content": lead.get("company", "")}}]},
        "Email":    {"email": lead.get("email", "")},
        "Role":     {"rich_text": [{"text": {"content": lead.get("role") or ""}}]},
        "City":     {"rich_text": [{"text": {"content": lead.get("city") or ""}}]},
        "Industry": {"select":    {"name": lead.get("industry") or "other"}},
        "Status":   {"select":    {"name": lead.get("status") or "new"}},
        "Source":   {"select":    {"name": lead.get("source") or "manual"}},
    }

    try:
        page = _client().pages.create(
            parent={"database_id": s.notion_database_id},
            properties=properties,
        )
        notion_id = page["id"]
        logger.info("Notion: synced lead %s @ %s → page %s", lead.get("name"), lead.get("company"), notion_id)
        return {"notion_page_id": notion_id, "url": page.get("url", "")}
    except Exception as e:
        logger.error("Notion sync failed for %s: %s", lead.get("email"), e)
        return {"error": str(e)}


async def update_lead_status_in_notion(notion_page_id: str, new_status: str) -> dict:
    """Update the Status property on an existing Notion lead page."""
    if not _is_configured() or not notion_page_id:
        return {"skipped": True}
    try:
        _client().pages.update(
            page_id=notion_page_id,
            properties={"Status": {"select": {"name": new_status}}},
        )
        return {"updated": True, "status": new_status}
    except Exception as e:
        logger.error("Notion status update failed for page %s: %s", notion_page_id, e)
        return {"error": str(e)}
