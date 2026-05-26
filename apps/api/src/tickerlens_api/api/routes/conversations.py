from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from tickerlens_api.auth.dependencies import get_current_user
from tickerlens_api.conversations.schemas import (
    ConversationOut,
    CreateConversationRequest,
    MessageOut,
    RagRunOut,
    UpdateConversationRequest,
)
from tickerlens_api.conversations.service import (
    UNSET,
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
    list_messages,
    list_rag_runs,
    update_conversation,
)
from tickerlens_api.db.session import get_db


router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationOut)
def create(
    req: CreateConversationRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationOut:
    c = create_conversation(db, user_id=user.user_id, title=req.title, tickers=req.tickers)
    return ConversationOut(
        conversation_id=c.conversation_id,
        title=c.title,
        tickers=list(c.tickers or []),
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("", response_model=list[ConversationOut])
def list_(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=1000000),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConversationOut]:
    rows = list_conversations(db, user_id=user.user_id, limit=limit, offset=offset)
    return [
        ConversationOut(
            conversation_id=c.conversation_id,
            title=c.title,
            tickers=list(c.tickers or []),
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in rows
    ]


@router.get("/{conversation_id}", response_model=ConversationOut)
def get_(
    conversation_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationOut:
    c = get_conversation(db, conversation_id=conversation_id, user_id=user.user_id)
    if not c:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationOut(
        conversation_id=c.conversation_id,
        title=c.title,
        tickers=list(c.tickers or []),
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.patch("/{conversation_id}", response_model=ConversationOut)
def patch_(
    conversation_id: str,
    req: UpdateConversationRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationOut:
    data = req.model_dump(exclude_unset=True)
    c = update_conversation(
        db,
        conversation_id=conversation_id,
        user_id=user.user_id,
        title=data["title"] if "title" in data else UNSET,
        tickers=data["tickers"] if "tickers" in data else UNSET,
    )
    if not c:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationOut(
        conversation_id=c.conversation_id,
        title=c.title,
        tickers=list(c.tickers or []),
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.delete("/{conversation_id}")
def delete_(
    conversation_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    ok = delete_conversation(db, conversation_id=conversation_id, user_id=user.user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"ok": True}


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def messages(
    conversation_id: str,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=1000000),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MessageOut]:
    c = get_conversation(db, conversation_id=conversation_id, user_id=user.user_id)
    if not c:
        raise HTTPException(status_code=404, detail="Conversation not found")

    rows = list_messages(db, conversation_id=conversation_id, user_id=user.user_id, limit=limit, offset=offset)
    return [
        MessageOut(
            message_id=m.message_id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
        )
        for m in rows
    ]


@router.get("/{conversation_id}/runs", response_model=list[RagRunOut])
def rag_runs(
    conversation_id: str,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=1000000),
    include_payloads: bool = Query(default=False, description="If true, returns retrieval/citations payloads (bigger)."),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RagRunOut]:
    c = get_conversation(db, conversation_id=conversation_id, user_id=user.user_id)
    if not c:
        raise HTTPException(status_code=404, detail="Conversation not found")

    rows = list_rag_runs(db, conversation_id=conversation_id, user_id=user.user_id, limit=limit, offset=offset)
    out: list[RagRunOut] = []
    for r in rows:
        out.append(
            RagRunOut(
                run_id=r.run_id,
                conversation_id=r.conversation_id,
                question=r.question,
                answer=r.answer,
                created_at=r.created_at,
                tickers=r.tickers,
                doc_ids=r.doc_ids,
                retrieval=r.retrieval if include_payloads else None,
                citations=r.citations if include_payloads else None,
                timings_ms=r.timings_ms if include_payloads else None,
                models=r.models if include_payloads else None,
            )
        )
    return out
