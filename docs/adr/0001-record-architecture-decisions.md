# 0001 — Record architecture decisions

## Context

TickerLens is a production-style RAG system with many long-lived design choices (ingestion, parsing, chunking,
indexing, retrieval, reranking, citation mapping, observability). Without a record of decisions, the codebase
accumulates “tribal knowledge” and later changes become risky.

## Decision

We will keep **Architecture Decision Records (ADRs)** in `docs/adr/` using a simple format:

- `NNNN-short-title.md` filenames
- Sections: **Context / Decision / Consequences**
- Each ADR describes:
  - the problem being solved
  - the option chosen (and notable alternatives)
  - the tradeoffs we accept

## Consequences

- Design discussions become easier because past decisions are visible.
- Future refactors have a clear starting point: what we intended and why.
- ADRs must be kept short and updated when a decision is superseded (add a new ADR).

