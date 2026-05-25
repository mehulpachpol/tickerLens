from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


class DocumentFileOut(BaseModel):
    bucket: str
    object_key: str
    content_type: str | None
    size_bytes: int
    checksum: str


class DocumentOut(BaseModel):
    doc_id: str
    ticker: str
    company_name: str | None
    document_type: str
    fiscal_year: str | None
    filing_date: dt.date | None
    source_url: str | None
    checksum: str
    version: int


class UploadDocumentResponse(BaseModel):
    document: DocumentOut
    file: DocumentFileOut
    deduplicated: bool = Field(
        default=False, description="True if an identical document already existed and was returned."
    )


class DownloadLinkResponse(BaseModel):
    doc_id: str
    url: str
    expires_in_seconds: int


class DocumentListItem(BaseModel):
    doc_id: str
    ticker: str
    company_name: str | None
    document_type: str
    fiscal_year: str | None
    filing_date: dt.date | None
    source_url: str | None
    checksum: str
    version: int
    created_at: dt.datetime
    updated_at: dt.datetime

