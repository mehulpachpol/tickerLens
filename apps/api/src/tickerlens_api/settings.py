from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TICKERLENS_", env_file=".env", extra="ignore")

    environment: str = "dev"
    log_level: str = "INFO"

    api_title: str = "TickerLens API"
    api_version: str = "0.1.0"

    # Database
    # Default points to docker-compose service hostname. Override with TICKERLENS_DATABASE_URL for local runs.
    database_url: str = "postgresql+psycopg://tickerlens:tickerlens@postgres:5432/tickerlens"

    # Object storage (MinIO / S3-compatible)
    s3_endpoint_url: str = "http://minio:9000"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin123"
    s3_region_name: str = "us-east-1"
    s3_raw_docs_bucket: str = "raw-docs"
    s3_force_path_style: bool = True


settings = Settings()
