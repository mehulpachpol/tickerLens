from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentIntent:
    comparison: bool
    exhaustive_mentions: bool
    asks_latest: bool
    tool_eligible_financials: bool
    reason: str


@dataclass(frozen=True)
class AgentPlan:
    """
    Deterministic plan used to choose retrieval parameters and answer format.

    This is intentionally simple/transparent in v1 so we can debug agent behavior
    without extra model calls.
    """

    top_k: int
    per_ticker_k: int | None
    rerank_top_n: int
    reason: str


@dataclass(frozen=True)
class AgentClarification:
    kind: str  # "tickers" | "comparison_scope" | "timeframe" | "other"
    question: str
    options: list[str] | None
    reason: str

