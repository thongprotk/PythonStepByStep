import httpx
import pytest

from app.tools import doc_scraper

SAMPLE_HTML = """
<html>
<head><title>Ignore me</title></head>
<body>
<nav>skip this nav</nav>
<main>
<h1>Chan Bot Theo IP</h1>
<p>Huong dan chan bot theo dia chi IP va khu vuc.</p>
<img src="data:image/png;base64,AAAA" alt="icon rac">
<img src="https://mida.example/diagram.png" alt="So do he thong">
</main>
<footer>skip this footer</footer>
</body>
</html>
"""

PUBLIC_IP = "93.184.216.34"  # example.com-style public address


class FakeResponse:
    def __init__(
        self,
        text: str = "",
        content: bytes = b"",
        status_ok: bool = True,
        redirect_to: str | None = None,
    ):
        self.text = text
        self.content = content
        self._status_ok = status_ok
        self.headers = {"location": redirect_to} if redirect_to else {}
        self.is_redirect = redirect_to is not None

    def raise_for_status(self):
        if not self._status_ok:
            raise httpx.HTTPStatusError(
                "boom",
                request=httpx.Request("GET", "https://mida.example/bad"),
                response=httpx.Response(404),
            )


def _mock_public_dns(monkeypatch):
    monkeypatch.setattr(
        doc_scraper.socket,
        "getaddrinfo",
        lambda host, port: [(None, None, None, None, (PUBLIC_IP, 0))],
    )


def test_slugify_basic():
    assert doc_scraper.slugify("Chặn Bot Theo IP") == "ch-n-bot-theo-ip"


def test_slugify_empty_falls_back():
    assert doc_scraper.slugify("!!!") == "untitled"


def test_assert_safe_url_rejects_non_http_scheme(monkeypatch):
    _mock_public_dns(monkeypatch)
    with pytest.raises(doc_scraper.ScrapeError):
        doc_scraper._assert_safe_url("ftp://mida.example/file")


def test_assert_safe_url_rejects_private_address(monkeypatch):
    monkeypatch.setattr(
        doc_scraper.socket,
        "getaddrinfo",
        lambda host, port: [(None, None, None, None, ("127.0.0.1", 0))],
    )
    with pytest.raises(doc_scraper.ScrapeError):
        doc_scraper._assert_safe_url("http://mida.example/")


def test_assert_safe_url_rejects_link_local_metadata_address(monkeypatch):
    monkeypatch.setattr(
        doc_scraper.socket,
        "getaddrinfo",
        lambda host, port: [(None, None, None, None, ("169.254.169.254", 0))],
    )
    with pytest.raises(doc_scraper.ScrapeError):
        doc_scraper._assert_safe_url("http://mida.example/")


def test_assert_safe_url_allows_public_address(monkeypatch):
    _mock_public_dns(monkeypatch)
    doc_scraper._assert_safe_url("https://mida.example/")


def test_safe_get_revalidates_each_redirect_hop(monkeypatch):
    _mock_public_dns(monkeypatch)

    calls = {"n": 0}

    def fake_get(url, timeout, follow_redirects):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResponse(redirect_to="https://mida.example/final")
        return FakeResponse(text="ok")

    monkeypatch.setattr(doc_scraper.httpx, "get", fake_get)
    response = doc_scraper._safe_get("https://mida.example/start", timeout=5.0)
    assert response.text == "ok"
    assert calls["n"] == 2


