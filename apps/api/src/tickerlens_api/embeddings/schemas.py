from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class EmbeddingRunOut(BaseModel):
    run_id: str
    doc_id: str
    parse_run_id: str
    chunk_run_id: str
    status: str
    embedding_model: str
    dimensions: int | None
    vector_size: int
    qdrant_collection: str
    started_at: dt.datetime | None
    finished_at: dt.datetime | None
    embedded_chunks: int | None
    error_message: str | None
    created_at: dt.datetime

