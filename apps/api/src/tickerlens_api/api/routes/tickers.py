from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from tickerlens_api.auth.dependencies import require_user_if_auth_enabled
from tickerlens_api.db.session import get_db
from tickerlens_api.documents.schemas import DocumentListItem
from tickerlens_api.documents.service import list_documents_for_ticker


router = APIRouter(prefix="/tickers", tags=["tickers"], dependencies=[Depends(require_user_if_auth_enabled)])


@router.get("/{ticker}/documents", response_model=list[DocumentListItem])
def list_documents(
    ticker: str,
    document_types: list[str] | None = Query(default=None, description="Optional document_type filters."),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=1000000),
    db: Session = Depends(get_db),
) -> list[DocumentListItem]:
    """
    Phase 9: Timeline API building block.

    Returns documents ordered by filing_date DESC (NULLS LAST), then created_at DESC.
    """

    docs = list_documents_for_ticker(
        db, ticker=ticker, document_types=document_types, limit=limit, offset=offset
    )
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
        for d in docs
    ]
