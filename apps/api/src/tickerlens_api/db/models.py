from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, DateTime, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


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
