from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from tickerlens_api.settings import settings


@dataclass(frozen=True)
class EmbeddingConfig:
    model: str
    dimensions: int | None


def get_embedding_config() -> EmbeddingConfig:
    return EmbeddingConfig(model=settings.openai_embedding_model, dimensions=settings.openai_embedding_dimensions)


def get_openai_client() -> OpenAI:
    # The OpenAI SDK also supports OPENAI_API_KEY via env var; we validate via settings for clearer errors.
    if not settings.openai_api_key:
        raise RuntimeError("Missing OpenAI API key. Set OPENAI_API_KEY (or TICKERLENS_OPENAI_API_KEY).")
    return OpenAI(api_key=settings.openai_api_key)


def embed_texts(*, texts: list[str], model: str, dimensions: int | None) -> list[list[float]]:
    """
    Returns one embedding vector per input text.
    """

    client = get_openai_client()
    kwargs: dict = {"model": model, "input": texts, "encoding_format": "float"}
    if dimensions is not None:
        kwargs["dimensions"] = dimensions
    resp = client.embeddings.create(**kwargs)
    # Keep ordering stable: API returns embeddings with an index field.
    data = sorted(resp.data, key=lambda d: d.index)
    return [d.embedding for d in data]
