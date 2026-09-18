import json

import pytest
from fastapi.testclient import TestClient

import app.api.routes.mida_assistant as mida_route
from app.core.config import get_settings
from app.llm.mida_prompt import build_user_content, parse_assistant_reply
from app.main import app

client = TestClient(app)

VALID_REPLY = {
    "answer": "Bạn có thể bật geo-block ở mục Rules > Geo-block.",
    "cited_sources": ["Chặn theo IP & khu vực"],
    "suggested_features": ["VPN/proxy detection"],
    "confidence": 0.9,
    "needs_escalation": False,
    "in_scope": True,
}


def test_build_user_content_rejects_empty_message():
    with pytest.raises(ValueError):
        build_user_content(user_message="   ")


def test_build_user_content_includes_all_blocks():
    content = build_user_content(
        user_message="Làm sao chặn bot theo quốc gia?",
        retrieved_chunks=["Chặn theo IP & khu vực: ..."],
        customer_config={"geo_block": False},
        feature_catalog=[{"name": "geo_block"}],
        recent_history=[{"role": "user", "content": "hi"}],
        max_history_turns=5,
    )
    assert "Chặn theo IP & khu vực" in content
    assert '"geo_block": false' in content
    assert "Làm sao chặn bot theo quốc gia?" in content


def test_parse_assistant_reply_valid_json():
    parsed = parse_assistant_reply(json.dumps(VALID_REPLY))
    assert parsed["in_scope"] is True
    assert parsed["confidence"] == 0.9


def test_parse_assistant_reply_strips_code_fence():
    fenced = "```json\n" + json.dumps(VALID_REPLY) + "\n```"
    parsed = parse_assistant_reply(fenced)
    assert parsed["answer"] == VALID_REPLY["answer"]


def test_parse_assistant_reply_clamps_confidence():
    bad = {**VALID_REPLY, "confidence": 5.0}
    parsed = parse_assistant_reply(json.dumps(bad))
    assert parsed["confidence"] == 1.0


def test_parse_assistant_reply_rejects_missing_keys():
    with pytest.raises(ValueError):
        parse_assistant_reply(json.dumps({"answer": "hi"}))


def test_parse_assistant_reply_rejects_invalid_json():
    with pytest.raises(ValueError):
        parse_assistant_reply("not json")


def test_endpoint_without_api_key_returns_500(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    get_settings.cache_clear()
    try:
        response = client.post(
            "/mida-assistant", json={"user_message": "Geo-block hoạt động thế nào?"}
        )
        assert response.status_code == 500
    finally:
        get_settings.cache_clear()


def test_endpoint_success_with_mock(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    get_settings.cache_clear()

    class FakeClient:
        def ask_with_system(self, system: str, message: str, model=None) -> str:
            return json.dumps(VALID_REPLY)

    monkeypatch.setattr(mida_route, "get_llm_client", lambda: FakeClient())
    monkeypatch.setattr(mida_route, "log_qa_session", lambda *a, **k: None)
    try:
        response = client.post(
            "/mida-assistant", json={"user_message": "Geo-block hoạt động thế nào?"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["in_scope"] is True
        assert body["confidence"] == 0.9
    finally:
        get_settings.cache_clear()


def test_endpoint_rejects_empty_message(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    get_settings.cache_clear()
    try:
        response = client.post("/mida-assistant", json={"user_message": "   "})
        assert response.status_code == 422
    finally:
        get_settings.cache_clear()


def test_endpoint_malformed_model_reply_returns_502(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    get_settings.cache_clear()

    class BrokenReplyClient:
        def ask_with_system(self, system: str, message: str, model=None) -> str:
            return "not json at all"

    monkeypatch.setattr(mida_route, "get_llm_client", lambda: BrokenReplyClient())
    try:
        response = client.post(
            "/mida-assistant", json={"user_message": "Geo-block hoạt động thế nào?"}
        )
        assert response.status_code == 502
    finally:
        get_settings.cache_clear()


def test_endpoint_auto_retrieves_chunks_when_none_supplied(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    get_settings.cache_clear()

    captured = {}

    class CapturingClient:
        def ask_with_system(self, system: str, message: str, model=None) -> str:
            captured["message"] = message
            return json.dumps(VALID_REPLY)

    monkeypatch.setattr(
        mida_route,
        "retrieve_relevant_chunks",
        lambda query: ["[Geo Block] (nguồn: docs) noi dung geo block"],
    )
    monkeypatch.setattr(mida_route, "get_llm_client", lambda: CapturingClient())
    monkeypatch.setattr(mida_route, "log_qa_session", lambda *a, **k: None)
    try:
        response = client.post(
            "/mida-assistant", json={"user_message": "Geo-block hoạt động thế nào?"}
        )
        assert response.status_code == 200
        assert "Geo Block" in captured["message"]
    finally:
        get_settings.cache_clear()


def test_endpoint_skips_auto_retrieval_when_chunks_supplied(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    get_settings.cache_clear()

    def fail_if_called(query):
        raise AssertionError("retrieve_relevant_chunks should not be called")

    class CapturingClient:
        def ask_with_system(self, system: str, message: str, model=None) -> str:
            return json.dumps(VALID_REPLY)

    monkeypatch.setattr(mida_route, "retrieve_relevant_chunks", fail_if_called)
    monkeypatch.setattr(mida_route, "get_llm_client", lambda: CapturingClient())
    monkeypatch.setattr(mida_route, "log_qa_session", lambda *a, **k: None)
    try:
        response = client.post(
            "/mida-assistant",
            json={
                "user_message": "Geo-block hoạt động thế nào?",
                "retrieved_chunks": ["chunk da co san"],
            },
        )
        assert response.status_code == 200
    finally:
        get_settings.cache_clear()


def test_endpoint_upstream_error_returns_502(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    get_settings.cache_clear()

    class BrokenClient:
        def ask_with_system(self, system: str, message: str, model=None) -> str:
            raise RuntimeError("connection reset")

    monkeypatch.setattr(mida_route, "get_llm_client", lambda: BrokenClient())
    try:
        response = client.post(
            "/mida-assistant", json={"user_message": "Geo-block hoạt động thế nào?"}
        )
        assert response.status_code == 502
    finally:
        get_settings.cache_clear()
