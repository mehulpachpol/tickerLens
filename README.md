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

## OpenAI (Phase 5 embeddings/search)

Set `OPENAI_API_KEY` in `infra/compose/.env` before running embedding or vector search endpoints.

## OpenSearch (Phase 6 BM25/hybrid)

Hybrid retrieval requires BM25 indexing in OpenSearch:

- Index a document's chunks: `POST /documents/{doc_id}/index`
- Search: `POST /search/bm25` or `POST /search/hybrid`

## Reranking (Phase 7)

- Reranked hybrid search: `POST /search/hybrid_rerank`
- Default reranker is local cross-encoder (FastEmbed). Override via:
  - env: `TICKERLENS_RERANK_BACKEND=openai|fastembed`
  - request: set `rerank_backend` and/or `rerank_model`

## Troubleshooting

- If vector search errors with Qdrant 404s, ensure the Qdrant **server** version matches the `qdrant-client` version (we run `qdrant/qdrant:v1.18.0` in Compose).
