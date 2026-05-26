"use client";

import { ArrowUp, Plus, Square, X } from "lucide-react";
import type { KeyboardEventHandler } from "react";
import { useEffect, useRef } from "react";

export function ChatComposer({
  value,
  onChange,
  onSend,
  onStop,
  isStreaming,
  disabled,
  tickers,
  onOpenTickerPicker,
  onRemoveTicker,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onStop: () => void;
  isStreaming: boolean;
  disabled: boolean;
  tickers: string[];
  onOpenTickerPicker: () => void;
  onRemoveTicker: (ticker: string) => void;
}) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 176)}px`;
  }, [value]);

  const onKeyDown: KeyboardEventHandler<HTMLTextAreaElement> = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="rounded-2xl bg-panel/70 ring-1 ring-border/70 transition focus-within:ring-primary/40">
      {tickers.length ? (
        <div className="flex flex-wrap gap-1.5 px-3 pt-2">
          {tickers.map((t) => (
            <span
              key={t}
              className="inline-flex items-center gap-1 rounded-full border border-border/70 bg-bg/25 px-2.5 py-1 text-[11px] text-text hover:bg-bg/35 transition"
            >
              <span className="font-semibold">{t}</span>
              <button
                type="button"
                onClick={() => onRemoveTicker(t)}
                className="rounded-full p-0.5 text-muted hover:bg-bg/40 hover:text-text transition"
                aria-label={`Remove ${t}`}
                disabled={isStreaming}
                title="Remove ticker"
              >
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
      ) : null}

      <div className="flex items-end gap-2 p-2">
        <button
          type="button"
          onClick={onOpenTickerPicker}
          className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-border/70 bg-bg/20 text-text hover:bg-bg/30 transition disabled:opacity-50"
          title="Add tickers"
          aria-label="Add tickers"
          disabled={isStreaming}
        >
          <Plus size={16} className="text-primary" />
        </button>

        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={disabled ? "Add tickers to start..." : "Message TickerLens..."}
          rows={1}
          className="no-scrollbar max-h-44 w-full resize-none overflow-y-auto bg-transparent px-1.5 py-2 text-sm leading-relaxed text-text placeholder:text-muted outline-none disabled:opacity-70 [scrollbar-gutter:stable]"
        />

        {isStreaming ? (
          <button
            type="button"
            onClick={onStop}
            className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-danger/40 bg-danger/15 text-dangerFg hover:bg-danger/20 transition"
            title="Stop"
            aria-label="Stop"
          >
            <Square size={16} className="text-danger" />
          </button>
        ) : (
          <button
            type="button"
            onClick={onSend}
            disabled={!value.trim()}
            className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-border/70 bg-bg/20 text-text hover:bg-bg/30 transition disabled:opacity-50"
            title="Send"
            aria-label="Send"
          >
            <ArrowUp size={16} className="text-primary" />
          </button>
        )}
      </div>

    </div>
  );
}
