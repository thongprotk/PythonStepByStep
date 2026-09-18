from app.tools import doc_retriever


def _write_doc(dir_path, filename, title, source, body):
    text = f"---\ntitle: {title}\nsource: {source}\nscraped_at: 2026-09-18T00:00:00+00:00\n---\n\n{body}\n"
    (dir_path / filename).write_text(text, encoding="utf-8")


def test_load_docs_parses_front_matter(tmp_path):
    _write_doc(
        tmp_path, "geo-block.md", "Geo Block", "https://mida.example/geo", "Noi dung."
    )
    docs = doc_retriever.load_docs(tmp_path)
    assert len(docs) == 1
    assert docs[0].title == "Geo Block"
    assert docs[0].source == "https://mida.example/geo"
    assert docs[0].content == "Noi dung."


def test_load_docs_missing_dir_returns_empty():
    assert doc_retriever.load_docs(docs_dir="/nonexistent/dir") == []


def test_retrieve_relevant_chunks_ranks_by_keyword_overlap(tmp_path):
    _write_doc(
        tmp_path,
        "geo-block.md",
        "Chan theo IP va khu vuc",
        "https://mida.example/geo",
        "Huong dan chan bot theo quoc gia va thanh pho.",
    )
    _write_doc(
        tmp_path,
        "vpn.md",
        "Chan VPN proxy",
        "https://mida.example/vpn",
        "Phat hien va chan VPN proxy truy cap store.",
    )

    chunks = doc_retriever.retrieve_relevant_chunks(
        "Lam sao chan bot theo quoc gia?", docs_dir=tmp_path, top_k=1
    )
    assert len(chunks) == 1
    assert "Chan theo IP va khu vuc" in chunks[0]


def test_retrieve_relevant_chunks_empty_query_returns_empty(tmp_path):
    assert doc_retriever.retrieve_relevant_chunks("", docs_dir=tmp_path) == []


def test_retrieve_relevant_chunks_no_match_returns_empty(tmp_path):
    _write_doc(
        tmp_path, "geo-block.md", "Geo Block", "https://mida.example/geo", "abc xyz"
    )
    chunks = doc_retriever.retrieve_relevant_chunks(
        "unrelated query zzz", docs_dir=tmp_path
    )
    assert chunks == []
