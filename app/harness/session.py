"""Port of cross-harness's packages/acp-client/src/session.ts.

Runs one ACP session against a connected worker: initialize -> session/new ->
session/prompt, answering session/request_permission per policy.decide_permission
and collecting session/update notifications into a transcript.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
from typing import Any

from app.harness.policy import decide_permission
from app.harness.protocol import JsonRpcPeer
from app.harness.transports import TransportConnection
from app.harness.types import PermissionMode, TranscriptEntry, WorkerTurnResult

PROTOCOL_VERSION = 1


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


class WorkerTimeoutError(Exception):
    def __init__(self, timeout_s: float) -> None:
        super().__init__(f"worker turn timed out after {timeout_s}s")


class WorkerSession:
    def __init__(
        self,
        peer: JsonRpcPeer,
        connection: TransportConnection,
        session_id: str,
        entries: list[TranscriptEntry],
    ) -> None:
        self._peer = peer
        self._connection = connection
        self.session_id = session_id
        self._entries = entries

    async def prompt(self, text: str, timeout_s: float | None = None) -> WorkerTurnResult:
        self._entries.clear()
        params = {"sessionId": self.session_id, "prompt": [{"type": "text", "text": text}]}
        coro = self._peer.request("session/prompt", params)
        try:
            if timeout_s is not None:
                response = await asyncio.wait_for(coro, timeout=timeout_s)
            else:
                response = await coro
        except asyncio.TimeoutError as exc:
            self._connection.kill()
            raise WorkerTimeoutError(timeout_s) from exc
        self._entries.append(TranscriptEntry(at=_now(), kind="prompt_response", payload=response))
        return _build_turn_result(self._entries, response.get("stopReason", "end_turn"))

    async def close(self) -> None:
        await self._peer.close()
        self._connection.kill()
        await self._connection.process.wait()


async def open_worker_session(
    connection: TransportConnection, cwd: str, mode: PermissionMode
) -> WorkerSession:
    peer = JsonRpcPeer(connection.reader, connection.writer)
    entries: list[TranscriptEntry] = []

    async def handle_permission(params: dict[str, Any]) -> dict[str, Any]:
        entries.append(TranscriptEntry(at=_now(), kind="permission_request", payload=params))
        decision = decide_permission(mode, params.get("options", []))
        entries.append(TranscriptEntry(at=_now(), kind="permission_decision", payload=decision))
        return decision

    async def handle_update(params: dict[str, Any]) -> None:
        entries.append(TranscriptEntry(at=_now(), kind="session_update", payload=params))

    peer.on_request("session/request_permission", handle_permission)
    peer.on_notification("session/update", handle_update)

    await peer.request(
        "initialize",
        {
            "protocolVersion": PROTOCOL_VERSION,
            "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False}, "terminal": False},
        },
    )
    session_response = await peer.request("session/new", {"cwd": cwd, "mcpServers": []})
    return WorkerSession(peer, connection, session_response["sessionId"], entries)


async def run_worker_turn(
    connection: TransportConnection,
    cwd: str,
    prompt: str,
    mode: PermissionMode,
    timeout_s: float | None = None,
) -> WorkerTurnResult:
    session = await open_worker_session(connection, cwd, mode)
    try:
        return await session.prompt(prompt, timeout_s)
    finally:
        await session.close()


def _build_turn_result(entries: list[TranscriptEntry], stop_reason: str) -> WorkerTurnResult:
    response_text = ""
    for entry in entries:
        if entry.kind != "session_update":
            continue
        update: dict[str, Any] = entry.payload.get("update", {})
        if update.get("sessionUpdate") != "agent_message_chunk":
            continue
        content = update.get("content", {})
        if content.get("type") == "text":
            response_text += content.get("text", "")
    return WorkerTurnResult(transcript=entries, response_text=response_text, stop_reason=stop_reason)
