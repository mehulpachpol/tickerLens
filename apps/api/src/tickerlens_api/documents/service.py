from __future__ import annotations

import datetime as dt
import os
import re
import uuid

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from tickerlens_api.db.models import Company, Document, DocumentFile
from tickerlens_api.settings import settings
from tickerlens_api.storage.s3 import presign_get_object, put_object_fileobj
from tickerlens_api.utils.files import spool_to_temp_and_hash


_SAFE_TOKEN_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _safe_token(value: str) -> str:
    value = value.strip()
    value = _SAFE_TOKEN_RE.sub("_", value)
    return value[:200] if len(value) > 200 else value


def normalize_ticker(ticker: str) -> str:
    return _safe_token(ticker).upper()


def build_raw_doc_object_key(
    *,
    ticker: str,
    document_type: str,
    filing_date: dt.date | None,
    doc_id: str,
    original_filename: str | None,
) -> str:
    year = str(filing_date.year) if filing_date else "unknown-year"
    doc_type = _safe_token(document_type).lower() or "unknown-type"

    # Keep extension if provided, otherwise default to .pdf (most common for filings).
    ext = ".pdf"
    if original_filename and "." in original_filename:
        ext_candidate = "." + original_filename.rsplit(".", 1)[-1].lower()
        if 1 < len(ext_candidate) <= 10:
            ext = ext_candidate

    return f"raw_docs/{ticker}/{doc_type}/{year}/{doc_id}{ext}"


def upsert_company(db: Session, *, ticker: str, company_name: str | None) -> None:
    existing = db.get(Company, ticker)
    if existing:
        if company_name and not existing.name:
            existing.name = company_name
        return
    db.add(Company(ticker=ticker, name=company_name))


def upload_document(
    db: Session,
    *,
    file: UploadFile,
    ticker: str,
    company_name: str | None,
    document_type: str,
    fiscal_year: str | None,
    filing_date: dt.date | None,
    source_url: str | None,
) -> tuple[Document, DocumentFile, bool]:
    """
    Core ingestion v1:
    - compute checksum
    - dedupe and/or version
    - store raw file in MinIO
    - persist metadata in Postgres
    """

    ticker_norm = normalize_ticker(ticker)
    company_name_norm = company_name.strip() if company_name else None
    document_type_norm = _safe_token(document_type).lower()
    fiscal_year_norm = fiscal_year.strip() if fiscal_year else None
    source_url_norm = source_url.strip() if source_url else None

    if not document_type_norm:
        raise ValueError("document_type is required")

    # 1) Spool file + checksum (read once)
    digest = spool_to_temp_and_hash(file.file)

    try:
        document, doc_file, deduped = ingest_document_from_tempfile_digest(
            db,
            temp_path=digest.path,
            sha256=digest.sha256,
            size_bytes=digest.size_bytes,
            original_filename=file.filename,
            content_type=file.content_type,
            ticker=ticker_norm,
            company_name=company_name_norm,
            document_type=document_type_norm,
            fiscal_year=fiscal_year_norm,
            filing_date=filing_date,
            source_url=source_url_norm,
        )
        return document, doc_file, deduped
    finally:
        try:
            os.remove(digest.path)
        except OSError:
            pass


