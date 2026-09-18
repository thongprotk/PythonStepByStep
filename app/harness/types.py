from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

PermissionMode = Literal["read-only", "read-write"]
TranscriptKind = Literal["session_update", "prompt_response", "permission_request", "permission_decision"]


@dataclass
class TranscriptEntry:
    at: str
    kind: TranscriptKind
    payload: Any


@dataclass
class WorkerTurnResult:
    transcript: list[TranscriptEntry]
    response_text: str
    stop_reason: str
