from fastapi.testclient import TestClient

import app.api.routes.docs_tools as docs_tools_route
from app.main import app
from app.tools.doc_retriever import LoadedDoc
from app.tools.doc_scraper import ScrapedDoc

client = TestClient(app)


def test_scrape_rejects_empty_urls():
    response = client.post("/docs/scrape", json={"urls": []})
    assert response.status_code == 422


def test_scrape_success_with_mock(monkeypatch, tmp_path):
    fake_path = tmp_path / "geo-block.md"
    fake_path.write_text("content", encoding="utf-8")

    def fake_scrape_urls(urls, output_dir=None):
        return {
            "saved": [
                ScrapedDoc(url=urls[0], title="Geo Block", path=fake_path)
            ],
            "errors": [],
        }

    monkeypatch.setattr(docs_tools_route.doc_scraper, "scrape_urls", fake_scrape_urls)
    response = client.post(
        "/docs/scrape", json={"urls": ["https://mida.example/geo"]}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["saved"][0]["title"] == "Geo Block"
    assert body["errors"] == []


def test_list_docs_with_mock(monkeypatch, tmp_path):
    fake_path = tmp_path / "geo-block.md"

    monkeypatch.setattr(
        docs_tools_route,
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
    response = client.get("/docs/list")
    assert response.status_code == 200
    body = response.json()
    assert body[0]["title"] == "Geo Block"
    assert body[0]["source"] == "https://mida.example/geo"
