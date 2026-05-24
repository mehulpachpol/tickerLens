from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceChunk:
    chunk_id: str
    ticker: str
    text: str

    doc_id: str | None = None
    document_type: str | None = None
    fiscal_year: str | None = None
    filing_date: str | None = None
    version: int | None = None

    section: str | None = None
    page_start: int | None = None
    page_end: int | None = None


def _truncate(*, text: str, max_chars: int | None) -> str:
    if max_chars is None:
        return text
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def build_context_blocks(
    *,
    requested_tickers: list[str] | None,
    chunks: list[EvidenceChunk],
    max_chunk_chars: int | None = None,
) -> list[tuple[str, list[str], str]]:
    """
    Returns a list of (ticker, chunk_ids, context_text) blocks.

    Concept:
    - Keep evidence separated per ticker to avoid citation mixing.
    - Include minimal metadata per chunk so Phase 8 can cite correctly.
    """

    by_ticker: dict[str, list[EvidenceChunk]] = {}
    for ch in chunks:
        by_ticker.setdefault(ch.ticker, []).append(ch)

    if requested_tickers:
        ticker_order = list(requested_tickers)
    else:
        ticker_order = sorted(by_ticker.keys())

    out: list[tuple[str, list[str], str]] = []
    for ticker in ticker_order:
        items = by_ticker.get(ticker) or []
        if not items:
            continue

        lines: list[str] = [f"[{ticker} CONTEXT]"]
        chunk_ids: list[str] = []

        for c in items:
            chunk_ids.append(c.chunk_id)
            meta_parts: list[str] = []
            if c.document_type:
                meta_parts.append(f"document_type={c.document_type}")
            if c.fiscal_year:
                meta_parts.append(f"fiscal_year={c.fiscal_year}")
            if c.filing_date:
                meta_parts.append(f"filing_date={c.filing_date}")
            if c.version is not None:
                meta_parts.append(f"version={c.version}")
            if c.page_start is not None and c.page_end is not None:
                meta_parts.append(f"pages={c.page_start}-{c.page_end}")
            if c.section:
                meta_parts.append(f"section={c.section}")

            meta = " | ".join(meta_parts)
            if meta:
                lines.append(f"(chunk_id={c.chunk_id} | {meta})")
            else:
                lines.append(f"(chunk_id={c.chunk_id})")

            lines.append(_truncate(text=c.text, max_chars=max_chunk_chars).strip())
            lines.append("")  # blank line between chunks

        out.append((ticker, chunk_ids, "\n".join(lines).rstrip() + "\n"))

    return out

