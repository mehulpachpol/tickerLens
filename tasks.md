# STOCK INTELLIGENCE RAG PLATFORM (NSE Multi‑Ticker)
## Project Tasks — 11 Phases (Open‑Source + Free Stack)

**Non‑negotiables**
- **Platform components are open-source + free** (runtime, DBs, indexes, observability). **Models use OpenAI API** during early phases (paid), with a later option to switch to self-hosted open models.
- **Citation-first** answers: every claim must map to an explicit source span (doc + page + chunk id).
- **Temporal correctness**: answers must prefer the most recent relevant filings and clearly state dates.
- **Auditability**: store lineage from raw doc → parsed text → chunks → embeddings → retrieval → answer.

**Reference open-source stack (baseline)**
- **Frontend**: Next.js + React + Tailwind CSS
- **API / Orchestration**: FastAPI (Python)
- **Workers**: Python (Celery / Dramatiq) or pure async workers
- **DB**: PostgreSQL
- **Object storage**: MinIO (S3-compatible)
- **Vector DB**: Qdrant
- **Keyword/BM25**: OpenSearch
- **Cache**: Redis
- **Queue/Event bus**: Apache Kafka (optional early; can start with Redis streams)
- **LLM serving**: OpenAI API initially; later Ollama or vLLM for self-hosted models
- **Embeddings / rerank**: OpenAI embeddings initially; later Sentence-Transformers + BGE family (open models)
- **Observability**: OpenTelemetry + Prometheus + Grafana
- **RAG traces/evals**: Langfuse (OSS) + Phoenix (OSS)

> Notes: The project can start small (manual document uploads) and later add automated NSE/BSE ingestion once the core pipeline is stable and legal/ToS constraints are handled.

---

## Phase 1 — Repo + Local Dev Platform (Foundation)
**Outcome**: A working local environment where you can run the API, UI, and core data services with one command.

**Steps**
1. Create a clean repo layout: `apps/web`, `apps/api`, `services/ingestion`, `services/indexing`, `infra/compose`, `docs/`.
2. Add `docker-compose.yml` for Postgres, MinIO, Qdrant, OpenSearch, Redis, Grafana/Prometheus (later), plus volumes.
3. Add `.env.example` for all services (ports, credentials, bucket names, index names).
4. Add Makefile / task runner scripts (`make up`, `make down`, `make logs`, `make reset`).
5. Define coding standards: formatting (ruff/black), type checking (mypy), pre-commit hooks (optional).
6. Add minimal FastAPI service with `/health` and `/version`.
7. Add minimal Next.js app with a “TickerLens” landing page and a “Chat” route placeholder.

**Learning goals**
- Docker Compose fundamentals, service networking, env management, basic API + UI skeletons.

**Deliverables**
- One-command local startup, health checks for all services, basic repo scaffolding.

---

## Phase 2 — Document Ingestion v1 (Manual Upload + Metadata)
**Outcome**: You can upload a PDF (annual report/filing) for a ticker and store it reliably with metadata + checksums.

**Steps**
1. Define **document types** and naming conventions (annual_report, quarterly_results, concall, investor_presentation, etc.).
2. Create Postgres schema for:
   - `companies` (ticker, name)
   - `documents` (doc_id, ticker, type, fiscal_year, filing_date, source_url, checksum, version, created_at)
   - `document_files` (object storage key, mime, size, checksum)
3. Implement API endpoints:
   - `POST /documents/upload` (multipart: file + metadata)
   - `GET /documents/{doc_id}` (metadata)
   - `GET /documents/{doc_id}/download` (signed URL from MinIO)
4. Store raw docs into MinIO under `/raw_docs/{TICKER}/{document_type}/{YYYY}/...`.
5. Implement deduplication via checksum (skip duplicates, bump version if needed).
6. Add an admin-only UI page to upload docs and view ingestion status.

**Learning goals**
- Designing schemas, handling uploads, object storage patterns, checksum-based dedupe.

**Deliverables**
- Raw document store + metadata DB + upload UI + basic governance (admin-only).

---

## Phase 3 — Parsing + Normalization (Text, OCR, Tables)
**Outcome**: Convert raw PDFs into a canonical, queryable document representation with page-level text.

**Steps**
1. Implement a parsing worker pipeline:
   - PDF text extraction (PyMuPDF / pdfplumber)
   - OCR fallback for scanned pages (Tesseract or PaddleOCR)
   - Table extraction (Camelot/Tabula where feasible)
2. Store normalized outputs:
   - `document_pages` (doc_id, page_num, text, ocr_used, checksum)
   - `document_tables` (doc_id, page_num, table_json, extraction_tool)
