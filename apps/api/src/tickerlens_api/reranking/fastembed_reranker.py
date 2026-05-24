from __future__ import annotations

import os
import shutil
import threading
from functools import lru_cache

from tickerlens_api.reranking.types import RerankCandidate, truncate_text
from tickerlens_api.settings import settings

_INIT_LOCK = threading.Lock()
_DEFAULT_CACHE_DIR = "/tmp/fastembed_cache"


def _purge_broken_cache(model_name: str) -> None:
    """
    Best-effort cleanup for partial HuggingFace snapshot downloads (e.g. *.incomplete blobs).

    FastEmbed uses HF Hub cache layout: /tmp/fastembed_cache/models--ORG--REPO/...
    """

    safe = model_name.replace("/", "--")
    candidate_dir = os.path.join(_DEFAULT_CACHE_DIR, f"models--{safe}")
    if os.path.isdir(candidate_dir):
        shutil.rmtree(candidate_dir, ignore_errors=True)


@lru_cache(maxsize=4)
def _get_reranker(model_name: str):
    # Imported lazily so the API can still start even if fastembed isn't installed.
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    # Model download happens inside TextCrossEncoder init. Guard it so concurrent
    # requests don't corrupt the cache, and retry once if a partial download left
    # a broken cache entry behind.
    with _INIT_LOCK:
        try:
            return TextCrossEncoder(model_name=model_name)
        except Exception as e:
            msg = str(e)
            if "NO_SUCHFILE" in msg or "NoSuchFile" in msg or ".incomplete" in msg:
                _purge_broken_cache(model_name)
                return TextCrossEncoder(model_name=model_name)
            raise


def rerank(
    *,
    query: str,
    candidates: list[RerankCandidate],
    model: str,
    max_passage_chars: int,
    batch_size: int | None = None,
) -> dict[str, float]:
    """
    Returns {chunk_id: score}.

    Notes:
    - Scores are raw cross-encoder logits (unbounded). Use only for ordering.
    - First call downloads the model into the container cache.
    """

    if not candidates:
        return {}

    reranker = _get_reranker(model)
    passages = [truncate_text(text=c.passage, max_chars=max_passage_chars) for c in candidates]
    bs = batch_size or settings.fastembed_rerank_batch_size

    try:
        scores = list(reranker.rerank(query, passages, batch_size=bs))
    except TypeError:
        # Older fastembed versions may not accept batch_size.
        scores = list(reranker.rerank(query, passages))

    by_id: dict[str, float] = {}
    for i, c in enumerate(candidates):
        try:
            by_id[c.chunk_id] = float(scores[i])
        except Exception:
            by_id[c.chunk_id] = 0.0

    return by_id


def get_default_rerank_model() -> str:
    return settings.fastembed_rerank_model
