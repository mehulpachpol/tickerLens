# TickerLens

TickerLens is a production-oriented **Stock Intelligence RAG Platform** focused on **NSE multi-ticker conversational financial intelligence**.

It is designed to answer analyst-style questions over primary-source documents (annual reports, filings, concalls, presentations) with:

- High retrieval accuracy (hybrid search + reranking)
- Auditability (raw → parse → chunk → index/embed → retrieval outputs)
- Temporal correctness (“latest” means latest by filing date, not model memory)
- Strict grounding (later phases add constrained generation + citations)

## Current status

Implemented and working locally:

- Manual pipeline: upload → parse → chunk → index/embed
- Vector search (Qdrant + OpenAI embeddings)
- BM25 keyword search (OpenSearch)
- Hybrid search (RRF fusion of BM25 + vector)
- Hybrid + rerank with multi-ticker context packaging
  - Default reranker is local cross-encoder (FastEmbed / ONNX) for low latency after warmup
  - Optional OpenAI reranker backend is supported for experimentation

## Architecture (local dev)

```
Next.js (planned) ──> FastAPI (apps/api)
                         │
                         ├─ Postgres (metadata + extracted text + chunks)
                         ├─ MinIO (raw PDFs and artifacts)
                         ├─ Qdrant (vector search)
                         ├─ OpenSearch (BM25 keyword search)
                         └─ Redis (reserved for caching/queues in later phases)
```

## Repository layout

- `apps/api` — FastAPI backend (document pipeline + search APIs)
- `apps/web` — frontend placeholder (Next.js planned)
- `infra/compose` — local Docker stack (Postgres / MinIO / Qdrant / OpenSearch / Redis)
- `services/ingestion` — ingestion worker placeholder (planned)
- `services/indexing` — indexing worker placeholder (planned)

Note: `docs/adr/` is intentionally gitignored for local-only notes.

## Local development (Docker Compose)

Prereqs: Docker Desktop + PowerShell.

1. Create env file (the script will auto-create it if missing):
   - `Copy-Item infra/compose/.env.example infra/compose/.env`
2. Start stack:
   - `.\scripts\dev.ps1 up`
3. Verify API:
   - `http://localhost:8000/health`
   - `http://localhost:8000/version`

Useful helpers:

- `.\scripts\dev.ps1 ps`
- `.\scripts\dev.ps1 logs`
- `.\scripts\dev.ps1 api` (rebuild/restart API only)

## Configuration

Edit `infra/compose/.env` (never commit secrets).

- `OPENAI_API_KEY` is required for:
  - embedding generation (`POST /documents/{doc_id}/embed`)
  - vector search (`POST /search/vector`)
  - hybrid search (vector side)
- Reranking backend (Phase 7):
  - `TICKERLENS_RERANK_BACKEND=fastembed|openai`
  - `TICKERLENS_FASTEMBED_RERANK_MODEL` (default: `Xenova/ms-marco-MiniLM-L-6-v2`)
  - `TICKERLENS_FASTEMBED_RERANK_BATCH_SIZE` (default: `32`)

## Core workflows

### 1) Manual document pipeline

1. Upload: `POST /documents/upload`
2. Parse (extract text / OCR as needed): `POST /documents/{doc_id}/parse`
3. Chunk: `POST /documents/{doc_id}/chunk`
4. Index into OpenSearch (BM25): `POST /documents/{doc_id}/index`
5. Embed + upsert into Qdrant: `POST /documents/{doc_id}/embed`

### 2) Retrieval APIs

- Vector only: `POST /search/vector`
- BM25 only: `POST /search/bm25`
- Hybrid (BM25 + vector + RRF): `POST /search/hybrid`
- Hybrid + rerank + per-ticker context blocks: `POST /search/hybrid_rerank`
  - Returns `timings_ms` so you can debug latency (embed vs retrieval vs rerank).

For a full endpoint list, see `apps/api/README.md`.
OpenAPI/Swagger is available at `http://localhost:8000/docs` when the API is running.

## Performance notes (Phase 7 reranking)

- `fastembed` reranking is designed for low latency after warmup.
  - First request may be slow due to model download; the cache is persisted via a Docker volume.
- `openai` reranking is supported but can be multi-second because the model must read N passages.
  - Use smaller `rerank_top_n` and `passage_max_chars` if you choose this backend.

## Troubleshooting

- Qdrant 404s: ensure Qdrant server version matches the client expectations (Compose runs `qdrant/qdrant:v1.18.0`).
- Slow first rerank call: model download/warmup; subsequent calls should be fast with `fastembed`.

## Roadmap

Planned major capabilities:

- Constrained answer generation + citation engine (chat endpoint)
- Temporal reasoning (“latest” correctness) + incremental updates/versioning
- Automated daily NSE ingestion (start Nifty 50 → expand to full universe)
