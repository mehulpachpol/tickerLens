from __future__ import annotations

import json
import time
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from tickerlens_api.auth.dependencies import get_current_user_optional
from tickerlens_api.chat.citations import extract_chunk_ids, strip_unknown_citations
from tickerlens_api.chat.prompting import build_system_prompt, build_user_prompt
from tickerlens_api.chat.schemas import ChatCitationsPayload, ChatStreamRequest, Citation
from tickerlens_api.conversations.service import (
    add_message,
    add_rag_run,
    create_conversation,
    get_conversation,
    update_conversation,
)
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
def chat_stream(
    req: ChatStreamRequest,
    request: Request,
    db: Session = Depends(get_db),
    auth_user=Depends(get_current_user_optional),
) -> StreamingResponse:
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

    if settings.auth_enabled and not auth_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    effective_tickers: list[str] | None = req.tickers

    conversation_id: str | None = None
    if settings.auth_enabled and auth_user:
        if req.conversation_id:
            c = get_conversation(db, conversation_id=req.conversation_id, user_id=auth_user.user_id)
            if not c:
                raise HTTPException(status_code=404, detail="Conversation not found")
            conversation_id = c.conversation_id

            # If the client omitted tickers, fall back to the persisted conversation scope.
            if effective_tickers is None:
                effective_tickers = list(c.tickers or [])

            # Keep conversation scope in sync if the client provides a new scope.
            if effective_tickers is not None and list(c.tickers or []) != list(effective_tickers):
                update_conversation(
                    db,
                    conversation_id=conversation_id,
                    user_id=auth_user.user_id,
                    tickers=list(effective_tickers),
                )

            # If the conversation was pre-created (e.g. by UI) with no title, set a title from the first question.
            if not c.title:
                title = req.question.strip()
                title = title[:120] if len(title) > 120 else title
                if title:
                    update_conversation(
                        db,
                        conversation_id=conversation_id,
                        user_id=auth_user.user_id,
                        title=title,
                    )
        else:
            if effective_tickers is None:
                effective_tickers = []
            title = req.question.strip()
            title = title[:120] if len(title) > 120 else title
            c = create_conversation(
                db,
                user_id=auth_user.user_id,
                title=title or None,
                tickers=list(effective_tickers),
            )
            conversation_id = c.conversation_id

        add_message(db, conversation_id=conversation_id, user_id=auth_user.user_id, role="user", content=req.question)

    # Reuse Phase 7 retrieval by calling the same internal function.
    # We intentionally keep this manual-first and will refactor into a shared service later.
    from tickerlens_api.api.routes.search import hybrid_rerank_search

    # Phase 9: temporal scoping (doc_ids) for "latest" questions.
    effective_doc_ids = req.doc_ids
    temporal_debug: dict | None = None
    if effective_doc_ids is None and effective_tickers:
        intent = detect_temporal_intent(question=req.question)
        if intent.mode == "latest":
            prefs = infer_document_type_preferences(question=req.question)
            scope = resolve_latest_doc_scope(
                db,
                tickers=effective_tickers,
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
        tickers=effective_tickers,
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
    user_prompt = build_user_prompt(question=req.question, allowed_chunk_ids=allowed_chunk_ids, context=context)

    client = get_openai_client()

    def stream() -> Iterable[bytes]:
        # Small debug payload for clients (optional to use).
        meta = {"retrieval_ms": retrieval_ms, "candidates": retrieval.candidates}
        if temporal_debug:
            meta["temporal"] = temporal_debug
        if conversation_id:
            meta["conversation_id"] = conversation_id
        yield _sse_event(event="meta", data=meta)

        answer_parts: list[str] = []
        try:
            t_gen = time.perf_counter()
            resp = client.chat.completions.create(
                model=settings.openai_chat_model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user_prompt}],
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
            gen_ms = int((time.perf_counter() - t_gen) * 1000)
            answer_text = strip_unknown_citations(text=answer_text, allowed_chunk_ids=allowed_set)

            used = list(dict.fromkeys(extract_chunk_ids(answer_text)))
            used = [cid for cid in used if cid in allowed_set]

            citations = [palette[cid] for cid in used if cid in palette]
            payload = ChatCitationsPayload(used_chunk_ids=used, citations=citations)

            # Phase 11: persist assistant response + retrieval/citation audit.
            if settings.auth_enabled and auth_user and conversation_id:
                add_message(
                    db,
                    conversation_id=conversation_id,
                    user_id=auth_user.user_id,
                    role="assistant",
                    content=answer_text,
                )
                add_rag_run(
                    db,
                    conversation_id=conversation_id,
                    user_id=auth_user.user_id,
                    question=req.question,
                    answer=answer_text,
                    tickers=effective_tickers,
                    doc_ids=effective_doc_ids,
                    retrieval={**retrieval.model_dump(), "temporal": temporal_debug} if temporal_debug else retrieval.model_dump(),
                    citations=payload.model_dump(),
                    timings_ms={**(retrieval.timings_ms or {}), "retrieval_ms": retrieval_ms, "generation_ms": gen_ms},
                    models={
                        "chat_model": settings.openai_chat_model,
                        "embedding_model": retrieval.embedding_model,
                        "rerank_model": retrieval.rerank_model,
                    },
                )

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
