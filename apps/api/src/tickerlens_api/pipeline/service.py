from __future__ import annotations

import traceback
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from tickerlens_api.chunking.service import create_chunk_run, get_latest_successful_chunk_run_for_parse, run_chunk_job
from tickerlens_api.db.models import DocumentChunkRun, DocumentEmbeddingRun, DocumentIndexRun, DocumentParseRun
from tickerlens_api.db.session import SessionLocal
from tickerlens_api.documents.service import get_document
from tickerlens_api.embeddings.service import (
    compute_embedding_target,
    create_embedding_run,
    get_latest_successful_embedding_run_for_chunk,
    run_embedding_job,
)
from tickerlens_api.indexing.service import (
    compute_index_target,
    create_index_run,
    get_latest_successful_index_run_for_chunk,
    run_index_job,
)
from tickerlens_api.parsing.service import create_parse_run, get_latest_successful_run, run_parse_job
from tickerlens_api.pipeline.schemas import PipelineGoal, ProcessDocumentRequest, StageRef


@dataclass(frozen=True)
class PipelinePlan:
    goal: PipelineGoal
    parse: StageRef | None
    chunk: StageRef | None
    embed: StageRef | None
    index: StageRef | None
    embedding_target: dict | None
    index_target: dict | None


def _wants(*, goal: PipelineGoal, stage: str) -> bool:
    order = ["parse", "chunk", "embed", "index"]
    if goal == "searchable":
        return stage in order
    want_idx = order.index(goal)
    return order.index(stage) <= want_idx


