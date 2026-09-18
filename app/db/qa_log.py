"""Persists each answered /chat or /mida-assistant turn to Supabase (table
`qa_logs`, see supabase/migrations/0002_create_qa_logs.sql) so question/
answer history survives process restarts instead of only living in the
response the caller happened to receive.

Best-effort by design: a failed write must never break the HTTP response
that already succeeded — on any error it falls back to the local error log
(app/core/error_log.py) so the failure is still visible somewhere, then
returns normally.
"""

from __future__ import annotations

from typing import Any

from app.core.error_log import log_error
from app.db.supabase_client import get_supabase

TABLE = "qa_logs"


def log_qa_session(
    endpoint: str,
    user_message: str,
    answer: str,
    extra: dict[str, Any] | None = None,
) -> None:
    try:
        client = get_supabase()
        client.table(TABLE).insert(
            {
                "endpoint": endpoint,
                "user_message": user_message,
                "answer": answer,
                "extra": extra or {},
            }
        ).execute()
    except Exception as exc:  # noqa: BLE001 — logging a QA turn must never break the request
        log_error(
            source=f"qa_log:{endpoint}",
            error=str(exc),
            context={"user_message": user_message},
        )
