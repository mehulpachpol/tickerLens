from __future__ import annotations

import datetime as dt
import hashlib
import time
import uuid
from dataclasses import dataclass
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from tickerlens_api.db.models import IngestionDiscoveredItem, IngestionRun
from tickerlens_api.documents.service import normalize_ticker
from tickerlens_api.ingestion.nse_client import NseClient
from tickerlens_api.settings import settings


IST = ZoneInfo("Asia/Kolkata")


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def infer_document_type_from_desc(desc: str | None) -> str | None:
    """
    Best-effort mapping from NSE 'desc' category to our normalized document_type tokens.

    This is intentionally conservative; we can refine mappings over time.
    """

    if not desc:
        return None
    d = desc.strip().lower()

    if "investor" in d and "presentation" in d:
        return "investor_presentation"
    if "transcript" in d or "conference call" in d or "earnings call" in d or "concall" in d:
        return "concall"
    if "annual report" in d:
        return "annual_report"
    if "financial result" in d or "results" in d:
        # Could be quarterly or annual; we treat as quarterly_results for retrieval preference purposes.
        return "quarterly_results"

    # Generic fallback for exchange filings/announcements with attachments.
    return "filing"


def _parse_sort_date(sort_date: str | None) -> dt.datetime | None:
    """
    NSE returns sort_date like '2026-05-25 22:08:56' (local exchange time).
    Store it as an aware datetime in IST.
    """

    if not sort_date:
        return None
    try:
        naive = dt.datetime.strptime(sort_date, "%Y-%m-%d %H:%M:%S")
        return naive.replace(tzinfo=IST)
    except ValueError:
        return None


def normalize_attachment_url(url: str) -> str:
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return urljoin(settings.nse_base_url.rstrip("/") + "/", u.lstrip("/"))
    return u


def compute_fingerprint(*, ticker: str, seq_id: str | None, source_url: str | None) -> str:
    """
    Stable id for a discovered item.

    Prefer seq_id (seems unique per announcement). Fall back to URL hash.
    """

    t = normalize_ticker(ticker)
    if seq_id:
        return _sha256(f"nse:corp-ann:{t}:{seq_id}")
    if source_url:
        return _sha256(f"nse:corp-ann:{t}:url:{source_url}")
    # Last resort: should be extremely rare.
    return _sha256(f"nse:corp-ann:{t}:rand:{uuid.uuid4()}")


@dataclass(frozen=True)
class DiscoveryStats:
    fetched: int
    created: int
    updated: int


def upsert_discovered_items(
    db: Session,
    *,
    universe_id: str,
    ticker: str,
    source: str,
    raw_items: list[dict],
) -> DiscoveryStats:
    created = 0
    updated = 0
    now = dt.datetime.now(dt.timezone.utc)
    ticker_norm = normalize_ticker(ticker)

    for item in raw_items:
        source_url = item.get("attchmntFile") or item.get("attachmentURL") or item.get("attachmentUrl")
        if isinstance(source_url, str) and source_url.strip():
            source_url = normalize_attachment_url(source_url)
        seq_id = item.get("seq_id") or item.get("seqId")
        fp = compute_fingerprint(ticker=ticker_norm, seq_id=str(seq_id) if seq_id is not None else None, source_url=source_url)

        existing = (
            db.execute(
                select(IngestionDiscoveredItem)
                .where(IngestionDiscoveredItem.universe_id == universe_id)
                .where(IngestionDiscoveredItem.ticker == ticker_norm)
                .where(IngestionDiscoveredItem.fingerprint == fp)
                .limit(1)
            )
            .scalars()
            .first()
        )

        desc = item.get("desc")
        doc_type = infer_document_type_from_desc(str(desc) if desc is not None else None)
        published_at = _parse_sort_date(item.get("sort_date") or item.get("sortDate"))

        if existing:
            existing.last_seen_at = now
            existing.source_url = source_url or existing.source_url
            existing.title = item.get("attchmntText") or item.get("title") or existing.title
            existing.document_type = doc_type or existing.document_type
            existing.published_at = published_at or existing.published_at
            existing.payload = item
            updated += 1
            continue

        if not source_url:
            # We currently ingest only attachment-backed items.
            continue

        row = IngestionDiscoveredItem(
            item_id=str(uuid.uuid4()),
            universe_id=universe_id,
            ticker=ticker_norm,
            source=source,
            fingerprint=fp,
            source_url=source_url,
            title=item.get("attchmntText") or item.get("title"),
            document_type=doc_type,
            published_at=published_at,
            status="discovered",
            first_seen_at=now,
            last_seen_at=now,
            payload=item,
        )
        db.add(row)
        created += 1

    db.commit()
    return DiscoveryStats(fetched=len(raw_items), created=created, updated=updated)


def create_ingestion_run(
    db: Session,
    *,
    universe_id: str,
    ticker: str,
    job_type: str,
    scheduled_for: dt.date | None,
) -> IngestionRun:
    run = IngestionRun(
        run_id=str(uuid.uuid4()),
        universe_id=universe_id,
        ticker=normalize_ticker(ticker),
        job_type=job_type,
        status="running",
        scheduled_for=scheduled_for,
        started_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def finish_ingestion_run(
    db: Session,
    *,
    run_id: str,
    status: str,
    error_message: str | None = None,
    discovered_items: int | None = None,
    downloaded_items: int | None = None,
    ingested_items: int | None = None,
) -> None:
    run = db.get(IngestionRun, run_id)
    if not run:
        return
    run.status = status
    run.error_message = error_message
    run.discovered_items = discovered_items
    run.downloaded_items = downloaded_items
    run.ingested_items = ingested_items
    run.finished_at = dt.datetime.now(dt.timezone.utc)
    db.commit()


def discover_nse_announcements_for_ticker(
    db: Session,
    *,
    universe_id: str,
    ticker: str,
    from_date: dt.date,
    to_date: dt.date,
    throttle_ms: int = 250,
) -> DiscoveryStats:
    """
    Phase 10: discover announcement attachments for a ticker (idempotent).
    """

    if throttle_ms > 0:
        time.sleep(throttle_ms / 1000.0)

    client = NseClient(
        user_agent=settings.nse_user_agent,
        timeout_s=float(settings.nse_timeout_s),
        base_url=settings.nse_base_url,
    )
    try:
        raw = client.corporate_announcements(symbol=normalize_ticker(ticker), from_date=from_date, to_date=to_date)
        return upsert_discovered_items(
            db,
            universe_id=universe_id,
            ticker=ticker,
            source="nse",
            raw_items=raw,
        )
    finally:
        client.close()
