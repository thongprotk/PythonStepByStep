import pytest

from app.core.config import get_settings
from app.llm.openrouter_client import OpenRouterClient


class FakeResponse:
    def __init__(self, content: str):
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            OpenRouterClient()
    finally:
        get_settings.cache_clear()


def test_ask_rejects_empty_message(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    get_settings.cache_clear()
    try:
        client = OpenRouterClient()
        with pytest.raises(ValueError):
            client.ask("   ")
    finally:
        get_settings.cache_clear()


def test_ask_success(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    get_settings.cache_clear()

    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse("hello back")

    try:
        import app.llm.openrouter_client as mod

        monkeypatch.setattr(mod.httpx, "post", fake_post)
        client = OpenRouterClient()
        reply = client.ask("hi")
        assert reply == "hello back"
        assert captured["url"].endswith("/chat/completions")
        assert captured["headers"]["Authorization"] == "Bearer sk-or-test"
        assert captured["json"]["messages"] == [{"role": "user", "content": "hi"}]
    finally:
        get_settings.cache_clear()


def test_ask_with_system_includes_system_message(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    get_settings.cache_clear()

    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["json"] = json
        return FakeResponse("ok")

    try:
        import app.llm.openrouter_client as mod

        monkeypatch.setattr(mod.httpx, "post", fake_post)
        client = OpenRouterClient()
        client.ask_with_system("be terse", "hi")
        assert captured["json"]["messages"] == [
            {"role": "system", "content": "be terse"},
            {"role": "user", "content": "hi"},
        ]
    finally:
        get_settings.cache_clear()
