from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request
from qdrant_client import models as qmodels
from sqlalchemy import select
from sqlalchemy.orm import Session

from tickerlens_api.auth.dependencies import require_user_if_auth_enabled
from tickerlens_api.context.assembler import EvidenceChunk, build_context_blocks
from tickerlens_api.db.models import DocumentChunk
from tickerlens_api.db.session import get_db
from tickerlens_api.embeddings.openai_embedder import embed_texts
from tickerlens_api.embeddings.service import compute_embedding_target
from tickerlens_api.keywordstore.opensearch_store import compute_chunks_index_name, get_opensearch_client
from tickerlens_api.reranking.service import get_default_model, resolve_backend, rerank as rerank_candidates
from tickerlens_api.reranking.types import RerankCandidate
from tickerlens_api.search.schemas import (
    BM25SearchRequest,
    BM25SearchResponse,
    HybridRerankRequest,
    HybridRerankResponse,
    HybridSearchRequest,
    HybridSearchResponse,
    TickerContextBlock,
    VectorSearchRequest,
    VectorSearchResponse,
)
from tickerlens_api.settings import settings
from tickerlens_api.security.limits import rate_limit_request
from tickerlens_api.observability.tracing import start_span
from tickerlens_api.vectorstore.qdrant_store import ensure_collection, search as qdrant_search
from tickerlens_api.temporal.intent import detect_temporal_intent, infer_document_type_preferences
from tickerlens_api.temporal.scope import resolve_latest_doc_scope
from tickerlens_api.observability.rag_metrics import inc_request, observe_stage

router = APIRouter(prefix="/search", tags=["search"], dependencies=[Depends(require_user_if_auth_enabled)])


