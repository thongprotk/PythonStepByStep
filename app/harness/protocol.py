"""JSON-RPC 2.0 over newline-delimited stdio — the wire format the Agent Client
Protocol (https://agentclientprotocol.com) uses between a commander and a worker
coding agent.

Bidirectional by design: a client-initiated call (e.g. `session/prompt`) can
have the agent call back into the client mid-flight (e.g.
`session/request_permission`), so both directions run through the same
JsonRpcPeer rather than a simple request/response helper.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable

RequestHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
NotificationHandler = Callable[[dict[str, Any]], Awaitable[None]]


class RpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


class JsonRpcPeer:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._reader = reader
        self._writer = writer
        self._next_id = 1
        self._pending: dict[int, asyncio.Future] = {}
        self._request_handlers: dict[str, RequestHandler] = {}
        self._notification_handlers: dict[str, NotificationHandler] = {}
        self._closed = False
        self._reader_task = asyncio.create_task(self._read_loop())

    def on_request(self, method: str, handler: RequestHandler) -> None:
        self._request_handlers[method] = handler

    def on_notification(self, method: str, handler: NotificationHandler) -> None:
        self._notification_handlers[method] = handler

    async def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        msg_id = self._next_id
        self._next_id += 1
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = future
        await self._send({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}})
        try:
            return await future
        finally:
            self._pending.pop(msg_id, None)

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        await self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    async def _send(self, message: dict[str, Any]) -> None:
        line = json.dumps(message) + "\n"
        self._writer.write(line.encode("utf-8"))
        await self._writer.drain()

    async def _read_loop(self) -> None:
        try:
            while True:
                raw = await self._reader.readline()
                if not raw:
                    break
                line = raw.strip()
                if not line:
                    continue
                message = json.loads(line)
                asyncio.create_task(self._dispatch(message))
        except asyncio.CancelledError:
            pass
        finally:
            self._fail_pending(RpcError(-32000, "connection closed"))

    def _fail_pending(self, error: Exception) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_exception(error)

    async def _dispatch(self, message: dict[str, Any]) -> None:
        if "method" in message and "id" in message:
            await self._handle_incoming_request(message)
        elif "method" in message:
            await self._handle_incoming_notification(message)
        elif "id" in message:
            self._handle_response(message)

    async def _handle_incoming_request(self, message: dict[str, Any]) -> None:
        method = message["method"]
        handler = self._request_handlers.get(method)
        if handler is None:
            await self._send(
                {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "error": {"code": -32601, "message": f"method not found: {method}"},
                }
            )
            return
        try:
            result = await handler(message.get("params") or {})
            await self._send({"jsonrpc": "2.0", "id": message["id"], "result": result})
        except Exception as exc:  # noqa: BLE001 - must always answer the peer, even on a handler bug
            await self._send(
                {"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32000, "message": str(exc)}}
            )

    async def _handle_incoming_notification(self, message: dict[str, Any]) -> None:
        handler = self._notification_handlers.get(message["method"])
        if handler is not None:
            await handler(message.get("params") or {})

    def _handle_response(self, message: dict[str, Any]) -> None:
        future = self._pending.get(message["id"])
        if future is None or future.done():
            return
        if "error" in message:
            err = message["error"]
            future.set_exception(RpcError(err.get("code", -1), err.get("message", ""), err.get("data")))
        else:
            future.set_result(message.get("result"))

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._reader_task.cancel()
        await asyncio.gather(self._reader_task, return_exceptions=True)
