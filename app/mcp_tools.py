"""Plain-function tool implementations shared by app/mcp_server.py.

Kept free of any `mcp` import so they're testable the same way as a route
handler — monkeypatch `app.mcp_tools.get_llm_client` / `.doc_scraper` /
`.retrieve_relevant_chunks` — without spinning up an MCP session.
"""

from __future__ import annotations

from app.db.qa_log import log_qa_session
from app.llm.mida_prompt import SYSTEM_PROMPT, build_user_content, parse_assistant_reply
from app.llm.provider import get_llm_client
from app.tools import doc_scraper
from app.tools.doc_retriever import load_docs, retrieve_relevant_chunks


def scrape_doc(url: str) -> dict:
    """Fetch one URL, extract its main content, and save it as Markdown under docs/."""
    result = doc_scraper.scrape_urls([url])
    if result["errors"]:
        return {"ok": False, "error": result["errors"][0]["error"]}
    doc = result["saved"][0]
    return {"ok": True, "title": doc.title, "path": str(doc.path)}


def list_docs() -> list[dict]:
    """List every doc currently scraped into docs/ (title, source URL, file path)."""
    return [
        {"title": d.title, "source": d.source, "path": str(d.path)}
        for d in load_docs()
    ]


def ask_mida_assistant(user_message: str) -> dict:
    """Ask the scoped MIDA Assistant persona a fraud/bot-blocking question.

    Auto-grounds from docs/ (populate it with scrape_doc first) and returns
    the same JSON contract as POST /mida-assistant: answer, cited_sources,
    suggested_features, confidence, needs_escalation, in_scope.
    """
    chunks = retrieve_relevant_chunks(user_message)
    content = build_user_content(user_message=user_message, retrieved_chunks=chunks)
    client = get_llm_client()
    raw_reply = client.ask_with_system(SYSTEM_PROMPT, content)
    parsed = parse_assistant_reply(raw_reply)
    log_qa_session(
        "mcp:ask_mida_assistant",
        user_message,
        parsed["answer"],
        extra={
            "confidence": parsed["confidence"],
            "in_scope": parsed["in_scope"],
            "needs_escalation": parsed["needs_escalation"],
        },
    )
    return parsed
