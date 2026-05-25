from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TemporalIntent:
    """
    Phase 9: lightweight temporal intent detection (deterministic, auditable).

    We intentionally start with heuristics over an LLM classifier because:
    - predictable behavior
    - cheap (no token cost)
    - easy to explain/debug
    """

    mode: str  # "none" | "latest"
    reason: str


_LATEST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\blatest\b", re.IGNORECASE),
    re.compile(r"\bmost\s+recent\b", re.IGNORECASE),
    re.compile(r"\bnewest\b", re.IGNORECASE),
    re.compile(r"\bcurrent\b", re.IGNORECASE),
    re.compile(r"\brecent\b", re.IGNORECASE),
    re.compile(r"\bas\s+of\b", re.IGNORECASE),
]


def detect_temporal_intent(*, question: str) -> TemporalIntent:
    q = (question or "").strip()
    if not q:
        return TemporalIntent(mode="none", reason="empty")

    for pat in _LATEST_PATTERNS:
        m = pat.search(q)
        if m:
            return TemporalIntent(mode="latest", reason=f"matched:{pat.pattern}")

    return TemporalIntent(mode="none", reason="no_match")


@dataclass(frozen=True)
class DocTypePreferences:
    """
    Document type hints inferred from the user's question.

    The returned list is ordered from most to least preferred.
    """

    document_types: list[str]
    reason: str


def infer_document_type_preferences(*, question: str) -> DocTypePreferences:
    """
    Phase 9: infer which document types are most likely to contain the requested information.

    Notes:
    - This is not a hard filter by default; it's a preference list used for scoping when the
      question has a "latest" temporal intent.
    - The values must match our normalized `document_type` tokens (lowercase, safe chars).
    """

    q = (question or "").lower()

    # Explicit doc-type mentions should dominate.
    if any(k in q for k in ("earnings call", "concall", "conference call", "transcript")):
        return DocTypePreferences(document_types=["concall"], reason="explicit:concall")
    if any(k in q for k in ("quarterly", "q1", "q2", "q3", "q4", "results")):
        # "results" is ambiguous, but in filings context usually means quarterly results.
        return DocTypePreferences(document_types=["quarterly_results", "concall"], reason="explicit:quarterly")
    if any(k in q for k in ("investor presentation", "presentation", "deck")):
        return DocTypePreferences(document_types=["investor_presentation"], reason="explicit:presentation")
    if any(k in q for k in ("annual report", "risk factors", "board report")):
        return DocTypePreferences(document_types=["annual_report"], reason="explicit:annual_report")

    # "Management commentary" is usually from concalls / results decks.
    if any(k in q for k in ("management commentary", "management comment", "management remarks")):
        return DocTypePreferences(
            document_types=["concall", "quarterly_results", "investor_presentation"],
            reason="semantic:management_commentary",
        )

    # Default for "latest" style questions: prefer higher-frequency, management-facing docs.
    return DocTypePreferences(
        document_types=["quarterly_results", "concall", "investor_presentation", "annual_report"],
        reason="default",
    )

