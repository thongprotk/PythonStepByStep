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

    monkeypatch.setattr(chat_route, "get_llm_client", lambda: FakeClient())
    monkeypatch.setattr(chat_route, "log_qa_session", lambda *a, **k: None)
    try:
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 200
        assert response.json()["reply"] == "echo: hello"
    finally:
        get_settings.cache_clear()


def test_chat_uses_openrouter_when_configured(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    get_settings.cache_clear()

    class FakeOpenRouterClient:
        def ask(self, message: str, model=None) -> str:
            return f"openrouter: {message}"

    import app.llm.provider as provider_module

    monkeypatch.setattr(
        provider_module, "OpenRouterClient", lambda: FakeOpenRouterClient()
    )
    monkeypatch.setattr(chat_route, "log_qa_session", lambda *a, **k: None)
    try:
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 200
        assert response.json()["reply"] == "openrouter: hello"
    finally:
        get_settings.cache_clear()


def test_chat_unknown_provider_returns_500(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "not-a-real-provider")
    get_settings.cache_clear()
    try:
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 500
    finally:
        get_settings.cache_clear()


def test_chat_upstream_error_returns_502(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    get_settings.cache_clear()

    class BrokenClient:
        def ask(self, message: str, model=None) -> str:
            raise RuntimeError("connection reset")

    monkeypatch.setattr(chat_route, "get_llm_client", lambda: BrokenClient())
    try:
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 502
    finally:
        get_settings.cache_clear()
