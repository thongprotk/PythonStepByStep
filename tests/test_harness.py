"""Hermetic tests for app/harness — no real opencode/claude/codex/cursor binary
needed. A fake in-process ACP agent talks JSON-RPC over a unix socket, matching
the wire shapes verified against @agentclientprotocol/sdk@1.4.0's real type
declarations (see app/harness/README.md)."""

from __future__ import annotations

import asyncio
import os
import tempfile

from app.harness.policy import decide_permission
from app.harness.protocol import JsonRpcPeer
from app.harness.session import WorkerTimeoutError, run_worker_turn
from app.harness.transports import TransportConnection


class _FakeProcess:
    """Duck-types the subset of asyncio.subprocess.Process that TransportConnection.kill()
    and WorkerSession.close() touch, without spawning a real OS process."""

    def __init__(self) -> None:
        self.returncode: int | None = None
        self._killed = asyncio.Event()

    def kill(self) -> None:
        self.returncode = -9
        self._killed.set()

    async def wait(self) -> int:
        await self._killed.wait()
        return self.returncode  # type: ignore[return-value]


async def _run_fake_agent(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, *, stop_reason: str) -> None:
    peer = JsonRpcPeer(reader, writer)

    async def handle_initialize(_params: dict) -> dict:
        return {"protocolVersion": 1, "agentCapabilities": {}}

    async def handle_new_session(_params: dict) -> dict:
        return {"sessionId": "sess-1"}

    async def handle_prompt(_params: dict) -> dict:
        await peer.notify(
            "session/update",
            {
                "sessionId": "sess-1",
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": "pong"},
                },
            },
        )
        return {"stopReason": stop_reason}

    peer.on_request("initialize", handle_initialize)
    peer.on_request("session/new", handle_new_session)
    peer.on_request("session/prompt", handle_prompt)
    await asyncio.sleep(3600)  # stay alive until the test cancels this task


async def _connect_fake_agent(socket_path: str, stop_reason: str = "end_turn") -> TransportConnection:
    agent_task_holder: dict[str, asyncio.Task] = {}

    async def on_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        agent_task_holder["task"] = asyncio.create_task(_run_fake_agent(reader, writer, stop_reason=stop_reason))

    server = await asyncio.start_unix_server(on_client, path=socket_path)
    reader, writer = await asyncio.open_unix_connection(socket_path)

    # give the server's accept callback a tick to register the agent task
    await asyncio.sleep(0.05)

    process = _FakeProcess()
    original_kill = process.kill

    def kill_and_stop_server() -> None:
        original_kill()
        server.close()
        task = agent_task_holder.get("task")
        if task is not None:
            task.cancel()

    process.kill = kill_and_stop_server  # type: ignore[method-assign]
    return TransportConnection(reader=reader, writer=writer, process=process)  # type: ignore[arg-type]


def _socket_path() -> str:
    return os.path.join(tempfile.mkdtemp(), "acp-fake.sock")


def test_run_worker_turn_returns_agent_message_text() -> None:
    async def scenario() -> None:
        connection = await _connect_fake_agent(_socket_path())
        result = await run_worker_turn(connection, "/tmp", "ping", "read-only")
        assert result.response_text == "pong"
        assert result.stop_reason == "end_turn"
        assert any(entry.kind == "session_update" for entry in result.transcript)

    asyncio.run(scenario())


def test_run_worker_turn_times_out_on_a_hanging_prompt() -> None:
    async def scenario() -> None:
        socket_path = _socket_path()

        async def hang_forever(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            peer = JsonRpcPeer(reader, writer)
            peer.on_request("initialize", lambda _p: _resolve({"protocolVersion": 1}))
            peer.on_request("session/new", lambda _p: _resolve({"sessionId": "sess-1"}))
            peer.on_request("session/prompt", lambda _p: asyncio.sleep(3600))
            await asyncio.sleep(3600)

        server = await asyncio.start_unix_server(hang_forever, path=socket_path)
        reader, writer = await asyncio.open_unix_connection(socket_path)
        await asyncio.sleep(0.05)
        process = _FakeProcess()
        original_kill = process.kill

        def kill_and_stop_server() -> None:
            original_kill()
            server.close()

        process.kill = kill_and_stop_server  # type: ignore[method-assign]
        connection = TransportConnection(reader=reader, writer=writer, process=process)  # type: ignore[arg-type]

        try:
            await run_worker_turn(connection, "/tmp", "ping", "read-only", timeout_s=0.2)
            assert False, "expected WorkerTimeoutError"
        except WorkerTimeoutError:
            pass

    asyncio.run(scenario())


async def _resolve(value: dict) -> dict:
    return value


def test_decide_permission_read_only_prefers_reject_once() -> None:
    options = [
        {"optionId": "allow-1", "name": "Allow", "kind": "allow_once"},
        {"optionId": "reject-1", "name": "Reject", "kind": "reject_once"},
    ]
    decision = decide_permission("read-only", options)
    assert decision == {"outcome": {"outcome": "selected", "optionId": "reject-1"}}


def test_decide_permission_falls_back_to_cancelled_when_no_viable_option() -> None:
    decision = decide_permission("read-only", [{"optionId": "allow-1", "name": "Allow", "kind": "allow_once"}])
    assert decision == {"outcome": {"outcome": "cancelled"}}
