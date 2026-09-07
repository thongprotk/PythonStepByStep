from anthropic import Anthropic

from app.core.config import get_settings


class LLMClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = Anthropic(api_key=settings.anthropic_api_key)

    def ask(self, message: str, model: str = "claude-sonnet-5") -> str:
        response = self._client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": message}],
        )
        return response.content[0].text
