"""Port of cross-harness's packages/acp-client/src/policy.ts decidePermission.

Wire shapes verified against @agentclientprotocol/sdk@1.4.0's real type
declarations (RequestPermissionOutcome / SelectedPermissionOutcome / PermissionOption
in dist/schema/types.gen.d.ts), not guessed from docs.
"""

from __future__ import annotations

from typing import Any

from app.harness.types import PermissionMode

_NO_VIABLE_CHOICE: dict[str, Any] = {"outcome": {"outcome": "cancelled"}}


def _find_by_kind(options: list[dict[str, Any]], kind: str) -> dict[str, Any] | None:
    return next((option for option in options if option.get("kind") == kind), None)


def decide_permission(mode: PermissionMode, options: list[dict[str, Any]]) -> dict[str, Any]:
    """Answers a `session/request_permission` call. NOT a write guarantee — some ACP
    agents (observed: opencode) execute a tool without ever calling this method. Real
    isolation is worktree + OS-level, not ported yet (see app/harness/README.md)."""
    if mode == "read-only":
        preferred = _find_by_kind(options, "reject_once")
        fallback = _find_by_kind(options, "reject_always")
    else:
        preferred = _find_by_kind(options, "allow_once")
        fallback = _find_by_kind(options, "allow_always")

    chosen = preferred or fallback
    if chosen is None:
        return _NO_VIABLE_CHOICE
    return {"outcome": {"outcome": "selected", "optionId": chosen["optionId"]}}
