"use client";

import { ExternalLink, Files, Quote, X } from "lucide-react";
import { useState } from "react";

import type { ChatCitationsPayload, Citation } from "@/lib/types";

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

function formatPages(c: Citation) {
  if (c.page_start != null && c.page_end != null) {
    return c.page_start === c.page_end ? `p.${c.page_start}` : `p.${c.page_start}–${c.page_end}`;
  }
  return null;
}

export function CitationsDrawer({
  open,
  onOpenChange,
  payload,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  payload?: ChatCitationsPayload;
}) {
  const [busyDocId, setBusyDocId] = useState<string | null>(null);
  const citations = payload?.citations ?? [];

  const openPdf = async (c: Citation) => {
    if (!c.doc_id) return;
    const popup = window.open("about:blank", "_blank");
    if (!popup) {
      // Popup blocked. Keep the UI responsive and avoid leaving the user with no feedback.
      alert("Popup blocked. Please allow popups for this site to open source PDFs.");
      return;
    }
    try {
      popup.opener = null;
      popup.document.title = "Opening source…";
      popup.document.body.innerHTML =
        "<div style='font-family: ui-sans-serif, system-ui; padding: 24px; color: #e5e7eb; background: #0b1020;'>Opening source…</div>";
    } catch {
      // Ignore (some environments restrict access even for about:blank).
    }
    setBusyDocId(c.doc_id);
    try {
      const url = await fetchDownloadUrl(c.doc_id);
      const page = c.page_start ?? c.page_end ?? null;
      const finalUrl = page ? `${url}#page=${page}` : url;
      try {
        popup.location.href = finalUrl;
      } catch {
        // Fallback if navigating the already-opened tab is blocked.
        window.open(finalUrl, "_blank");
      }
    } catch (e) {
      try {
        popup.close();
      } catch {
        // ignore
      }
      // Avoid unhandled promise rejections from event handlers.
      // eslint-disable-next-line no-console
      console.error("Failed to open source PDF", e);
      alert("Could not open the source PDF. Please try again.");
    } finally {
      setBusyDocId(null);
    }
  };

  return (
    <div className={["fixed inset-0 z-50", open ? "pointer-events-auto" : "pointer-events-none"].join(" ")}>
      <button
        type="button"
        className={[
          "absolute inset-0 bg-black/35 backdrop-blur-sm transition-opacity duration-200",
          open ? "opacity-100" : "opacity-0",
        ].join(" ")}
        onClick={() => onOpenChange(false)}
        aria-label="Close citations"
      />

      <aside
        className={[
          "absolute right-0 top-0 h-full w-[min(520px,calc(100vw-2.5rem))] border-l border-border/70 bg-panel/95 shadow-soft transition-transform duration-200",
          open ? "translate-x-0" : "translate-x-full",
        ].join(" ")}
      >
        <div className="flex items-center justify-between gap-2 border-b border-border/60 px-4 py-3">
          <div className="flex items-center gap-2">
            <Quote size={16} className="text-primary" />
            <div>
              <div className="text-sm font-semibold">Citations</div>
              <div className="text-[11px] text-muted">
                Sources referenced in the selected answer
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded-lg p-2 text-muted hover:bg-bg/35 hover:text-text transition"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        {citations.length === 0 ? (
          <div className="px-4 py-6 text-sm text-muted">No citations for this message.</div>
        ) : (
          <div className="h-[calc(100dvh-3.25rem)] overflow-auto p-3">
            <ul className="space-y-2">
              {citations.map((c) => {
                const pages = formatPages(c);
                const titleBits = [
                  c.ticker ?? null,
                  c.document_type ?? null,
                  c.fiscal_year ?? null,
                  c.filing_date ? `filed ${c.filing_date}` : null,
                ].filter(Boolean);

                return (
                  <li key={c.chunk_id} className="rounded-xl border border-border/70 bg-bg/20 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          {c.ticker ? (
                            <span className="rounded-full border border-border/70 bg-bg/35 px-2 py-0.5 text-[11px] font-semibold">
                              {c.ticker}
                            </span>
                          ) : null}
                          <div className="truncate text-xs text-muted">{titleBits.join(" • ")}</div>
                        </div>
                        <div className="mt-1 text-xs text-muted">
                          {pages ? <span className="mr-2">{pages}</span> : null}
                          {c.section ? <span className="truncate">{c.section}</span> : null}
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {c.doc_id ? (
                          <button
                            type="button"
                            onClick={() => openPdf(c)}
                            disabled={busyDocId === c.doc_id}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-border/70 bg-bg/25 px-2 py-1 text-xs text-text hover:bg-bg/40 transition disabled:opacity-60"
                            title="Open source PDF"
                          >
                            <ExternalLink size={14} />
                            {busyDocId === c.doc_id ? "Opening…" : "Open"}
                          </button>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => navigator.clipboard.writeText(c.chunk_id)}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-border/70 bg-bg/25 px-2 py-1 text-xs text-text hover:bg-bg/40 transition"
                          title="Copy chunk_id"
                        >
                          <Files size={14} />
                          Copy
                        </button>
                      </div>
                    </div>

                    <div className="mt-2 text-[11px] text-muted">
                      chunk_id: <span className="font-mono text-text/90">{c.chunk_id}</span>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </aside>
    </div>
  );
}
