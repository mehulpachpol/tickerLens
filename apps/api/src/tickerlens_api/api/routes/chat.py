from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from tickerlens_api.agent.controller import run_agent_stream, validate_agent_enabled
from tickerlens_api.auth.dependencies import get_current_user_optional
from tickerlens_api.chat.schemas import ChatStreamRequest
from tickerlens_api.conversations.service import add_message, create_conversation, get_conversation, update_conversation
from tickerlens_api.db.session import get_db
from tickerlens_api.security.limits import rate_limit_request
from tickerlens_api.settings import settings


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/stream")
def chat_stream(
    req: ChatStreamRequest,
    request: Request,
    db: Session = Depends(get_db),
    auth_user=Depends(get_current_user_optional),
) -> StreamingResponse:
    """
    Phase 12.1: Agentic chat controller + constrained generation with citations + SSE streaming.

    Streaming protocol:
    - event: delta      data: {"delta":"..."}
    - event: agent_step data: {"step":"...", ...}  (optional UI transparency)
    - event: clarify    data: {"kind":"...", "question":"...", "options":[...]} (optional)
    - event: citations  data: {"used_chunk_ids":[...], "citations":[...]}
    - event: done       data: {"ok":true}
    """

    validate_agent_enabled()

    # Phase 11.3: cost-protection. Fail-open if Redis isn't available.
    # Apply before auth checks so unauthenticated abuse is also throttled by IP.
    rate_limit_request(request=request, prefix="chat:stream", limit=settings.rl_chat_per_minute, window_s=60)

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

    return StreamingResponse(
        run_agent_stream(
            req,
            request=request,
            db=db,
            auth_user=auth_user,
            conversation_id=conversation_id,
            effective_tickers=effective_tickers,
            effective_doc_ids=req.doc_ids,
            temporal_debug=None,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

