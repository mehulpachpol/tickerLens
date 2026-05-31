from __future__ import annotations

import json
import time
from typing import Iterable

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from tickerlens_api.agent.heuristics import infer_intent, infer_tickers_from_question, maybe_clarify, plan_retrieval
from tickerlens_api.audit.service import log_audit
from tickerlens_api.chat.citations import extract_chunk_ids, strip_unknown_citations
from tickerlens_api.chat.prompting import build_system_prompt, build_user_prompt
from tickerlens_api.chat.schemas import ChatCitationsPayload, ChatStreamRequest, Citation
from tickerlens_api.conversations.service import add_message, add_rag_run, update_conversation
from tickerlens_api.embeddings.openai_embedder import get_openai_client
from tickerlens_api.observability.rag_metrics import inc_request, observe_citations, observe_stage
from tickerlens_api.observability.tracing import start_span
from tickerlens_api.search.schemas import HybridRerankRequest
from tickerlens_api.temporal.intent import detect_temporal_intent, infer_document_type_preferences
from tickerlens_api.temporal.scope import resolve_latest_doc_scope
from tickerlens_api.settings import settings


def _sse_event(*, event: str, data: dict | str) -> bytes:
    if isinstance(data, dict):
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    else:
        payload = data
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


def _tool_def(*, name: str, description: str, parameters: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "strict": True,
            "parameters": parameters,
        },
    }


def _agent_research_system_prompt() -> str:
    return (
        "You are TickerLens Agent Controller.\n"
        "You are NOT allowed to answer the user directly in this phase.\n"
        "You must operate by calling the provided tools in a loop.\n"
        "\n"
        "Policy:\n"
        "- If tickers are missing, call tool_ask_user(kind='tickers', ...) to ask for tickers.\n"
        "- For each run with tickers, call tool_yahoo_fundamentals first (Yahoo snapshot), then tool_rag_retrieve (filings).\n"
        "- If filings retrieval returns few/no relevant results, call tool_doc_coverage to see what's available, then ask ONE follow-up question via tool_ask_user.\n"
        "- When you have enough evidence to write a high-quality answer, call tool_finish_research.\n"
        "\n"
        "Important:\n"
        "- Call exactly ONE tool per step.\n"
        "- Keep tool arguments small and bounded.\n"
    )


def _agent_research_user_prompt(*, question: str, tickers: list[str], doc_ids: list[str] | None) -> str:
    return (
        "User question:\n"
        f"{question.strip()}\n\n"
        "Selected tickers:\n"
        f"{', '.join(tickers)}\n\n"
        "Doc scope (doc_ids) restriction:\n"
        f"{', '.join(doc_ids or []) if doc_ids else '(none)'}\n\n"
        "Run your tool loop now."
    )


