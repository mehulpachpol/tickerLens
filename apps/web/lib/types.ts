export type Citation = {
  chunk_id: string;
  ticker?: string | null;
  doc_id?: string | null;
  document_type?: string | null;
  fiscal_year?: string | null;
  filing_date?: string | null;
  version?: number | null;
  section?: string | null;
  page_start?: number | null;
  page_end?: number | null;
  download_endpoint?: string | null;
};

export type ChatCitationsPayload = {
  used_chunk_ids: string[];
  citations: Citation[];
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
  citations?: ChatCitationsPayload;
  error?: string;
  status?: "streaming" | "done" | "stopped";
};

export type ChatSession = {
  id: string;
  title: string;
  createdAt: number;
  tickers: string[];
  messages: ChatMessage[];
};

export type SseEvent =
  | { event: "meta"; data: { retrieval_ms?: number; candidates?: number } }
  | { event: "delta"; data: { delta: string } }
  | { event: "citations"; data: ChatCitationsPayload }
  | { event: "done"; data: { ok: true } }
  | { event: "error"; data: { error: string } };

export type DocumentListItem = {
  doc_id: string;
  ticker: string;
  company_name?: string | null;
  document_type: string;
  fiscal_year?: string | null;
  filing_date?: string | null;
  source_url?: string | null;
  checksum: string;
  version: number;
  created_at: string;
  updated_at: string;
};

export type ProcessDocumentResponse = {
  doc_id: string;
  goal: "parse" | "chunk" | "embed" | "index" | "searchable";
  parse?: { stage: "parse"; run_id: string; status: string; action: string } | null;
  chunk?: { stage: "chunk"; run_id: string; status: string; action: string } | null;
  embed?: { stage: "embed"; run_id: string; status: string; action: string } | null;
  index?: { stage: "index"; run_id: string; status: string; action: string } | null;
  embedding_target?: { model: string; dimensions?: number | null; vector_size: number; collection: string } | null;
  index_target?: { backend: string; index_name: string } | null;
};
