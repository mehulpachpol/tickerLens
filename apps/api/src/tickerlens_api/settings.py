from pydantic import AliasChoices, Field
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
    # Public URL used in responses (e.g., presigned download links). Useful when the API runs
    # inside Docker and the client is outside (host browser can't resolve "minio").
    # Example: "http://localhost:9000"
    s3_public_endpoint_url: str | None = None
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin123"
    s3_region_name: str = "us-east-1"
    s3_raw_docs_bucket: str = "raw-docs"
    s3_force_path_style: bool = True

    # Parsing / OCR
    parse_text_min_chars_for_digital: int = 40
    ocr_language: str = "eng"
    ocr_dpi: int = 200

    # OpenAI embeddings
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TICKERLENS_OPENAI_API_KEY", "OPENAI_API_KEY"),
        description="OpenAI API key.",
    )
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int | None = None

    # OpenAI chat generation (Phase 8)
    openai_chat_model: str = "gpt-4o-mini"
    openai_chat_temperature: float = 0.2
    openai_chat_max_tokens: int = 900

    # OpenAI reranking (Phase 7)
    openai_rerank_model: str = "gpt-4o-mini"
    openai_rerank_max_passage_chars: int = 1200

    # Cross-encoder reranking (Phase 7, low-latency default)
    # Uses FastEmbed (ONNX Runtime) models (no PyTorch).
    rerank_backend: str = "fastembed"  # "fastembed" | "openai"
    fastembed_rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    fastembed_rerank_batch_size: int = 32

    # Qdrant
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection_prefix: str = "tickerlens_chunks"

    # OpenSearch (BM25 keyword search)
    opensearch_url: str = "http://opensearch:9200"
    opensearch_chunks_index_prefix: str = "tickerlens_chunks"

    # ---------------------------------------------------------------------
    # Phase 10: Automated NSE ingestion (scheduler + discovery/download)
    # ---------------------------------------------------------------------
    ingestion_enabled: bool = True
    ingestion_universe_id: str = "NIFTY_50"
    ingestion_lookback_days: int = 3  # scheduler queries [today-lookback, today]
    ingestion_limit_per_ticker: int = 10

    # Scheduler cadence (IST)
    ingestion_scheduler_enabled: bool = True
    ingestion_cron_hour_ist: int = 19
    ingestion_cron_minute_ist: int = 0

    # NSE endpoints
    nse_base_url: str = "https://www.nseindia.com"
    nse_index: str = "equities"
    nse_timeout_s: int = 30
    nse_throttle_ms: int = 250
    nse_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    # ---------------------------------------------------------------------
    # Phase 11: Auth + sessions
    # ---------------------------------------------------------------------
    auth_enabled: bool = False
    auth_allow_register: bool = False

    auth_bootstrap_admin_email: str | None = None
    auth_bootstrap_admin_password: str | None = None

    auth_session_cookie_name: str = "tickerlens_session"
    auth_session_ttl_hours: int = 24 * 7
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"  # "lax"|"strict"|"none"
    auth_cookie_domain: str | None = None

    # ---------------------------------------------------------------------
    # Phase 11: Observability
    # ---------------------------------------------------------------------
    metrics_enabled: bool = True
    metrics_path: str = "/metrics"

    otel_enabled: bool = False
    otel_service_name: str = "tickerlens-api"
    otel_otlp_endpoint: str | None = None  # e.g. http://otel-collector:4318

    # Rate limiting (Phase 11)
    redis_url: str = "redis://redis:6379/0"

    # Fixed-window limits (best-effort; fail-open if Redis unavailable)
    rl_chat_per_minute: int = 20
    rl_vector_search_per_minute: int = 60
    rl_doc_download_per_minute: int = 120
    rl_doc_upload_per_minute: int = 10


settings = Settings()
