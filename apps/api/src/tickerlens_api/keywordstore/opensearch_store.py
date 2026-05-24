from __future__ import annotations

import re
from dataclasses import dataclass

from opensearchpy import OpenSearch

from tickerlens_api.settings import settings


@dataclass(frozen=True)
class OpenSearchConfig:
    url: str
    chunks_index: str


_INDEX_SAFE_RE = re.compile(r"[^a-z0-9._-]+")


def _safe_index_name(value: str) -> str:
    value = value.lower()
    value = _INDEX_SAFE_RE.sub("_", value)
    return value[:255]


def compute_chunks_index_name(*, version: str = "v1") -> str:
    # Index name is part of the contract; include an explicit version so we can reindex safely later.
    return _safe_index_name(f"{settings.opensearch_chunks_index_prefix}__{version}")


def get_opensearch_client() -> OpenSearch:
    # Security is disabled in our local docker-compose OpenSearch.
    return OpenSearch(hosts=[settings.opensearch_url], http_compress=True)


def ensure_chunks_index(*, index_name: str) -> None:
    client = get_opensearch_client()
    if client.indices.exists(index=index_name):
        return

    body = {
        "settings": {"index": {"number_of_shards": 1, "number_of_replicas": 0}},
        "mappings": {
            "properties": {
                "chunk_id": {"type": "keyword"},
                "doc_id": {"type": "keyword"},
                "parse_run_id": {"type": "keyword"},
                "chunk_run_id": {"type": "keyword"},
                "ticker": {"type": "keyword"},
                "document_type": {"type": "keyword"},
                "fiscal_year": {"type": "keyword"},
                "filing_date": {"type": "date"},
                "version": {"type": "integer"},
                "section": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "page_start": {"type": "integer"},
                "page_end": {"type": "integer"},
                "text": {"type": "text"},
            }
        },
    }
    client.indices.create(index=index_name, body=body)