def _latest_active_parse_run(db: Session, *, doc_id: str) -> DocumentParseRun | None:
    stmt = (
        select(DocumentParseRun)
        .where(DocumentParseRun.doc_id == doc_id)
        .where(DocumentParseRun.status.in_(["queued", "running"]))
        .order_by(DocumentParseRun.created_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def _latest_active_chunk_run(
    db: Session,
    *,
    doc_id: str,
    parse_run_id: str,
    max_chunk_chars: int,
    overlap_chars: int,
    max_block_chars: int,
) -> DocumentChunkRun | None:
    stmt = (
        select(DocumentChunkRun)
        .where(DocumentChunkRun.doc_id == doc_id)
        .where(DocumentChunkRun.parse_run_id == parse_run_id)
        .where(DocumentChunkRun.max_chunk_chars == max_chunk_chars)
        .where(DocumentChunkRun.overlap_chars == overlap_chars)
        .where(DocumentChunkRun.max_block_chars == max_block_chars)
        .where(DocumentChunkRun.status.in_(["queued", "running"]))
        .order_by(DocumentChunkRun.created_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def _latest_active_embedding_run(
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
        .where(DocumentEmbeddingRun.status.in_(["queued", "running"]))
        .order_by(DocumentEmbeddingRun.created_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def _latest_active_index_run(
    db: Session,
    *,
    doc_id: str,
    parse_run_id: str,
    chunk_run_id: str,
    backend: str,
    index_name: str,
) -> DocumentIndexRun | None:
    stmt = (
        select(DocumentIndexRun)
        .where(DocumentIndexRun.doc_id == doc_id)
        .where(DocumentIndexRun.parse_run_id == parse_run_id)
        .where(DocumentIndexRun.chunk_run_id == chunk_run_id)
        .where(DocumentIndexRun.backend == backend)
        .where(DocumentIndexRun.index_name == index_name)
        .where(DocumentIndexRun.status.in_(["queued", "running"]))
        .order_by(DocumentIndexRun.created_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def plan_document_processing(db: Session, *, doc_id: str, req: ProcessDocumentRequest) -> PipelinePlan:
    """
    Computes an incremental processing plan and eagerly creates missing run records.

    This makes the endpoint idempotent:
    - If a suitable run already exists (succeeded or active), it is reused.
    - Otherwise a new run is created (queued) and the orchestrator will execute it.
    """

    doc = get_document(db, doc_id=doc_id)
    if not doc:
        raise ValueError("Document not found")

    parse_ref: StageRef | None = None
    chunk_ref: StageRef | None = None
    embed_ref: StageRef | None = None
    index_ref: StageRef | None = None

    embedding_target: dict | None = None
    index_target: dict | None = None

    parse_run: DocumentParseRun | None = None
    if _wants(goal=req.goal, stage="parse"):
        if not req.force_parse:
            parse_run = _latest_active_parse_run(db, doc_id=doc_id) or get_latest_successful_run(db, doc_id=doc_id)
        if parse_run is None:
            parse_run = create_parse_run(db, doc_id=doc_id)
            action = "created"
        else:
            action = "reused"
        parse_ref = StageRef(stage="parse", run_id=parse_run.run_id, status=parse_run.status, action=action)

    chunk_run: DocumentChunkRun | None = None
    if _wants(goal=req.goal, stage="chunk"):
        if not parse_run:
            raise ValueError("parse stage is required before chunking")
        parse_run_id = parse_run.run_id

        if not req.force_chunk:
            chunk_run = (
                _latest_active_chunk_run(
                    db,
                    doc_id=doc_id,
                    parse_run_id=parse_run_id,
                    max_chunk_chars=req.max_chunk_chars,
                    overlap_chars=req.overlap_chars,
                    max_block_chars=req.max_block_chars,
                )
                or get_latest_successful_chunk_run_for_parse(
                    db,
                    doc_id=doc_id,
                    parse_run_id=parse_run_id,
                    max_chunk_chars=req.max_chunk_chars,
                    overlap_chars=req.overlap_chars,
                    max_block_chars=req.max_block_chars,
                )
            )
        if chunk_run is None:
            chunk_run = create_chunk_run(
                db,
                doc_id=doc_id,
                parse_run_id=parse_run_id,
                max_chunk_chars=req.max_chunk_chars,
                overlap_chars=req.overlap_chars,
                max_block_chars=req.max_block_chars,
            )
            action = "created"
        else:
            action = "reused"
        chunk_ref = StageRef(stage="chunk", run_id=chunk_run.run_id, status=chunk_run.status, action=action)

    if _wants(goal=req.goal, stage="embed"):
        if not parse_run or not chunk_run:
            raise ValueError("parse + chunk stages are required before embedding")

        model, dims, vector_size, collection = compute_embedding_target(
            embedding_model=req.embedding_model, dimensions=req.dimensions
        )
        embedding_target = {"model": model, "dimensions": dims, "vector_size": vector_size, "collection": collection}

        if not req.force_embed:
            active = _latest_active_embedding_run(
                db,
                doc_id=doc_id,
                parse_run_id=parse_run.run_id,
                chunk_run_id=chunk_run.run_id,
                embedding_model=model,
                dimensions=dims,
                qdrant_collection=collection,
            )
            succeeded = get_latest_successful_embedding_run_for_chunk(
                db,
                doc_id=doc_id,
                parse_run_id=parse_run.run_id,
                chunk_run_id=chunk_run.run_id,
                embedding_model=model,
                dimensions=dims,
                qdrant_collection=collection,
            )
            embed_run = active or succeeded
        else:
            embed_run = None

        if embed_run is None:
            embed_run = create_embedding_run(
                db,
                doc_id=doc_id,
                parse_run_id=parse_run.run_id,
                chunk_run_id=chunk_run.run_id,
                embedding_model=model,
                dimensions=dims,
                vector_size=vector_size,
                qdrant_collection=collection,
            )
            action = "created"
        else:
            action = "reused"

        embed_ref = StageRef(stage="embed", run_id=embed_run.run_id, status=embed_run.status, action=action)

    if _wants(goal=req.goal, stage="index") or req.goal == "searchable":
        if not parse_run or not chunk_run:
            raise ValueError("parse + chunk stages are required before indexing")

        backend, index_name = compute_index_target(backend=None, index_version=req.index_version)
        index_target = {"backend": backend, "index_name": index_name}

        if not req.force_index:
            active = _latest_active_index_run(
                db,
                doc_id=doc_id,
                parse_run_id=parse_run.run_id,
                chunk_run_id=chunk_run.run_id,
                backend=backend,
                index_name=index_name,
            )
            succeeded = get_latest_successful_index_run_for_chunk(
                db,
                doc_id=doc_id,
                parse_run_id=parse_run.run_id,
                chunk_run_id=chunk_run.run_id,
                backend=backend,
                index_name=index_name,
            )
            idx_run = active or succeeded
        else:
            idx_run = None

        if idx_run is None:
            idx_run = create_index_run(
                db,
                doc_id=doc_id,
                parse_run_id=parse_run.run_id,
                chunk_run_id=chunk_run.run_id,
                backend=backend,
                index_name=index_name,
            )
            action = "created"
        else:
            action = "reused"

        index_ref = StageRef(stage="index", run_id=idx_run.run_id, status=idx_run.status, action=action)

    return PipelinePlan(
        goal=req.goal,
        parse=parse_ref,
        chunk=chunk_ref,
        embed=embed_ref,
        index=index_ref,
        embedding_target=embedding_target,
        index_target=index_target,
    )


def run_document_processing(*, doc_id: str, req: ProcessDocumentRequest) -> None:
    """
    Phase 9: best-effort sequential orchestration (in-process).

    This is intentionally simple and uses our existing run_* job functions. It is:
    - deterministic (parse -> chunk -> embed/index)
    - incremental (reuses existing successful runs)
    - auditable (all work is recorded in run tables)

    For production scale we will move this to a dedicated worker/queue.
    """

    db = SessionLocal()
    try:
        plan = plan_document_processing(db, doc_id=doc_id, req=req)
    except Exception:
        db.close()
        return
    finally:
        try:
            db.close()
        except Exception:
            pass

    try:
        # Parse
        if plan.parse and _wants(goal=plan.goal, stage="parse"):
            run_parse_job(run_id=plan.parse.run_id)

            db = SessionLocal()
            try:
                r = db.get(DocumentParseRun, plan.parse.run_id)
                if not r or r.status != "succeeded":
                    return
            finally:
                db.close()

        # Chunk
        if plan.chunk and _wants(goal=plan.goal, stage="chunk"):
            run_chunk_job(chunk_run_id=plan.chunk.run_id)

            db = SessionLocal()
            try:
                r = db.get(DocumentChunkRun, plan.chunk.run_id)
                if not r or r.status != "succeeded":
                    return
            finally:
                db.close()

        # Embed
        if plan.embed and _wants(goal=plan.goal, stage="embed"):
            run_embedding_job(run_id=plan.embed.run_id)

            db = SessionLocal()
            try:
                r = db.get(DocumentEmbeddingRun, plan.embed.run_id)
                if not r or r.status != "succeeded":
                    return
            finally:
                db.close()

        # Index (BM25)
        if plan.index and (_wants(goal=plan.goal, stage="index") or plan.goal == "searchable"):
            run_index_job(run_id=plan.index.run_id)
    except Exception:
        # The lower-level job functions already capture errors into their run records.
        # Keep the orchestrator quiet; it should never crash the API process.
        _ = traceback.format_exc()

