from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from tickerlens_api.ingestion.discovery import (
    create_ingestion_run,
    discover_nse_announcements_for_ticker,
    finish_ingestion_run,
)
from tickerlens_api.ingestion.download import ingest_pending_for_ticker
from tickerlens_api.ingestion.universe_service import list_active_universe_tickers
from tickerlens_api.settings import settings


IST = ZoneInfo("Asia/Kolkata")


def _today_ist() -> dt.date:
    return dt.datetime.now(IST).date()


def compute_window(
    *,
    from_date: dt.date | None,
    to_date: dt.date | None,
    lookback_days: int | None,
) -> tuple[dt.date, dt.date]:
    if to_date is None:
        to_date = _today_ist()
    if from_date is None:
        lb = settings.ingestion_lookback_days if lookback_days is None else lookback_days
        from_date = to_date - dt.timedelta(days=max(0, lb))
    return from_date, to_date


def run_nse_discovery(
    db: Session,
    *,
    universe_id: str,
    tickers: list[str] | None = None,
    from_date: dt.date | None = None,
    to_date: dt.date | None = None,
    lookback_days: int | None = None,
) -> list[dict]:
    from_date, to_date = compute_window(from_date=from_date, to_date=to_date, lookback_days=lookback_days)
    tickers = tickers or list_active_universe_tickers(db, universe_id=universe_id)

    results: list[dict] = []
    for ticker in tickers:
        run = create_ingestion_run(
            db,
            universe_id=universe_id,
            ticker=ticker,
            job_type="discover",
            scheduled_for=to_date,
        )
        try:
            stats = discover_nse_announcements_for_ticker(
                db,
                universe_id=universe_id,
                ticker=ticker,
                from_date=from_date,
                to_date=to_date,
                throttle_ms=int(settings.nse_throttle_ms),
            )
            finish_ingestion_run(
                db,
                run_id=run.run_id,
                status="succeeded",
                discovered_items=stats.fetched,
            )
            results.append(
                {
                    "run_id": run.run_id,
                    "ticker": ticker,
                    "from_date": from_date.isoformat(),
                    "to_date": to_date.isoformat(),
                    "fetched": stats.fetched,
                    "created": stats.created,
                    "updated": stats.updated,
                    "status": "succeeded",
                }
            )
        except Exception as e:
            finish_ingestion_run(db, run_id=run.run_id, status="failed", error_message=str(e))
            results.append(
                {
                    "run_id": run.run_id,
                    "ticker": ticker,
                    "from_date": from_date.isoformat(),
                    "to_date": to_date.isoformat(),
                    "status": "failed",
                    "error": str(e),
                }
            )
    return results


def run_nse_ingest_pending(
    db: Session,
    *,
    universe_id: str,
    tickers: list[str] | None = None,
    limit_per_ticker: int = 10,
) -> list[dict]:
    tickers = tickers or list_active_universe_tickers(db, universe_id=universe_id)
    scheduled_for = _today_ist()

    results: list[dict] = []
    for ticker in tickers:
        run = create_ingestion_run(
            db,
            universe_id=universe_id,
            ticker=ticker,
            job_type="download",
            scheduled_for=scheduled_for,
        )
        try:
            r = ingest_pending_for_ticker(db, universe_id=universe_id, ticker=ticker, limit=limit_per_ticker)
            finish_ingestion_run(
                db,
                run_id=run.run_id,
                status="succeeded",
                downloaded_items=r.get("attempted"),
                ingested_items=r.get("ok"),
            )
            results.append({"run_id": run.run_id, **r, "status": "succeeded"})
        except Exception as e:
            finish_ingestion_run(db, run_id=run.run_id, status="failed", error_message=str(e))
            results.append({"run_id": run.run_id, "ticker": ticker, "status": "failed", "error": str(e)})

    return results


def run_nse_sync(
    db: Session,
    *,
    universe_id: str,
    tickers: list[str] | None = None,
    from_date: dt.date | None = None,
    to_date: dt.date | None = None,
    lookback_days: int | None = None,
    limit_per_ticker: int = 10,
) -> dict:
    """
    Convenience: discovery + ingest pending.

    Note: Phase 10 does NOT automatically parse/chunk/embed/index; that remains a separate step
    until we wire a worker/queue and have stable OCR throughput.
    """

    discovery = run_nse_discovery(
        db,
        universe_id=universe_id,
        tickers=tickers,
        from_date=from_date,
        to_date=to_date,
        lookback_days=lookback_days,
    )
    ingest = run_nse_ingest_pending(
        db,
        universe_id=universe_id,
        tickers=tickers,
        limit_per_ticker=limit_per_ticker,
    )
    return {"universe_id": universe_id, "discovery": discovery, "ingest": ingest}

