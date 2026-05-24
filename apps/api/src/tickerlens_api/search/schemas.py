from __future__ import annotations

from pydantic import BaseModel, Field


class VectorSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)

    tickers: list[str] | None = None
    doc_ids: list[str] | None = None
    chunk_run_id: str | None = None

    embedding_model: str | None = None
    dimensions: int | None = Field(default=None, ge=64, le=8192)


class VectorSearchHit(BaseModel):
    chunk_id: str
    score: float
    ticker: str | None = None
    doc_id: str | None = None
    document_type: str | None = None
    fiscal_year: str | None = None
    filing_date: str | None = None
    version: int | None = None
    section: str | None = None
    page_start: int | None = None
    page_end: int | None = None


class VectorSearchResponse(BaseModel):
    collection: str
    embedding_model: str
    dimensions: int | None
    vector_size: int
    hits: list[VectorSearchHit]


class BM25SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)

    tickers: list[str] | None = None
    doc_ids: list[str] | None = None
    chunk_run_id: str | None = None

    index_version: str = Field(default="v1", min_length=1, max_length=20)


class BM25SearchHit(BaseModel):
    chunk_id: str
    score: float

    ticker: str | None = None
    doc_id: str | None = None
    document_type: str | None = None
    fiscal_year: str | None = None
    filing_date: str | None = None
    version: int | None = None

    section: str | None = None
    page_start: int | None = None
    page_end: int | None = None

    highlight: list[str] | None = None


class BM25SearchResponse(BaseModel):
    index_name: str
    hits: list[BM25SearchHit]


class HybridSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)

    tickers: list[str] | None = None
    doc_ids: list[str] | None = None
    chunk_run_id: str | None = None

    # Vector parameters
    embedding_model: str | None = None
    dimensions: int | None = Field(default=None, ge=64, le=8192)
    vector_top_n: int = Field(default=50, ge=5, le=200)

    # BM25 parameters
    index_version: str = Field(default="v1", min_length=1, max_length=20)
    bm25_top_n: int = Field(default=50, ge=5, le=200)

    # Fusion parameters
    rrf_k: int = Field(default=60, ge=1, le=1000)
    vector_weight: float = Field(default=1.0, ge=0.0, le=10.0)
    bm25_weight: float = Field(default=1.0, ge=0.0, le=10.0)


class HybridSearchHit(BaseModel):
    chunk_id: str
    score: float

    ticker: str | None = None
    doc_id: str | None = None
    document_type: str | None = None
    fiscal_year: str | None = None
    filing_date: str | None = None
    version: int | None = None

    section: str | None = None
    page_start: int | None = None
    page_end: int | None = None

    vector_score: float | None = None
    bm25_score: float | None = None
    vector_rank: int | None = None
    bm25_rank: int | None = None

    highlight: list[str] | None = None


class HybridSearchResponse(BaseModel):
    index_name: str
    collection: str
    embedding_model: str
    dimensions: int | None
    vector_size: int
    hits: list[HybridSearchHit]


class HybridRerankRequest(HybridSearchRequest):
    rerank_backend: str | None = Field(default=None, description="Reranker backend: 'fastembed' (local) or 'openai'.")
    rerank_model: str | None = None
    rerank_top_n: int = Field(default=30, ge=5, le=400)
    passage_max_chars: int = Field(default=600, ge=200, le=5000)

    # If provided, tries to keep at least this many results per ticker (when multiple tickers are requested).
    per_ticker_k: int | None = Field(default=None, ge=1, le=50)


class HybridRerankHit(BaseModel):
    chunk_id: str
    rerank_score: float

    # Final fused rank score from Phase 6 (RRF), preserved for debugging.
    fusion_score: float | None = None

    ticker: str | None = None
    doc_id: str | None = None
    document_type: str | None = None
    fiscal_year: str | None = None
    filing_date: str | None = None
    version: int | None = None

    section: str | None = None
    page_start: int | None = None
    page_end: int | None = None

    vector_score: float | None = None
    bm25_score: float | None = None
    vector_rank: int | None = None
    bm25_rank: int | None = None

    highlight: list[str] | None = None


class TickerContextBlock(BaseModel):
    ticker: str
    chunks: list[str]
    context: str


class HybridRerankResponse(BaseModel):
    index_name: str
    collection: str
    embedding_model: str
    dimensions: int | None
    vector_size: int

    rerank_model: str
    candidates: int

    hits: list[HybridRerankHit]
    context_blocks: list[TickerContextBlock]
    timings_ms: dict[str, int] | None = None
