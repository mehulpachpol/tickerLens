from __future__ import annotations

from tickerlens_api.reranking.types import RerankCandidate
from tickerlens_api.settings import settings

RERANK_BACKENDS = {"fastembed", "openai"}


def _looks_like_openai_model(model: str) -> bool:
    # Heuristic: OpenAI model ids typically start with gpt-/o1-/o3-/o4-.
    prefix = model.strip().lower()
    return prefix.startswith(("gpt-", "o1-", "o3-", "o4-"))


def resolve_backend(*, backend: str | None, model: str | None) -> str:
    if backend:
        b = backend.strip().lower()
        if b not in RERANK_BACKENDS:
            raise ValueError(f"Unknown rerank_backend '{backend}'. Expected one of: {sorted(RERANK_BACKENDS)}")
        return b

    if model and _looks_like_openai_model(model):
        return "openai"

    b = (settings.rerank_backend or "fastembed").strip().lower()
    if b not in RERANK_BACKENDS:
        return "fastembed"
    return b


def get_default_model(*, backend: str) -> str:
    if backend == "openai":
        from tickerlens_api.reranking.openai_reranker import get_default_rerank_model

        return get_default_rerank_model()

    from tickerlens_api.reranking.fastembed_reranker import get_default_rerank_model

    return get_default_rerank_model()


def rerank(
    *,
    backend: str,
    query: str,
    candidates: list[RerankCandidate],
    model: str,
    max_passage_chars: int,
) -> dict[str, float]:
    if backend == "openai":
        from tickerlens_api.reranking.openai_reranker import rerank as openai_rerank

        return openai_rerank(
            query=query, candidates=candidates, model=model, max_passage_chars=max_passage_chars
        )

    from tickerlens_api.reranking.fastembed_reranker import rerank as fastembed_rerank

    return fastembed_rerank(
        query=query,
        candidates=candidates,
        model=model,
        max_passage_chars=max_passage_chars,
        batch_size=settings.fastembed_rerank_batch_size,
    )

