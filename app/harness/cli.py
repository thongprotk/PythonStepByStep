"""Minimal CLI to exercise the harness end-to-end, mirroring cross-harness's
`xh run --worker <name> --prompt "..." <cwd>` (single-shot, no --keep/--watch/--isolate
yet — see app/harness/README.md).

Usage:
    .venv/bin/python -m app.harness.cli run --worker opencode --prompt "..." --cwd .
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.harness.session import WorkerTimeoutError, run_worker_turn
from app.harness.transports import connect_opencode
from app.harness.types import PermissionMode

_CONNECTORS = {"opencode": connect_opencode}


async def _run(worker: str, cwd: str, prompt: str, mode: PermissionMode, timeout_s: float | None) -> int:
    connector = _CONNECTORS.get(worker)
    if connector is None:
        print(
            f"worker {worker!r} not implemented yet — only {sorted(_CONNECTORS)} "
            "are ported (see app/harness/README.md)",
            file=sys.stderr,
        )
        return 1
    connection = await connector(cwd)
    try:
        result = await run_worker_turn(connection, cwd, prompt, mode, timeout_s)
    except WorkerTimeoutError as exc:
        print(json.dumps({"outcome": "timeout", "error": str(exc)}))
        return 1
    print(
        json.dumps(
            {"outcome": "ok", "stopReason": result.stop_reason, "responseText": result.response_text}
        )
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.harness.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--worker", required=True, choices=sorted(_CONNECTORS))
    run_parser.add_argument("--prompt", required=True)
    run_parser.add_argument("--cwd", default=".")
    run_parser.add_argument("--mode", default="read-only", choices=["read-only", "read-write"])
    run_parser.add_argument("--timeout", type=float, default=None, help="seconds")

    args = parser.parse_args()
    if args.command == "run":
        exit_code = asyncio.run(_run(args.worker, args.cwd, args.prompt, args.mode, args.timeout))
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
