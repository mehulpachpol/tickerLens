# TickerLens API

FastAPI backend for the Stock Intelligence RAG Platform.

## Run (dev)

1. Create a virtualenv (any tool you like).
2. Install dependencies:
   - `pip install -e .[dev]`
3. Start the server:
   - `uvicorn tickerlens_api.main:app --reload --port 8000`

## Endpoints

- `GET /health`
- `GET /version`

