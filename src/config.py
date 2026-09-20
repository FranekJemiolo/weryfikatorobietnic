"""Moduł konfiguracji aplikacji Weryfikator Obietnic.

Zarządza zmiennymi środowiskowymi, adresami API oraz poświadczeniami bazy danych.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Główna klasa konfiguracyjna aplikacji oparta o pydantic-settings."""

    # Parametry Sejm OpenAPI
    sejm_api_base_url: str = "https://api.sejm.gov.pl/sejm"
    default_sejm_term: int = 10
    request_timeout_seconds: int = 30
    user_agent: str = (
        "WeryfikatorObietnicBot/0.1.0 (+https://github.com/FranekJemiolo/weryfikatorobietnic)"
    )

    # Konfiguracja Bazy Danych
    database_url: str = "postgresql://airflow:airflow@localhost:5432/weryfikator_db"

    # Konfiguracja Modeli LLM
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    llm_model_name: str = "gemini-1.5-flash"

    # Konfiguracja serwera API (FastAPI)
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
