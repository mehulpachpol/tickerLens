"use client";

import { Check, Search, Tags, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { NIFTY_50 } from "@/lib/nifty50";

export function TickerPicker({
  value,
  onChange,
  open,
  onOpenChange,
}: {
  value: string[];
  onChange: (next: string[]) => void;
  open: boolean;
  onOpenChange: (next: boolean) => void;
}) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement | null>(null);
  const selected = useMemo(() => new Set(value), [value]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return NIFTY_50;
    return NIFTY_50.filter(
      (c) => c.ticker.toLowerCase().includes(q) || c.name.toLowerCase().includes(q)
    );
  }, [query]);

  const toggle = (ticker: string) => {
    if (selected.has(ticker)) {
      onChange(value.filter((t) => t !== ticker));
    } else {
      onChange([...value, ticker]);
    }
  };

  useEffect(() => {
    if (!open) {
      setQuery("");
      return;
    }
    // Give the sheet one frame to mount/animate, then focus.
    requestAnimationFrame(() => inputRef.current?.focus());
  }, [open]);

  return (
    <div className={["fixed inset-0 z-50", open ? "pointer-events-auto" : "pointer-events-none"].join(" ")}>
      <button
        type="button"
        className={[
          "absolute inset-0 bg-black/40 backdrop-blur-sm transition-opacity duration-200",
          open ? "opacity-100" : "opacity-0",
        ].join(" ")}
        onClick={() => onOpenChange(false)}
        aria-label="Close ticker picker"
      />

      <div
        className={[
          "absolute bottom-6 left-1/2 w-[min(720px,calc(100vw-2rem))] -translate-x-1/2 rounded-2xl border border-border/70 bg-panel/90 shadow-soft transition-all duration-200",
          open ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0",
        ].join(" ")}
      >
        <div className="flex items-center justify-between gap-3 border-b border-border/60 px-4 py-3">
          <div className="flex items-center gap-2">
            <Tags size={16} className="text-primary" />
            <div>
              <div className="text-sm font-semibold">Select tickers</div>
              <div className="text-[11px] text-muted">Universe: Nifty 50</div>
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

        <div className="px-4 py-3">
          {value.length > 0 ? (
            <div className="mb-3 flex flex-wrap gap-1.5">
              {value.map((t) => (
                <span
                  key={t}
                  className="inline-flex items-center gap-1 rounded-full border border-border/70 bg-bg/30 px-2 py-1 text-[11px] text-text"
                >
                  <span className="font-medium">{t}</span>
                  <button
                    type="button"
                    onClick={() => toggle(t)}
                    className="rounded-full p-0.5 text-muted hover:bg-bg/40 hover:text-text transition"
                    aria-label={`Remove ${t}`}
                  >
                    <X size={12} />
                  </button>
                </span>
              ))}
            </div>
          ) : (
            <div className="mb-3 text-sm text-muted">
              Choose one or more tickers to scope retrieval.
            </div>
          )}

          <div className="flex items-center gap-2 rounded-xl border border-border/70 bg-bg/25 px-3 py-2">
            <Search size={16} className="text-muted" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search (e.g. INFY, Reliance)..."
              className="w-full bg-transparent text-sm text-text placeholder:text-muted outline-none"
            />
            {query ? (
              <button
                type="button"
                onClick={() => setQuery("")}
                className="rounded-lg p-1 text-muted hover:bg-bg/35 hover:text-text transition"
                aria-label="Clear search"
              >
                <X size={16} />
              </button>
            ) : null}
          </div>
        </div>

        <div className="max-h-80 overflow-auto border-t border-border/60">
          <ul className="divide-y divide-border/50">
            {filtered.map((c) => {
              const isSelected = selected.has(c.ticker);
              return (
                <li key={c.ticker}>
                  <button
                    type="button"
                    onClick={() => toggle(c.ticker)}
                    className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-bg/30 transition"
                  >
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-text">{c.ticker}</div>
                      <div className="truncate text-xs text-muted">{c.name}</div>
                    </div>
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-border/70 bg-bg/25">
                      {isSelected ? <Check size={16} className="text-primary" /> : null}
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-border/60 px-4 py-3">
          <div className="text-[11px] text-muted">
            Selected: <span className="font-semibold text-text">{value.length}</span>
          </div>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded-xl border border-primary/40 bg-primary/15 px-3 py-2 text-sm font-semibold text-primaryFg hover:bg-primary/20 transition"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
