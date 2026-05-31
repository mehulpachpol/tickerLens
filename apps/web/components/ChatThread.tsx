"use client";

import { ChevronDown, ChevronRight, Quote, TriangleAlert } from "lucide-react";
import { useState } from "react";

import type { ChatMessage } from "@/lib/types";

const INLINE_CITATION_RE = /\[\(chunk_id=[^)]+\)\]/g;
const INLINE_CITATION_PREFIX = "[(chunk_id=";

function stripInlineCitations(text: string) {
  let s = (text || "").replace(INLINE_CITATION_RE, "");

  // During streaming we can see partial tokens like "[(chunk_id=" before the closing ")]" arrives.
  // Hide the entire citation marker as soon as it starts, so it never flashes in the UI.
  while (true) {
    const i = s.indexOf(INLINE_CITATION_PREFIX);
    if (i === -1) break;
    const j = s.indexOf(")]", i);
    if (j === -1) {
      s = s.slice(0, i);
      break;
    }
    s = s.slice(0, i) + s.slice(j + 2);
  }

  return s.replace(/[ \t]+\n/g, "\n").trim();
}

function formatTime(ts: number) {
  try {
    return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function TypingDots() {
  return (
    <div className="inline-flex items-center gap-1.5">
      <span className="h-1.5 w-1.5 rounded-full bg-muted/70 animate-bounce [animation-delay:-0.2s]" />
      <span className="h-1.5 w-1.5 rounded-full bg-muted/70 animate-bounce [animation-delay:-0.1s]" />
      <span className="h-1.5 w-1.5 rounded-full bg-muted/70 animate-bounce" />
    </div>
  );
}

export function ChatThread({
  messages,
  activeCitationsMessageId,
  onSelectCitationsMessage,
  onOpenTickerPicker,
  onQuickReply,
}: {
  messages: ChatMessage[];
  activeCitationsMessageId: string | null;
  onSelectCitationsMessage: (id: string) => void;
  onOpenTickerPicker: () => void;
  onQuickReply: (text: string) => void;
}) {
  const [detailsOpenId, setDetailsOpenId] = useState<string | null>(null);

  const formatStepExtras = (s: any): string[] => {
    if (!s || typeof s !== "object") return [];
    const out: string[] = [];
    const push = (k: string, v: unknown) => {
      if (v === undefined || v === null) return;
      out.push(`${k}=${String(v)}`);
    };

    push("status", s.status);
    push("tool_ms", s.tool_ms);
    push("ok", s.ok);
    if (Array.isArray(s.errors) && s.errors.length) push("errors", s.errors.length);

    push("retrieval_ms", s.retrieval_ms);
    push("hits", s.hits);
    push("decision", s.decision);
    push("reason", s.reason);

    return out;
  };

  return (
    <div className="space-y-4">
      {messages.map((m) => {
        const isUser = m.role === "user";
        const isStreaming = m.role === "assistant" && m.status === "streaming";
        const citationsCount = m.citations?.citations?.length ?? 0;
        const isActive = activeCitationsMessageId === m.id;
        const display = isUser ? m.content : stripInlineCitations(m.content);
        const showLoader = !isUser && isStreaming && !display.trim() && !m.error;
        const clarification = !isUser ? m.clarification : undefined;
        const hasDetails =
          !isUser && ((m.agentSteps?.length ?? 0) > 0 || (m.meta && Object.keys(m.meta).length > 0));
        const detailsOpen = detailsOpenId === m.id;

        return (
          <div
            key={m.id}
            className={[
              "flex gap-3",
              isUser ? "justify-end" : "justify-start",
              "transition-opacity duration-300",
            ].join(" ")}
          >
            <div
              className={[
                "max-w-[48rem] rounded-2xl border px-4 py-3 shadow-[0_1px_0_rgba(255,255,255,0.03)]",
                isUser ? "border-border/60 bg-bg/20 text-text" : "border-border/60 bg-panel/60 text-text",
              ].join(" ")}
            >
              <div className="whitespace-pre-wrap text-sm leading-relaxed">
                {showLoader ? (
                  <div className="flex items-center gap-2 text-muted">
                    <TypingDots />
                    <span className="text-xs">Thinking...</span>
                  </div>
                ) : display || (!isUser && isStreaming) ? (
                  <>
                    {display}
                    {!isUser && isStreaming ? <span className="ml-0.5 animate-pulse">▍</span> : null}
                  </>
                ) : (
                  display
                )}
              </div>

              {!isUser && clarification ? (
                <div className="mt-3 rounded-xl border border-border/70 bg-bg/15 p-3">
                  <div className="text-[11px] font-semibold text-text">Clarification needed</div>
                  {display.trim() && display.trim() === (clarification.question || "").trim() ? (
                    <div className="mt-1 text-xs text-muted">Choose an option to continue.</div>
                  ) : (
                    <div className="mt-1 text-xs text-muted">{clarification.question}</div>
                  )}

                  <div className="mt-3 flex flex-wrap gap-2">
                    {clarification.kind === "tickers" || clarification.kind === "comparison_scope" ? (
                      <button
                        type="button"
                        onClick={onOpenTickerPicker}
                        className="inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-bg/25 px-3 py-1.5 text-xs font-semibold text-text hover:bg-bg/40 transition"
                      >
                        Select tickers
                      </button>
                    ) : null}

                    {clarification.options?.length
                      ? clarification.options.map((opt) => (
                          <button
                            key={opt}
                            type="button"
                            onClick={() => onQuickReply(opt)}
                            className="inline-flex items-center rounded-full border border-border/70 bg-bg/25 px-3 py-1.5 text-xs font-semibold text-text hover:bg-bg/40 transition"
                          >
                            {opt}
                          </button>
                        ))
                      : null}
                  </div>
                </div>
              ) : null}

              <div className="mt-2 flex items-center justify-between gap-3 text-[11px] opacity-90">
                <div className="text-muted">{formatTime(m.createdAt)}</div>
                {!isUser ? (
                  <div className="flex items-center gap-2">
                    {m.error ? (
                      <span className="inline-flex items-center gap-1 rounded-full border border-danger/40 bg-danger/10 px-2 py-0.5 text-dangerFg">
                        <TriangleAlert size={12} className="text-danger" />
                        Error
                      </span>
                    ) : null}

                    {hasDetails && !isStreaming ? (
                      <button
                        type="button"
                        onClick={() => setDetailsOpenId((cur) => (cur === m.id ? null : m.id))}
                        className="inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-bg/15 px-2 py-0.5 text-text hover:bg-bg/30 transition"
                        title="Show agent details"
                      >
                        {detailsOpen ? (
                          <ChevronDown size={12} className="text-muted" />
                        ) : (
                          <ChevronRight size={12} className="text-muted" />
                        )}
                        Details
                      </button>
                    ) : null}

                    {citationsCount > 0 && !isStreaming ? (
                      <button
                        type="button"
                        onClick={() => onSelectCitationsMessage(m.id)}
                        className={[
                          "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 transition",
                          isActive
                            ? "border-primary/50 bg-primary/15 text-text"
                            : "border-border/70 bg-bg/15 text-text hover:bg-bg/30",
                        ].join(" ")}
                        title="Show citations"
                      >
                        <Quote size={12} className="text-primary" />
                        Citations
                        <span className="ml-0.5 rounded-full bg-bg/30 px-1.5 py-0.5 text-[10px] text-muted">
                          {citationsCount}
                        </span>
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </div>

              {!isUser && hasDetails && detailsOpen ? (
                <div className="mt-3 rounded-xl border border-border/70 bg-bg/10 p-3 text-[11px] text-muted">
                  <div className="font-semibold text-text">Agent details</div>
                  <div className="mt-2 space-y-1">
                    {(m.agentSteps ?? []).map((s, idx) => (
                      <div key={`${m.id}:step:${idx}`} className="flex flex-wrap gap-2">
                        <span className="rounded-full border border-border/70 bg-bg/20 px-2 py-0.5 font-mono text-[10px] text-text/90">
                          {String(s.step ?? "step")}
                        </span>
                        {formatStepExtras(s as any).map((t) => (
                          <span key={`${m.id}:step:${idx}:${t}`}>{t}</span>
                        ))}
                      </div>
                    ))}
                  </div>

                  {m.meta ? (
                    <details className="mt-3">
                      <summary className="cursor-pointer select-none text-[11px] text-text/90">Raw payload</summary>
                      <pre className="mt-2 max-h-56 overflow-auto rounded-lg border border-border/70 bg-bg/20 p-2 text-[10px] leading-relaxed text-text/90">
                        {JSON.stringify({ meta: m.meta, agentSteps: m.agentSteps ?? [] }, null, 2)}
                      </pre>
                    </details>
                  ) : null}
                </div>
              ) : null}

              {m.error ? (
                <div className="mt-2 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-text">
                  <div className="font-semibold text-danger">Request failed</div>
                  <div className="mt-1 whitespace-pre-wrap text-muted">{m.error}</div>
                </div>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
