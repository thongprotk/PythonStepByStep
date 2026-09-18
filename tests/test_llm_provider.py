import pytest

from app.core.config import get_settings
from app.llm import provider
from app.llm.client import LLMClient
from app.llm.openrouter_client import OpenRouterClient


def test_default_provider_returns_llm_client(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    get_settings.cache_clear()
    try:
        client = provider.get_llm_client()
        assert isinstance(client, LLMClient)
    finally:
        get_settings.cache_clear()


def test_openrouter_provider_returns_openrouter_client(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    get_settings.cache_clear()
    try:
        client = provider.get_llm_client()
        assert isinstance(client, OpenRouterClient)
    finally:
        get_settings.cache_clear()


def test_provider_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "OpenRouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    get_settings.cache_clear()
    try:
        client = provider.get_llm_client()
        assert isinstance(client, OpenRouterClient)
    finally:
        get_settings.cache_clear()


def test_unknown_provider_raises_runtime_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "not-a-real-provider")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            provider.get_llm_client()
    finally:
        get_settings.cache_clear()


def test_openrouter_without_key_raises_runtime_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            provider.get_llm_client()
    finally:
        get_settings.cache_clear()
