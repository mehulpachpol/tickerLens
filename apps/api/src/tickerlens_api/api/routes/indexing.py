from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from tickerlens_api.auth.dependencies import require_admin_if_auth_enabled
from tickerlens_api.chunking.service import get_chunk_run, get_latest_successful_chunk_run
from tickerlens_api.db.session import get_db
from tickerlens_api.documents.service import get_document
from tickerlens_api.indexing.schemas import IndexRunOut
from tickerlens_api.indexing.service import (
    compute_index_target,
    create_index_run,
    get_index_run,
    list_index_runs,
    run_index_job,
)

router = APIRouter(tags=["indexing"], dependencies=[Depends(require_admin_if_auth_enabled)])


@router.post("/documents/{doc_id}/index", response_model=IndexRunOut)
def trigger_indexing(
    doc_id: str,
    background_tasks: BackgroundTasks,
    chunk_run_id: str | None = Query(default=None, description="Chunk run id. Defaults to latest successful chunk run."),
    backend: str | None = Query(default=None, description="Index backend. Only 'opensearch' supported for now."),
    index_version: str = Query(default="v1", min_length=1, max_length=20),
    db: Session = Depends(get_db),
) -> IndexRunOut:
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

    try:
        resolved_backend, index_name = compute_index_target(backend=backend, index_version=index_version)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    run = create_index_run(
        db,
        doc_id=doc_id,
        parse_run_id=chunk_run.parse_run_id,
        chunk_run_id=chunk_run.run_id,
        backend=resolved_backend,
        index_name=index_name,
    )
    background_tasks.add_task(run_index_job, run_id=run.run_id)
    return IndexRunOut.model_validate(run, from_attributes=True)


@router.get("/documents/{doc_id}/index-runs", response_model=list[IndexRunOut])
def runs(doc_id: str, db: Session = Depends(get_db)) -> list[IndexRunOut]:
    doc = get_document(db, doc_id=doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    items = list_index_runs(db, doc_id=doc_id)
    return [IndexRunOut.model_validate(r, from_attributes=True) for r in items]


@router.get("/index-runs/{run_id}", response_model=IndexRunOut)
def run_detail(run_id: str, db: Session = Depends(get_db)) -> IndexRunOut:
    run = get_index_run(db, run_id=run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Index run not found")
    return IndexRunOut.model_validate(run, from_attributes=True)