3. Define a canonical **document JSON** (doc schema from the spec) and persist it (DB + optional JSON in MinIO).
4. Add “document viewer” UI:
   - page navigation
   - extracted text preview
   - table preview (basic)
5. Add parsing quality checks:
   - empty-page detection
   - OCR confidence thresholds (if available)
   - basic language detection (optional)

**Learning goals**
- Practical PDF parsing realities, OCR decisioning, structured normalization.

**Deliverables**
- Deterministic parse pipeline + stored normalized pages/tables + viewer.

---

## Phase 4 — Chunking Engine (Section‑Aware + Lineage)
**Outcome**: High-quality chunks with stable IDs and precise source mapping (page + offsets), ready for embedding.

**Steps**
1. Design chunk schema:
   - `chunks` (chunk_id, doc_id, ticker, page_start, page_end, section, token_count, char_start/end per page, chunk_text)
2. Implement **structure-aware chunking**:
   - detect headings (font size heuristics / regex)
   - keep paragraphs intact
   - handle tables as separate chunks
   - maintain max token window with overlap (only when needed)
3. Record lineage for citations:
   - source page numbers
   - character offsets
   - checksum of chunk_text
4. Build a “chunk debugger” UI:
   - show chunks per doc
   - highlight page text spans used by a chunk
5. Add regression fixtures:
   - a small set of PDFs with expected chunk counts/sections (golden tests)

**Learning goals**
- Why chunking matters, how to preserve citations, building debuggable pipelines.

**Deliverables**
- Reproducible chunking + chunk inspection tooling + baseline tests.

---

## Phase 5 — Embeddings + Vector Search (Qdrant)
**Outcome**: Semantic search working end-to-end with ticker filtering and top‑K chunk retrieval.

**Steps**
1. Select an open embedding model (Sentence-Transformers; BGE family or equivalent).
2. Implement embedding worker:
   - clean chunk text
   - compute embeddings
   - upsert into Qdrant with payload metadata (ticker, doc_id, filing_date, doc_type, pages, section)
3. Implement vector retrieval API:
   - `POST /search/vector` (query + filters + top_k)
4. Add search UI:
   - query bar + ticker filter
   - results list with page + snippet
   - open source viewer for citations
5. Add re-indexing controls (per doc / per ticker) and idempotency guarantees.

**Learning goals**
- Embedding quality, vector DB payload design, filterable semantic retrieval.

**Deliverables**
- Working semantic search with traceable results and stable IDs.

---

## Phase 6 — Hybrid Retrieval (OpenSearch BM25 + Merge)
**Outcome**: Hybrid retrieval that combines BM25 + vectors and performs better on financial keywords/numbers.

**Steps**
1. Create OpenSearch index mapping for chunks (text + keyword fields: ticker, doc_type, fiscal_year, filing_date).
2. Index chunks into OpenSearch with consistent IDs matching the chunk table.
3. Implement BM25 search API:
   - `POST /search/bm25`
4. Implement hybrid search API:
   - run BM25 + vector in parallel
   - normalize scores
   - merge and de-duplicate by `chunk_id`
   - enforce ticker/document filters
5. Add query expansion (lightweight):
   - ticker symbol normalization
   - common finance synonyms (capex ↔ capital expenditure, EV ↔ electric vehicle)

**Learning goals**
- Why hybrid matters, scoring normalization, practical query rewriting.

**Deliverables**
- Hybrid search endpoint + UI toggle + measurable uplift on keyword-heavy queries.

---

## Phase 7 — Reranking + Multi‑Ticker Context Assembly
**Outcome**: Better relevance via reranking and safe multi-ticker evidence separation (no citation mixing).

**Steps**
1. Add a cross-encoder reranker (open model) to score (query, chunk_text) pairs.
2. Retrieve top N (e.g., 100) candidates from hybrid search; rerank; select top K (e.g., 10–20).
3. Implement multi-ticker context assembler:
   - group evidence by ticker
   - order by recency + relevance
   - emit structured context blocks:
     - `[TCS CONTEXT] ...`
     - `[INFY CONTEXT] ...`
4. Add “why this result” debug output:
   - bm25 score, vector score, rerank score, rank position
5. Add latency budget tracking (p50/p95) and caching of rerank results for repeated queries.

**Learning goals**
- Cross-encoders, relevance tuning, and evidence isolation for comparisons.

**Deliverables**
- Reranked hybrid retrieval + robust multi-ticker context packaging.

---

## Phase 8 — Constrained LLM Generation + Citation Engine (Zero‑Hallucination)
**Outcome**: A chat endpoint that answers strictly from retrieved context with verifiable citations.

