from __future__ import annotations

import datetime as dt
import os
import traceback
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from tickerlens_api.db.models import DocumentFile, DocumentPage, DocumentParseRun
from tickerlens_api.db.session import SessionLocal
from tickerlens_api.parsing.pdf import extract_page_texts
from tickerlens_api.storage.s3 import download_object_to_path


def create_parse_run(db: Session, *, doc_id: str) -> DocumentParseRun:
    run = DocumentParseRun(run_id=str(uuid.uuid4()), doc_id=doc_id, status="queued")
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def get_parse_run(db: Session, *, run_id: str) -> DocumentParseRun | None:
    return db.get(DocumentParseRun, run_id)


def list_parse_runs(db: Session, *, doc_id: str, limit: int = 20) -> list[DocumentParseRun]:
    stmt = (
        select(DocumentParseRun)
        .where(DocumentParseRun.doc_id == doc_id)
        .order_by(DocumentParseRun.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def get_latest_successful_run(db: Session, *, doc_id: str) -> DocumentParseRun | None:
    stmt = (
        select(DocumentParseRun)
        .where(DocumentParseRun.doc_id == doc_id)
        .where(DocumentParseRun.status == "succeeded")
        .order_by(DocumentParseRun.finished_at.desc().nullslast(), DocumentParseRun.created_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def list_pages(db: Session, *, doc_id: str, run_id: str) -> list[DocumentPage]:
    stmt = (
        select(DocumentPage)
        .where(DocumentPage.doc_id == doc_id)
        .where(DocumentPage.run_id == run_id)
        .order_by(DocumentPage.page_num.asc())
    )
    return list(db.execute(stmt).scalars().all())


def get_page(db: Session, *, doc_id: str, run_id: str, page_num: int) -> DocumentPage | None:
    stmt = (
        select(DocumentPage)
        .where(DocumentPage.doc_id == doc_id)
        .where(DocumentPage.run_id == run_id)
        .where(DocumentPage.page_num == page_num)
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def _find_document_file(db: Session, *, doc_id: str) -> DocumentFile | None:
    stmt = select(DocumentFile).where(DocumentFile.doc_id == doc_id).limit(1)
    return db.execute(stmt).scalars().first()


def run_parse_job(*, run_id: str) -> None:
    """
    Execute a parse run. Intended to be called from a background task.

    Important: this uses its own DB session because FastAPI request-scoped sessions are not safe to share.
    """

    db = SessionLocal()
    temp_path: str | None = None
    try:
        run = db.get(DocumentParseRun, run_id)
        if not run:
            return
        if run.status in {"running", "succeeded"}:
            return

        run.status = "running"
        run.started_at = dt.datetime.now(dt.timezone.utc)
        db.commit()

        doc_file = _find_document_file(db, doc_id=run.doc_id)
        if not doc_file:
            raise RuntimeError("Document file not found (upload raw doc first).")

        temp_path = os.path.join("/tmp", f"{run.doc_id}-{run.run_id}.pdf")
        download_object_to_path(bucket=doc_file.bucket, key=doc_file.object_key, path=temp_path)

        page_texts = extract_page_texts(temp_path)

        ocr_pages = 0
        for p in page_texts:
            if p.extraction_method == "ocr":
                ocr_pages += 1
            db.add(
                DocumentPage(
                    doc_id=run.doc_id,
                    run_id=run.run_id,
                    page_num=p.page_num,
                    extraction_method=p.extraction_method,
                    text=p.text,
                    char_count=p.char_count,
                    checksum=p.checksum,
                )
            )

        run.page_count = len(page_texts)
        run.ocr_page_count = ocr_pages
        run.status = "succeeded"
        run.finished_at = dt.datetime.now(dt.timezone.utc)
        db.commit()
    except Exception as e:
        run = db.get(DocumentParseRun, run_id)
        if run:
            run.status = "failed"
            run.finished_at = dt.datetime.now(dt.timezone.utc)
            run.error_message = f"{e}\n{traceback.format_exc()}"
            db.commit()
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass
        db.close()

