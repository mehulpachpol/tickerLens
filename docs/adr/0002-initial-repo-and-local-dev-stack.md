# 0002 — Initial repo structure and local dev stack

## Context

TickerLens will grow into multiple components (API, UI, ingestion workers, indexing workers, shared libraries,
and infrastructure). We need a layout that supports iterative development and keeps local setup simple.

## Decision

- Use a **monorepo** with top-level areas:
  - `apps/` for user-facing services (API/UI)
  - `services/` for background workers (ingestion/indexing)
  - `infra/compose/` for local infrastructure via Docker Compose
  - `docs/adr/` for architectural decisions
- Start the backend with **FastAPI** (Python) and a minimal `/health` + `/version` surface.
- Use a local, fully open-source stack in Docker Compose:
  - PostgreSQL (metadata)
  - MinIO (raw docs)
  - Qdrant (vector search)
  - OpenSearch (BM25/keyword search)
  - Redis (cache/queues later)

## Consequences

- The repo stays organized as new services are added without a restructure.
- Docker Compose provides a predictable dev environment and reduces “works on my machine” issues.
- We accept that OpenSearch and its JVM footprint is heavier; we keep it in Compose because hybrid search is a core
  requirement and we want to validate it early.

