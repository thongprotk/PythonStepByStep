from fastapi.testclient import TestClient

import app.api.routes.chat as chat_route
from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def test_chat_without_api_key_returns_500(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    get_settings.cache_clear()
    try:
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 500
    finally:
        get_settings.cache_clear()


def test_chat_success_with_mock(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    get_settings.cache_clear()

    class FakeClient:
        def ask(self, message: str, model=None) -> str:
            return f"echo: {message}"

    monkeypatch.setattr(chat_route, "LLMClient", lambda: FakeClient())
    try:
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 200
        assert response.json()["reply"] == "echo: hello"
    finally:
        get_settings.cache_clear()


def test_chat_upstream_error_returns_502(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    get_settings.cache_clear()

    class BrokenClient:
        def ask(self, message: str, model=None) -> str:
            raise RuntimeError("connection reset")

    monkeypatch.setattr(chat_route, "LLMClient", lambda: BrokenClient())
    try:
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 502
    finally:
        get_settings.cache_clear()
