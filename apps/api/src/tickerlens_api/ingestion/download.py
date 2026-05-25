from __future__ import annotations

import datetime as dt
import hashlib
import os
import tempfile
import traceback
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from tickerlens_api.db.models import IngestionDiscoveredItem
from tickerlens_api.documents.service import ingest_document_from_tempfile_digest
from tickerlens_api.settings import settings


@dataclass(frozen=True)
class DownloadDigest:
    path: str
    sha256: str
    size_bytes: int
    content_type: str | None
    filename: str | None


def _filename_from_url(url: str) -> str | None:
    try:
        p = urlparse(url)
        name = os.path.basename(p.path)
        return name or None
    except Exception:
        return None


def download_to_tempfile_and_hash(*, url: str) -> DownloadDigest:
    """
    Downloads the URL to a temp file while computing SHA-256.

    We avoid loading whole PDFs into memory, and we reuse the computed digest for
    dedupe/versioning when creating `documents` rows.
    """

    hasher = hashlib.sha256()
    size_bytes = 0
    filename = _filename_from_url(url)

    suffix = ""
    if filename and "." in filename:
        suffix = "." + filename.rsplit(".", 1)[-1].lower()
        if len(suffix) > 10:
            suffix = ""

    fd, path = tempfile.mkstemp(prefix="tickerlens-nse-", suffix=suffix or ".bin")
    content_type: str | None = None
    try:
        headers = {
            "User-Agent": settings.nse_user_agent,
            "Accept": "*/*",
            "Referer": "https://www.nseindia.com/",
        }
        with httpx.stream("GET", url, headers=headers, timeout=float(settings.nse_timeout_s)) as r:
            r.raise_for_status()
            content_type = r.headers.get("content-type")
            with os.fdopen(fd, "wb") as f:
                for chunk in r.iter_bytes():
                    if not chunk:
                        continue
                    size_bytes += len(chunk)
                    hasher.update(chunk)
                    f.write(chunk)
    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
        try:
            os.remove(path)
        except OSError:
            pass
        raise

    return DownloadDigest(
        path=path,
        sha256=hasher.hexdigest(),
        size_bytes=size_bytes,
        content_type=content_type,
        filename=filename,
    )


def ingest_discovered_item(db: Session, *, item_id: str) -> tuple[str | None, bool]:
    """
    Phase 10: download a discovered attachment and upsert it into the documents store.

    Returns (doc_id, deduplicated).
    """

    item = db.get(IngestionDiscoveredItem, item_id)
    if not item:
        raise ValueError("Discovered item not found")
    if item.status == "ingested" and item.doc_id:
        return item.doc_id, True
    if not item.source_url:
        raise ValueError("Discovered item has no source_url")

    # Derive minimal normalized metadata.
    company_name = None
    if isinstance(item.payload, dict):
        company_name = item.payload.get("sm_name") or item.payload.get("company") or item.payload.get("companyName")

    filing_date: dt.date | None = None
    if item.published_at:
        try:
            filing_date = item.published_at.date()
        except Exception:
            filing_date = None

    document_type = item.document_type or "filing"

    item.status = "downloading"
    item.last_error = None
    db.commit()

    digest = download_to_tempfile_and_hash(url=item.source_url)
    try:
        doc, _file, deduped = ingest_document_from_tempfile_digest(
            db,
            temp_path=digest.path,
            sha256=digest.sha256,
            size_bytes=digest.size_bytes,
            original_filename=digest.filename,
            content_type=digest.content_type,
            ticker=item.ticker,
            company_name=company_name,
            document_type=document_type,
            fiscal_year=None,
            filing_date=filing_date,
            source_url=item.source_url,
        )

        item.status = "ingested"
        item.doc_id = doc.doc_id
        item.checksum = doc.checksum
        item.ingested_at = dt.datetime.now(dt.timezone.utc)
        item.downloaded_at = item.downloaded_at or dt.datetime.now(dt.timezone.utc)
        db.commit()

        return doc.doc_id, deduped
    finally:
        try:
            os.remove(digest.path)
        except OSError:
            pass


def list_pending_discovered_items(
    db: Session,
    *,
    universe_id: str,
    ticker: str | None = None,
    limit: int = 50,
) -> list[IngestionDiscoveredItem]:
    stmt = select(IngestionDiscoveredItem).where(IngestionDiscoveredItem.universe_id == universe_id)
    if ticker:
        stmt = stmt.where(IngestionDiscoveredItem.ticker == ticker)
    stmt = stmt.where(IngestionDiscoveredItem.status.in_(["discovered", "failed"]))
    stmt = stmt.order_by(IngestionDiscoveredItem.published_at.desc().nullslast(), IngestionDiscoveredItem.first_seen_at.desc())
    stmt = stmt.limit(limit)
    return list(db.execute(stmt).scalars().all())


def ingest_pending_for_ticker(
    db: Session,
    *,
    universe_id: str,
    ticker: str,
    limit: int = 10,
) -> dict:
    """
    Helper for worker: ingest up to N pending discovered items for a ticker.
    """

    items = list_pending_discovered_items(db, universe_id=universe_id, ticker=ticker, limit=limit)
    ok = 0
    failed = 0
    for it in items:
        try:
            ingest_discovered_item(db, item_id=it.item_id)
            ok += 1
        except Exception as e:
            failed += 1
            row = db.get(IngestionDiscoveredItem, it.item_id)
            if row:
                row.status = "failed"
                row.last_error = f"{e}\n{traceback.format_exc()}"
                db.commit()

    return {"ticker": ticker, "attempted": len(items), "ok": ok, "failed": failed}

