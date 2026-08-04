from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    anthropic_api_key: str | None = None
    watchdog_model: str = "claude-haiku-4-5-20251001"
    analyst_model: str = "claude-sonnet-5"
    alpaca_api_key: str | None = None
    alpaca_secret_key: str | None = None
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_data_url: str = "https://data.alpaca.markets"
    database_url: str = "sqlite:///./sentinel.db"
    watchdog_interval_minutes: int = 15
    volume_spike_threshold_multiplier: float = 2.0
    price_move_threshold_pct: float = 3.0
    environment: str = "development"
    reasoning_backend: str | None = None

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
