"""Append-only local error log — a lightweight, greppable memory of failures.

Anything that fails outside the normal HTTP error path (right now: a failed
Supabase write in app/db/qa_log.py) gets appended here instead of just
raising/vanishing, so the same error pattern can be looked up and matched
against next time instead of re-debugged from scratch.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "errors.jsonl"


def log_error(
    source: str,
    error: str,
    context: dict[str, Any] | None = None,
    log_path: Path | str = DEFAULT_LOG_PATH,
) -> None:
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": source,
        "error": error,
        "context": context or {},
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def search_errors(
    keyword: str, limit: int = 10, log_path: Path | str = DEFAULT_LOG_PATH
) -> list[dict[str, Any]]:
    """Grep the local error log for `keyword` (case-insensitive, whole entry).

    Check this before treating an error as new — the same Supabase/network
    failure tends to repeat with the same shape.
    """
    log_path = Path(log_path)
    if not log_path.exists():
        return []
    keyword_lower = keyword.lower()
    matches: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        haystack = json.dumps(entry, ensure_ascii=False).lower()
        if keyword_lower in haystack:
            matches.append(entry)
    return matches[-limit:]
