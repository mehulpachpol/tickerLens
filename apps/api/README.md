# TickerLens API

FastAPI backend for the Stock Intelligence RAG Platform.

## Run (dev)

1. Create a virtualenv (any tool you like).
2. Install dependencies:
   - `pip install -e .[dev]`
3. Start the server:
   - `uvicorn tickerlens_api.main:app --reload --port 8000`

## Database migrations

Migrations are managed via Alembic. For local (non-Docker) runs, set `TICKERLENS_DATABASE_URL` then:

- `alembic upgrade head`

In Docker Compose, a `migrate` service runs automatically before the API starts.

## Endpoints

- `GET /health`
- `GET /version`
- `POST /documents/upload`
- `GET /documents/{doc_id}`
- `GET /documents/{doc_id}/versions`
- `GET /documents/{doc_id}/download`
- `POST /documents/{doc_id}/process`
- `POST /documents/{doc_id}/parse`
- `GET /documents/{doc_id}/parse-runs`
- `GET /parse-runs/{run_id}`
- `GET /documents/{doc_id}/pages`
- `GET /documents/{doc_id}/pages/{page_num}`
- `POST /documents/{doc_id}/chunk`
- `GET /documents/{doc_id}/chunk-runs`
- `GET /chunk-runs/{run_id}`
- `GET /documents/{doc_id}/chunks`
- `GET /chunks/{chunk_id}`
- `POST /documents/{doc_id}/index`
- `GET /documents/{doc_id}/index-runs`
- `GET /index-runs/{run_id}`
- `POST /documents/{doc_id}/embed`
- `GET /documents/{doc_id}/embed-runs`
- `GET /embed-runs/{run_id}`
- `GET /tickers/{ticker}/documents`
- `POST /search/vector`
- `POST /search/bm25`
- `POST /search/hybrid`
- `POST /search/hybrid_rerank`
- `POST /chat/stream`

## OpenAI config

Vector search depends on OpenAI embeddings. Set `OPENAI_API_KEY` (or `TICKERLENS_OPENAI_API_KEY`) before using:

- `POST /documents/{doc_id}/embed`
- `POST /search/vector`

## Manual pipeline (Phases 2-6)

The current implementation is intentionally manual-first: upload -> parse -> chunk -> index/embed -> search.

1. Upload a PDF -> get `doc_id`
2. `POST /documents/{doc_id}/parse`
3. `POST /documents/{doc_id}/chunk`
4. `POST /documents/{doc_id}/index`
5. `POST /documents/{doc_id}/embed`
6. `POST /search/vector` or `POST /search/bm25` or `POST /search/hybrid` or `POST /search/hybrid_rerank`

## Chat (Phase 8, streaming)

- `POST /chat/stream` streams Server-Sent Events (SSE):
  - `event: delta` -> incremental answer text
  - `event: citations` -> final citations payload (chunk_id -> doc/page metadata)
  - `event: done`

The model is instructed to cite sources inline using `[(chunk_id=<id>)]` where `<id>` is a chunk id returned by retrieval.
