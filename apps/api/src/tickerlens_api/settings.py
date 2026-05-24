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


settings = Settings()
