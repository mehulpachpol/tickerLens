from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from tickerlens_api.db.models import Document


@dataclass(frozen=True)
class ScopedDocument:
    doc_id: str
    ticker: str
    document_type: str
    fiscal_year: str | None
    filing_date: str | None
    version: int


@dataclass(frozen=True)
class TemporalDocScope:
    """
    A concrete, auditable retrieval scope for Phase 9.

    We use this to implement "latest within relevant document types" without relying on
    fuzzy score boosting. Scoping via doc_ids gives:
    - deterministic behavior
    - lower latency (smaller search space)
    - easier audit ("these were the only docs considered for 'latest'")
    """

    mode: str  # "latest"
    reason: str
    preferred_document_types: list[str]
    selected: list[ScopedDocument]

    @property
    def doc_ids(self) -> list[str]:
        return [d.doc_id for d in self.selected]


def _latest_docs_for_ticker(
    db: Session,
    *,
    ticker: str,
    document_types: list[str] | None,
    limit: int,
) -> list[Document]:
    stmt = select(Document).where(Document.ticker == ticker)
    if document_types:
        stmt = stmt.where(Document.document_type.in_(document_types))
    stmt = stmt.order_by(
        Document.filing_date.desc().nulls_last(),
        Document.version.desc(),
        Document.created_at.desc(),
    ).limit(limit)
    return list(db.execute(stmt).scalars().all())


def resolve_latest_doc_scope(
    db: Session,
    *,
    tickers: list[str],
    preferred_document_types: list[str],
    reason: str,
    max_docs_per_ticker: int = 5,
) -> TemporalDocScope:
    """
    Select a bounded set of doc_ids per ticker for "latest" questions.

    Strategy:
    1) Try preferred doc types first
    2) If none exist for a ticker, fall back to any doc type (still latest-first)
    """

    chosen: list[ScopedDocument] = []

    for t in tickers:
        rows = _latest_docs_for_ticker(
            db, ticker=t, document_types=preferred_document_types, limit=max_docs_per_ticker
        )
        if not rows:
            rows = _latest_docs_for_ticker(db, ticker=t, document_types=None, limit=min(2, max_docs_per_ticker))

        for d in rows:
            chosen.append(
                ScopedDocument(
                    doc_id=d.doc_id,
                    ticker=d.ticker,
                    document_type=d.document_type,
                    fiscal_year=d.fiscal_year,
                    filing_date=d.filing_date.isoformat() if d.filing_date else None,
                    version=d.version,
                )
            )

    # Stable de-dupe by doc_id (doc_ids are globally unique)
    unique_by_id: dict[str, ScopedDocument] = {d.doc_id: d for d in chosen}
    selected = list(unique_by_id.values())

    return TemporalDocScope(
        mode="latest",
        reason=reason,
        preferred_document_types=preferred_document_types,
        selected=selected,
    )
