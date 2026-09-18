"""Spawns a sibling coding-agent CLI and exposes its stdio as an ACP JSON-RPC
transport. Only the opencode transport is implemented here — it speaks ACP
natively (`opencode acp`), so it needed no translation shim, unlike claude/codex/
cursor in the original TS repo (see app/harness/README.md, Phase 1 scope note).
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

WORKER_SESSION_ENV_VAR = "XH_WORKER_SESSION"


@dataclass
class TransportConnection:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    process: asyncio.subprocess.Process

    def kill(self) -> None:
        if self.process.returncode is None:
            self.process.kill()


async def connect_opencode(cwd: str) -> TransportConnection:
    """Matches cross-harness's packages/transports/src/opencode.ts connectOpencode."""
    env = {**os.environ, WORKER_SESSION_ENV_VAR: "1"}
    process = await asyncio.create_subprocess_exec(
        "opencode",
        "acp",
        cwd=cwd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=None,  # inherit — matches the TS transport's stdio: [pipe, pipe, "inherit"]
        env=env,
    )
    assert process.stdin is not None and process.stdout is not None
    return TransportConnection(reader=process.stdout, writer=process.stdin, process=process)
