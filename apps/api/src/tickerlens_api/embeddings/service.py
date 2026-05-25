from __future__ import annotations

import datetime as dt
import traceback
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from tickerlens_api.db.models import Document, DocumentChunk, DocumentChunkRun, DocumentEmbeddingRun
from tickerlens_api.db.session import SessionLocal
from tickerlens_api.embeddings.openai_embedder import embed_texts, get_embedding_config
from tickerlens_api.settings import settings
from tickerlens_api.vectorstore.qdrant_store import (
    compute_collection_name,
    compute_vector_size,
    ensure_collection,
    upsert_points,
)

from qdrant_client import models as qmodels


def create_embedding_run(
    db: Session,
    *,
    doc_id: str,
    parse_run_id: str,
    chunk_run_id: str,
    embedding_model: str,
    dimensions: int | None,
    vector_size: int,
    qdrant_collection: str,
) -> DocumentEmbeddingRun:
    run = DocumentEmbeddingRun(
        run_id=str(uuid.uuid4()),
        doc_id=doc_id,
        parse_run_id=parse_run_id,
        chunk_run_id=chunk_run_id,
        status="queued",
        embedding_model=embedding_model,
        dimensions=dimensions,
        vector_size=vector_size,
        qdrant_collection=qdrant_collection,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def get_embedding_run(db: Session, *, run_id: str) -> DocumentEmbeddingRun | None:
    return db.get(DocumentEmbeddingRun, run_id)


def list_embedding_runs(db: Session, *, doc_id: str, limit: int = 20) -> list[DocumentEmbeddingRun]:
    stmt = (
        select(DocumentEmbeddingRun)
        .where(DocumentEmbeddingRun.doc_id == doc_id)
        .order_by(DocumentEmbeddingRun.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def get_latest_successful_embedding_run_for_chunk(
    db: Session,
    *,
    doc_id: str,
    parse_run_id: str,
    chunk_run_id: str,
    embedding_model: str,
    dimensions: int | None,
    qdrant_collection: str,
) -> DocumentEmbeddingRun | None:
    stmt = (
        select(DocumentEmbeddingRun)
        .where(DocumentEmbeddingRun.doc_id == doc_id)
        .where(DocumentEmbeddingRun.parse_run_id == parse_run_id)
        .where(DocumentEmbeddingRun.chunk_run_id == chunk_run_id)
        .where(DocumentEmbeddingRun.embedding_model == embedding_model)
        .where(DocumentEmbeddingRun.dimensions == dimensions)
        .where(DocumentEmbeddingRun.qdrant_collection == qdrant_collection)
        .where(DocumentEmbeddingRun.status == "succeeded")
        .order_by(DocumentEmbeddingRun.finished_at.desc().nullslast(), DocumentEmbeddingRun.created_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def _get_doc(db: Session, *, doc_id: str) -> Document | None:
    return db.get(Document, doc_id)


def _get_chunk_run(db: Session, *, run_id: str) -> DocumentChunkRun | None:
    return db.get(DocumentChunkRun, run_id)


def _iter_chunks(db: Session, *, doc_id: str, chunk_run_id: str, batch_size: int = 200):
    """
    Stream chunks in deterministic order without loading everything into memory.
    """
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


def run_embedding_job(*, run_id: str) -> None:
    """
    Embeds all chunks for a chunk run and upserts them into Qdrant.

    This is intentionally "manual-first" (triggered by an API call) and runs as a FastAPI BackgroundTask.
    For large-scale usage we will move this to a proper worker/queue.
    """

    db = SessionLocal()
    try:
        run = db.get(DocumentEmbeddingRun, run_id)
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

        ensure_collection(collection_name=run.qdrant_collection, vector_size=run.vector_size)

        embedded = 0
        batch_ids: list[str] = []
        batch_texts: list[str] = []
        batch_payloads: list[dict] = []

        def flush_batch() -> None:
            nonlocal embedded, batch_ids, batch_texts, batch_payloads
            if not batch_ids:
                return
            vectors = embed_texts(texts=batch_texts, model=run.embedding_model, dimensions=run.dimensions)
            points: list[qmodels.PointStruct] = []
            for chunk_id, vec, payload in zip(batch_ids, vectors, batch_payloads, strict=True):
                points.append(qmodels.PointStruct(id=chunk_id, vector=vec, payload=payload))
            upsert_points(collection_name=run.qdrant_collection, points=points)
            embedded += len(points)
            batch_ids = []
            batch_texts = []
            batch_payloads = []

        # Keep batches modest to avoid token burst and to keep failures localized.
        embed_batch_size = 32

        for ch in _iter_chunks(db, doc_id=run.doc_id, chunk_run_id=run.chunk_run_id, batch_size=200):
            text = ch.text or ""
            if not text.strip():
                continue
            batch_ids.append(ch.chunk_id)
            batch_texts.append(text)
            batch_payloads.append(
                {
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
                }
            )
            if len(batch_ids) >= embed_batch_size:
                flush_batch()

        flush_batch()

        run.embedded_chunks = embedded
        run.status = "succeeded"
        run.finished_at = dt.datetime.now(dt.timezone.utc)
        db.commit()
    except Exception as e:
        run = db.get(DocumentEmbeddingRun, run_id)
        if run:
            run.status = "failed"
            run.finished_at = dt.datetime.now(dt.timezone.utc)
            run.error_message = f"{e}\n{traceback.format_exc()}"
            db.commit()
    finally:
        db.close()


def compute_embedding_target(*, embedding_model: str | None, dimensions: int | None) -> tuple[str, int | None, int, str]:
    """
    Returns (model, dimensions, vector_size, collection_name) based on settings defaults.
    """

    cfg = get_embedding_config()
    model = embedding_model or cfg.model
    dims = dimensions if dimensions is not None else cfg.dimensions
    vector_size = compute_vector_size(model=model, dimensions=dims)
    collection = compute_collection_name(model=model, vector_size=vector_size)
    return model, dims, vector_size, collection