def ingest_document_from_tempfile_digest(
    db: Session,
    *,
    temp_path: str,
    sha256: str,
    size_bytes: int,
    original_filename: str | None,
    content_type: str | None,
    ticker: str,
    company_name: str | None,
    document_type: str,
    fiscal_year: str | None,
    filing_date: dt.date | None,
    source_url: str | None,
) -> tuple[Document, DocumentFile, bool]:
    """
    Shared ingestion primitive (Phase 2 uploads, Phase 10 auto-ingestion).

    Accepts a temp file path + checksum computed upstream. This avoids re-reading the file to hash it.
    """

    # 1) Check for exact duplicate within same semantic identity (ticker + type + date + fiscal year).
    stmt = (
        select(Document)
        .where(Document.ticker == ticker)
        .where(Document.document_type == document_type)
        .order_by(Document.version.desc())
    )
    if fiscal_year is None:
        stmt = stmt.where(Document.fiscal_year.is_(None))
    else:
        stmt = stmt.where(Document.fiscal_year == fiscal_year)
    if filing_date is None:
        stmt = stmt.where(Document.filing_date.is_(None))
    else:
        stmt = stmt.where(Document.filing_date == filing_date)

    existing_docs = db.execute(stmt).scalars().all()

    for doc in existing_docs:
        if doc.checksum == sha256:
            existing_file = db.execute(select(DocumentFile).where(DocumentFile.doc_id == doc.doc_id)).scalars().first()
            if existing_file:
                return doc, existing_file, True

    next_version = (existing_docs[0].version + 1) if existing_docs else 1
    doc_id = str(uuid.uuid4())

    object_key = build_raw_doc_object_key(
        ticker=ticker,
        document_type=document_type,
        filing_date=filing_date,
        doc_id=doc_id,
        original_filename=original_filename,
    )

    # 2) Upload bytes to S3/MinIO
    with open(temp_path, "rb") as f:
        put_object_fileobj(
            bucket=settings.s3_raw_docs_bucket,
            key=object_key,
            fileobj=f,
            content_type=content_type,
        )

    # 3) Persist metadata
    upsert_company(db, ticker=ticker, company_name=company_name)

    document = Document(
        doc_id=doc_id,
        ticker=ticker,
        company_name=company_name,
        document_type=document_type,
        fiscal_year=fiscal_year,
        filing_date=filing_date,
        source_url=source_url,
        checksum=sha256,
        version=next_version,
    )
    db.add(document)

    doc_file = DocumentFile(
        doc_id=doc_id,
        bucket=settings.s3_raw_docs_bucket,
        object_key=object_key,
        content_type=content_type,
        size_bytes=size_bytes,
        checksum=sha256,
    )
    db.add(doc_file)

    db.commit()
    db.refresh(document)
    db.refresh(doc_file)

    return document, doc_file, False


def get_document(db: Session, *, doc_id: str) -> Document | None:
    return db.get(Document, doc_id)


def get_document_file(db: Session, *, doc_id: str) -> DocumentFile | None:
    return db.execute(select(DocumentFile).where(DocumentFile.doc_id == doc_id)).scalars().first()


def list_documents_for_ticker(
    db: Session,
    *,
    ticker: str,
    document_types: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Document]:
    ticker_norm = normalize_ticker(ticker)
    stmt = select(Document).where(Document.ticker == ticker_norm)
    if document_types:
        # document_type is normalized to lowercase in ingestion.
        doc_types = [(_safe_token(x).lower()) for x in document_types if x]
        if doc_types:
            stmt = stmt.where(Document.document_type.in_(doc_types))
    stmt = (
        stmt.order_by(
            Document.filing_date.desc().nulls_last(),
            Document.version.desc(),
            Document.created_at.desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def list_document_versions(db: Session, *, doc_id: str, limit: int = 50) -> list[Document]:
    """
    Phase 9: retrieve the version chain for a document.

    "Same document" identity = (ticker, document_type, fiscal_year, filing_date).
    """

    doc = get_document(db, doc_id=doc_id)
    if not doc:
        return []

    stmt = (
        select(Document)
        .where(Document.ticker == doc.ticker)
        .where(Document.document_type == doc.document_type)
    )
    if doc.fiscal_year is None:
        stmt = stmt.where(Document.fiscal_year.is_(None))
    else:
        stmt = stmt.where(Document.fiscal_year == doc.fiscal_year)

    if doc.filing_date is None:
        stmt = stmt.where(Document.filing_date.is_(None))
    else:
        stmt = stmt.where(Document.filing_date == doc.filing_date)

    stmt = stmt.order_by(Document.version.desc(), Document.created_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars().all())


def create_download_link(*, bucket: str, key: str, expires_in_seconds: int = 3600) -> str:
    return presign_get_object(bucket=bucket, key=key, expires_in_seconds=expires_in_seconds)