def test_safe_get_rejects_redirect_to_private_address(monkeypatch):
    def fake_getaddrinfo(host, port):
        if host == "internal":
            return [(None, None, None, None, ("127.0.0.1", 0))]
        return [(None, None, None, None, (PUBLIC_IP, 0))]

    monkeypatch.setattr(doc_scraper.socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(
        doc_scraper.httpx,
        "get",
        lambda url, timeout, follow_redirects: FakeResponse(
            redirect_to="http://internal/secret"
        ),
    )
    with pytest.raises(doc_scraper.ScrapeError):
        doc_scraper._safe_get("https://mida.example/start", timeout=5.0)


def test_extract_title_and_markdown_strips_nav_and_footer(monkeypatch):
    _mock_public_dns(monkeypatch)
    monkeypatch.setattr(
        doc_scraper,
        "_describe_image",
        lambda img_tag, base_url: "[Hinh: placeholder]",
    )
    title, markdown = doc_scraper.extract_title_and_markdown(
        SAMPLE_HTML, base_url="https://mida.example/docs/geo-block"
    )
    assert title == "Chan Bot Theo IP"
    assert "skip this nav" not in markdown
    assert "skip this footer" not in markdown
    assert "Huong dan chan bot" in markdown


def test_extract_title_and_markdown_raises_on_empty_body():
    with pytest.raises(doc_scraper.ScrapeError):
        doc_scraper.extract_title_and_markdown(
            "<html><body></body></html>", base_url="https://mida.example/"
        )


def test_describe_image_drops_data_uri_without_alt():
    tag = _FakeTag(src="data:image/png;base64,AAAA", alt="")
    assert doc_scraper._describe_image(tag, "https://mida.example/") == ""


def test_describe_image_keeps_alt_for_data_uri():
    tag = _FakeTag(src="data:image/png;base64,AAAA", alt="icon rac")
    assert (
        doc_scraper._describe_image(tag, "https://mida.example/") == "[Hình: icon rac]"
    )


def test_describe_image_drops_small_icon(monkeypatch):
    monkeypatch.setattr(
        doc_scraper, "_safe_get", lambda url, timeout: FakeResponse(content=b"fake")
    )
    monkeypatch.setattr(doc_scraper.cv2, "imdecode", lambda arr, flag: _FakeArray(20, 20))
    tag = _FakeTag(src="https://mida.example/icon.png", alt="icon")
    assert doc_scraper._describe_image(tag, "https://mida.example/") == ""


def test_describe_image_keeps_real_image_as_placeholder(monkeypatch):
    monkeypatch.setattr(
        doc_scraper, "_safe_get", lambda url, timeout: FakeResponse(content=b"fake")
    )
    monkeypatch.setattr(
        doc_scraper.cv2, "imdecode", lambda arr, flag: _FakeArray(600, 800)
    )
    tag = _FakeTag(src="https://mida.example/diagram.png", alt="So do he thong")
    result = doc_scraper._describe_image(tag, "https://mida.example/")
    assert result == "[Hình: So do he thong (800x600)]"


def test_describe_image_falls_back_on_fetch_error(monkeypatch):
    def raise_error(url, timeout):
        raise doc_scraper.ScrapeError("network down")

    monkeypatch.setattr(doc_scraper, "_safe_get", raise_error)
    tag = _FakeTag(src="https://mida.example/diagram.png", alt="So do")
    assert doc_scraper._describe_image(tag, "https://mida.example/") == "[Hình: So do]"


class _FakeTag:
    def __init__(self, src: str, alt: str):
        self._attrs = {"src": src, "alt": alt}

    def get(self, key, default=None):
        return self._attrs.get(key, default)


class _FakeArray:
    """Stand-in for the numpy array cv2.imdecode returns (height, width, ...)."""

    def __init__(self, height: int, width: int):
        self.shape = (height, width, 3)


def test_scrape_url_to_markdown_writes_file(tmp_path, monkeypatch):
    _mock_public_dns(monkeypatch)
    monkeypatch.setattr(
        doc_scraper.httpx,
        "get",
        lambda url, timeout, follow_redirects: FakeResponse(text=SAMPLE_HTML),
    )
    monkeypatch.setattr(
        doc_scraper, "_describe_image", lambda img_tag, base_url: ""
    )
    doc = doc_scraper.scrape_url_to_markdown(
        "https://mida.example/docs/geo-block", output_dir=tmp_path
    )
    assert doc.path.exists()
    text = doc.path.read_text(encoding="utf-8")
    assert "source: https://mida.example/docs/geo-block" in text
    assert "Huong dan chan bot" in text


def test_scrape_urls_collects_errors(tmp_path, monkeypatch):
    _mock_public_dns(monkeypatch)

    def fake_get(url, timeout, follow_redirects):
        if "bad" in url:
            return FakeResponse(status_ok=False)
        return FakeResponse(text=SAMPLE_HTML)

    monkeypatch.setattr(doc_scraper.httpx, "get", fake_get)
    monkeypatch.setattr(doc_scraper, "_describe_image", lambda img_tag, base_url: "")
    result = doc_scraper.scrape_urls(
        ["https://mida.example/good", "https://mida.example/bad"],
        output_dir=tmp_path,
    )
    assert len(result["saved"]) == 1
    assert len(result["errors"]) == 1
    assert result["errors"][0]["url"] == "https://mida.example/bad"
