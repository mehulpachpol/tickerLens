from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


class ConversationOut(BaseModel):
    conversation_id: str
    title: str | None
    tickers: list[str] = Field(default_factory=list)
    created_at: dt.datetime
    updated_at: dt.datetime


class CreateConversationRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    tickers: list[str] = Field(default_factory=list, description="Conversation ticker scope (e.g. ['INFY','TCS']).")


class UpdateConversationRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    tickers: list[str] | None = Field(default=None, description="If provided, replaces the conversation ticker scope.")


class MessageOut(BaseModel):
    message_id: str
    conversation_id: str
    role: str
    content: str
    created_at: dt.datetime


class RagRunOut(BaseModel):
    run_id: str
    conversation_id: str
    question: str
    answer: str | None = None
    created_at: dt.datetime

    tickers: list[str] | None = None
    doc_ids: list[str] | None = None

    retrieval: dict | None = None
    citations: dict | None = None
    timings_ms: dict | None = None
    models: dict | None = None
