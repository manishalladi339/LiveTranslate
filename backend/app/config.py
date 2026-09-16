from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LiveTranslate API"
    environment: str = "development"
    translation_provider: str = "demo"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    allowed_origins: list[str] | str = ["http://localhost:5173", "http://localhost:8080"]
    max_text_length: int = 2000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", enable_decoding=False)

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("translation_provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        if value not in {"demo", "openai"}:
            raise ValueError("TRANSLATION_PROVIDER must be 'demo' or 'openai'")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
