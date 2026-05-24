from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from tickerlens_api.db.session import get_db
from tickerlens_api.documents.service import get_document
from tickerlens_api.parsing.schemas import PageOut, PagePreviewOut, ParseRunOut
from tickerlens_api.parsing.service import (
    create_parse_run,
    get_latest_successful_run,
    get_page,
    get_parse_run,
    list_pages,
    list_parse_runs,
    run_parse_job,
)

router = APIRouter(tags=["parsing"])


@router.post("/documents/{doc_id}/parse", response_model=ParseRunOut)
def trigger_parse(
    doc_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ParseRunOut:
    doc = get_document(db, doc_id=doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    run = create_parse_run(db, doc_id=doc_id)
    background_tasks.add_task(run_parse_job, run_id=run.run_id)
    return ParseRunOut.model_validate(run, from_attributes=True)


@router.get("/documents/{doc_id}/parse-runs", response_model=list[ParseRunOut])
def runs(doc_id: str, db: Session = Depends(get_db)) -> list[ParseRunOut]:
    doc = get_document(db, doc_id=doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    items = list_parse_runs(db, doc_id=doc_id)
    return [ParseRunOut.model_validate(r, from_attributes=True) for r in items]


@router.get("/parse-runs/{run_id}", response_model=ParseRunOut)
def run_detail(run_id: str, db: Session = Depends(get_db)) -> ParseRunOut:
    run = get_parse_run(db, run_id=run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Parse run not found")
    return ParseRunOut.model_validate(run, from_attributes=True)


@router.get("/documents/{doc_id}/pages", response_model=list[PagePreviewOut])
def pages(doc_id: str, run_id: str | None = None, db: Session = Depends(get_db)) -> list[PagePreviewOut]:
    doc = get_document(db, doc_id=doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if run_id is None:
        latest = get_latest_successful_run(db, doc_id=doc_id)
        if not latest:
            raise HTTPException(status_code=404, detail="No successful parse runs yet")
        run_id = latest.run_id

    items = list_pages(db, doc_id=doc_id, run_id=run_id)
    out: list[PagePreviewOut] = []
    for p in items:
        preview = (p.text or "")[:400]
        out.append(
            PagePreviewOut(
                doc_id=p.doc_id,
                run_id=p.run_id,
                page_num=p.page_num,
                extraction_method=p.extraction_method,
                char_count=p.char_count,
                checksum=p.checksum,
                preview=preview,
            )
        )
    return out


@router.get("/documents/{doc_id}/pages/{page_num}", response_model=PageOut)
def page(
    doc_id: str, page_num: int, run_id: str | None = None, db: Session = Depends(get_db)
) -> PageOut:
    doc = get_document(db, doc_id=doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if run_id is None:
        latest = get_latest_successful_run(db, doc_id=doc_id)
        if not latest:
            raise HTTPException(status_code=404, detail="No successful parse runs yet")
        run_id = latest.run_id

    p = get_page(db, doc_id=doc_id, run_id=run_id, page_num=page_num)
    if not p:
        raise HTTPException(status_code=404, detail="Page not found for given run")
    return PageOut(
        doc_id=p.doc_id,
        run_id=p.run_id,
        page_num=p.page_num,
        extraction_method=p.extraction_method,
        char_count=p.char_count,
        checksum=p.checksum,
        text=p.text,
    )

