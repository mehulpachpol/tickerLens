from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class _NoopMetric:
    def labels(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return self

    def observe(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None

    def inc(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None


try:
    from prometheus_client import Counter, Histogram  # type: ignore

    RAG_STAGE_MS = Histogram(
        "tickerlens_rag_stage_duration_ms",
        "RAG pipeline stage duration in milliseconds.",
        labelnames=("endpoint", "stage"),
        buckets=(5, 10, 25, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000),
    )

    RAG_REQUESTS_TOTAL = Counter(
        "tickerlens_rag_requests_total",
        "RAG request count (chat/search) by endpoint and status.",
        labelnames=("endpoint", "status"),
    )

    RAG_CITATIONS_PER_ANSWER = Histogram(
        "tickerlens_rag_citations_per_answer",
        "Number of citations attached to an answer.",
        labelnames=("endpoint",),
        buckets=(0, 1, 2, 3, 4, 5, 8, 12, 20, 40),
    )
except Exception:
    # Metrics are optional; keep the API usable even if prometheus deps aren't installed.
    RAG_STAGE_MS = _NoopMetric()
    RAG_REQUESTS_TOTAL = _NoopMetric()
    RAG_CITATIONS_PER_ANSWER = _NoopMetric()


def observe_stage(*, endpoint: str, stage: str, duration_ms: int | float) -> None:
    try:
        RAG_STAGE_MS.labels(endpoint=endpoint, stage=stage).observe(float(duration_ms))
    except Exception:
        return


def inc_request(*, endpoint: str, status: str) -> None:
    try:
        RAG_REQUESTS_TOTAL.labels(endpoint=endpoint, status=status).inc()
    except Exception:
        return


def observe_citations(*, endpoint: str, count: int) -> None:
    try:
        RAG_CITATIONS_PER_ANSWER.labels(endpoint=endpoint).observe(float(count))
    except Exception:
        return

