from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from tickerlens_api.auth.dependencies import require_admin_if_auth_enabled, require_user_if_auth_enabled
from tickerlens_api.audit.service import log_audit
from tickerlens_api.db.session import get_db
from tickerlens_api.documents.schemas import DocumentListItem, DownloadLinkResponse, UploadDocumentResponse
from tickerlens_api.documents.service import (
    create_download_link,
    get_document,
    get_document_file,
    list_document_versions,
    upload_document,
)

router = APIRouter(prefix="/documents", tags=["documents"], dependencies=[Depends(require_user_if_auth_enabled)])


@router.post("/upload", response_model=UploadDocumentResponse)
def upload(
    request: Request,
    file: Annotated[UploadFile, File(..., description="PDF/HTML filing document")],
    ticker: Annotated[str, Form(..., description="NSE ticker symbol, e.g. INFY")],
    document_type: Annotated[str, Form(..., description="annual_report, concall, quarterly_results, ...")],
    company_name: Annotated[str | None, Form(description="Optional company name")] = None,
    fiscal_year: Annotated[str | None, Form(description="e.g. FY24")] = None,
    filing_date: Annotated[str | None, Form(description="YYYY-MM-DD")] = None,
    source_url: Annotated[str | None, Form(description="Optional source URL")] = None,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin_if_auth_enabled),
) -> UploadDocumentResponse:
    filing_date_parsed: dt.date | None = None
    if filing_date:
        try:
            filing_date_parsed = dt.date.fromisoformat(filing_date)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=f"Invalid filing_date: {e}") from e

    try:
        document, doc_file, deduped = upload_document(
            db,
            file=file,
            ticker=ticker,
            company_name=company_name,
            document_type=document_type,
            fiscal_year=fiscal_year,
            filing_date=filing_date_parsed,
            source_url=source_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    log_audit(
        db,
        action="documents.upload",
        request=request,
        user_id=getattr(request.state, "user_id", None),
        status_code=200,
        details={"ticker": ticker, "document_type": document_type, "deduplicated": deduped},
    )

    return UploadDocumentResponse(
        document={
            "doc_id": document.doc_id,
            "ticker": document.ticker,
            "company_name": document.company_name,
            "document_type": document.document_type,
            "fiscal_year": document.fiscal_year,
            "filing_date": document.filing_date,
            "source_url": document.source_url,
            "checksum": document.checksum,
            "version": document.version,
        },
        file={
            "bucket": doc_file.bucket,
            "object_key": doc_file.object_key,
            "content_type": doc_file.content_type,
            "size_bytes": doc_file.size_bytes,
            "checksum": doc_file.checksum,
        },
        deduplicated=deduped,
    )


@router.get("/{doc_id}")
def get_metadata(doc_id: str, db: Session = Depends(get_db)) -> dict:
    doc = get_document(db, doc_id=doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc_file = get_document_file(db, doc_id=doc_id)
    return {
        "document": {
            "doc_id": doc.doc_id,
            "ticker": doc.ticker,
            "company_name": doc.company_name,
            "document_type": doc.document_type,
            "fiscal_year": doc.fiscal_year,
            "filing_date": doc.filing_date,
            "source_url": doc.source_url,
            "checksum": doc.checksum,
            "version": doc.version,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
        },
        "file": (
            {
                "bucket": doc_file.bucket,
                "object_key": doc_file.object_key,
                "content_type": doc_file.content_type,
                "size_bytes": doc_file.size_bytes,
                "checksum": doc_file.checksum,
                "created_at": doc_file.created_at,
            }
            if doc_file
            else None
        ),
    }


@router.get("/{doc_id}/download", response_model=DownloadLinkResponse)
def download(doc_id: str, db: Session = Depends(get_db)) -> DownloadLinkResponse:
    doc_file = get_document_file(db, doc_id=doc_id)
    if not doc_file:
        raise HTTPException(status_code=404, detail="Document file not found")

    expires = 3600
    url = create_download_link(bucket=doc_file.bucket, key=doc_file.object_key, expires_in_seconds=expires)
    return DownloadLinkResponse(doc_id=doc_id, url=url, expires_in_seconds=expires)


@router.get("/{doc_id}/versions", response_model=list[DocumentListItem])
def versions(doc_id: str, db: Session = Depends(get_db)) -> list[DocumentListItem]:
    """
    Phase 9: list all known versions for the same semantic document identity.

    Identity = (ticker, document_type, fiscal_year, filing_date)
    """

    items = list_document_versions(db, doc_id=doc_id, limit=100)
    if not items:
        doc = get_document(db, doc_id=doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return []

    return [
        DocumentListItem(
            doc_id=d.doc_id,
            ticker=d.ticker,
            company_name=d.company_name,
            document_type=d.document_type,
            fiscal_year=d.fiscal_year,
            filing_date=d.filing_date,
            source_url=d.source_url,
            checksum=d.checksum,
            version=d.version,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in items
    ]
