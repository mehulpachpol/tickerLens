from __future__ import annotations

import datetime as dt
import traceback
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from tickerlens_api.chunking.text import Block, PageSpan, iter_blocks_from_page_text, sha256_text
from tickerlens_api.db.models import (
    Document,
    DocumentChunk,
    DocumentChunkRun,
    DocumentChunkSpan,
    DocumentPage,
    DocumentParseRun,
)
from tickerlens_api.db.session import SessionLocal


@dataclass(frozen=True)
class Chunk:
    text: str
    section: str | None
    page_start: int
    page_end: int
    spans: list[PageSpan]


def create_chunk_run(
    db: Session,
    *,
    doc_id: str,
    parse_run_id: str,
    max_chunk_chars: int,
    overlap_chars: int,
    max_block_chars: int,
) -> DocumentChunkRun:
    run = DocumentChunkRun(
        run_id=str(uuid.uuid4()),
        doc_id=doc_id,
        parse_run_id=parse_run_id,
        status="queued",
        max_chunk_chars=max_chunk_chars,
        overlap_chars=overlap_chars,
        max_block_chars=max_block_chars,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def get_chunk_run(db: Session, *, run_id: str) -> DocumentChunkRun | None:
    return db.get(DocumentChunkRun, run_id)


def list_chunk_runs(db: Session, *, doc_id: str, limit: int = 20) -> list[DocumentChunkRun]:
    stmt = (
        select(DocumentChunkRun)
        .where(DocumentChunkRun.doc_id == doc_id)
        .order_by(DocumentChunkRun.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def get_latest_successful_chunk_run(db: Session, *, doc_id: str) -> DocumentChunkRun | None:
    stmt = (
        select(DocumentChunkRun)
        .where(DocumentChunkRun.doc_id == doc_id)
        .where(DocumentChunkRun.status == "succeeded")
        .order_by(DocumentChunkRun.finished_at.desc().nullslast(), DocumentChunkRun.created_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def list_chunks(db: Session, *, doc_id: str, chunk_run_id: str) -> list[DocumentChunk]:
    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.doc_id == doc_id)
        .where(DocumentChunk.chunk_run_id == chunk_run_id)
        .order_by(DocumentChunk.page_start.asc(), DocumentChunk.chunk_id.asc())
    )
    return list(db.execute(stmt).scalars().all())


def get_chunk(db: Session, *, chunk_id: str) -> DocumentChunk | None:
    return db.get(DocumentChunk, chunk_id)


def list_chunk_spans(db: Session, *, chunk_id: str) -> list[DocumentChunkSpan]:
    stmt = select(DocumentChunkSpan).where(DocumentChunkSpan.chunk_id == chunk_id).order_by(
        DocumentChunkSpan.page_num.asc(), DocumentChunkSpan.char_start.asc()
    )
    return list(db.execute(stmt).scalars().all())


def _get_document(db: Session, *, doc_id: str) -> Document | None:
    return db.get(Document, doc_id)


def _get_parse_run(db: Session, *, run_id: str) -> DocumentParseRun | None:
    return db.get(DocumentParseRun, run_id)


def _list_pages_for_parse_run(db: Session, *, doc_id: str, parse_run_id: str) -> list[DocumentPage]:
    stmt = (
        select(DocumentPage)
        .where(DocumentPage.doc_id == doc_id)
        .where(DocumentPage.run_id == parse_run_id)
        .order_by(DocumentPage.page_num.asc())
    )
    return list(db.execute(stmt).scalars().all())


def build_chunks_from_pages(
    *,
    pages: list[DocumentPage],
    max_chunk_chars: int,
    overlap_chars: int,
    max_block_chars: int,
) -> list[Chunk]:
    """
    Packs page-derived blocks into chunks while preserving page offsets for citations.

    Design choice: blocks are substrings of the original page text, so offsets are stable and auditable.
    Chunk text is assembled by concatenating block texts; spans map back to page substrings.
    """

    blocks: list[Block] = []
    for p in pages:
        blocks.extend(
            iter_blocks_from_page_text(page_num=p.page_num, page_text=p.text, max_block_chars=max_block_chars)
        )

    chunks: list[Chunk] = []
    current_blocks: list[Block] = []
    current_section: str | None = None

    def blocks_text(bs: list[Block]) -> str:
        return "".join(b.text for b in bs)

    def blocks_len(bs: list[Block]) -> int:
        return sum(len(b.text) for b in bs)

    def to_spans(bs: list[Block]) -> list[PageSpan]:
        spans: dict[int, list[tuple[int, int]]] = {}
        for b in bs:
            spans.setdefault(b.page_num, []).append((b.char_start, b.char_end))
        merged: list[PageSpan] = []
        for page_num in sorted(spans.keys()):
            ranges = sorted(spans[page_num])
            cur_s, cur_e = ranges[0]
            for s, e in ranges[1:]:
                if s <= cur_e:  # overlap/adjacent
                    cur_e = max(cur_e, e)
                else:
                    merged.append(PageSpan(page_num=page_num, char_start=cur_s, char_end=cur_e))
                    cur_s, cur_e = s, e
            merged.append(PageSpan(page_num=page_num, char_start=cur_s, char_end=cur_e))
        return merged

    def flush(*, carry_overlap: bool = True) -> None:
        nonlocal current_blocks
        if not current_blocks:
            return
        txt = blocks_text(current_blocks)
        spans = to_spans(current_blocks)
        page_start = min(s.page_num for s in spans)
        page_end = max(s.page_num for s in spans)
        chunks.append(
            Chunk(
                text=txt,
                section=current_section,
                page_start=page_start,
                page_end=page_end,
                spans=spans,
            )
        )

        if not carry_overlap or overlap_chars <= 0:
            current_blocks = []
            return

        # Block-level overlap: keep a suffix of blocks up to overlap_chars.
        suffix: list[Block] = []
        total = 0
        for b in reversed(current_blocks):
            if total + len(b.text) > overlap_chars and suffix:
                break
            suffix.append(b)
            total += len(b.text)
            if total >= overlap_chars:
                break
        current_blocks = list(reversed(suffix))

    for b in blocks:
        if b.is_heading:
            # Headings act as soft boundaries: start a new chunk so the heading stays with its section text.
            if current_blocks:
                flush(carry_overlap=False)
            current_section = b.text.strip()
            current_blocks.append(b)
            continue

        if not current_blocks:
            current_blocks.append(b)
            continue

        if blocks_len(current_blocks) + len(b.text) <= max_chunk_chars:
            current_blocks.append(b)
            continue

        flush(carry_overlap=True)
        current_blocks.append(b)

    flush()
    return chunks


def run_chunk_job(*, chunk_run_id: str) -> None:
    """
    Execute a chunk run in-process (manual trigger).

    Like parsing, this uses its own DB session so it can run safely in a FastAPI BackgroundTask.
    """

    db = SessionLocal()
    try:
        run = db.get(DocumentChunkRun, chunk_run_id)
        if not run:
            return
        if run.status in {"running", "succeeded"}:
            return

        doc = _get_document(db, doc_id=run.doc_id)
        if not doc:
            raise RuntimeError("Document not found")

        parse_run = _get_parse_run(db, run_id=run.parse_run_id)
        if not parse_run or parse_run.status != "succeeded":
            raise RuntimeError("Parse run not found or not succeeded")

        pages = _list_pages_for_parse_run(db, doc_id=run.doc_id, parse_run_id=run.parse_run_id)
        if not pages:
            raise RuntimeError("No parsed pages found for given parse run")

        run.status = "running"
        run.started_at = dt.datetime.now(dt.timezone.utc)
        db.commit()

        chunks = build_chunks_from_pages(
            pages=pages,
            max_chunk_chars=run.max_chunk_chars,
            overlap_chars=run.overlap_chars,
            max_block_chars=run.max_block_chars,
        )

        for ch in chunks:
            chunk_id = str(uuid.uuid4())
            chunk_row = DocumentChunk(
                chunk_id=chunk_id,
                doc_id=run.doc_id,
                parse_run_id=run.parse_run_id,
                chunk_run_id=run.run_id,
                ticker=doc.ticker,
                section=ch.section,
                page_start=ch.page_start,
                page_end=ch.page_end,
                text=ch.text,
                char_count=len(ch.text),
                checksum=sha256_text(ch.text),
            )
            db.add(chunk_row)
            for sp in ch.spans:
                db.add(
                    DocumentChunkSpan(
                        chunk_id=chunk_id,
                        page_num=sp.page_num,
                        char_start=sp.char_start,
                        char_end=sp.char_end,
                    )
                )

        run.chunk_count = len(chunks)
        run.status = "succeeded"
        run.finished_at = dt.datetime.now(dt.timezone.utc)
        db.commit()
    except Exception as e:
        run = db.get(DocumentChunkRun, chunk_run_id)
        if run:
            run.status = "failed"
            run.finished_at = dt.datetime.now(dt.timezone.utc)
            run.error_message = f"{e}\n{traceback.format_exc()}"
            db.commit()
    finally:
        db.close()
