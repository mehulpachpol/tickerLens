from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# Cross-dialect JSON column:
# - PostgreSQL uses JSONB for better indexing/ops
# - SQLite (tests) uses the generic JSON type
JSONB = JSON().with_variant(PG_JSONB, "postgresql")


class Company(Base):
    __tablename__ = "companies"

    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Document(Base):
    __tablename__ = "documents"

    doc_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    company_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    document_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    fiscal_year: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    filing_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True, index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class DocumentFile(Base):
    __tablename__ = "document_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    bucket: Mapped[str] = mapped_column(String(63), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)

    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DocumentParseRun(Base):
    __tablename__ = "document_parse_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    doc_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    parser_version: Mapped[str] = mapped_column(String(50), nullable=False, default="pymupdf+tesseract:v1")

    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ocr_page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    page_num: Mapped[int] = mapped_column(Integer, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(20), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DocumentChunkRun(Base):
    __tablename__ = "document_chunk_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    doc_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    parse_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    chunker_version: Mapped[str] = mapped_column(String(50), nullable=False, default="linepack:v1")

    max_chunk_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=5000)
    overlap_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=250)
    max_block_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=1200)

    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    chunk_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    doc_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    parse_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    chunk_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    section: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)

    page_start: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DocumentChunkSpan(Base):
    __tablename__ = "document_chunk_spans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chunk_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    page_num: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DocumentEmbeddingRun(Base):
    __tablename__ = "document_embedding_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    doc_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    parse_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    chunk_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vector_size: Mapped[int] = mapped_column(Integer, nullable=False)

    qdrant_collection: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    embedded_chunks: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DocumentIndexRun(Base):
    __tablename__ = "document_index_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    doc_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    parse_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    chunk_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    backend: Mapped[str] = mapped_column(String(20), nullable=False, index=True, default="opensearch")
    index_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    indexed_chunks: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TickerUniverse(Base):
    __tablename__ = "ticker_universes"

    universe_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TickerUniverseMember(Base):
    __tablename__ = "ticker_universe_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    universe_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    start_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    universe_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    job_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # discover|download|sync
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # queued|running|succeeded|failed

    scheduled_for: Mapped[dt.date | None] = mapped_column(Date, nullable=True, index=True)

    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    discovered_items: Mapped[int | None] = mapped_column(Integer, nullable=True)
    downloaded_items: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ingested_items: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IngestionDiscoveredItem(Base):
    __tablename__ = "ingestion_discovered_items"

    item_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    universe_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, index=True, default="nse")

    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)

    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True, default="discovered")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    first_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    downloaded_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    doc_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, index=True, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Store only a hash of the session token (defense in depth if DB is leaked).
    session_token_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    tickers: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    message_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # user|assistant|system
    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RagRun(Base):
    __tablename__ = "rag_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)

    tickers: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    doc_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    retrieval: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    citations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    timings_ms: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    models: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    occurred_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