def run_agent_stream(
    req: ChatStreamRequest,
    *,
    request: Request,
    db: Session,
    auth_user,
    conversation_id: str | None,
    effective_tickers: list[str] | None,
    effective_doc_ids: list[str] | None,
    temporal_debug: dict | None,
) -> Iterable[bytes]:
    """
    Phase 12.1: Agent Controller (core loop).

    The agent is deterministic in v1:
    - infer intent
    - derive a retrieval plan
    - gate answerability (clarify vs answer)
    - perform constrained RAG generation with citations
    """

    # Reuse Phase 7 retrieval by calling the same internal function.
    # We intentionally keep this manual-first and will refactor into a shared service later.
    from tickerlens_api.api.routes.search import hybrid_rerank_search

    t_agent = time.perf_counter()
    ledger: dict = {"steps": [], "intent": None, "plan": None}

    def step(name: str, *, details: dict) -> None:
        ledger["steps"].append({"step": name, "t_ms": int((time.perf_counter() - t_agent) * 1000), **details})

    # ------------------------------------------------------------------
    # analyze_intent
    # ------------------------------------------------------------------
    intent = infer_intent(question=req.question)
    ledger["intent"] = {
        "comparison": intent.comparison,
        "exhaustive_mentions": intent.exhaustive_mentions,
        "asks_latest": intent.asks_latest,
        "tool_eligible_financials": intent.tool_eligible_financials,
        "reason": intent.reason,
    }
    step("analyze_intent", details={"intent": ledger["intent"]})
    yield _sse_event(event="agent_step", data={"step": "analyze_intent", "intent": ledger["intent"]})

    # If the question explicitly mentions tickers, prefer them over any pre-selected scope.
    # This prevents a common UX failure mode: user had INFY selected, asks about TCS, and we still answer for INFY.
    inferred = infer_tickers_from_question(db, question=req.question)
    if inferred:
        prev = list(effective_tickers or [])
        prev_set = set(prev)
        inferred_set = set(inferred)

        # For this *run*, always narrow scope to the explicitly mentioned tickers.
        # (If the user wrote "TCS", we should retrieve for TCS even if INFY is selected.)
        effective_tickers = inferred

        # For the *conversation scope* (what the UI shows as selected), keep the previous
        # tickers and append any newly mentioned ones. This matches user expectation:
        # "I asked about a new ticker, so add it to my scope", without losing the old one.
        merged_scope = list(prev)
        for t in inferred:
            if t not in prev_set:
                merged_scope.append(t)

        reason = "found_in_question" if not prev else ("narrow_to_question_tickers" if inferred_set.issubset(prev_set) else "narrow_and_expand_scope")

        step(
            "infer_tickers",
            details={
                "tickers_for_run": list(effective_tickers or []),
                "conversation_scope": merged_scope,
                "reason": reason,
                "previous_scope": prev,
            },
        )
        yield _sse_event(
            event="agent_step",
            data={
                "step": "infer_tickers",
                "tickers": list(effective_tickers or []),
                "reason": reason,
                "conversation_scope": merged_scope,
            },
        )

        # Keep conversation scope in sync so the UI reflects the newly mentioned ticker(s).
        if settings.auth_enabled and auth_user and conversation_id and merged_scope != prev:
            try:
                update_conversation(
                    db,
                    conversation_id=conversation_id,
                    user_id=auth_user.user_id,
                    tickers=merged_scope,
                )
            except Exception:
                pass

    clarification = maybe_clarify(intent=intent, tickers=effective_tickers)
    if clarification:
        step("ask_clarifying_question", details={"kind": clarification.kind, "reason": clarification.reason})
        yield _sse_event(
            event="clarify",
            data={"kind": clarification.kind, "question": clarification.question, "options": clarification.options},
        )

        # Compatibility: also emit a delta so existing clients show the question.
        yield _sse_event(event="delta", data={"delta": clarification.question})

        if settings.auth_enabled and auth_user and conversation_id:
            add_message(
                db,
                conversation_id=conversation_id,
                user_id=auth_user.user_id,
                role="assistant",
                content=clarification.question,
            )
            # Persist a run record so the UI (which renders from /runs) keeps this turn.
            try:
                add_rag_run(
                    db,
                    conversation_id=conversation_id,
                    user_id=auth_user.user_id,
                    question=req.question,
                    answer=clarification.question,
                    tickers=effective_tickers,
                    doc_ids=effective_doc_ids,
                    retrieval={"agent": ledger},
                    citations=ChatCitationsPayload(used_chunk_ids=[], citations=[]).model_dump(),
                    timings_ms={"agent_ms": int((time.perf_counter() - t_agent) * 1000)},
                    models={"chat_model": settings.openai_chat_model},
                )
            except Exception:
                pass

        inc_request(endpoint="chat.stream", status="clarify")
        yield _sse_event(event="citations", data=ChatCitationsPayload(used_chunk_ids=[], citations=[]).model_dump())
        yield _sse_event(event="done", data={"ok": True, "mode": "clarify"})
        return

    # ------------------------------------------------------------------
    # temporal scoping (Phase 9) - reuse current behavior
    # ------------------------------------------------------------------
    if effective_doc_ids is None and (effective_tickers or []):
        intent_temporal = detect_temporal_intent(question=req.question)
        if intent_temporal.mode == "latest":
            prefs = infer_document_type_preferences(question=req.question)
            scope = resolve_latest_doc_scope(
                db,
                tickers=list(effective_tickers or []),
                preferred_document_types=prefs.document_types,
                reason=f"{intent_temporal.reason};{prefs.reason}",
            )
            if scope.doc_ids:
                effective_doc_ids = scope.doc_ids
                temporal_debug = {
                    "mode": scope.mode,
                    "reason": scope.reason,
                    "preferred_document_types": scope.preferred_document_types,
                    "selected_docs": [d.__dict__ for d in scope.selected],
                }
                step("temporal_scope", details={"doc_ids": effective_doc_ids, "temporal": temporal_debug})
                yield _sse_event(event="agent_step", data={"step": "temporal_scope", "doc_ids": effective_doc_ids})

    # ------------------------------------------------------------------
    # plan (retrieval knobs)
    # ------------------------------------------------------------------
    plan = plan_retrieval(intent=intent, requested_top_k=req.top_k, tickers=effective_tickers)
    ledger["plan"] = {"top_k": plan.top_k, "per_ticker_k": plan.per_ticker_k, "rerank_top_n": plan.rerank_top_n, "reason": plan.reason}
    step("plan", details={"plan": ledger["plan"]})
    yield _sse_event(event="agent_step", data={"step": "plan", "plan": ledger["plan"]})

    # ------------------------------------------------------------------
    # tool: Yahoo Finance fundamentals (Phase 12.2)
    # ------------------------------------------------------------------
    tool_chunk_ids: list[str] = []
    tool_palette: dict[str, Citation] = {}
    tool_context_by_ticker: dict[str, str] = {}
    tool_chunk_id_by_ticker: dict[str, str] = {}
    tool_errors: dict[str, str] = {}
    tool_ms: int | None = None

    if intent.tool_eligible_financials and (effective_tickers or []):
        yield _sse_event(
            event="agent_step",
            data={"step": "tool_yahoo_finance", "status": "start", "tickers": list(effective_tickers or [])},
        )
        t_tool = time.perf_counter()
        try:
            from tickerlens_api.tools.yahoo_finance import (
                get_yahoo_fundamentals_context,
                make_yahoo_chunk_id,
                make_yahoo_doc_id,
            )

            for tkr in list(effective_tickers or []):
                try:
                    tool_ctx = get_yahoo_fundamentals_context(ticker=tkr)
                    chunk_id = make_yahoo_chunk_id(tool_ctx.yahoo_symbol)
                    doc_id = make_yahoo_doc_id(tool_ctx.yahoo_symbol)
                    ctx = tool_ctx.context_text

                    tool_chunk_ids.append(chunk_id)
                    tool_chunk_id_by_ticker[tkr] = chunk_id
                    tool_palette[chunk_id] = Citation(
                        chunk_id=chunk_id,
                        ticker=tkr,
                        doc_id=doc_id,
                        document_type="yahoo_finance",
                        fiscal_year=None,
                        filing_date=tool_ctx.as_of,
                        version=None,
                        section="Fundamentals snapshot (Yahoo Finance)",
                        page_start=None,
                        page_end=None,
                        download_endpoint=f"/documents/{doc_id}/download",
                    )
                    tool_context_by_ticker[tkr] = (
                        f"(chunk_id={chunk_id} | document_type=yahoo_finance | as_of={tool_ctx.as_of})\n"
                        f"{ctx.strip()}\n"
                    )
                except Exception as e:
                    tool_errors[tkr] = str(e)
        finally:
            tool_ms = int((time.perf_counter() - t_tool) * 1000)
            step(
                "tool_yahoo_finance",
                details={
                    "tool_ms": tool_ms,
                    "tickers": list(effective_tickers or []),
                    "ok": len(tool_chunk_ids),
                    "errors": list(tool_errors.keys()),
                },
            )
            yield _sse_event(
                event="agent_step",
                data={
                    "step": "tool_yahoo_finance",
                    "status": "done",
                    "tool_ms": tool_ms,
                    "ok": len(tool_chunk_ids),
                    "errors": list(tool_errors.keys()),
                },
            )

    # ------------------------------------------------------------------
    # retrieve (filings) — Yahoo first → filings second (per product policy)
    # ------------------------------------------------------------------
    search_req = HybridRerankRequest(
        query=req.question,
        top_k=plan.top_k,
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
        rerank_top_n=plan.rerank_top_n,
        passage_max_chars=req.passage_max_chars,
        per_ticker_k=plan.per_ticker_k,
    )

    with start_span(
        "agent.retrieval",
        endpoint="chat.stream",
        tickers_count=len(effective_tickers or []),
        doc_ids_count=len(effective_doc_ids or []),
        rerank_backend=req.rerank_backend,
        rerank_top_n=plan.rerank_top_n,
        top_k=plan.top_k,
    ):
        t = time.perf_counter()
        retrieval = hybrid_rerank_search(search_req, request=request, db=db)
        retrieval_ms = int((time.perf_counter() - t) * 1000)
    observe_stage(endpoint="chat.stream", stage="retrieval", duration_ms=retrieval_ms)
    step("retrieve", details={"retrieval_ms": retrieval_ms, "hits": len(retrieval.hits), "candidates": retrieval.candidates})
    yield _sse_event(event="agent_step", data={"step": "retrieve", "retrieval_ms": retrieval_ms, "hits": len(retrieval.hits)})

    # ------------------------------------------------------------------
    # answerability gate
    # ------------------------------------------------------------------
    if not retrieval.hits and not tool_chunk_ids:
        follow_up = (
            "I’m not seeing relevant filing evidence in the currently ingested documents for this question. "
            "Which document type should I use next (annual_report, concall, quarterly_results), or do you want to upload a specific filing to index?"
        )
        step("answerability_gate", details={"decision": "clarify", "reason": "no_hits"})
        yield _sse_event(event="agent_step", data={"step": "answerability_gate", "decision": "clarify", "reason": "no_hits"})
        step(
            "ask_clarifying_question",
            details={
                "kind": "evidence_scope",
                "reason": "no_hits",
                "options": ["annual_report", "concall", "quarterly_results"],
            },
        )
        yield _sse_event(
            event="clarify",
            data={
                "kind": "evidence_scope",
                "question": follow_up,
                "options": ["annual_report", "concall", "quarterly_results"],
            },
        )

        # Compatibility: also emit a delta so existing clients show the question.
        yield _sse_event(event="delta", data={"delta": follow_up})

        if settings.auth_enabled and auth_user and conversation_id:
            add_message(
                db,
                conversation_id=conversation_id,
                user_id=auth_user.user_id,
                role="assistant",
                content=follow_up,
            )

            # Persist a run record so the UI keeps this turn even though we didn't answer.
            try:
                add_rag_run(
                    db,
                    conversation_id=conversation_id,
                    user_id=auth_user.user_id,
                    question=req.question,
                    answer=follow_up,
                    tickers=effective_tickers,
                    doc_ids=effective_doc_ids,
                    retrieval={"agent": ledger, "retrieval": retrieval.model_dump(), "temporal": temporal_debug},
                    citations=ChatCitationsPayload(used_chunk_ids=[], citations=[]).model_dump(),
                    timings_ms={"retrieval_ms": retrieval_ms},
                    models={"chat_model": settings.openai_chat_model, "embedding_model": retrieval.embedding_model, "rerank_model": retrieval.rerank_model},
                )
            except Exception:
                pass

        inc_request(endpoint="chat.stream", status="clarify")
        yield _sse_event(event="citations", data=ChatCitationsPayload(used_chunk_ids=[], citations=[]).model_dump())
        yield _sse_event(event="done", data={"ok": True, "mode": "clarify"})
        return

    reason = "hits_present" if retrieval.hits else "tool_only"
    step("answerability_gate", details={"decision": "answer", "reason": reason})
    yield _sse_event(event="agent_step", data={"step": "answerability_gate", "decision": "answer", "reason": reason})

    # Keep ordering consistent with context: Yahoo tool chunks first → filings chunks second.
    allowed_chunk_ids = list(tool_chunk_ids) + [h.chunk_id for h in retrieval.hits]
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

    # Build model context with strict separation:
    # Yahoo Finance snapshots first → filings context second.
    context_parts: list[str] = []
    if tool_context_by_ticker:
        context_parts.append("YAHOO FINANCE SNAPSHOTS (tool outputs):")
        for tkr in sorted(tool_context_by_ticker.keys()):
            context_parts.append(f"[{tkr} YAHOO FINANCE]\n{tool_context_by_ticker[tkr].strip()}")
    if retrieval.context_blocks:
        context_parts.append("FILINGS CONTEXT (ingested documents):")
        for b in retrieval.context_blocks:
            context_parts.append((b.context or "").strip())

    # Tool palette entries overlay/extend document citations.
    palette.update(tool_palette)

    context = "\n\n".join(p for p in context_parts if p and p.strip()).strip()

    system = build_system_prompt()
    user_prompt = build_user_prompt(question=req.question, allowed_chunk_ids=allowed_chunk_ids, context=context)

    client = get_openai_client()

    meta = {
        "retrieval_ms": retrieval_ms,
        "candidates": retrieval.candidates,
        "agent": {"intent": ledger["intent"], "plan": ledger["plan"]},
    }
    if tool_ms is not None:
        meta["tools"] = {"yahoo_finance": {"tool_ms": tool_ms, "ok": len(tool_chunk_ids), "errors": list(tool_errors.keys())}}
    if temporal_debug:
        meta["temporal"] = temporal_debug
    if conversation_id:
        meta["conversation_id"] = conversation_id
    yield _sse_event(event="meta", data=meta)

    answer_parts: list[str] = []
    t_stream = time.perf_counter()
    try:
        t_gen = time.perf_counter()
        with start_span(
            "agent.openai.generate",
            model=settings.openai_chat_model,
            max_tokens=settings.openai_chat_max_tokens,
            temperature=settings.openai_chat_temperature,
        ):
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
        observe_stage(endpoint="chat.stream", stage="generation", duration_ms=gen_ms)
        answer_text = strip_unknown_citations(text=answer_text, allowed_chunk_ids=allowed_set)

        with start_span("agent.citations.extract", endpoint="chat.stream"):
            used = list(dict.fromkeys(extract_chunk_ids(answer_text)))
            used = [cid for cid in used if cid in allowed_set]

        citations = [palette[cid] for cid in used if cid in palette]
        payload = ChatCitationsPayload(used_chunk_ids=used, citations=citations)
        observe_citations(endpoint="chat.stream", count=len(citations))

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
                retrieval={"agent": ledger, "retrieval": retrieval.model_dump(), "temporal": temporal_debug},
                citations=payload.model_dump(),
                timings_ms={**(retrieval.timings_ms or {}), "retrieval_ms": retrieval_ms, "generation_ms": gen_ms},
                models={
                    "chat_model": settings.openai_chat_model,
                    "embedding_model": retrieval.embedding_model,
                    "rerank_model": retrieval.rerank_model,
                },
            )

        try:
            log_audit(
                db,
                action="agent.chat.stream",
                request=request,
                user_id=getattr(auth_user, "user_id", None),
                status_code=200,
                details={
                    "conversation_id": conversation_id,
                    "tickers": effective_tickers,
                    "doc_ids": effective_doc_ids,
                    "used_chunk_ids": used,
                    "retrieval_ms": retrieval_ms,
                    "generation_ms": gen_ms,
                    "agent_intent": ledger["intent"],
                    "agent_plan": ledger["plan"],
                },
            )
        except Exception:
            pass

        observe_stage(endpoint="chat.stream", stage="total", duration_ms=int((time.perf_counter() - t_stream) * 1000))
        inc_request(endpoint="chat.stream", status="ok")
        yield _sse_event(event="citations", data=payload.model_dump())
        yield _sse_event(event="done", data={"ok": True})
    except Exception as e:
        try:
            log_audit(
                db,
                action="agent.chat.stream_error",
                request=request,
                user_id=getattr(auth_user, "user_id", None),
                status_code=500,
                details={
                    "conversation_id": conversation_id,
                    "tickers": effective_tickers,
                    "doc_ids": effective_doc_ids,
                    "error": str(e),
                },
            )
        except Exception:
            pass

        inc_request(endpoint="chat.stream", status="error")
        yield _sse_event(event="error", data={"error": str(e)})


def validate_agent_enabled() -> None:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=422,
            detail="Missing OpenAI API key. Set OPENAI_API_KEY (or TICKERLENS_OPENAI_API_KEY).",
        )
