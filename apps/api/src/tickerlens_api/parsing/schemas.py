from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class ParseRunOut(BaseModel):
    run_id: str
    doc_id: str
    status: str
    parser_version: str
    started_at: dt.datetime | None
    finished_at: dt.datetime | None
    page_count: int | None
    ocr_page_count: int | None
    error_message: str | None
    created_at: dt.datetime


class PagePreviewOut(BaseModel):
    doc_id: str
    run_id: str
    page_num: int
    extraction_method: str
    char_count: int
    checksum: str
    preview: str


class PageOut(BaseModel):
    doc_id: str
    run_id: str
    page_num: int
    extraction_method: str
    char_count: int
    checksum: str
    text: str

