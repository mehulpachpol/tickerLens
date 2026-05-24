from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from tickerlens_api.chunking.schemas import ChunkOut, ChunkPreviewOut, ChunkRunOut, ChunkSpanOut
from tickerlens_api.chunking.service import (
    create_chunk_run,
    get_chunk,
    get_chunk_run,
    get_latest_successful_chunk_run,
    list_chunk_runs,
    list_chunk_spans,
    list_chunks,
    run_chunk_job,
)
from tickerlens_api.db.session import get_db
from tickerlens_api.documents.service import get_document
from tickerlens_api.parsing.service import get_latest_successful_run

router = APIRouter(tags=["chunking"])


@router.post("/documents/{doc_id}/chunk", response_model=ChunkRunOut)
def trigger_chunking(
    doc_id: str,
    background_tasks: BackgroundTasks,
    parse_run_id: str | None = Query(default=None, description="Parse run id. Defaults to latest successful parse."),
    max_chunk_chars: int = Query(default=5000, ge=500, le=20000),
    overlap_chars: int = Query(default=250, ge=0, le=2000),
    max_block_chars: int = Query(default=1200, ge=200, le=5000),
    db: Session = Depends(get_db),
) -> ChunkRunOut:
    doc = get_document(db, doc_id=doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if parse_run_id is None:
        latest = get_latest_successful_run(db, doc_id=doc_id)
        if not latest:
            raise HTTPException(status_code=404, detail="No successful parse runs yet")
        parse_run_id = latest.run_id

    run = create_chunk_run(
        db,
        doc_id=doc_id,
        parse_run_id=parse_run_id,
        max_chunk_chars=max_chunk_chars,
        overlap_chars=overlap_chars,
        max_block_chars=max_block_chars,
    )
    background_tasks.add_task(run_chunk_job, chunk_run_id=run.run_id)
    return ChunkRunOut.model_validate(run, from_attributes=True)


@router.get("/documents/{doc_id}/chunk-runs", response_model=list[ChunkRunOut])
def chunk_runs(doc_id: str, db: Session = Depends(get_db)) -> list[ChunkRunOut]:
    doc = get_document(db, doc_id=doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    runs = list_chunk_runs(db, doc_id=doc_id)
    return [ChunkRunOut.model_validate(r, from_attributes=True) for r in runs]


@router.get("/chunk-runs/{run_id}", response_model=ChunkRunOut)
def chunk_run_detail(run_id: str, db: Session = Depends(get_db)) -> ChunkRunOut:
    run = get_chunk_run(db, run_id=run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Chunk run not found")
    return ChunkRunOut.model_validate(run, from_attributes=True)


@router.get("/documents/{doc_id}/chunks", response_model=list[ChunkPreviewOut])
def chunks(
    doc_id: str, chunk_run_id: str | None = None, db: Session = Depends(get_db)
) -> list[ChunkPreviewOut]:
    doc = get_document(db, doc_id=doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if chunk_run_id is None:
        latest = get_latest_successful_chunk_run(db, doc_id=doc_id)
        if not latest:
            raise HTTPException(status_code=404, detail="No successful chunk runs yet")
        chunk_run_id = latest.run_id

    items = list_chunks(db, doc_id=doc_id, chunk_run_id=chunk_run_id)
    out: list[ChunkPreviewOut] = []
    for ch in items:
        out.append(
            ChunkPreviewOut(
                chunk_id=ch.chunk_id,
                doc_id=ch.doc_id,
                chunk_run_id=ch.chunk_run_id,
                parse_run_id=ch.parse_run_id,
                ticker=ch.ticker,
                section=ch.section,
                page_start=ch.page_start,
                page_end=ch.page_end,
                char_count=ch.char_count,
                checksum=ch.checksum,
                preview=(ch.text or "")[:500],
            )
        )
    return out


@router.get("/chunks/{chunk_id}", response_model=ChunkOut)
def chunk_detail(chunk_id: str, db: Session = Depends(get_db)) -> ChunkOut:
    ch = get_chunk(db, chunk_id=chunk_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Chunk not found")
    spans = list_chunk_spans(db, chunk_id=chunk_id)
    return ChunkOut(
        chunk_id=ch.chunk_id,
        doc_id=ch.doc_id,
        chunk_run_id=ch.chunk_run_id,
        parse_run_id=ch.parse_run_id,
        ticker=ch.ticker,
        section=ch.section,
        page_start=ch.page_start,
        page_end=ch.page_end,
        char_count=ch.char_count,
        checksum=ch.checksum,
        text=ch.text,
        spans=[
            ChunkSpanOut(page_num=s.page_num, char_start=s.char_start, char_end=s.char_end) for s in spans
        ],
    )

