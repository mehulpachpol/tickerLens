# TickerLens

Stock Intelligence RAG Platform (NSE multi‑ticker conversational financial intelligence).

## Goals

- High retrieval accuracy and low hallucination rate
- Citation-backed answers (doc + page + chunk id)
- Temporal correctness (“latest” means latest by filing date)
- Auditable lineage from raw docs → parsing → chunks → indexes → answers


## Repo layout (current)

- `apps/api` — FastAPI backend (health/version endpoints now; RAG APIs later)
- `apps/web` — frontend placeholder (Next.js planned)
- `services/ingestion` — ingestion workers (planned)
- `services/indexing` — chunking/embedding/indexing workers (planned)
- `infra/compose` — local Docker services (Postgres/MinIO/Qdrant/OpenSearch/Redis)

## Local dev (Docker)

1. (Optional) Create an env file (the dev script will auto-create it if missing):
   - `Copy-Item infra/compose/.env.example infra/compose/.env`
2. Start services:
   - `.\scripts\dev.ps1 up`
3. Check API:
   - `http://localhost:8000/health`
   - `http://localhost:8000/version`