@router.post("/vector", response_model=VectorSearchResponse)
def vector_search(req: VectorSearchRequest, request: Request) -> VectorSearchResponse:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=422,
            detail="Missing OpenAI API key. Set OPENAI_API_KEY (or TICKERLENS_OPENAI_API_KEY).",
        )

    # Phase 11.3: protect embedding spend.
    rate_limit_request(request=request, prefix="search:vector", limit=settings.rl_vector_search_per_minute, window_s=60)

    try:
        model, dims, vector_size, collection = compute_embedding_target(
            embedding_model=req.embedding_model, dimensions=req.dimensions
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    ensure_collection(collection_name=collection, vector_size=vector_size)

    t = time.perf_counter()
    with start_span("rag.embed.query", endpoint="search.vector", model=model, dimensions=dims or 0):
        query_vec = embed_texts(texts=[req.query], model=model, dimensions=dims)[0]
    observe_stage(endpoint="search.vector", stage="embed_query", duration_ms=int((time.perf_counter() - t) * 1000))

    must: list[qmodels.FieldCondition] = []
    if req.tickers:
        must.append(qmodels.FieldCondition(key="ticker", match=qmodels.MatchAny(any=req.tickers)))
    if req.doc_ids:
        must.append(qmodels.FieldCondition(key="doc_id", match=qmodels.MatchAny(any=req.doc_ids)))
    if req.chunk_run_id:
        must.append(qmodels.FieldCondition(key="chunk_run_id", match=qmodels.MatchValue(value=req.chunk_run_id)))

    query_filter = qmodels.Filter(must=must) if must else None
    t = time.perf_counter()
    with start_span("rag.qdrant.query", endpoint="search.vector", collection=collection, limit=req.top_k):
        hits = qdrant_search(collection_name=collection, query_vector=query_vec, query_filter=query_filter, limit=req.top_k)
    observe_stage(endpoint="search.vector", stage="qdrant_query", duration_ms=int((time.perf_counter() - t) * 1000))

    inc_request(endpoint="search.vector", status="ok")

    return VectorSearchResponse(
        collection=collection,
        embedding_model=model,
        dimensions=dims,
        vector_size=vector_size,
        hits=[
            {
                "chunk_id": str(h.id),
                "score": float(h.score),
                "ticker": (h.payload or {}).get("ticker") if h.payload else None,
                "doc_id": (h.payload or {}).get("doc_id") if h.payload else None,
                "document_type": (h.payload or {}).get("document_type") if h.payload else None,
                "fiscal_year": (h.payload or {}).get("fiscal_year") if h.payload else None,
                "filing_date": (h.payload or {}).get("filing_date") if h.payload else None,
                "version": (h.payload or {}).get("version") if h.payload else None,
                "section": (h.payload or {}).get("section") if h.payload else None,
                "page_start": (h.payload or {}).get("page_start") if h.payload else None,
                "page_end": (h.payload or {}).get("page_end") if h.payload else None,
            }
            for h in hits
        ],
    )


@router.post("/bm25", response_model=BM25SearchResponse)
def bm25_search(req: BM25SearchRequest) -> BM25SearchResponse:
    index_name = compute_chunks_index_name(version=req.index_version)
    client = get_opensearch_client()

    if not client.indices.exists(index=index_name):
        raise HTTPException(
            status_code=404,
            detail=f"OpenSearch index '{index_name}' not found. Run POST /documents/{{doc_id}}/index first.",
        )

    filters: list[dict] = []
    if req.tickers:
        filters.append({"terms": {"ticker": req.tickers}})
    if req.doc_ids:
        filters.append({"terms": {"doc_id": req.doc_ids}})
    if req.chunk_run_id:
        filters.append({"term": {"chunk_run_id": req.chunk_run_id}})

    body = {
        "query": {
            "bool": {
                "must": [{"multi_match": {"query": req.query, "fields": ["text^3", "section"]}}],
                "filter": filters,
            }
        },
        "size": req.top_k,
        "highlight": {"fields": {"text": {"fragment_size": 160, "number_of_fragments": 2}}},
    }

    resp = client.search(index=index_name, body=body)
    hits = (((resp or {}).get("hits") or {}).get("hits") or [])

    out_hits: list[dict] = []
    for h in hits:
        src = h.get("_source") or {}
        hl = (h.get("highlight") or {}).get("text")
        out_hits.append(
            {
                "chunk_id": h.get("_id"),
                "score": float(h.get("_score") or 0.0),
                "ticker": src.get("ticker"),
                "doc_id": src.get("doc_id"),
                "document_type": src.get("document_type"),
                "fiscal_year": src.get("fiscal_year"),
                "filing_date": src.get("filing_date"),
                "version": src.get("version"),
                "section": src.get("section"),
                "page_start": src.get("page_start"),
                "page_end": src.get("page_end"),
                "highlight": hl,
            }
        )

    return BM25SearchResponse(index_name=index_name, hits=out_hits)


@router.post("/hybrid", response_model=HybridSearchResponse)
def hybrid_search(req: HybridSearchRequest, request: Request, db: Session = Depends(get_db)) -> HybridSearchResponse:
    # Hybrid search needs both OpenSearch (BM25) and Qdrant (vector).
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=422,
            detail="Missing OpenAI API key. Set OPENAI_API_KEY (or TICKERLENS_OPENAI_API_KEY).",
        )

    # Phase 11.3: protect embedding spend.
    rate_limit_request(request=request, prefix="search:hybrid", limit=settings.rl_vector_search_per_minute, window_s=60)

    # Phase 9 temporal scoping: if the query asks for "latest", restrict to latest relevant docs (unless doc_ids explicitly provided).
    effective_doc_ids = req.doc_ids
    if effective_doc_ids is None and req.tickers:
        intent = detect_temporal_intent(question=req.query)
        if intent.mode == "latest":
            prefs = infer_document_type_preferences(question=req.query)
            scope = resolve_latest_doc_scope(
                db,
                tickers=req.tickers,
                preferred_document_types=prefs.document_types,
                reason=f"{intent.reason};{prefs.reason}",
            )
            if scope.doc_ids:
                effective_doc_ids = scope.doc_ids

    # Vector side
    try:
        model, dims, vector_size, collection = compute_embedding_target(
            embedding_model=req.embedding_model, dimensions=req.dimensions
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    ensure_collection(collection_name=collection, vector_size=vector_size)
    t = time.perf_counter()
    with start_span("rag.embed.query", endpoint="search.hybrid", model=model, dimensions=dims or 0):
        query_vec = embed_texts(texts=[req.query], model=model, dimensions=dims)[0]
    observe_stage(endpoint="search.hybrid", stage="embed_query", duration_ms=int((time.perf_counter() - t) * 1000))

    must: list[qmodels.FieldCondition] = []
    if req.tickers:
        must.append(qmodels.FieldCondition(key="ticker", match=qmodels.MatchAny(any=req.tickers)))
    if effective_doc_ids:
        must.append(qmodels.FieldCondition(key="doc_id", match=qmodels.MatchAny(any=effective_doc_ids)))
    if req.chunk_run_id:
        must.append(qmodels.FieldCondition(key="chunk_run_id", match=qmodels.MatchValue(value=req.chunk_run_id)))
    query_filter = qmodels.Filter(must=must) if must else None

    t = time.perf_counter()
    with start_span("rag.qdrant.query", endpoint="search.hybrid", collection=collection, limit=req.vector_top_n):
        vector_hits = qdrant_search(
            collection_name=collection,
            query_vector=query_vec,
            query_filter=query_filter,
            limit=req.vector_top_n,
        )
    observe_stage(endpoint="search.hybrid", stage="qdrant_query", duration_ms=int((time.perf_counter() - t) * 1000))

    # BM25 side
    index_name = compute_chunks_index_name(version=req.index_version)
    os_client = get_opensearch_client()
    if not os_client.indices.exists(index=index_name):
        raise HTTPException(
            status_code=404,
            detail=f"OpenSearch index '{index_name}' not found. Run POST /documents/{{doc_id}}/index first.",
        )

    os_filters: list[dict] = []
    if req.tickers:
        os_filters.append({"terms": {"ticker": req.tickers}})
    if effective_doc_ids:
        os_filters.append({"terms": {"doc_id": effective_doc_ids}})
    if req.chunk_run_id:
        os_filters.append({"term": {"chunk_run_id": req.chunk_run_id}})

    os_body = {
        "query": {
            "bool": {
                "must": [{"multi_match": {"query": req.query, "fields": ["text^3", "section"]}}],
                "filter": os_filters,
            }
        },
        "size": req.bm25_top_n,
        "highlight": {"fields": {"text": {"fragment_size": 160, "number_of_fragments": 2}}},
    }
    t = time.perf_counter()
    with start_span("rag.opensearch.search", endpoint="search.hybrid", index=index_name, size=req.bm25_top_n):
        os_resp = os_client.search(index=index_name, body=os_body)
    observe_stage(
        endpoint="search.hybrid",
        stage="opensearch_query",
        duration_ms=int((time.perf_counter() - t) * 1000),
    )
    bm25_hits = (((os_resp or {}).get("hits") or {}).get("hits") or [])

    # Reciprocal Rank Fusion (rank-based merge so we don't have to calibrate score scales).
    # score = sum(weight / (k + rank)) across retrievers.
    rrf_k = req.rrf_k
    scores: dict[str, float] = {}
    merged: dict[str, dict] = {}

    def add_rrf(*, chunk_id: str, rank: int, weight: float) -> None:
        scores[chunk_id] = scores.get(chunk_id, 0.0) + (weight / float(rrf_k + rank))

    for rank, h in enumerate(vector_hits, start=1):
        chunk_id = str(h.id)
        add_rrf(chunk_id=chunk_id, rank=rank, weight=req.vector_weight)
        payload = h.payload or {}
        merged.setdefault(
            chunk_id,
            {
                "chunk_id": chunk_id,
                "vector_score": float(h.score),
                "vector_rank": rank,
                "bm25_score": None,
                "bm25_rank": None,
                "highlight": None,
                "ticker": payload.get("ticker"),
                "doc_id": payload.get("doc_id"),
                "document_type": payload.get("document_type"),
                "fiscal_year": payload.get("fiscal_year"),
                "filing_date": payload.get("filing_date"),
                "version": payload.get("version"),
                "section": payload.get("section"),
                "page_start": payload.get("page_start"),
                "page_end": payload.get("page_end"),
            },
        )

    for rank, h in enumerate(bm25_hits, start=1):
        chunk_id = h.get("_id")
        if not chunk_id:
            continue
        add_rrf(chunk_id=chunk_id, rank=rank, weight=req.bm25_weight)
        src = h.get("_source") or {}
        hl = (h.get("highlight") or {}).get("text")
        entry = merged.setdefault(
            chunk_id,
            {
                "chunk_id": chunk_id,
                "vector_score": None,
                "vector_rank": None,
                "bm25_score": None,
                "bm25_rank": None,
                "highlight": None,
                "ticker": src.get("ticker"),
                "doc_id": src.get("doc_id"),
                "document_type": src.get("document_type"),
                "fiscal_year": src.get("fiscal_year"),
                "filing_date": src.get("filing_date"),
                "version": src.get("version"),
                "section": src.get("section"),
                "page_start": src.get("page_start"),
                "page_end": src.get("page_end"),
            },
        )
        entry["bm25_score"] = float(h.get("_score") or 0.0)
        entry["bm25_rank"] = rank
        entry["highlight"] = hl

        # If vector already populated some metadata, avoid overwriting with None.
        for key in (
            "ticker",
            "doc_id",
            "document_type",
            "fiscal_year",
            "filing_date",
            "version",
            "section",
            "page_start",
            "page_end",
        ):
            if entry.get(key) is None and src.get(key) is not None:
                entry[key] = src.get(key)

    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_ids = [cid for cid, _ in ordered[: req.top_k]]

    inc_request(endpoint="search.hybrid", status="ok")
    return HybridSearchResponse(
        index_name=index_name,
        collection=collection,
        embedding_model=model,
        dimensions=dims,
        vector_size=vector_size,
        hits=[
            {
                **merged[cid],
                "score": float(scores[cid]),
            }
            for cid in top_ids
            if cid in merged
        ],
    )


@router.post("/hybrid_rerank", response_model=HybridRerankResponse)
def hybrid_rerank_search(req: HybridRerankRequest, request: Request, db: Session = Depends(get_db)) -> HybridRerankResponse:
    """
    Phase 7: run hybrid retrieval (Phase 6), then rerank the top-N candidates.

    Reranking backends:
    - fastembed (local cross-encoder, low latency)
    - openai (LLM-based, higher latency)

    This is manual-first and intended for development/learning. We'll move reranking to a worker later.
    """

    timings: dict[str, int] = {}
    t_total = time.perf_counter()

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=422,
            detail="Missing OpenAI API key. Set OPENAI_API_KEY (or TICKERLENS_OPENAI_API_KEY).",
        )

    # Phase 11.3: protect embedding spend (hybrid_rerank includes embedding + rerank compute).
    rate_limit_request(request=request, prefix="search:hybrid_rerank", limit=settings.rl_vector_search_per_minute, window_s=60)

    # Phase 9 temporal scoping (same behavior as /search/hybrid).
    effective_doc_ids = req.doc_ids
    if effective_doc_ids is None and req.tickers:
        intent = detect_temporal_intent(question=req.query)
        if intent.mode == "latest":
            prefs = infer_document_type_preferences(question=req.query)
            scope = resolve_latest_doc_scope(
                db,
                tickers=req.tickers,
                preferred_document_types=prefs.document_types,
                reason=f"{intent.reason};{prefs.reason}",
            )
            if scope.doc_ids:
                effective_doc_ids = scope.doc_ids

    # Vector side
    try:
        model, dims, vector_size, collection = compute_embedding_target(
            embedding_model=req.embedding_model, dimensions=req.dimensions
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    ensure_collection(collection_name=collection, vector_size=vector_size)

    t = time.perf_counter()
    with start_span("rag.embed.query", endpoint="search.hybrid_rerank", model=model, dimensions=dims or 0):
        query_vec = embed_texts(texts=[req.query], model=model, dimensions=dims)[0]
    timings["openai_embed_ms"] = int((time.perf_counter() - t) * 1000)
    observe_stage(endpoint="search.hybrid_rerank", stage="embed_query", duration_ms=timings["openai_embed_ms"])

    must: list[qmodels.FieldCondition] = []
    if req.tickers:
        must.append(qmodels.FieldCondition(key="ticker", match=qmodels.MatchAny(any=req.tickers)))
    if effective_doc_ids:
        must.append(qmodels.FieldCondition(key="doc_id", match=qmodels.MatchAny(any=effective_doc_ids)))
    if req.chunk_run_id:
        must.append(qmodels.FieldCondition(key="chunk_run_id", match=qmodels.MatchValue(value=req.chunk_run_id)))
    query_filter = qmodels.Filter(must=must) if must else None

    t = time.perf_counter()
    with start_span("rag.qdrant.query", endpoint="search.hybrid_rerank", collection=collection, limit=req.vector_top_n):
        vector_hits = qdrant_search(
            collection_name=collection,
            query_vector=query_vec,
            query_filter=query_filter,
            limit=req.vector_top_n,
        )
    timings["qdrant_query_ms"] = int((time.perf_counter() - t) * 1000)
    observe_stage(endpoint="search.hybrid_rerank", stage="qdrant_query", duration_ms=timings["qdrant_query_ms"])

    # BM25 side
    index_name = compute_chunks_index_name(version=req.index_version)
    os_client = get_opensearch_client()
    if not os_client.indices.exists(index=index_name):
        raise HTTPException(
            status_code=404,
            detail=f"OpenSearch index '{index_name}' not found. Run POST /documents/{{doc_id}}/index first.",
        )

    os_filters: list[dict] = []
    if req.tickers:
        os_filters.append({"terms": {"ticker": req.tickers}})
    if effective_doc_ids:
        os_filters.append({"terms": {"doc_id": effective_doc_ids}})
    if req.chunk_run_id:
        os_filters.append({"term": {"chunk_run_id": req.chunk_run_id}})

    os_body = {
        "query": {
            "bool": {
                "must": [{"multi_match": {"query": req.query, "fields": ["text^3", "section"]}}],
                "filter": os_filters,
            }
        },
        "size": req.bm25_top_n,
        "highlight": {"fields": {"text": {"fragment_size": 160, "number_of_fragments": 2}}},
    }
    t = time.perf_counter()
    with start_span("rag.opensearch.search", endpoint="search.hybrid_rerank", index=index_name, size=req.bm25_top_n):
        os_resp = os_client.search(index=index_name, body=os_body)
    timings["opensearch_query_ms"] = int((time.perf_counter() - t) * 1000)
    observe_stage(endpoint="search.hybrid_rerank", stage="opensearch_query", duration_ms=timings["opensearch_query_ms"])
    bm25_hits = (((os_resp or {}).get("hits") or {}).get("hits") or [])

    # Reciprocal Rank Fusion candidates (Phase 6 output).
    rrf_k = req.rrf_k
    fusion_scores: dict[str, float] = {}
    merged: dict[str, dict] = {}

    def add_rrf(*, chunk_id: str, rank: int, weight: float) -> None:
        fusion_scores[chunk_id] = fusion_scores.get(chunk_id, 0.0) + (weight / float(rrf_k + rank))

    for rank, h in enumerate(vector_hits, start=1):
        chunk_id = str(h.id)
        add_rrf(chunk_id=chunk_id, rank=rank, weight=req.vector_weight)
        payload = h.payload or {}
        merged.setdefault(
            chunk_id,
            {
                "chunk_id": chunk_id,
                "vector_score": float(h.score),
                "vector_rank": rank,
                "bm25_score": None,
                "bm25_rank": None,
                "highlight": None,
                "ticker": payload.get("ticker"),
                "doc_id": payload.get("doc_id"),
                "document_type": payload.get("document_type"),
                "fiscal_year": payload.get("fiscal_year"),
                "filing_date": payload.get("filing_date"),
                "version": payload.get("version"),
                "section": payload.get("section"),
                "page_start": payload.get("page_start"),
                "page_end": payload.get("page_end"),
            },
        )

    for rank, h in enumerate(bm25_hits, start=1):
        chunk_id = h.get("_id")
        if not chunk_id:
            continue
        add_rrf(chunk_id=chunk_id, rank=rank, weight=req.bm25_weight)
        src = h.get("_source") or {}
        hl = (h.get("highlight") or {}).get("text")
        entry = merged.setdefault(
            chunk_id,
            {
                "chunk_id": chunk_id,
                "vector_score": None,
                "vector_rank": None,
                "bm25_score": None,
                "bm25_rank": None,
                "highlight": None,
                "ticker": src.get("ticker"),
                "doc_id": src.get("doc_id"),
                "document_type": src.get("document_type"),
                "fiscal_year": src.get("fiscal_year"),
                "filing_date": src.get("filing_date"),
                "version": src.get("version"),
                "section": src.get("section"),
                "page_start": src.get("page_start"),
                "page_end": src.get("page_end"),
            },
        )
        entry["bm25_score"] = float(h.get("_score") or 0.0)
        entry["bm25_rank"] = rank
        entry["highlight"] = hl

        for key in (
            "ticker",
            "doc_id",
            "document_type",
            "fiscal_year",
            "filing_date",
            "version",
            "section",
            "page_start",
            "page_end",
        ):
            if entry.get(key) is None and src.get(key) is not None:
                entry[key] = src.get(key)

    ordered = sorted(fusion_scores.items(), key=lambda kv: kv[1], reverse=True)
    candidate_ids = [cid for cid, _ in ordered[: req.rerank_top_n] if cid in merged]

    # Fetch chunk texts for reranking + context assembly.
    t = time.perf_counter()
    text_by_id: dict[str, str] = {}
    if candidate_ids:
        with start_span("rag.postgres.chunk_fetch", endpoint="search.hybrid_rerank", candidates=len(candidate_ids)):
            stmt = select(DocumentChunk).where(DocumentChunk.chunk_id.in_(candidate_ids))
            rows = list(db.execute(stmt).scalars().all())
            for r in rows:
                text_by_id[r.chunk_id] = r.text or ""
    timings["postgres_chunk_fetch_ms"] = int((time.perf_counter() - t) * 1000)
    observe_stage(endpoint="search.hybrid_rerank", stage="postgres_chunk_fetch", duration_ms=timings["postgres_chunk_fetch_ms"])

    backend = resolve_backend(backend=req.rerank_backend, model=req.rerank_model)
    rerank_model = req.rerank_model or get_default_model(backend=backend)
    max_passage_chars = req.passage_max_chars

    candidates = [
        RerankCandidate(chunk_id=cid, passage=text_by_id.get(cid, "")) for cid in candidate_ids
    ]
    t = time.perf_counter()
    with start_span("rag.rerank", endpoint="search.hybrid_rerank", backend=backend, model=rerank_model, candidates=len(candidates)):
        rerank_scores = rerank_candidates(
            backend=backend,
            query=req.query,
            candidates=candidates,
            model=rerank_model,
            max_passage_chars=max_passage_chars,
        )
    timings["rerank_ms"] = int((time.perf_counter() - t) * 1000)
    observe_stage(endpoint="search.hybrid_rerank", stage="rerank", duration_ms=timings["rerank_ms"])

    # Rank by rerank score, with fusion score as tie-breaker.
    scored = []
    for cid in candidate_ids:
        scored.append(
            (
                cid,
                float(rerank_scores.get(cid, 0.0)),
                float(fusion_scores.get(cid, 0.0)),
            )
        )
    scored.sort(key=lambda t: (t[1], t[2]), reverse=True)

    selected_ids: list[str] = []
    if req.per_ticker_k and req.tickers and len(req.tickers) > 1:
        per_ticker: dict[str, list[str]] = {t: [] for t in req.tickers}
        for cid, _, _ in scored:
            ticker = (merged.get(cid) or {}).get("ticker")
            if not ticker or ticker not in per_ticker:
                continue
            if len(per_ticker[ticker]) < req.per_ticker_k:
                per_ticker[ticker].append(cid)
        for t in req.tickers:
            selected_ids.extend(per_ticker.get(t) or [])
        selected_ids = list(dict.fromkeys(selected_ids))  # stable de-dupe

    for cid, _, _ in scored:
        if cid in selected_ids:
            continue
        selected_ids.append(cid)
        if len(selected_ids) >= req.top_k:
            break

    # Build context blocks (per ticker) from selected chunks.
    evidence: list[EvidenceChunk] = []
    for cid in selected_ids:
        m = merged.get(cid) or {}
        ticker = m.get("ticker") or "UNKNOWN"
        evidence.append(
            EvidenceChunk(
                chunk_id=cid,
                ticker=ticker,
                text=text_by_id.get(cid, ""),
                doc_id=m.get("doc_id"),
                document_type=m.get("document_type"),
                fiscal_year=m.get("fiscal_year"),
                filing_date=m.get("filing_date"),
                version=m.get("version"),
                section=m.get("section"),
                page_start=m.get("page_start"),
                page_end=m.get("page_end"),
            )
        )

    t = time.perf_counter()
    with start_span("rag.context.build", endpoint="search.hybrid_rerank", selected=len(selected_ids)):
        blocks = build_context_blocks(
            requested_tickers=req.tickers,
            chunks=evidence,
            max_chunk_chars=max_passage_chars,
        )
    timings["context_build_ms"] = int((time.perf_counter() - t) * 1000)
    observe_stage(endpoint="search.hybrid_rerank", stage="context_build", duration_ms=timings["context_build_ms"])

    context_blocks = [
        TickerContextBlock(ticker=t, chunks=chunk_ids, context=ctx) for t, chunk_ids, ctx in blocks
    ]

    hits_out = []
    for cid in selected_ids:
        m = merged.get(cid) or {}
        hits_out.append(
            {
                **m,
                "chunk_id": cid,
                "rerank_score": float(rerank_scores.get(cid, 0.0)),
                "fusion_score": float(fusion_scores.get(cid, 0.0)),
            }
        )

    observe_stage(endpoint="search.hybrid_rerank", stage="total", duration_ms=int((time.perf_counter() - t_total) * 1000))
    inc_request(endpoint="search.hybrid_rerank", status="ok")
    return HybridRerankResponse(
        index_name=index_name,
        collection=collection,
        embedding_model=model,
        dimensions=dims,
        vector_size=vector_size,
        rerank_model=rerank_model,
        candidates=len(candidate_ids),
        hits=hits_out,
        context_blocks=context_blocks,
        timings_ms={**timings, "total_ms": int((time.perf_counter() - t_total) * 1000)},
    )
