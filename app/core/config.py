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


@lru_cache
def get_settings() -> Settings:
    return Settings()