**Steps**
1. Deploy a self-hosted LLM via Ollama/vLLM (open model suitable for instruction following).
2. Implement constrained prompting:
   - “Use ONLY provided context”
   - “Every sentence must have at least one citation”
   - “If evidence is insufficient, say so”
3. Implement citation engine:
   - map answer spans → `chunk_id` references
   - enrich citations with (ticker, doc name/type, filing_date, pages, source link/object key)
4. Build chat API:
   - `POST /chat` (tickers + question)
   - returns streaming tokens (SSE) + citations payload
5. Build chat UI:
   - ticker selector
   - streaming answer
   - citation panel with clickable sources (page + highlight)

**Learning goals**
- RAG prompting, grounding, citation mapping, streaming UX.

**Deliverables**
- End-to-end chat with citations and “insufficient evidence” behavior.

---

## Phase 9 — Temporal Reasoning + Incremental Updates
**Outcome**: “Latest info” answers are correct and defensible; ingestion and indexing support incremental updates and versioning.

**Steps**
1. Add temporal ranking rules:
   - prioritize latest filing_date for “latest/current/most recent” intents
   - show explicit dates in responses
2. Implement document versioning:
   - detect re-filed documents
   - keep old versions for audit
3. Add incremental pipelines:
   - only re-parse/re-chunk/re-embed on changed docs
   - background jobs + retry policies
4. Add a “timeline view” UI per ticker:
   - documents by date/type
   - open and compare versions

**Learning goals**
- Temporal intent detection, stable updates, and the difference between “freshness” and “truth”.

**Deliverables**
- Reliable “latest” answers + incremental indexing + timeline explorer.

---

## Phase 10 — Automated NSE Ingestion (Daily Scheduler, Nifty 50 → Full Universe)
**Outcome**: Documents are discovered and ingested automatically every day from the NSE website, starting with Nifty 50 and scaling to 2000+ listed companies.

**Steps**
1. Do a compliance check:
   - review NSE Terms/robots constraints for automated access
   - implement strict rate limits, caching, and exponential backoff
2. Create a ticker universe model:
   - `universes` (e.g., `NIFTY_50`, `ALL_NSE`)
   - `universe_members` (ticker, start_date, end_date, active)
   - seed with Nifty 50 first; then expand to all listed tickers
3. Implement a filing discovery crawler:
   - daily per-ticker discovery job (scheduler driven)
   - parse NSE pages to detect new filings/attachments
   - store `discovered_items` with source URL, discovered_at, and a stable fingerprint
4. Implement download + dedupe workers:
   - fetch PDFs/HTML, compute checksum, and de-duplicate against existing docs
   - persist raw files in MinIO + create/upgrade `documents` rows
   - record provenance (source URL + retrieval time)
5. Add a scheduler service:
   - APScheduler or Celery Beat (timezone-aware)
   - configurable cadence per universe (Nifty 50 daily; long-tail less frequent)
6. Add ingestion safeguards + observability:
   - per-domain concurrency limits, retries with jitter, circuit breaker on repeated failures
   - metrics for discovery/download success rate and lag (discovered_at → ingested_at)
7. Build an ingestion ops UI:
   - per-ticker status, last run time, failures, and backlog
   - pause/resume a universe, manual re-run for a ticker

**Learning goals**
- Building reliable crawlers: scheduling, throttling, idempotency, provenance, and scaling from 50 → 2000+ tickers.

**Deliverables**
- Daily automated ingestion pipeline for Nifty 50 + a controlled path to scale to the full NSE universe.

---

## Phase 11 — Production Hardening (Evals, Observability, Security, Release)
**Outcome**: A production-ready system with evaluation, monitoring, security controls, and repeatable deployment.

**Steps**
1. Add authentication + RBAC:
   - users, sessions, API keys/JWT
   - admin-only ingestion
2. Add rate limiting + audit logs:
   - request logs with user/session ids
   - document access logs
3. Add observability:
   - OpenTelemetry traces for ingestion → retrieval → LLM
   - Prometheus metrics (latency, hit rates, failures)
   - Grafana dashboards
4. Add evaluation harness:
   - curated benchmark queries per ticker
   - metrics: retrieval precision/recall, citation accuracy, faithfulness, latency
   - regression runs in CI
5. Add deployment packaging:
   - Docker images per service
   - config management
   - backup/restore for Postgres + MinIO

**Learning goals**
- Building systems you can trust: monitoring, testing, governance, safe releases.

**Deliverables**
- E2E evals + dashboards + security controls + deployable stack.

---

## Suggested “First Milestone” (1–2 weeks)
- Complete Phases **1–3** with 1–2 tickers and ~10 PDFs total.
- Validate parsing quality and build the document viewer early (debugging is 10× easier with UI).
