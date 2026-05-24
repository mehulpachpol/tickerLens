from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class ChunkRunOut(BaseModel):
    run_id: str
    doc_id: str
    parse_run_id: str
    status: str
    chunker_version: str
    max_chunk_chars: int
    overlap_chars: int
    max_block_chars: int
    started_at: dt.datetime | None
    finished_at: dt.datetime | None
    chunk_count: int | None
    error_message: str | None
    created_at: dt.datetime


class ChunkPreviewOut(BaseModel):
    chunk_id: str
    doc_id: str
    chunk_run_id: str
    parse_run_id: str
    ticker: str
    section: str | None
    page_start: int
    page_end: int
    char_count: int
    checksum: str
    preview: str


class ChunkSpanOut(BaseModel):
    page_num: int
    char_start: int
    char_end: int


class ChunkOut(BaseModel):
    chunk_id: str
    doc_id: str
    chunk_run_id: str
    parse_run_id: str
    ticker: str
    section: str | None
    page_start: int
    page_end: int
    char_count: int
    checksum: str
    text: str
    spans: list[ChunkSpanOut]

