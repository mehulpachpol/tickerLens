from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from tickerlens_api.db.models import IngestionDiscoveredItem, IngestionRun
from tickerlens_api.db.session import get_db
from tickerlens_api.ingestion.runner import run_nse_discovery, run_nse_ingest_pending, run_nse_sync
from tickerlens_api.ingestion.universe_service import list_active_universe_tickers, seed_nifty50
from tickerlens_api.settings import settings


router = APIRouter(prefix="/ingestion", tags=["ingestion"])


class SeedUniverseResponse(BaseModel):
    universe_id: str
    members: int


class NseDiscoveryRequest(BaseModel):
    universe_id: str = Field(default_factory=lambda: settings.ingestion_universe_id)
    tickers: list[str] | None = None
    from_date: dt.date | None = None
    to_date: dt.date | None = None
    lookback_days: int | None = None


class NseIngestRequest(BaseModel):
    universe_id: str = Field(default_factory=lambda: settings.ingestion_universe_id)
    tickers: list[str] | None = None
    limit_per_ticker: int = Field(default=10, ge=1, le=200)


class NseSyncRequest(BaseModel):
    universe_id: str = Field(default_factory=lambda: settings.ingestion_universe_id)
    tickers: list[str] | None = None
    from_date: dt.date | None = None
    to_date: dt.date | None = None
    lookback_days: int | None = None
    limit_per_ticker: int = Field(default=10, ge=1, le=200)


class DiscoveredItemOut(BaseModel):
    item_id: str
    universe_id: str
    ticker: str
    source: str
    fingerprint: str
    source_url: str
    title: str | None
    document_type: str | None
    published_at: dt.datetime | None
    status: str
    last_error: str | None
    first_seen_at: dt.datetime
    last_seen_at: dt.datetime
    downloaded_at: dt.datetime | None
    ingested_at: dt.datetime | None
    doc_id: str | None
    checksum: str | None


class IngestionRunOut(BaseModel):
    run_id: str
    universe_id: str
    ticker: str
    job_type: str
    status: str
    scheduled_for: dt.date | None
    started_at: dt.datetime | None
    finished_at: dt.datetime | None
    error_message: str | None
    discovered_items: int | None
    downloaded_items: int | None
    ingested_items: int | None
    created_at: dt.datetime


@router.post("/universes/nifty50/seed", response_model=SeedUniverseResponse)
def seed_universe_nifty50(db: Session = Depends(get_db)) -> SeedUniverseResponse:
    """
    Phase 10: bootstrap the NIFTY_50 universe (idempotent).
    """

    seed_nifty50(db)
    tickers = list_active_universe_tickers(db, universe_id="NIFTY_50")
    return SeedUniverseResponse(universe_id="NIFTY_50", members=len(tickers))


@router.post("/nse/discover")
def nse_discover(req: NseDiscoveryRequest, db: Session = Depends(get_db)) -> dict:
    """
    Phase 10: discover NSE corporate announcement attachments into `ingestion_discovered_items`.
    """

    results = run_nse_discovery(
        db,
        universe_id=req.universe_id,
        tickers=req.tickers,
        from_date=req.from_date,
        to_date=req.to_date,
        lookback_days=req.lookback_days,
    )
    return {"universe_id": req.universe_id, "results": results}


@router.post("/nse/ingest")
def nse_ingest(req: NseIngestRequest, db: Session = Depends(get_db)) -> dict:
    """
    Phase 10: download + dedupe + store raw docs in MinIO for discovered items (per ticker).
    """

    results = run_nse_ingest_pending(
        db,
        universe_id=req.universe_id,
        tickers=req.tickers,
        limit_per_ticker=req.limit_per_ticker,
    )
    return {"universe_id": req.universe_id, "results": results}


@router.post("/nse/sync")
def nse_sync(req: NseSyncRequest, db: Session = Depends(get_db)) -> dict:
    """
    Phase 10: convenience endpoint (discover + ingest pending).
    """

    return run_nse_sync(
        db,
        universe_id=req.universe_id,
        tickers=req.tickers,
        from_date=req.from_date,
        to_date=req.to_date,
        lookback_days=req.lookback_days,
        limit_per_ticker=req.limit_per_ticker,
    )


@router.get("/discovered", response_model=list[DiscoveredItemOut])
def list_discovered_items(
    universe_id: str = Query(default=settings.ingestion_universe_id),
    ticker: str | None = Query(default=None),
    status: str | None = Query(default=None, description="Filter by status (discovered|downloading|ingested|failed)."),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=1000000),
    db: Session = Depends(get_db),
) -> list[DiscoveredItemOut]:
    stmt = select(IngestionDiscoveredItem).where(IngestionDiscoveredItem.universe_id == universe_id)
    if ticker:
        stmt = stmt.where(IngestionDiscoveredItem.ticker == ticker)
    if status:
        stmt = stmt.where(IngestionDiscoveredItem.status == status)

    stmt = (
        stmt.order_by(
            IngestionDiscoveredItem.published_at.desc().nullslast(),
            IngestionDiscoveredItem.first_seen_at.desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    rows = list(db.execute(stmt).scalars().all())
    return [
        DiscoveredItemOut(
            item_id=r.item_id,
            universe_id=r.universe_id,
            ticker=r.ticker,
            source=r.source,
            fingerprint=r.fingerprint,
            source_url=r.source_url,
            title=r.title,
            document_type=r.document_type,
            published_at=r.published_at,
            status=r.status,
            last_error=r.last_error,
            first_seen_at=r.first_seen_at,
            last_seen_at=r.last_seen_at,
            downloaded_at=r.downloaded_at,
            ingested_at=r.ingested_at,
            doc_id=r.doc_id,
            checksum=r.checksum,
        )
        for r in rows
    ]


@router.get("/runs", response_model=list[IngestionRunOut])
def list_ingestion_runs(
    universe_id: str = Query(default=settings.ingestion_universe_id),
    ticker: str | None = Query(default=None),
    job_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=1000000),
    db: Session = Depends(get_db),
) -> list[IngestionRunOut]:
    stmt = select(IngestionRun).where(IngestionRun.universe_id == universe_id)
    if ticker:
        stmt = stmt.where(IngestionRun.ticker == ticker)
    if job_type:
        stmt = stmt.where(IngestionRun.job_type == job_type)
    if status:
        stmt = stmt.where(IngestionRun.status == status)

    stmt = stmt.order_by(IngestionRun.created_at.desc()).offset(offset).limit(limit)
    rows = list(db.execute(stmt).scalars().all())
    return [
        IngestionRunOut(
            run_id=r.run_id,
            universe_id=r.universe_id,
            ticker=r.ticker,
            job_type=r.job_type,
            status=r.status,
            scheduled_for=r.scheduled_for,
            started_at=r.started_at,
            finished_at=r.finished_at,
            error_message=r.error_message,
            discovered_items=r.discovered_items,
            downloaded_items=r.downloaded_items,
            ingested_items=r.ingested_items,
            created_at=r.created_at,
        )
        for r in rows
    ]
