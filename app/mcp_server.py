"""MCP stdio server exposing this project's docs/mida-assistant tools
directly (no HTTP round trip) to MCP-aware clients — Claude Code, opencode,
Claude Desktop, or any other MCP host.

Run directly:  .venv/bin/python -m app.mcp_server
Registered for auto-discovery in `.mcp.json` at the project root.

Thin adapter only — the actual logic lives in app/mcp_tools.py so it stays
unit-testable without an MCP session.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from app.mcp_tools import ask_mida_assistant, list_docs, scrape_doc

mcp = MCPServer(
    name="py-mida-tools",
    instructions=(
        "Tools backing the MIDA fraud-app support bot: scrape_doc saves a "
        "URL's content as Markdown under docs/, list_docs shows what's been "
        "scraped, and ask_mida_assistant answers a fraud/bot-blocking "
        "support question, auto-grounded from docs/."
    ),
)

mcp.tool()(scrape_doc)
mcp.tool()(list_docs)
mcp.tool()(ask_mida_assistant)


if __name__ == "__main__":
    mcp.run()
