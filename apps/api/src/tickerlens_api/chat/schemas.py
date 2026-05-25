from __future__ import annotations

from pydantic import BaseModel, Field


class ChatStreamRequest(BaseModel):
    question: str = Field(min_length=1, description="User question in natural language.")
    tickers: list[str] | None = Field(default=None, description="Restrict retrieval to these tickers.")

    # Retrieval parameters (Phase 7)
    top_k: int = Field(default=10, ge=1, le=50)
    doc_ids: list[str] | None = None
    chunk_run_id: str | None = None

    embedding_model: str | None = None
    dimensions: int | None = Field(default=None, ge=64, le=8192)

    vector_top_n: int = Field(default=50, ge=5, le=200)
    index_version: str = Field(default="v1", min_length=1, max_length=20)
    bm25_top_n: int = Field(default=50, ge=5, le=200)

    rrf_k: int = Field(default=60, ge=1, le=1000)
    vector_weight: float = Field(default=1.0, ge=0.0, le=10.0)
    bm25_weight: float = Field(default=1.0, ge=0.0, le=10.0)

    rerank_backend: str | None = Field(
        default=None, description="Reranker backend: 'fastembed' (local) or 'openai'."
    )
    rerank_model: str | None = None
    rerank_top_n: int = Field(default=30, ge=5, le=400)
    passage_max_chars: int = Field(default=600, ge=200, le=5000)
    per_ticker_k: int | None = Field(default=None, ge=1, le=50)


class Citation(BaseModel):
    chunk_id: str
    ticker: str | None = None
    doc_id: str | None = None

    document_type: str | None = None
    fiscal_year: str | None = None
    filing_date: str | None = None
    version: int | None = None

    section: str | None = None
    page_start: int | None = None
    page_end: int | None = None

    download_endpoint: str | None = None


class ChatCitationsPayload(BaseModel):
    used_chunk_ids: list[str]
    citations: list[Citation]

