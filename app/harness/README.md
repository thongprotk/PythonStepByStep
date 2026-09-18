# app/harness — Python port of cross-harness (Phase 1)

Origin: `/home/bss-group/cross-harness` (TypeScript). A commander session delegates a
one-shot task to a sibling ACP-speaking coding-agent CLI, waits for the turn to finish,
and gets the result back. This port keeps the same split: `harness` never builds the
prompt, decides who reviews whom, or scores anything — that stays with whatever calls
`run_worker_turn` (a route, an MCP tool, a script).

## What's here (Phase 1)

- `protocol.py` — a bidirectional JSON-RPC 2.0 peer over newline-delimited stdio (the
  wire format ACP uses). Handles both directions on one connection because the agent
  can call back into the commander mid-turn (`session/request_permission`).
- `policy.py` — port of `packages/acp-client/src/policy.ts` `decidePermission`.
- `session.py` — port of `packages/acp-client/src/session.ts`: `initialize` ->
  `session/new` -> `session/prompt`, collecting `session/update` into a transcript and
  extracting the final `agent_message_chunk` text.
- `transports.py` — **only `connect_opencode`** is implemented. `opencode acp` speaks
  ACP natively, so (like the TS original) it needs no translation shim.
- `cli.py` — `python -m app.harness.cli run --worker opencode --prompt "..." --cwd .`

All wire shapes (`SessionUpdate.sessionUpdate` discriminator, `StopReason` enum,
`RequestPermissionOutcome` nesting, `PermissionOption.kind` values) were checked against
`@agentclientprotocol/sdk@1.4.0`'s actual `.d.ts` files, not guessed from prose docs —
one online doc source disagreed with the real types and was wrong.

Verified end-to-end against a real `opencode acp` process (see `tests/test_harness.py`
for the hermetic version using a fake in-process agent over a unix socket, no external
binary required).

## What's NOT here yet

Ported from cross-harness's TS implementation, still open:

- **claude/codex/cursor transports.** `claude` needs spawning the
  `@agentclientprotocol/claude-agent-acp` bridge (same ndjson stdio as opencode — no
  shim, straightforward). `codex` and `cursor` each need a translation shim (~500 lines
  of TS each in the original: `packages/transports/src/{codex,cursor}-shim/`) because
  neither speaks ACP natively.
- **`collect`** — run the same prompt on several workers in parallel, return an
  anonymized/shuffled list (`--blind` in the original) so a later judge isn't biased by
  identity or launch order.
- **`--isolate`** — run inside a detached git worktree and return a diff instead of
  writing to `cwd` directly.
- **`--keep` / daemon / multi-turn (`xh reply`)** — answering a worker's clarifying
  question on the same live session instead of one-shot turns.
- **preflight** — detect which harnesses are installed + their version/model.
- **MCP exposure** — re-expose `run_worker_turn`/`collect` as MCP tools (mirroring
  `mcp/xh-control`) via `app/mcp_server.py`, so a commander can delegate without
  shelling out to the CLI.

Ask before extending — each of the above is its own scoped chunk of work, not a
one-line add.
