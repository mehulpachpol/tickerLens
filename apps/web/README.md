# TickerLens Web

Next.js (App Router) + Tailwind UI for TickerLens.

## Run (dev)

Prereqs:
- Node.js `>=20.9`
- Backend API running (Compose): `.\scripts\dev.ps1 up`

From repo root:

```powershell
cd apps\web
Copy-Item .env.example .env -ErrorAction SilentlyContinue
npm install
npm run dev
```

The UI runs on `http://localhost:3010`.

Pages:
- Chat: `http://localhost:3010/`
- Timeline: `http://localhost:3010/timeline`

## API proxy

The UI calls Next.js route handlers under `/api/...` to avoid CORS issues. These proxy to the FastAPI backend.

- `POST /api/chat/stream` -> FastAPI `POST /chat/stream` (SSE)
- `GET /api/tickers/:ticker/documents` -> FastAPI `GET /tickers/{ticker}/documents`
- `GET /api/documents/:docId/versions` -> FastAPI `GET /documents/{doc_id}/versions`
- `POST /api/documents/:docId/process` -> FastAPI `POST /documents/{doc_id}/process`
- `GET /api/documents/:docId/download` -> FastAPI `GET /documents/{doc_id}/download`
