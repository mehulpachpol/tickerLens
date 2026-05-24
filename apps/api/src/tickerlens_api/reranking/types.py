from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RerankCandidate:
    chunk_id: str
    passage: str


def truncate_text(*, text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."

