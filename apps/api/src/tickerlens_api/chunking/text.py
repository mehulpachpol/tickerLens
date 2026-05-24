from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PageSpan:
    page_num: int
    char_start: int
    char_end: int


@dataclass(frozen=True)
class Block:
    page_num: int
    char_start: int
    char_end: int
    text: str
    is_heading: bool


_HEADING_NUM_RE = re.compile(r"^\s*(\d+(\.\d+){0,4}|[A-Z]\)|[IVX]{1,6}\.)\s+\S+")


def is_heading_line(line: str) -> bool:
    """
    Heuristic heading detector for PDF-extracted text.

    We keep this conservative: a wrong "heading" classification is annoying but not fatal;
    chunk boundaries and offsets remain correct regardless.
    """

    s = line.strip()
    if not s:
        return False
    if len(s) > 120:
        return False
    if _HEADING_NUM_RE.match(s):
        return True

    letters = [c for c in s if c.isalpha()]
    if len(letters) < 6:
        return False
    upper = sum(1 for c in letters if c.isupper())
    ratio = upper / len(letters)
    if ratio >= 0.75 and len(s.split()) <= 12 and not s.endswith("."):
        return True
    return False


def iter_blocks_from_page_text(
    *, page_num: int, page_text: str, max_block_chars: int
) -> list[Block]:
    """
    Convert one page's text into blocks with offsets (char_start/char_end in the original page string).

    Approach:
    - keep original substrings (for traceability)
    - split primarily on blank lines and detected headings
    - cap block size to avoid huge "one-block pages"
    """

    blocks: list[Block] = []
    pos = 0
    lines = page_text.splitlines(keepends=True)

    current_start: int | None = None
    current_end: int | None = None

    def flush_current() -> None:
        nonlocal current_start, current_end
        if current_start is None or current_end is None:
            return
        text = page_text[current_start:current_end]
        if text.strip():
            blocks.append(
                Block(
                    page_num=page_num,
                    char_start=current_start,
                    char_end=current_end,
                    text=text,
                    is_heading=False,
                )
            )
        current_start = None
        current_end = None

    for line in lines:
        start = pos
        end = pos + len(line)
        pos = end

        stripped = line.strip()
        if not stripped:
            flush_current()
            continue

        if is_heading_line(stripped):
            flush_current()
            blocks.append(
                Block(
                    page_num=page_num,
                    char_start=start,
                    char_end=end,
                    text=page_text[start:end],
                    is_heading=True,
                )
            )
            continue

        if current_start is None:
            current_start = start
            current_end = end
        else:
            current_end = end

        if current_start is not None and current_end is not None:
            if current_end - current_start >= max_block_chars:
                flush_current()

    flush_current()
    return blocks


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()

