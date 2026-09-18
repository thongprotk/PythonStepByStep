"""Docs scraper: fetch a URL, extract the main content, save it as Markdown.

Feeds the `docs/` folder that `app.tools.doc_retriever` reads from to ground
`/mida-assistant` answers — see that module for how the two connect. Exposed
both as a plain Python API (for reuse/tests) and as `/docs/scrape` (for a chat
agent orchestrator to call as a tool that refreshes grounding material before
answering).

Every outbound fetch (page + images) goes through `_safe_get`, which resolves
the hostname and rejects loopback/private/link-local/reserved targets before
each hop — this endpoint accepts arbitrary caller-supplied URLs, so without
that guard it's an SSRF vector onto the host's internal network.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import cv2
import httpx
import numpy as np
from bs4 import BeautifulSoup
from markdownify import markdownify

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOCS_DIR = PROJECT_ROOT / "docs"

_STRIP_TAGS = ("script", "style", "nav", "header", "footer", "aside", "noscript")
_CONTENT_SELECTORS = ("main", "article", "[role=main]", "body")
_MAX_REDIRECTS = 5
_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_MIN_MEANINGFUL_IMAGE_SIDE = 48  # px — smaller is assumed to be an icon/spacer


@dataclass
class ScrapedDoc:
    url: str
    title: str
    path: Path


class ScrapeError(RuntimeError):
    """Raised when a URL can't be safely/successfully fetched or parsed."""


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "untitled"


def _assert_safe_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ScrapeError(f"unsupported URL scheme: {parsed.scheme!r}")
    hostname = parsed.hostname
    if not hostname:
        raise ScrapeError(f"URL has no hostname: {url}")
    try:
        addrinfos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ScrapeError(f"could not resolve hostname {hostname}: {exc}") from exc
    for *_, sockaddr in addrinfos:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ScrapeError(f"{hostname} resolves to a disallowed address: {ip}")


def _safe_get(url: str, timeout: float) -> httpx.Response:
    """GET with SSRF guarding on every hop (redirects are not auto-followed)."""
    current_url = url
    for _ in range(_MAX_REDIRECTS + 1):
        _assert_safe_url(current_url)
        try:
            response = httpx.get(current_url, timeout=timeout, follow_redirects=False)
        except httpx.HTTPError as exc:
            raise ScrapeError(f"failed to fetch {current_url}: {exc}") from exc
        if response.is_redirect:
            location = response.headers.get("location")
            if not location:
                raise ScrapeError(f"redirect from {current_url} has no Location")
            current_url = urljoin(current_url, location)
            continue
        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ScrapeError(f"failed to fetch {current_url}: {exc}") from exc
        return response
    raise ScrapeError(f"too many redirects starting from {url}")


def fetch_html(url: str, timeout: float = 15.0) -> str:
    return _safe_get(url, timeout).text


def _describe_image(img_tag, base_url: str) -> str:
    """Replace an <img> with a short text placeholder instead of a markdown
    image link, so scraped docs stay cheap to pass into an agent's context.
    Drops small icons/spacers entirely and never embeds raw image bytes.
    """
    alt = (img_tag.get("alt") or "").strip()
    src = img_tag.get("src") or ""
    if not src or src.startswith("data:"):
        # data: URIs can carry megabytes of base64 inline — never keep them.
        return f"[Hình: {alt}]" if alt else ""

    try:
        absolute_url = urljoin(base_url, src)
        response = _safe_get(absolute_url, timeout=10.0)
        image_bytes = response.content
        if len(image_bytes) > _MAX_IMAGE_BYTES:
            raise ScrapeError("image exceeds max size")
        array = np.frombuffer(image_bytes, dtype=np.uint8)
        decoded = cv2.imdecode(array, cv2.IMREAD_UNCHANGED)
        if decoded is None:
            raise ScrapeError("could not decode image")
        height, width = decoded.shape[:2]
    except Exception:  # noqa: BLE001 — best-effort description, never blocks the scrape
        return f"[Hình: {alt}]" if alt else ""

    if min(height, width) < _MIN_MEANINGFUL_IMAGE_SIDE:
        return ""  # icon/spacer — drop, saves context for no informational loss

    label = alt or "ảnh minh hoạ"
    return f"[Hình: {label} ({width}x{height})]"


def extract_title_and_markdown(html: str, base_url: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")

    for tag_name in _STRIP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else "Untitled"

    content_node = None
    for selector in _CONTENT_SELECTORS:
        content_node = soup.select_one(selector)
        if content_node is not None:
            break
    if content_node is None:
        raise ScrapeError("no extractable content found in page")

    for img_tag in content_node.find_all("img"):
        img_tag.replace_with(_describe_image(img_tag, base_url))

    markdown = markdownify(str(content_node), heading_style="ATX").strip()
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    if not markdown:
        raise ScrapeError("extracted content is empty after conversion")

    return title, markdown


def scrape_url_to_markdown(
    url: str, output_dir: Path | str = DEFAULT_DOCS_DIR
) -> ScrapedDoc:
    html = fetch_html(url)
    title, markdown = extract_title_and_markdown(html, base_url=url)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"{slugify(title)}.md"

    scraped_at = datetime.now(UTC).isoformat(timespec="seconds")
    front_matter = (
        "---\n"
        f"title: {title}\n"
        f"source: {url}\n"
        f"scraped_at: {scraped_at}\n"
        "---\n\n"
    )
    file_path.write_text(front_matter + markdown + "\n", encoding="utf-8")

    return ScrapedDoc(url=url, title=title, path=file_path)


def scrape_urls(
    urls: list[str], output_dir: Path | str = DEFAULT_DOCS_DIR
) -> dict[str, list]:
    saved: list[ScrapedDoc] = []
    errors: list[dict[str, str]] = []
    for url in urls:
        try:
            saved.append(scrape_url_to_markdown(url, output_dir=output_dir))
        except ScrapeError as exc:
            errors.append({"url": url, "error": str(exc)})
    return {"saved": saved, "errors": errors}
