# TickerLens

TickerLens is a production-oriented **Stock Intelligence RAG Platform** focused on **NSE multi-ticker conversational financial intelligence**.

It is designed to answer analyst-style questions over primary-source documents (annual reports, filings, concalls, presentations) with:

- High retrieval accuracy (hybrid search + reranking)
- Auditability (raw -> parse -> chunk -> index/embed -> retrieval outputs)
- Temporal correctness ("latest" means latest by filing date, not model memory)
- Strict grounding (answers are generated only from retrieved context + citations)

## Current status

Implemented and working locally:

- Manual pipeline: upload -> parse -> chunk -> index/embed
- Retrieval: vector search (Qdrant) + BM25 (OpenSearch) + hybrid (RRF fusion)
- Reranked retrieval + multi-ticker context blocks (FastEmbed cross-encoder; optional OpenAI rerank backend)
- Streaming chat endpoint (SSE) with inline citations in the format `[(chunk_id=<id>)]`
- Next.js UI with streaming chat + citation panel + timeline viewer (port 3010)
- Phase 9 (partial): "latest" temporal scoping for hybrid retrieval + incremental `/documents/{doc_id}/process` orchestrator
- Timeline building blocks: `GET /tickers/{ticker}/documents` + `GET /documents/{doc_id}/versions`
- Phase 10 (v1): daily NSE ingestion for `NIFTY_50` (discovery + download/dedupe + raw storage) + APScheduler service
- Phase 11 (v1): optional session auth (cookie) + RBAC, per-user conversation + RAG run persistence, Prometheus metrics endpoint

## Architecture (local dev)

```
Next.js UI (apps/web) --> Next.js Route Handlers (/api/* proxy)
                               |
                               v
                         FastAPI (apps/api)
                               |
  +----------------------------+----------------------------+
  |                            |                            |
  v                            v                            v
Postgres                    Qdrant                      OpenSearch
(metadata, text, chunks)    (vector search)             (BM25 keyword search)
  |
  v
MinIO (raw PDFs and artifacts)

Ingestion scheduler (infra/compose: ingestion_scheduler) -> FastAPI DB/MinIO pipeline
```

## Repository layout

- `apps/api` - FastAPI backend (document pipeline + retrieval + chat APIs)
- `apps/web` - Next.js UI (App Router + Tailwind), runs on `http://localhost:3010`
- `infra/compose` - local Docker stack (Postgres / MinIO / Qdrant / OpenSearch / Redis)
- `services/ingestion` - ingestion worker placeholder (planned)
- `services/indexing` - indexing worker placeholder (planned)

Note: `docs/adr/` is intentionally gitignored for local-only notes.

## Local development

Prereqs:
- Docker Desktop
- PowerShell
- Node.js >= 20.9 (for the UI)

### 1) Start the backend stack

1. Create env file (the dev script will auto-create it if missing):
   - `Copy-Item infra/compose/.env.example infra/compose/.env`
2. Start services:
   - `.\scripts\dev.ps1 up`
3. Verify API:
   - `http://localhost:8000/health`
   - `http://localhost:8000/version`
   - Swagger/OpenAPI: `http://localhost:8000/docs`

### 2) Start the UI (port 3010)

```powershell
cd apps/web
Copy-Item .env.example .env -ErrorAction SilentlyContinue
npm install
npm run dev
```

Open: `http://localhost:3010`

## Configuration

Edit `infra/compose/.env` (never commit secrets).

- `OPENAI_API_KEY` is required for:
  - embeddings (`POST /documents/{doc_id}/embed`)
  - vector/hybrid search (`POST /search/vector`, `POST /search/hybrid`, `POST /search/hybrid_rerank`)
  - chat generation (`POST /chat/stream`)
- Reranking backend:
  - `TICKERLENS_RERANK_BACKEND=fastembed|openai`

The UI uses a proxy to the backend:

- `POST /api/chat/stream` -> FastAPI `POST /chat/stream` (SSE)
  - `GET /api/documents/:docId/download` -> FastAPI `GET /documents/:docId/download`

### Phase 11: auth (optional)

Auth is recommended for any real usage. It’s enabled in `infra/compose/.env.example`; configure in `infra/compose/.env` (and restart the API):

- `TICKERLENS_AUTH_ENABLED=true`
- `TICKERLENS_AUTH_ALLOW_REGISTER=true` (dev convenience; disable in production if needed)
- `TICKERLENS_AUTH_BOOTSTRAP_ADMIN_EMAIL=admin@local`
- `TICKERLENS_AUTH_BOOTSTRAP_ADMIN_PASSWORD=...`

When auth is enabled:
- `/search/*`, `/tickers/*`, `/documents/*` require an authenticated user
- ingestion + processing endpoints require `role=admin`
- `/conversations/*` is used for user chat history and RAG run inspection

## Core workflows

### 1) Manual document pipeline

1. Upload: `POST /documents/upload`
2. Parse: `POST /documents/{doc_id}/parse`
3. Chunk: `POST /documents/{doc_id}/chunk`
4. Index (BM25): `POST /documents/{doc_id}/index`
5. Embed (vector): `POST /documents/{doc_id}/embed`

### 2) Retrieval APIs

- Vector only: `POST /search/vector`
- BM25 only: `POST /search/bm25`
- Hybrid: `POST /search/hybrid`
- Hybrid + rerank: `POST /search/hybrid_rerank` (returns `timings_ms`)

### 3) Chat (streaming)

- Streaming SSE chat: `POST /chat/stream`
  - `event: delta` - incremental answer text
  - `event: citations` - final citations payload (chunk_id -> doc/page metadata)
  - `event: done`

### 4) Automated NSE ingestion (Phase 10 v1)

This runs **daily** via the `ingestion_scheduler` compose service (APScheduler, IST timezone). It discovers NSE corporate announcement attachments and ingests raw PDFs into MinIO + `documents` in Postgres (dedupe + versioning).

Key endpoints:

1. Seed universe (idempotent):
   - `POST /ingestion/universes/nifty50/seed`
2. Discover attachments:
   - `POST /ingestion/nse/discover`
3. Download + ingest discovered items:
   - `POST /ingestion/nse/ingest`
4. Convenience (discover + ingest):
   - `POST /ingestion/nse/sync`
5. Ops views:
   - `GET /ingestion/discovered`
   - `GET /ingestion/runs`

Config is in `infra/compose/.env` (see Phase 10 keys in `infra/compose/.env.example`).

## Roadmap

Planned major capabilities:

- Phase 9 completion: timeline UI + stronger incremental/version audit tooling
- Automated daily NSE ingestion (start Nifty 50 -> expand to full universe)
- Authentication + server-side conversation tracking (Phase 11)
