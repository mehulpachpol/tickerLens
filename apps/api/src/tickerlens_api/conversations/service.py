from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from tickerlens_api.db.models import Conversation, ConversationMessage, RagRun


UNSET: object = object()


def create_conversation(
    db: Session,
    *,
    user_id: str,
    title: str | None,
    tickers: list[str] | None = None,
) -> Conversation:
    c = Conversation(conversation_id=str(uuid.uuid4()), user_id=user_id, title=title, tickers=tickers or [])
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def get_conversation(db: Session, *, conversation_id: str, user_id: str) -> Conversation | None:
    c = db.get(Conversation, conversation_id)
    if not c:
        return None
    return c if c.user_id == user_id else None


def list_conversations(
    db: Session,
    *,
    user_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[Conversation]:
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def touch_conversation(db: Session, *, conversation_id: str) -> None:
    c = db.get(Conversation, conversation_id)
    if not c:
        return
    c.updated_at = dt.datetime.now(dt.timezone.utc)
    db.commit()


def update_conversation(
    db: Session,
    *,
    conversation_id: str,
    user_id: str,
    title: str | None | object = UNSET,
    tickers: list[str] | None | object = UNSET,
) -> Conversation | None:
    c = get_conversation(db, conversation_id=conversation_id, user_id=user_id)
    if not c:
        return None

    changed = False
    if title is not UNSET:
        c.title = title
        changed = True
    if tickers is not UNSET:
        c.tickers = tickers or []
        changed = True

    if changed:
        db.commit()
        db.refresh(c)
    return c


def delete_conversation(db: Session, *, conversation_id: str, user_id: str) -> bool:
    c = get_conversation(db, conversation_id=conversation_id, user_id=user_id)
    if not c:
        return False
    db.delete(c)
    db.commit()
    return True


def add_message(
    db: Session,
    *,
    conversation_id: str,
    user_id: str,
    role: str,
    content: str,
) -> ConversationMessage:
    m = ConversationMessage(
        message_id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        user_id=user_id,
        role=role,
        content=content,
    )
    db.add(m)
    db.commit()
    db.refresh(m)

    # Best-effort: update conversation updated_at for list sorting.
    try:
        touch_conversation(db, conversation_id=conversation_id)
    except Exception:
        db.rollback()

    return m


def list_messages(
    db: Session,
    *,
    conversation_id: str,
    user_id: str,
    limit: int = 200,
    offset: int = 0,
) -> list[ConversationMessage]:
    stmt = (
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .where(ConversationMessage.user_id == user_id)
        .order_by(ConversationMessage.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def add_rag_run(
    db: Session,
    *,
    conversation_id: str,
    user_id: str,
    question: str,
    answer: str,
    tickers: list[str] | None,
    doc_ids: list[str] | None,
    retrieval: dict | None,
    citations: dict | None,
    timings_ms: dict | None,
    models: dict | None,
) -> RagRun:
    r = RagRun(
        run_id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        user_id=user_id,
        question=question,
        answer=answer,
        tickers=tickers,
        doc_ids=doc_ids,
        retrieval=retrieval,
        citations=citations,
        timings_ms=timings_ms,
        models=models,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def list_rag_runs(
    db: Session,
    *,
    conversation_id: str,
    user_id: str,
    limit: int = 100,
    offset: int = 0,
) -> list[RagRun]:
    stmt = (
        select(RagRun)
        .where(RagRun.conversation_id == conversation_id)
        .where(RagRun.user_id == user_id)
        .order_by(RagRun.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())
