import sqlalchemy as sa
from sqlalchemy.orm import Session

from tickerlens_api.agent.heuristics import (
    infer_intent,
    infer_tickers_from_question,
    maybe_clarify,
    plan_retrieval,
)
from tickerlens_api.db.models import Base, Company


def _make_db() -> Session:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_infer_intent_detects_comparison_and_latest() -> None:
    intent = infer_intent(question="Compare INFY vs TCS latest management commentary")
    assert intent.comparison is True
    assert intent.asks_latest is True


def test_plan_retrieval_comparison_scales_top_k() -> None:
    intent = infer_intent(question="Compare INFY vs TCS")
    plan = plan_retrieval(intent=intent, requested_top_k=10, tickers=["INFY", "TCS"])
    assert plan.per_ticker_k == 3
    assert plan.top_k >= 10
    assert plan.rerank_top_n >= plan.top_k * 3


def test_infer_tickers_from_question_uses_companies_table() -> None:
    db = _make_db()
    db.add_all([Company(ticker="INFY", name="Infosys"), Company(ticker="TCS", name="TCS")])
    db.commit()

    tickers = infer_tickers_from_question(db, question="Compare INFY and TCS FY24 risk factors")
    assert tickers == ["INFY", "TCS"]


def test_maybe_clarify_requires_tickers() -> None:
    intent = infer_intent(question="What are the risk factors?")
    clarification = maybe_clarify(intent=intent, tickers=[])
    assert clarification is not None
    assert clarification.kind == "tickers"

