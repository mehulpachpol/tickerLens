from __future__ import annotations

import re
from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from tickerlens_api.settings import settings


@dataclass(frozen=True)
class VectorStoreConfig:
    url: str
    collection: str
    vector_size: int


_COLLECTION_SAFE_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _safe_collection_name(value: str) -> str:
    value = _COLLECTION_SAFE_RE.sub("_", value)
    return value[:200]


def compute_vector_size(*, model: str, dimensions: int | None) -> int:
    if dimensions is not None:
        return dimensions
    # Defaults documented for v3 embedding models.
    if model == "text-embedding-3-small":
        return 1536
    if model == "text-embedding-3-large":
        return 3072
    # Fallback: require explicit dimensions for unknown models to avoid creating a wrong collection.
    raise ValueError(f"Unknown embedding model '{model}'. Set TICKERLENS_OPENAI_EMBEDDING_DIMENSIONS explicitly.")


def compute_collection_name(*, model: str, vector_size: int) -> str:
    base = f"{settings.qdrant_collection_prefix}__{model}__{vector_size}"
    return _safe_collection_name(base)


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)


def ensure_collection(*, collection_name: str, vector_size: int) -> None:
    client = get_qdrant_client()
    if client.collection_exists(collection_name=collection_name):
        return
    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
    )


def upsert_points(
    *,
    collection_name: str,
    points: list[models.PointStruct],
) -> None:
    client = get_qdrant_client()
    client.upsert(collection_name=collection_name, points=points)


def search(
    *,
    collection_name: str,
    query_vector: list[float],
    query_filter: models.Filter | None,
    limit: int,
) -> list[models.ScoredPoint]:
    client = get_qdrant_client()
    resp = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    )
    return list(resp.points)
