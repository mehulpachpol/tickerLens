from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from tickerlens_api.db.models import TickerUniverse, TickerUniverseMember
from tickerlens_api.documents.service import normalize_ticker, upsert_company
from tickerlens_api.ingestion.nifty50 import NIFTY_50


def ensure_universe(
    db: Session,
    *,
    universe_id: str,
    name: str,
    description: str | None,
) -> TickerUniverse:
    existing = db.get(TickerUniverse, universe_id)
    if existing:
        if name and existing.name != name:
            existing.name = name
        if description is not None and existing.description != description:
            existing.description = description
        db.commit()
        db.refresh(existing)
        return existing

    u = TickerUniverse(universe_id=universe_id, name=name, description=description)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def upsert_universe_member(
    db: Session,
    *,
    universe_id: str,
    ticker: str,
    active: bool = True,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
) -> TickerUniverseMember:
    ticker_norm = normalize_ticker(ticker)
    stmt = (
        select(TickerUniverseMember)
        .where(TickerUniverseMember.universe_id == universe_id)
        .where(TickerUniverseMember.ticker == ticker_norm)
        .limit(1)
    )
    existing = db.execute(stmt).scalars().first()
    if existing:
        existing.active = active
        existing.start_date = start_date
        existing.end_date = end_date
        db.commit()
        db.refresh(existing)
        return existing

    m = TickerUniverseMember(
        universe_id=universe_id,
        ticker=ticker_norm,
        active=active,
        start_date=start_date,
        end_date=end_date,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def seed_nifty50(db: Session) -> None:
    """
    Phase 10: seed the NIFTY_50 universe for scheduler-driven ingestion.

    This is safe to run multiple times (idempotent).
    """

    ensure_universe(
        db,
        universe_id="NIFTY_50",
        name="Nifty 50",
        description="Seeded universe for Phase 10 daily NSE ingestion.",
    )

    for c in NIFTY_50:
        ticker = c["ticker"]
        name = c.get("name")
        upsert_company(db, ticker=normalize_ticker(ticker), company_name=name)
        upsert_universe_member(db, universe_id="NIFTY_50", ticker=ticker, active=True)


def list_active_universe_tickers(db: Session, *, universe_id: str) -> list[str]:
    stmt = (
        select(TickerUniverseMember.ticker)
        .where(TickerUniverseMember.universe_id == universe_id)
        .where(TickerUniverseMember.active.is_(True))
        .order_by(TickerUniverseMember.ticker.asc())
    )
    return [r[0] for r in db.execute(stmt).all()]
