"use client";

import { MessageSquarePlus, Trash2 } from "lucide-react";

import type { Conversation } from "@/lib/types";

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString([], { month: "short", day: "2-digit" });
  } catch {
    return "";
  }
}

export function ChatSessions({
  sessions,
  activeId,
  onNew,
  onSelect,
  onDelete,
  showHeader = true,
}: {
  sessions: Conversation[];
  activeId: string | null;
  onNew: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  showHeader?: boolean;
}) {
  return (
    <div className={showHeader ? "rounded-xl border border-border/80 bg-panel/60 p-3 shadow-soft" : undefined}>
      {showHeader ? (
        <div className="flex items-center justify-between gap-2">
          <div>
            <div className="text-xs font-semibold tracking-wide text-text">Chats</div>
            <div className="text-[11px] text-muted">Synced to your account</div>
          </div>
          <button
            type="button"
            onClick={onNew}
            className="inline-flex items-center gap-1.5 rounded-lg border border-primary/40 bg-primary/15 px-2 py-1 text-xs font-semibold text-primaryFg hover:bg-primary/20 transition"
            title="New chat"
          >
            <MessageSquarePlus size={14} className="text-primary" />
            New
          </button>
        </div>
      ) : null}

      {sessions.length === 0 ? (
        <div className={showHeader ? "mt-3 text-sm text-muted" : "text-sm text-muted"}>No chats yet.</div>
      ) : (
        <ul className={showHeader ? "mt-3 space-y-2" : "space-y-2"}>
          {sessions.map((s) => {
            const id = s.conversation_id;
            const isActive = id === activeId;
            return (
              <li key={id}>
                <div
                  className={[
                    "group flex items-center justify-between gap-2 rounded-lg border px-3 py-2 transition",
                    isActive
                      ? "border-primary/40 bg-primary/10"
                      : "border-border/60 bg-transparent hover:bg-bg/20",
                  ].join(" ")}
                >
                  <button
                    type="button"
                    onClick={() => onSelect(id)}
                    className="min-w-0 flex-1 text-left"
                  >
                    <div className="truncate text-sm font-medium text-text">{s.title ?? "New chat"}</div>
                    <div className="mt-0.5 flex items-center gap-2 text-[11px] text-muted">
                      <span>{formatDate(s.created_at)}</span>
                      <span>•</span>
                      <span className="truncate">{s.tickers.join(", ") || "No tickers"}</span>
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(id)}
                    className="rounded-md p-2 text-muted opacity-0 transition hover:bg-bg/35 hover:text-text group-hover:opacity-100"
                    title="Delete chat"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
