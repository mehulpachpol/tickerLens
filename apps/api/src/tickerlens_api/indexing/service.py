from __future__ import annotations

import datetime as dt
import traceback
import uuid

from opensearchpy.helpers import bulk
from sqlalchemy import select
from sqlalchemy.orm import Session

from tickerlens_api.db.models import Document, DocumentChunk, DocumentChunkRun, DocumentIndexRun
from tickerlens_api.db.session import SessionLocal
from tickerlens_api.keywordstore.opensearch_store import compute_chunks_index_name, ensure_chunks_index, get_opensearch_client


def create_index_run(
    db: Session,
    *,
    doc_id: str,
    parse_run_id: str,
    chunk_run_id: str,
    backend: str,
    index_name: str,
) -> DocumentIndexRun:
    run = DocumentIndexRun(
        run_id=str(uuid.uuid4()),
        doc_id=doc_id,
        parse_run_id=parse_run_id,
        chunk_run_id=chunk_run_id,
        status="queued",
        backend=backend,
        index_name=index_name,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def get_index_run(db: Session, *, run_id: str) -> DocumentIndexRun | None:
    return db.get(DocumentIndexRun, run_id)


def list_index_runs(db: Session, *, doc_id: str, limit: int = 20) -> list[DocumentIndexRun]:
    stmt = (
        select(DocumentIndexRun)
        .where(DocumentIndexRun.doc_id == doc_id)
        .order_by(DocumentIndexRun.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def _get_doc(db: Session, *, doc_id: str) -> Document | None:
    return db.get(Document, doc_id)


def _get_chunk_run(db: Session, *, run_id: str) -> DocumentChunkRun | None:
    return db.get(DocumentChunkRun, run_id)


def _iter_chunks(db: Session, *, doc_id: str, chunk_run_id: str, batch_size: int = 200):
    offset = 0
    while True:
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.doc_id == doc_id)
            .where(DocumentChunk.chunk_run_id == chunk_run_id)
            .order_by(DocumentChunk.page_start.asc(), DocumentChunk.chunk_id.asc())
            .offset(offset)
            .limit(batch_size)
        )
        rows = list(db.execute(stmt).scalars().all())
        if not rows:
            return
        for r in rows:
            yield r
        offset += len(rows)


def compute_index_target(*, backend: str | None = None, index_version: str = "v1") -> tuple[str, str]:
    """
    Returns (backend, index_name).
    """

    resolved_backend = backend or "opensearch"
    if resolved_backend != "opensearch":
        raise ValueError(f"Unsupported backend '{resolved_backend}'")
    return resolved_backend, compute_chunks_index_name(version=index_version)


def run_index_job(*, run_id: str) -> None:
    """
    Indexes all chunks for a chunk run into OpenSearch (BM25).

    Manual-first: triggered via API and runs as a FastAPI BackgroundTask.
    """

    db = SessionLocal()
    try:
        run = db.get(DocumentIndexRun, run_id)
        if not run:
            return
        if run.status in {"running", "succeeded"}:
            return

        doc = _get_doc(db, doc_id=run.doc_id)
        if not doc:
            raise RuntimeError("Document not found")

        chunk_run = _get_chunk_run(db, run_id=run.chunk_run_id)
        if not chunk_run or chunk_run.status != "succeeded":
            raise RuntimeError("Chunk run not found or not succeeded")

        run.status = "running"
        run.started_at = dt.datetime.now(dt.timezone.utc)
        db.commit()

        ensure_chunks_index(index_name=run.index_name)
        client = get_opensearch_client()

        indexed = 0
        actions: list[dict] = []
        bulk_batch_size = 500

        def flush() -> None:
            nonlocal indexed, actions
            if not actions:
                return
            ok, errors = bulk(client, actions, raise_on_error=False, stats_only=False)
            indexed += int(ok)
            actions = []
            if errors:
                # Keep the message bounded.
                raise RuntimeError(f"Bulk indexing errors: {str(errors)[:2000]}")

        for ch in _iter_chunks(db, doc_id=run.doc_id, chunk_run_id=run.chunk_run_id, batch_size=200):
            text = ch.text or ""
            if not text.strip():
                continue
            source = {
                "chunk_id": ch.chunk_id,
                "doc_id": ch.doc_id,
                "parse_run_id": ch.parse_run_id,
                "chunk_run_id": ch.chunk_run_id,
                "ticker": ch.ticker,
                "document_type": doc.document_type,
                "fiscal_year": doc.fiscal_year,
                "filing_date": doc.filing_date.isoformat() if doc.filing_date else None,
                "version": doc.version,
                "section": ch.section,
                "page_start": ch.page_start,
                "page_end": ch.page_end,
                "text": text,
            }
            actions.append({"_op_type": "index", "_index": run.index_name, "_id": ch.chunk_id, "_source": source})
            if len(actions) >= bulk_batch_size:
                flush()

        flush()
        client.indices.refresh(index=run.index_name)

        run.status = "succeeded"
        run.indexed_chunks = indexed
        run.finished_at = dt.datetime.now(dt.timezone.utc)
        db.commit()
    except Exception as e:
        run = db.get(DocumentIndexRun, run_id)
        if run:
            run.status = "failed"
            run.finished_at = dt.datetime.now(dt.timezone.utc)
            run.error_message = f"{e}\n{traceback.format_exc()}"
            db.commit()
    finally:
        db.close()

