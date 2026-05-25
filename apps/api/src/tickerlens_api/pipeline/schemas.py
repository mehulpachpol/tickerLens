from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


PipelineGoal = Literal["parse", "chunk", "embed", "index", "searchable"]


class ProcessDocumentRequest(BaseModel):
    """
    Phase 9: Incremental processing orchestrator.

    Goal semantics:
    - parse: ensure a successful parse run exists
    - chunk: parse + chunk
    - embed: parse + chunk + vector embedding (Qdrant)
    - index: parse + chunk + BM25 indexing (OpenSearch)
    - searchable: parse + chunk + embed + index (default for hybrid retrieval)
    """

    goal: PipelineGoal = Field(default="searchable")

    # Force re-run of stages even if a successful run exists.
    force_parse: bool = Field(default=False)
    force_chunk: bool = Field(default=False)
    force_embed: bool = Field(default=False)
    force_index: bool = Field(default=False)

    # Chunking parameters (must match chunking endpoint constraints)
    max_chunk_chars: int = Field(default=5000, ge=500, le=20000)
    overlap_chars: int = Field(default=250, ge=0, le=2000)
    max_block_chars: int = Field(default=1200, ge=200, le=5000)

    # Embedding parameters (OpenAI)
    embedding_model: str | None = None
    dimensions: int | None = Field(default=None, ge=64, le=8192)

    # Indexing parameters (OpenSearch)
    index_version: str = Field(default="v1", min_length=1, max_length=20)


class StageRef(BaseModel):
    stage: str
    run_id: str
    status: str
    action: str


class ProcessDocumentResponse(BaseModel):
    doc_id: str
    goal: PipelineGoal

    parse: StageRef | None = None
    chunk: StageRef | None = None
    embed: StageRef | None = None
    index: StageRef | None = None

    embedding_target: dict | None = None
    index_target: dict | None = None

