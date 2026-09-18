"""The one switch for "which LLM backend answers" — `/chat`, `/mida-assistant`
and the MCP server (app/mcp_tools.py) all call `get_llm_client()` instead of
instantiating a provider directly, so changing `LLM_PROVIDER` in `.env`
re-routes every one of them without touching route/tool code.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.llm.client import LLMClient
from app.llm.openrouter_client import OpenRouterClient

_KNOWN_PROVIDERS = ("anthropic", "openrouter")


def get_llm_client() -> LLMClient | OpenRouterClient:
    settings = get_settings()
    provider = (settings.llm_provider or "anthropic").strip().lower()
    # Branches reference the module-global LLMClient/OpenRouterClient names
    # directly (not a dict built at import time) so tests can monkeypatch
    # either one on this module and have it take effect.
    if provider == "anthropic":
        return LLMClient()
    if provider == "openrouter":
        return OpenRouterClient()
    raise RuntimeError(
        f"Unknown LLM_PROVIDER {provider!r}; expected one of {_KNOWN_PROVIDERS}"
    )
