"""OpenRouter backend — same `ask`/`ask_with_system` contract as LLMClient
(app/llm/client.py) so app.llm.provider.get_llm_client() can hand either one
to a route/tool without the caller knowing which provider is configured.

OpenRouter speaks the OpenAI chat-completions shape, so this talks to it
directly over httpx instead of the Anthropic SDK.
"""

from __future__ import annotations

import httpx

from app.core.config import get_settings

DEFAULT_OPENROUTER_MODEL = "anthropic/claude-3.5-sonnet"


class OpenRouterClient:
    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        key = api_key if api_key is not None else settings.openrouter_api_key
        if not key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not configured; set it in .env or "
                "environment before using LLM_PROVIDER=openrouter"
            )
        self._api_key = key
        self._base_url = settings.openrouter_base_url.rstrip("/")
        self._default_model = settings.openrouter_model or DEFAULT_OPENROUTER_MODEL
        self._timeout = settings.llm_timeout

    def _complete(self, messages: list[dict[str, str]], model: str | None) -> str:
        response = httpx.post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={"model": model or self._default_model, "messages": messages},
            timeout=self._timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def ask(self, message: str, model: str | None = None) -> str:
        if not message or not message.strip():
            raise ValueError("message must be a non-empty string")
        return self._complete([{"role": "user", "content": message}], model)

    def ask_with_system(
        self, system: str, message: str, model: str | None = None
    ) -> str:
        if not message or not message.strip():
            raise ValueError("message must be a non-empty string")
        return self._complete(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": message},
            ],
            model,
        )
