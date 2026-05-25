from __future__ import annotations

import re

_CITATION_RE = re.compile(r"\[\(chunk_id=([^)]+)\)\]")


def extract_chunk_ids(text: str) -> list[str]:
    """
    Extract chunk ids from citations in the format: [(chunk_id=<id>)]
    """

    out: list[str] = []
    for m in _CITATION_RE.finditer(text or ""):
        cid = (m.group(1) or "").strip()
        cid = cid.strip("<>").strip()
        if cid:
            out.append(cid)
    return out


def strip_unknown_citations(*, text: str, allowed_chunk_ids: set[str]) -> str:
    """
    Remove citations that reference chunk ids not in allowed_chunk_ids.
    """

    def repl(match: re.Match) -> str:
        cid = (match.group(1) or "").strip().strip("<>").strip()
        if cid in allowed_chunk_ids:
            return match.group(0)
        return ""

    return _CITATION_RE.sub(repl, text or "")

