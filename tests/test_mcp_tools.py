import json

from app import mcp_tools
from app.tools.doc_retriever import LoadedDoc
from app.tools.doc_scraper import ScrapedDoc


def test_scrape_doc_success(monkeypatch, tmp_path):
    fake_path = tmp_path / "geo-block.md"
    fake_path.write_text("content", encoding="utf-8")

    monkeypatch.setattr(
        mcp_tools.doc_scraper,
        "scrape_urls",
        lambda urls: {
            "saved": [ScrapedDoc(url=urls[0], title="Geo Block", path=fake_path)],
            "errors": [],
        },
    )
    result = mcp_tools.scrape_doc("https://mida.example/geo")
    assert result == {"ok": True, "title": "Geo Block", "path": str(fake_path)}


def test_scrape_doc_error(monkeypatch):
    monkeypatch.setattr(
        mcp_tools.doc_scraper,
        "scrape_urls",
        lambda urls: {"saved": [], "errors": [{"url": urls[0], "error": "boom"}]},
    )
    result = mcp_tools.scrape_doc("https://mida.example/bad")
    assert result == {"ok": False, "error": "boom"}


def test_list_docs(monkeypatch, tmp_path):
    fake_path = tmp_path / "geo-block.md"
    monkeypatch.setattr(
        mcp_tools,
        "load_docs",
        lambda: [
            LoadedDoc(
                path=fake_path,
                title="Geo Block",
                source="https://mida.example/geo",
                content="...",
            )
        ],
    )
    assert mcp_tools.list_docs() == [
        {
            "title": "Geo Block",
            "source": "https://mida.example/geo",
            "path": str(fake_path),
        }
    ]


def test_ask_mida_assistant(monkeypatch):
    reply = {
        "answer": "Ban bat geo-block o muc Rules.",
        "cited_sources": ["Geo Block"],
        "suggested_features": [],
        "confidence": 0.9,
        "needs_escalation": False,
        "in_scope": True,
    }

    class FakeClient:
        def ask_with_system(self, system, message, model=None):
            assert "Geo Block" in message
            return json.dumps(reply)

    monkeypatch.setattr(
        mcp_tools, "retrieve_relevant_chunks", lambda query: ["[Geo Block] noi dung"]
    )
    monkeypatch.setattr(mcp_tools, "get_llm_client", lambda: FakeClient())

    logged = {}
    monkeypatch.setattr(
        mcp_tools,
        "log_qa_session",
        lambda endpoint, user_message, answer, extra=None: logged.update(
            endpoint=endpoint, user_message=user_message, answer=answer, extra=extra
        ),
    )

    result = mcp_tools.ask_mida_assistant("Geo-block hoat dong the nao?")
    assert result["in_scope"] is True
    assert result["confidence"] == 0.9
    assert logged["endpoint"] == "mcp:ask_mida_assistant"
    assert logged["answer"] == reply["answer"]
