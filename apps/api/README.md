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
- `GET /documents/{doc_id}/download`
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
