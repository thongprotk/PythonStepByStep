"""Naive keyword retrieval over the `docs/` folder that `doc_scraper` fills.

This is deliberately NOT a vector/semantic search — the project has no vector
store yet. It exists to close the loop end-to-end (scrape -> save -> retrieve
-> ground an answer) so `/mida-assistant` can auto-populate `retrieved_chunks`
for a chat agent that doesn't want to run its own RAG step. Swap this module
out for real embeddings-based retrieval without touching its callers — the
public contract is just `retrieve_relevant_chunks(query) -> list[str]`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.tools.doc_scraper import DEFAULT_DOCS_DIR

_WORD_RE = re.compile(r"\w+", re.UNICODE)
_FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n\n?(.*)$", re.DOTALL)


@dataclass
class LoadedDoc:
    path: Path
    title: str
    source: str
    content: str


def _tokenize(text: str) -> set[str]:
    return {tok.lower() for tok in _WORD_RE.findall(text) if len(tok) > 1}


def _parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text
    raw_meta, body = match.groups()
    meta: dict[str, str] = {}
    for line in raw_meta.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, body


def load_docs(docs_dir: Path | str = DEFAULT_DOCS_DIR) -> list[LoadedDoc]:
    docs_dir = Path(docs_dir)
    if not docs_dir.exists():
        return []
    loaded: list[LoadedDoc] = []
    for path in sorted(docs_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_front_matter(text)
        loaded.append(
            LoadedDoc(
                path=path,
                title=meta.get("title", path.stem),
                source=meta.get("source", ""),
                content=body.strip(),
            )
        )
    return loaded


def retrieve_relevant_chunks(
    query: str,
    docs_dir: Path | str = DEFAULT_DOCS_DIR,
    top_k: int = 3,
    max_chars: int = 1500,
) -> list[str]:
    if not query or not query.strip():
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    scored: list[tuple[int, LoadedDoc]] = []
    for doc in load_docs(docs_dir):
        doc_tokens = _tokenize(doc.title) | _tokenize(doc.content)
        score = len(query_tokens & doc_tokens)
        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda item: item[0], reverse=True)

    chunks = []
    for _, doc in scored[:top_k]:
        header = f"[{doc.title}]" + (f" (nguồn: {doc.source})" if doc.source else "")
        chunks.append(f"{header}\n{doc.content[:max_chars]}")
    return chunks
