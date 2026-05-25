"use client";

import Link from "next/link";
import { CalendarDays, ExternalLink, Filter, RefreshCw, Sparkles, Wand2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { TickerPicker } from "@/components/TickerPicker";
import type { DocumentListItem, ProcessDocumentResponse } from "@/lib/types";

const DOC_TYPES: { key: string; label: string }[] = [
  { key: "quarterly_results", label: "Quarterly" },
  { key: "concall", label: "Concall" },
  { key: "investor_presentation", label: "Presentation" },
  { key: "annual_report", label: "Annual report" },
  { key: "press_release", label: "Press release" },
];

async function fetchDownloadUrl(docId: string) {
  const res = await fetch(`/api/documents/${encodeURIComponent(docId)}/download`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`Download link failed (HTTP ${res.status})`);
  const data = (await res.json()) as { url?: string };
  if (!data.url) throw new Error("Missing download URL");
  return data.url;
}

function DocTypeBadge({ document_type }: { document_type: string }) {
  const label = DOC_TYPES.find((d) => d.key === document_type)?.label ?? document_type;
  return (
    <span className="rounded-full border border-border/70 bg-bg/30 px-2 py-0.5 text-[11px] font-semibold text-text">
      {label}
    </span>
  );
}

function fmtDate(d?: string | null) {
  if (!d) return "—";
  return d;
}

function fmtTime(d?: string | null) {
  if (!d) return "—";
  try {
    const dt = new Date(d);
    if (Number.isNaN(dt.getTime())) return d;
    return dt.toLocaleString();
  } catch {
    return d;
  }
}

export function TimelineApp() {
  const [tickers, setTickers] = useState<string[]>([]);
  const [isTickerPickerOpen, setIsTickerPickerOpen] = useState(false);

  const [docTypeFilter, setDocTypeFilter] = useState<string[]>([]);
  const [docsByTicker, setDocsByTicker] = useState<Record<string, DocumentListItem[]>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [activeDoc, setActiveDoc] = useState<DocumentListItem | null>(null);
  const [versions, setVersions] = useState<DocumentListItem[] | null>(null);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [processResult, setProcessResult] = useState<ProcessDocumentResponse | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  const queryString = useMemo(() => {
    const p = new URLSearchParams();
    p.set("limit", "50");
    for (const t of docTypeFilter) p.append("document_types", t);
    return p.toString();
  }, [docTypeFilter]);

  const refresh = async () => {
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    if (!tickers.length) {
      setDocsByTicker({});
      setError(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const entries = await Promise.all(
        tickers.map(async (t) => {
          const res = await fetch(`/api/tickers/${encodeURIComponent(t)}/documents?${queryString}`, {
            method: "GET",
            headers: { Accept: "application/json" },
            signal: ac.signal,
          });
          if (!res.ok) {
            const msg = await res.text();
            throw new Error(`Ticker ${t}: HTTP ${res.status} ${msg}`);
          }
          const data = (await res.json()) as DocumentListItem[];
          return [t, data] as const;
        })
      );
      const next: Record<string, DocumentListItem[]> = {};
      for (const [t, items] of entries) next[t] = items;
      setDocsByTicker(next);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tickers, queryString]);

  const toggleDocType = (k: string) => {
    setDocTypeFilter((prev) => (prev.includes(k) ? prev.filter((x) => x !== k) : [...prev, k]));
  };

  const openSource = async (docId: string, page?: number | null) => {
    const popup = window.open("about:blank", "_blank");
    if (!popup) {
      alert("Popup blocked. Please allow popups for this site to open source PDFs.");
      return;
    }
    try {
      popup.opener = null;
      popup.document.title = "Opening source…";
      popup.document.body.innerHTML =
        "<div style='font-family: ui-sans-serif, system-ui; padding: 24px; color: #e5e7eb; background: #0b1020;'>Opening source…</div>";
    } catch {
      // ignore
    }
    try {
      const url = await fetchDownloadUrl(docId);
      const finalUrl = page ? `${url}#page=${page}` : url;
      try {
        popup.location.href = finalUrl;
      } catch {
        window.open(finalUrl, "_blank");
      }
    } catch (e) {
      try {
        popup.close();
      } catch {
        // ignore
      }
      // eslint-disable-next-line no-console
      console.error("Failed to open source PDF", e);
      alert("Could not open the source PDF. Please try again.");
    }
  };

  const openVersions = async (doc: DocumentListItem) => {
    setActiveDoc(doc);
    setVersions(null);
    setProcessResult(null);
    setVersionsLoading(true);
    try {
      const res = await fetch(`/api/documents/${encodeURIComponent(doc.doc_id)}/versions`, {
        method: "GET",
        headers: { Accept: "application/json" },
      });
      if (!res.ok) throw new Error(`Versions failed (HTTP ${res.status})`);
      setVersions((await res.json()) as DocumentListItem[]);
    } catch (e) {
      setVersions([]);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setVersionsLoading(false);
    }
  };

  const processDoc = async (docId: string) => {
    setBusyAction(docId);
    setProcessResult(null);
    try {
      const res = await fetch(`/api/documents/${encodeURIComponent(docId)}/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ goal: "searchable" }),
      });
      if (!res.ok) throw new Error(`Process failed (HTTP ${res.status})`);
      setProcessResult((await res.json()) as ProcessDocumentResponse);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyAction(null);
    }
  };

  const closeDrawer = () => {
    setActiveDoc(null);
    setVersions(null);
    setProcessResult(null);
  };

  return (
    <div className="flex h-dvh flex-col">
      {/* Top bar */}
      <div className="flex items-center justify-between gap-2 border-b border-border/60 bg-bg/40 px-4 py-3 backdrop-blur">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-primary" />
          <div className="text-sm font-semibold">TickerLens</div>
          <span className="mx-2 h-4 w-px bg-border/80" />
          <div className="inline-flex items-center gap-2 text-xs text-muted">
            <CalendarDays size={14} />
            Timeline
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/"
            className="rounded-xl border border-border/70 bg-panel/50 px-3 py-2 text-sm font-semibold text-text hover:bg-panel/70 transition"
            title="Back to chat"
          >
            Chat
          </Link>
          <button
            type="button"
            onClick={() => setIsTickerPickerOpen(true)}
            className="rounded-xl border border-primary/40 bg-primary/15 px-3 py-2 text-sm font-semibold text-primaryFg hover:bg-primary/20 transition"
          >
            {tickers.length ? `Tickers (${tickers.length})` : "Select tickers"}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-4 py-6 no-scrollbar">
        <div className="mx-auto w-full max-w-5xl">
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border/70 bg-panel/40 p-4">
              <div className="min-w-0">
                <div className="text-sm font-semibold text-text">Document timeline</div>
                <div className="mt-1 text-xs text-muted">
                  Browse filings by <span className="font-semibold text-text">filing_date</span> and open sources.
                </div>
                {tickers.length ? (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {tickers.map((t) => (
                      <span
                        key={t}
                        className="inline-flex items-center gap-1 rounded-full border border-border/70 bg-bg/30 px-2 py-1 text-[11px] text-text"
                      >
                        <span className="font-semibold">{t}</span>
                      </span>
                    ))}
                  </div>
                ) : (
                  <div className="mt-3 inline-flex items-center gap-2 rounded-xl border border-border/70 bg-bg/25 px-3 py-2 text-sm text-muted">
                    <Wand2 size={16} className="text-muted" />
                    Select one or more tickers to view their filing timeline.
                  </div>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={refresh}
                  className="inline-flex items-center gap-2 rounded-xl border border-border/70 bg-bg/20 px-3 py-2 text-sm font-semibold text-text hover:bg-bg/35 transition disabled:opacity-60"
                  disabled={!tickers.length || loading}
                  title="Refresh"
                >
                  <RefreshCw size={16} className="text-primary" />
                  Refresh
                </button>
              </div>
            </div>

            <div className="rounded-2xl border border-border/70 bg-panel/30 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="inline-flex items-center gap-2 text-xs font-semibold text-muted">
                  <Filter size={14} />
                  Document types
                </div>
                <button
                  type="button"
                  onClick={() => setDocTypeFilter([])}
                  className="text-xs text-muted hover:text-text transition"
                  disabled={docTypeFilter.length === 0}
                >
                  Clear
                </button>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {DOC_TYPES.map((d) => {
                  const active = docTypeFilter.includes(d.key);
                  return (
                    <button
                      key={d.key}
                      type="button"
                      onClick={() => toggleDocType(d.key)}
                      className={[
                        "rounded-xl border px-3 py-1.5 text-xs font-semibold transition",
                        active
                          ? "border-primary/40 bg-primary/15 text-primaryFg"
                          : "border-border/70 bg-bg/20 text-text hover:bg-bg/35",
                      ].join(" ")}
                    >
                      {d.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {error ? (
              <div className="rounded-2xl border border-danger/40 bg-danger/10 p-4 text-sm text-dangerFg">
                {error}
              </div>
            ) : null}

            {tickers.length === 0 ? null : (
              <div className="space-y-6">
                {tickers.map((t) => {
                  const items = docsByTicker[t] ?? [];
                  return (
                    <section key={t} className="rounded-2xl border border-border/70 bg-panel/25">
                      <div className="flex items-center justify-between gap-2 border-b border-border/60 px-4 py-3">
                        <div className="text-sm font-semibold text-text">{t}</div>
                        <div className="text-xs text-muted">
                          {loading ? "Loading…" : `${items.length} document(s)`}
                        </div>
                      </div>

                      {items.length === 0 ? (
                        <div className="px-4 py-6 text-sm text-muted">No documents found.</div>
                      ) : (
                        <ul className="divide-y divide-border/50">
                          {items.map((d) => (
                            <li key={d.doc_id} className="px-4 py-3 hover:bg-bg/15 transition">
                              <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                                <div className="min-w-0">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <DocTypeBadge document_type={d.document_type} />
                                    {d.fiscal_year ? (
                                      <span className="text-xs text-muted">{d.fiscal_year}</span>
                                    ) : null}
                                    <span className="text-xs text-muted">
                                      filed <span className="font-semibold text-text">{fmtDate(d.filing_date)}</span>
                                    </span>
                                    <span className="text-xs text-muted">v{d.version}</span>
                                  </div>
                                  <div className="mt-1 truncate text-xs text-muted">
                                    doc_id: <span className="font-mono text-text/90">{d.doc_id}</span>
                                  </div>
                                </div>

                                <div className="flex flex-wrap items-center gap-2">
                                  <button
                                    type="button"
                                    onClick={() => openSource(d.doc_id, null)}
                                    className="inline-flex items-center gap-1.5 rounded-lg border border-border/70 bg-bg/25 px-2 py-1 text-xs text-text hover:bg-bg/40 transition"
                                    title="Open source PDF"
                                  >
                                    <ExternalLink size={14} />
                                    Open
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => openVersions(d)}
                                    className="rounded-lg border border-border/70 bg-bg/25 px-2 py-1 text-xs font-semibold text-text hover:bg-bg/40 transition"
                                  >
                                    Versions
                                  </button>
                                </div>
                              </div>
                            </li>
                          ))}
                        </ul>
                      )}
                    </section>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Drawer */}
      <div
        className={[
          "fixed inset-0 z-50",
          activeDoc ? "pointer-events-auto" : "pointer-events-none",
        ].join(" ")}
      >
        <button
          type="button"
          className={[
            "absolute inset-0 bg-black/35 backdrop-blur-sm transition-opacity duration-200",
            activeDoc ? "opacity-100" : "opacity-0",
          ].join(" ")}
          onClick={closeDrawer}
          aria-label="Close document panel"
        />

        <aside
          className={[
            "absolute right-0 top-0 h-full w-[min(560px,calc(100vw-2.5rem))] border-l border-border/70 bg-panel/95 shadow-soft transition-transform duration-200",
            activeDoc ? "translate-x-0" : "translate-x-full",
          ].join(" ")}
        >
          <div className="flex items-center justify-between gap-2 border-b border-border/60 px-4 py-3">
            <div className="min-w-0">
              <div className="text-sm font-semibold">Document</div>
              <div className="mt-0.5 truncate text-[11px] text-muted">
                {activeDoc ? `${activeDoc.ticker} • ${activeDoc.document_type} • v${activeDoc.version}` : ""}
              </div>
            </div>
            <button
              type="button"
              onClick={closeDrawer}
              className="rounded-lg p-2 text-muted hover:bg-bg/35 hover:text-text transition"
              aria-label="Close"
            >
              ✕
            </button>
          </div>

          {!activeDoc ? null : (
            <div className="h-[calc(100dvh-3.25rem)] overflow-auto p-4">
              <div className="rounded-2xl border border-border/70 bg-bg/20 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-xs text-muted">doc_id</div>
                  <div className="font-mono text-xs text-text/90">{activeDoc.doc_id}</div>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                  <div className="rounded-xl border border-border/70 bg-bg/20 p-3">
                    <div className="text-[11px] text-muted">Filing date</div>
                    <div className="mt-1 font-semibold text-text">{fmtDate(activeDoc.filing_date)}</div>
                  </div>
                  <div className="rounded-xl border border-border/70 bg-bg/20 p-3">
                    <div className="text-[11px] text-muted">Created</div>
                    <div className="mt-1 font-semibold text-text">{fmtTime(activeDoc.created_at)}</div>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => openSource(activeDoc.doc_id, null)}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-border/70 bg-bg/25 px-3 py-2 text-sm font-semibold text-text hover:bg-bg/40 transition"
                  >
                    <ExternalLink size={16} className="text-primary" />
                    Open PDF
                  </button>
                  <button
                    type="button"
                    disabled={busyAction === activeDoc.doc_id}
                    onClick={() => processDoc(activeDoc.doc_id)}
                    className="rounded-xl border border-primary/40 bg-primary/15 px-3 py-2 text-sm font-semibold text-primaryFg hover:bg-primary/20 transition disabled:opacity-60"
                    title="Run parse+chunk+embed+index incrementally"
                  >
                    {busyAction === activeDoc.doc_id ? "Processing…" : "Process (searchable)"}
                  </button>
                </div>
              </div>

              <div className="mt-4">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-semibold">Versions</div>
                  <div className="text-xs text-muted">{versionsLoading ? "Loading…" : ""}</div>
                </div>
                <div className="mt-2 rounded-2xl border border-border/70 bg-bg/10">
                  {versionsLoading ? (
                    <div className="px-4 py-6 text-sm text-muted">Loading versions…</div>
                  ) : !versions || versions.length === 0 ? (
                    <div className="px-4 py-6 text-sm text-muted">No versions found.</div>
                  ) : (
                    <ul className="divide-y divide-border/50">
                      {versions.map((v) => (
                        <li key={v.doc_id} className="px-4 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="text-xs font-semibold text-text">v{v.version}</span>
                                <span className="text-xs text-muted">
                                  filed <span className="font-semibold text-text">{fmtDate(v.filing_date)}</span>
                                </span>
                              </div>
                              <div className="mt-1 truncate text-[11px] text-muted">
                                checksum: <span className="font-mono text-text/90">{v.checksum}</span>
                              </div>
                              <div className="mt-0.5 truncate text-[11px] text-muted">
                                created: <span className="font-semibold text-text">{fmtTime(v.created_at)}</span>
                              </div>
                            </div>
                            <button
                              type="button"
                              onClick={() => openSource(v.doc_id, null)}
                              className="inline-flex items-center gap-1.5 rounded-lg border border-border/70 bg-bg/25 px-2 py-1 text-xs text-text hover:bg-bg/40 transition"
                            >
                              <ExternalLink size={14} />
                              Open
                            </button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>

              {processResult ? (
                <div className="mt-4 rounded-2xl border border-border/70 bg-panel/40 p-4">
                  <div className="text-sm font-semibold">Process result</div>
                  <div className="mt-2 grid grid-cols-1 gap-2 text-xs">
                    {(["parse", "chunk", "embed", "index"] as const).map((k) => {
                      const s = (processResult as any)[k] as
                        | { run_id: string; status: string; action: string }
                        | null
                        | undefined;
                      if (!s) return null;
                      return (
                        <div key={k} className="rounded-xl border border-border/70 bg-bg/20 p-3">
                          <div className="flex items-center justify-between gap-2">
                            <div className="font-semibold text-text">{k}</div>
                            <div className="text-[11px] text-muted">{s.action}</div>
                          </div>
                          <div className="mt-1 text-[11px] text-muted">
                            run_id: <span className="font-mono text-text/90">{s.run_id}</span>
                          </div>
                          <div className="mt-0.5 text-[11px] text-muted">
                            status: <span className="font-semibold text-text">{s.status}</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <div className="mt-3 text-[11px] text-muted">
                    Poll run status using the API run endpoints (parse/chunk/embed/index run detail endpoints).
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </aside>
      </div>

      <TickerPicker
        value={tickers}
        onChange={setTickers}
        open={isTickerPickerOpen}
        onOpenChange={setIsTickerPickerOpen}
      />
    </div>
  );
}

