from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from tickerlens_api.auth.dependencies import require_admin_if_auth_enabled
from tickerlens_api.chunking.service import get_chunk_run, get_latest_successful_chunk_run
from tickerlens_api.db.session import get_db
from tickerlens_api.documents.service import get_document
from tickerlens_api.embeddings.schemas import EmbeddingRunOut
from tickerlens_api.embeddings.service import (
    compute_embedding_target,
    create_embedding_run,
    get_embedding_run,
    list_embedding_runs,
    run_embedding_job,
)
from tickerlens_api.settings import settings

router = APIRouter(tags=["embeddings"], dependencies=[Depends(require_admin_if_auth_enabled)])


@router.post("/documents/{doc_id}/embed", response_model=EmbeddingRunOut)
def trigger_embedding(
    doc_id: str,
    background_tasks: BackgroundTasks,
    chunk_run_id: str | None = Query(default=None, description="Chunk run id. Defaults to latest successful chunk run."),
    embedding_model: str | None = Query(default=None, description="Overrides default embedding model."),
    dimensions: int | None = Query(default=None, ge=64, le=8192, description="Optional embedding dimensions override."),
    db: Session = Depends(get_db),
) -> EmbeddingRunOut:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=422,
            detail="Missing OpenAI API key. Set OPENAI_API_KEY (or TICKERLENS_OPENAI_API_KEY).",
        )

    doc = get_document(db, doc_id=doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if chunk_run_id is None:
        latest = get_latest_successful_chunk_run(db, doc_id=doc_id)
        if not latest:
            raise HTTPException(status_code=404, detail="No successful chunk runs yet")
        chunk_run_id = latest.run_id

    chunk_run = get_chunk_run(db, run_id=chunk_run_id)
    if not chunk_run or chunk_run.doc_id != doc_id:
        raise HTTPException(status_code=404, detail="Chunk run not found for this document")
    if chunk_run.status != "succeeded":
        raise HTTPException(status_code=409, detail="Chunk run is not in succeeded state")

    model, dims, vector_size, collection = compute_embedding_target(
        embedding_model=embedding_model, dimensions=dimensions
    )

    run = create_embedding_run(
        db,
        doc_id=doc_id,
        parse_run_id=chunk_run.parse_run_id,
        chunk_run_id=chunk_run.run_id,
        embedding_model=model,
        dimensions=dims,
        vector_size=vector_size,
        qdrant_collection=collection,
    )
    background_tasks.add_task(run_embedding_job, run_id=run.run_id)
    return EmbeddingRunOut.model_validate(run, from_attributes=True)


@router.get("/documents/{doc_id}/embed-runs", response_model=list[EmbeddingRunOut])
def runs(doc_id: str, db: Session = Depends(get_db)) -> list[EmbeddingRunOut]:
    doc = get_document(db, doc_id=doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    items = list_embedding_runs(db, doc_id=doc_id)
    return [EmbeddingRunOut.model_validate(r, from_attributes=True) for r in items]


@router.get("/embed-runs/{run_id}", response_model=EmbeddingRunOut)
def run_detail(run_id: str, db: Session = Depends(get_db)) -> EmbeddingRunOut:
    run = get_embedding_run(db, run_id=run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Embedding run not found")
    return EmbeddingRunOut.model_validate(run, from_attributes=True)
