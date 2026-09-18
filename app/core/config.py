from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    app_name: str = "PY Learning Project"
    debug: bool = False
    anthropic_api_key: str = ""
    database_url: str = "sqlite:///./app.db"
    chat_model: str = "claude-3-5-sonnet-latest"
    llm_timeout: float = 30.0
    model_path: str = "./model.joblib"
    supabase_url: str = ""
    supabase_key: str = ""

    # Which backend app.llm.provider.get_llm_client() picks: "anthropic" or
    # "openrouter". /chat, /mida-assistant, and the MCP server all follow it.
    llm_provider: str = "anthropic"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "anthropic/claude-3.5-sonnet"


@lru_cache
def get_settings() -> Settings:
    return Settings()
