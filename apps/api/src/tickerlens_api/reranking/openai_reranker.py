from __future__ import annotations

import json

from tickerlens_api.embeddings.openai_embedder import get_openai_client
from tickerlens_api.reranking.types import RerankCandidate, truncate_text
from tickerlens_api.settings import settings


def rerank(
    *,
    query: str,
    candidates: list[RerankCandidate],
    model: str,
    max_passage_chars: int,
) -> dict[str, float]:
    """
    Returns {chunk_id: score} where score is a float in [0, 1].

    Design goals (Phase 7):
    - Manual-first and debuggable
    - Deterministic enough for dev (temperature=0)
    - Bounded prompt size via passage truncation
    """

    if not candidates:
        return {}

    client = get_openai_client()

    items = [
        {"chunk_id": c.chunk_id, "passage": truncate_text(text=c.passage, max_chars=max_passage_chars)}
        for c in candidates
    ]

    system = (
        "You are a retrieval reranker.\n"
        "Given a user query and a list of passages, assign each passage a relevance score.\n"
        "Score meaning: 1.0 = directly answers the query; 0.0 = irrelevant.\n"
        "Return JSON only."
    )

    user = {
        "query": query,
        "passages": items,
        "output_format": {
            "scores": [{"chunk_id": "string", "score": "number between 0.0 and 1.0"}]
        },
        "rules": [
            "Return exactly one score per input passage.",
            "Use the provided chunk_id values verbatim.",
            "Do not add extra keys beyond 'scores'.",
        ],
    }

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False, separators=(",", ":"))},
        ],
        temperature=0,
        # Output is small but scales with number of candidates; keep a generous cap to
        # avoid truncating JSON (which would cause JSONDecodeError).
        max_tokens=min(4096, 200 + (len(candidates) * 120)),
        response_format={"type": "json_object"},
    )

    content = completion.choices[0].message.content or "{}"
    data = json.loads(content)
    scores = data.get("scores") or []

    by_id: dict[str, float] = {}
    allowed = {c.chunk_id for c in candidates}
    for row in scores:
        if not isinstance(row, dict):
            continue
        cid = row.get("chunk_id")
        if cid not in allowed:
            continue
        try:
            val = float(row.get("score"))
        except Exception:
            val = 0.0
        val = max(0.0, min(1.0, val))
        by_id[cid] = val

    # Ensure every candidate gets a score.
    for c in candidates:
        by_id.setdefault(c.chunk_id, 0.0)

    return by_id


def get_default_rerank_model() -> str:
    return settings.openai_rerank_model


def get_default_max_passage_chars() -> int:
    return settings.openai_rerank_max_passage_chars
