"use client";

import { Quote, TriangleAlert } from "lucide-react";

import type { ChatMessage } from "@/lib/types";

const INLINE_CITATION_RE = /\[\(chunk_id=[^)]+\)\]/g;

function stripInlineCitations(text: string) {
  return (text || "").replace(INLINE_CITATION_RE, "").replace(/[ \t]+\n/g, "\n").trim();
}

function formatTime(ts: number) {
  try {
    return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export function ChatThread({
  messages,
  activeCitationsMessageId,
  onSelectCitationsMessage,
}: {
  messages: ChatMessage[];
  activeCitationsMessageId: string | null;
  onSelectCitationsMessage: (id: string) => void;
}) {
  return (
    <div className="space-y-4">
      {messages.map((m) => {
        const isUser = m.role === "user";
        const isStreaming = m.role === "assistant" && m.status === "streaming";
        const citationsCount = m.citations?.citations?.length ?? 0;
        const isActive = activeCitationsMessageId === m.id;
        const display = isUser ? m.content : stripInlineCitations(m.content);

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
                {display || (!isUser && isStreaming) ? (
                  <>
                    {display}
                    {!isUser && isStreaming ? <span className="ml-0.5 animate-pulse">▍</span> : null}
                  </>
                ) : (
                  display
                )}
              </div>

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
