"""Настройки приложения. Значения берутся из окружения или backend/.env."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
CONFIG_DIR = BACKEND_DIR / "config"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_prefix="ANALYZER_",
        extra="ignore",
    )

    database_url: str = f"sqlite:///{(DATA_DIR / 'analyzer.db').as_posix()}"
    cache_dir: Path = DATA_DIR / "cache"

    # OpenDota работает и без ключа (60 запросов/мин, 2000/день).
    opendota_api_key: str | None = None
    opendota_rate_limit: int = 55

    # Опциональные источники: STRATZ закрывает часть статов, которых нет в
    # OpenDota; Steam — live-данные во время матчей.
    stratz_api_token: str | None = None
    steam_api_key: str | None = None

    fantasy_rules_path: Path = CONFIG_DIR / "ti15_fantasy.yaml"
    predictions_config_path: Path = CONFIG_DIR / "ti15_predictions.yaml"

    # Окно истории для рейтингов и проекций.
    history_days: int = 120
    # Длина рейтингового периода Glicko-2 в днях.
    rating_period_days: int = 7
    # Число прогонов Monte-Carlo по умолчанию.
    simulations: int = 20_000

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()
