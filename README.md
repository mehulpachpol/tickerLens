# TickerLens

Stock Intelligence RAG Platform (NSE multi‑ticker conversational financial intelligence).

## Goals

- High retrieval accuracy and low hallucination rate
- Citation-backed answers (doc + page + chunk id)
- Temporal correctness (“latest” means latest by filing date)
- Auditable lineage from raw docs → parsing → chunks → indexes → answers

The execution plan lives in `tasks.md`.

## Repo layout (current)

- `apps/api` — FastAPI backend (health/version endpoints now; RAG APIs later)
- `apps/web` — frontend placeholder (Next.js planned)
- `services/ingestion` — ingestion workers (planned)
- `services/indexing` — chunking/embedding/indexing workers (planned)
- `infra/compose` — local Docker services (Postgres/MinIO/Qdrant/OpenSearch/Redis)
- `docs/adr` — local-only Architecture Decision Records (gitignored)

## Local dev (Docker)

1. (Optional) Create an env file (the dev script will auto-create it if missing):
   - `Copy-Item infra/compose/.env.example infra/compose/.env`
2. Start services:
   - `.\scripts\dev.ps1 up`
3. Check API:
   - `http://localhost:8000/health`
   - `http://localhost:8000/version`

## Why ADRs?

This project has many “reasonable” choices (vector DB, chunking strategy, ingestion approach, schedulers, etc.).
We capture decisions in `docs/adr/` so future changes are intentional and traceable.
