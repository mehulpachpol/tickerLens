from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class IndexRunOut(BaseModel):
    run_id: str
    doc_id: str
    parse_run_id: str
    chunk_run_id: str
    status: str
    backend: str
    index_name: str
    started_at: dt.datetime | None
    finished_at: dt.datetime | None
    indexed_chunks: int | None
    error_message: str | None
    created_at: dt.datetime

