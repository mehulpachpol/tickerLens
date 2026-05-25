from __future__ import annotations

import json
import time
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from tickerlens_api.chat.citations import extract_chunk_ids, strip_unknown_citations
from tickerlens_api.chat.prompting import build_system_prompt, build_user_prompt
from tickerlens_api.chat.schemas import ChatCitationsPayload, ChatStreamRequest, Citation
from tickerlens_api.db.session import get_db
from tickerlens_api.embeddings.openai_embedder import get_openai_client
from tickerlens_api.search.schemas import HybridRerankRequest
from tickerlens_api.settings import settings
from tickerlens_api.temporal.intent import detect_temporal_intent, infer_document_type_preferences
from tickerlens_api.temporal.scope import resolve_latest_doc_scope


router = APIRouter(prefix="/chat", tags=["chat"])


def _sse_event(*, event: str, data: dict | str) -> bytes:
    if isinstance(data, dict):
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    else:
        payload = data
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


@router.post("/stream")
def chat_stream(req: ChatStreamRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    """
    Phase 8: Constrained generation with citations + SSE streaming.

    Streaming protocol:
    - event: delta      data: {"delta":"..."}
    - event: citations  data: {"used_chunk_ids":[...], "citations":[...]}
    - event: done       data: {"ok":true}
    """

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=422,
            detail="Missing OpenAI API key. Set OPENAI_API_KEY (or TICKERLENS_OPENAI_API_KEY).",
        )

    # Reuse Phase 7 retrieval by calling the same internal function.
    # We intentionally keep this manual-first and will refactor into a shared service later.
    from tickerlens_api.api.routes.search import hybrid_rerank_search

    # Phase 9: temporal scoping (doc_ids) for "latest" questions.
    effective_doc_ids = req.doc_ids
    temporal_debug: dict | None = None
    if effective_doc_ids is None and req.tickers:
        intent = detect_temporal_intent(question=req.question)
        if intent.mode == "latest":
            prefs = infer_document_type_preferences(question=req.question)
            scope = resolve_latest_doc_scope(
                db,
                tickers=req.tickers,
                preferred_document_types=prefs.document_types,
                reason=f"{intent.reason};{prefs.reason}",
            )
            if scope.doc_ids:
                effective_doc_ids = scope.doc_ids
                temporal_debug = {
                    "mode": scope.mode,
                    "reason": scope.reason,
                    "preferred_document_types": scope.preferred_document_types,
                    "selected_docs": [
                        {
                            "doc_id": d.doc_id,
                            "ticker": d.ticker,
                            "document_type": d.document_type,
                            "fiscal_year": d.fiscal_year,
                            "filing_date": d.filing_date,
                            "version": d.version,
                        }
                        for d in scope.selected
                    ],
                }

    search_req = HybridRerankRequest(
        query=req.question,
        top_k=req.top_k,
        tickers=req.tickers,
        doc_ids=effective_doc_ids,
        chunk_run_id=req.chunk_run_id,
        embedding_model=req.embedding_model,
        dimensions=req.dimensions,
        vector_top_n=req.vector_top_n,
        index_version=req.index_version,
        bm25_top_n=req.bm25_top_n,
        rrf_k=req.rrf_k,
        vector_weight=req.vector_weight,
        bm25_weight=req.bm25_weight,
        rerank_backend=req.rerank_backend,
        rerank_model=req.rerank_model,
        rerank_top_n=req.rerank_top_n,
        passage_max_chars=req.passage_max_chars,
        per_ticker_k=req.per_ticker_k,
    )

    t = time.perf_counter()
    retrieval = hybrid_rerank_search(search_req, db=db)
    retrieval_ms = int((time.perf_counter() - t) * 1000)

    allowed_chunk_ids = [h.chunk_id for h in retrieval.hits]
    allowed_set = set(allowed_chunk_ids)

    # Build per-chunk citation palette from retrieval hits. The model cites chunk_id; we attach the rest.
    palette: dict[str, Citation] = {}
    for h in retrieval.hits:
        download_endpoint = f"/documents/{h.doc_id}/download" if h.doc_id else None
        palette[h.chunk_id] = Citation(
            chunk_id=h.chunk_id,
            ticker=h.ticker,
            doc_id=h.doc_id,
            document_type=h.document_type,
            fiscal_year=h.fiscal_year,
            filing_date=str(h.filing_date) if h.filing_date else None,
            version=h.version,
            section=h.section,
            page_start=h.page_start,
            page_end=h.page_end,
            download_endpoint=download_endpoint,
        )

    context = "\n\n".join(b.context for b in retrieval.context_blocks).strip()

    system = build_system_prompt()
    user = build_user_prompt(question=req.question, allowed_chunk_ids=allowed_chunk_ids, context=context)

    client = get_openai_client()

    def stream() -> Iterable[bytes]:
        # Small debug payload for clients (optional to use).
        meta = {"retrieval_ms": retrieval_ms, "candidates": retrieval.candidates}
        if temporal_debug:
            meta["temporal"] = temporal_debug
        yield _sse_event(event="meta", data=meta)

        answer_parts: list[str] = []
        try:
            resp = client.chat.completions.create(
                model=settings.openai_chat_model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=settings.openai_chat_temperature,
                max_tokens=settings.openai_chat_max_tokens,
                stream=True,
            )

            for chunk in resp:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if not delta:
                    continue
                answer_parts.append(delta)
                yield _sse_event(event="delta", data={"delta": delta})

            answer_text = "".join(answer_parts)
            answer_text = strip_unknown_citations(text=answer_text, allowed_chunk_ids=allowed_set)

            used = list(dict.fromkeys(extract_chunk_ids(answer_text)))
            used = [cid for cid in used if cid in allowed_set]

            citations = [palette[cid] for cid in used if cid in palette]
            payload = ChatCitationsPayload(used_chunk_ids=used, citations=citations)
            yield _sse_event(event="citations", data=payload.model_dump())
            yield _sse_event(event="done", data={"ok": True})
        except Exception as e:
            yield _sse_event(event="error", data={"error": str(e)})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
