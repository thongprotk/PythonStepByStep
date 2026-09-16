from anthropic import Anthropic

from app.core.config import get_settings

DEFAULT_MODEL = "claude-3-5-sonnet-latest"


class LLMClient:
    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        key = api_key if api_key is not None else settings.anthropic_api_key
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not configured; "
                "set it in .env or environment before calling /chat"
            )
        self._client = Anthropic(api_key=key, timeout=settings.llm_timeout)
        self._default_model = settings.chat_model or DEFAULT_MODEL

    def ask(self, message: str, model: str | None = None) -> str:
        if not message or not message.strip():
            raise ValueError("message must be a non-empty string")
        response = self._client.messages.create(
            model=model or self._default_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": message}],
        )
        return response.content[0].text
