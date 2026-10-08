import secrets
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TicketFlow API"
    app_version: str = "0.1.0"
    environment: str = "development"
    database_url: str = (
        "postgresql+pg8000://ticketflow:ticketflow@localhost:5433/ticketflow"
    )
    sql_echo: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    jwt_secret_key: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        min_length=32,
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, gt=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
