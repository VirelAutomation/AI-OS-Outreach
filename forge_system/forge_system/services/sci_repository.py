"""Supabase persistence helpers for the SCI runtime."""

from __future__ import annotations

from typing import Any

from database.supabase import db

SCI_TABLES = {
    "world_states": "jarvis.sci_world_states",
    "objective_graphs": "jarvis.sci_objective_graphs",
    "counterfactual_plans": "jarvis.sci_counterfactual_plans",
    "task_allocations": "jarvis.sci_task_allocations",
    "agent_execution_traces": "jarvis.sci_agent_execution_traces",
    "evidence_packages": "jarvis.sci_evidence_packages",
    "policy_decisions": "jarvis.sci_policy_decisions",
    "model_evaluations": "jarvis.sci_model_evaluations",
}


class SciRepository:
    def __init__(self):
        self.client = db()

    def insert(self, table_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.client.table(SCI_TABLES[table_key]).insert(payload).execute().data[0]

    def bulk_insert(self, table_key: str, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not payloads:
            return []
        return self.client.table(SCI_TABLES[table_key]).insert(payloads).execute().data or []

    def list_latest(self, table_key: str, limit: int = 20, **filters: Any) -> list[dict[str, Any]]:
        query = self.client.table(SCI_TABLES[table_key]).select("*")
        for key, value in filters.items():
            if value is not None:
                query = query.eq(key, value)
        return query.order("created_at", desc=True).limit(limit).execute().data or []

    def latest_one(self, table_key: str, **filters: Any) -> dict[str, Any] | None:
        rows = self.list_latest(table_key, limit=1, **filters)
        return rows[0] if rows else None

    def update_by_id(self, table_key: str, id_field: str, row_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        data = (
            self.client.table(SCI_TABLES[table_key])
            .update(payload)
            .eq(id_field, row_id)
            .execute()
            .data
        )
        return data[0] if data else None

    def update_where(self, table_key: str, payload: dict[str, Any], **filters: Any) -> dict[str, Any] | None:
        query = self.client.table(SCI_TABLES[table_key]).update(payload)
        for key, value in filters.items():
            query = query.eq(key, value)
        data = query.execute().data
        return data[0] if data else None
