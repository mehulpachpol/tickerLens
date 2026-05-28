from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from tickerlens_api.agent.schemas import AgentClarification, AgentIntent, AgentPlan
from tickerlens_api.db.models import Company
from tickerlens_api.temporal.intent import detect_temporal_intent


_COMPARISON_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bcompare\b", re.IGNORECASE),
    re.compile(r"\bvs\.?\b", re.IGNORECASE),
    re.compile(r"\bversus\b", re.IGNORECASE),
    re.compile(r"\bdifference\b", re.IGNORECASE),
]

_EXHAUSTIVE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bshow\s+all\b", re.IGNORECASE),
    re.compile(r"\ball\s+mentions\b", re.IGNORECASE),
    re.compile(r"\bevery\s+mention\b", re.IGNORECASE),
    re.compile(r"\blist\s+all\b", re.IGNORECASE),
]

_FINANCIALS_TOOL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bbalance\s+sheet\b", re.IGNORECASE),
    re.compile(r"\bincome\s+statement\b", re.IGNORECASE),
    re.compile(r"\bcash\s*flow\b", re.IGNORECASE),
    re.compile(r"\bfinancials?\b", re.IGNORECASE),
    re.compile(r"\bmarket\s+cap\b", re.IGNORECASE),
    re.compile(r"\benterprise\s+value\b", re.IGNORECASE),
    re.compile(r"\b(?:p/e|pe\s+ratio|price\s+to\s+earnings)\b", re.IGNORECASE),
    re.compile(r"\b(?:p/b|price\s+to\s+book)\b", re.IGNORECASE),
    re.compile(r"\b(?:roe|roa)\b", re.IGNORECASE),
]

_TICKER_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9&]{1,11}\b")
_TICKER_BLACKLIST = {
    "FY",
    "Q1",
    "Q2",
    "Q3",
    "Q4",
    "CEO",
    "CFO",
    "EV",
    "AI",
}


def infer_intent(*, question: str) -> AgentIntent:
    q = (question or "").strip()
    comparison = any(p.search(q) for p in _COMPARISON_PATTERNS)
    exhaustive = any(p.search(q) for p in _EXHAUSTIVE_PATTERNS)
    tool_fin = any(p.search(q) for p in _FINANCIALS_TOOL_PATTERNS)
    temporal = detect_temporal_intent(question=q)
    asks_latest = temporal.mode == "latest"

    reasons: list[str] = []
    if comparison:
        reasons.append("comparison")
    if exhaustive:
        reasons.append("exhaustive_mentions")
    if asks_latest:
        reasons.append(f"latest:{temporal.reason}")
    if tool_fin:
        reasons.append("tool_eligible_financials")
    if not reasons:
        reasons.append("default")

    return AgentIntent(
        comparison=comparison,
        exhaustive_mentions=exhaustive,
        asks_latest=asks_latest,
        tool_eligible_financials=tool_fin,
        reason=";".join(reasons),
    )


def plan_retrieval(*, intent: AgentIntent, requested_top_k: int, tickers: list[str] | None) -> AgentPlan:
    """
    Choose retrieval knobs that improve answer quality without exploding latency.
    """

    tickers_count = len(tickers or [])

    # Start from requested defaults.
    top_k = requested_top_k
    rerank_top_n = max(30, min(150, top_k * 3))
    per_ticker_k: int | None = None

    if intent.comparison and tickers_count >= 2:
        # Comparisons need coverage across tickers; keep at least a few hits per company.
        per_ticker_k = 3
        top_k = max(top_k, min(20, 6 * tickers_count))
        rerank_top_n = max(rerank_top_n, min(200, top_k * 4))
        reason = "comparison:per_ticker_k=3;top_k_scaled"
    elif intent.exhaustive_mentions:
        # "Show all mentions" is inherently broad; start by widening candidates.
        top_k = max(top_k, 20)
        rerank_top_n = max(rerank_top_n, min(250, top_k * 5))
        reason = "exhaustive:top_k=20;rerank_top_n_scaled"
    else:
        reason = "default"

    return AgentPlan(top_k=top_k, per_ticker_k=per_ticker_k, rerank_top_n=rerank_top_n, reason=reason)


def infer_tickers_from_question(db: Session, *, question: str, limit: int = 5) -> list[str]:
    """
    Best-effort: extract explicit tickers mentioned in the user question.

    This is intentionally conservative: we only accept tokens that exist in our `companies` table.
    """

    tokens = _TICKER_TOKEN_RE.findall(question or "")
    candidates = []
    for t in tokens:
        t = (t or "").strip().upper()
        if t and t not in _TICKER_BLACKLIST:
            candidates.append(t)
    candidates = list(dict.fromkeys(candidates))  # stable de-dupe
    if not candidates:
        return []

    stmt = select(Company.ticker).where(Company.ticker.in_(candidates))
    found = [row[0] for row in db.execute(stmt).all()]
    found = list(dict.fromkeys(found))
    return found[:limit]


def maybe_clarify(*, intent: AgentIntent, tickers: list[str] | None) -> AgentClarification | None:
    tickers = list(tickers or [])

    if not tickers:
        return AgentClarification(
            kind="tickers",
            question="Which NSE ticker(s) should I analyze? Select one or more (e.g. INFY, TCS).",
            options=None,
            reason="no_tickers",
        )

    if intent.comparison and len(tickers) < 2:
        return AgentClarification(
            kind="comparison_scope",
            question="You asked for a comparison, but only one ticker is selected. Add one or more tickers to compare against.",
            options=None,
            reason="comparison_requires_multiple_tickers",
        )

    return None

