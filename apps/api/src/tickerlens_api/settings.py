from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TICKERLENS_", env_file=".env", extra="ignore")

    environment: str = "dev"
    log_level: str = "INFO"

    api_title: str = "TickerLens API"
    api_version: str = "0.1.0"


settings = Settings()

