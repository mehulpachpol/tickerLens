"use client";

import Link from "next/link";
import { PanelLeft, Plus, Sparkles, Wand2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { ChatComposer } from "@/components/ChatComposer";
import { ChatSessions } from "@/components/ChatSessions";
import { ChatThread } from "@/components/ChatThread";
import { CitationsDrawer } from "@/components/CitationsDrawer";
import { TickerPicker } from "@/components/TickerPicker";
import { streamSse } from "@/lib/sse";
import { loadActiveSessionId, loadSessions, saveActiveSessionId, saveSessions } from "@/lib/storage";
import type { ChatMessage, ChatSession, SseEvent } from "@/lib/types";

function uuid() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function newSession(tickers: string[]): ChatSession {
  return {
    id: uuid(),
    title: "New chat",
    createdAt: Date.now(),
    tickers,
    messages: [],
  };
}

export function ChatApp() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isTickerPickerOpen, setIsTickerPickerOpen] = useState(false);

  const [activeCitationsMessageId, setActiveCitationsMessageId] = useState<string | null>(null);
  const [isCitationsOpen, setIsCitationsOpen] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = () => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  };

  useEffect(() => {
    const s = loadSessions();
    setSessions(s);
    const active = loadActiveSessionId();
    if (active && s.some((x) => x.id === active)) setActiveId(active);
    else if (s[0]) setActiveId(s[0].id);
  }, []);

  useEffect(() => {
    saveSessions(sessions);
  }, [sessions]);

  useEffect(() => {
    if (activeId) saveActiveSessionId(activeId);
  }, [activeId]);

  const activeSession = useMemo(
    () => sessions.find((s) => s.id === activeId) ?? null,
    [sessions, activeId]
  );

  const tickers = activeSession?.tickers ?? [];

  const citationsPayload = useMemo(() => {
    if (!activeSession || !activeCitationsMessageId) return undefined;
    const msg = activeSession.messages.find((m) => m.id === activeCitationsMessageId);
    return msg?.citations;
  }, [activeSession, activeCitationsMessageId]);

  const setSessionTickers = (next: string[]) => {
    if (!activeSession) {
      const s = newSession(next);
      setSessions((prev) => [s, ...prev]);
      setActiveId(s.id);
      return;
    }
    setSessions((prev) => prev.map((s) => (s.id === activeSession.id ? { ...s, tickers: next } : s)));
  };

  const onNew = () => {
    const s = newSession(activeSession?.tickers ?? []);
    setSessions((prev) => [s, ...prev]);
    setActiveId(s.id);
    setActiveCitationsMessageId(null);
    setIsCitationsOpen(false);
    setInput("");
  };

  const onDelete = (id: string) => {
    setSessions((prev) => {
      const remaining = prev.filter((s) => s.id !== id);
      if (activeId === id) {
        setActiveId(remaining[0]?.id ?? null);
        setActiveCitationsMessageId(null);
        setIsCitationsOpen(false);
      }
      return remaining;
    });
  };

  const updateTitleIfNeeded = (sessionId: string, question: string) => {
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id !== sessionId) return s;
        if (s.title !== "New chat") return s;
        return { ...s, title: question.slice(0, 56).trim() || "Chat" };
      })
    );
  };

  const appendMessage = (sessionId: string, msg: ChatMessage) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === sessionId ? { ...s, messages: [...s.messages, msg] } : s))
    );
    requestAnimationFrame(scrollToBottom);
  };

  const patchMessage = (sessionId: string, messageId: string, patch: Partial<ChatMessage>) => {
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id !== sessionId) return s;
        return {
          ...s,
          messages: s.messages.map((m) => (m.id === messageId ? { ...m, ...patch } : m)),
        };
      })
    );
  };

  const appendDelta = (sessionId: string, messageId: string, delta: string) => {
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id !== sessionId) return s;
        return {
          ...s,
          messages: s.messages.map((m) => (m.id === messageId ? { ...m, content: m.content + delta } : m)),
        };
      })
    );
    requestAnimationFrame(scrollToBottom);
  };

  const stop = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
  };

  const handleEvent = (sessionId: string, assistantId: string, evt: SseEvent) => {
    if (evt.event === "delta") {
      appendDelta(sessionId, assistantId, evt.data.delta);
      return;
    }
    if (evt.event === "citations") {
      patchMessage(sessionId, assistantId, { citations: evt.data });
      // Do not auto-open: user explicitly asked citations should open only on click.
      return;
    }
    if (evt.event === "done") {
      patchMessage(sessionId, assistantId, { status: "done" });
      return;
    }
    if (evt.event === "error") {
      patchMessage(sessionId, assistantId, { error: evt.data.error, status: "done" });
      return;
    }
  };

  const send = async () => {
    if (isStreaming) return;
    const question = input.trim();
    if (!question) return;

    let session = activeSession;
    if (!session) {
      session = newSession([]);
      setSessions((prev) => [session!, ...prev]);
      setActiveId(session.id);
    }

    if (!session.tickers.length) {
      setIsTickerPickerOpen(true);
      return;
    }

    setInput("");
    updateTitleIfNeeded(session.id, question);
    setIsCitationsOpen(false);

    const userMsg: ChatMessage = { id: uuid(), role: "user", content: question, createdAt: Date.now() };
    const assistantMsg: ChatMessage = {
      id: uuid(),
      role: "assistant",
      content: "",
      createdAt: Date.now(),
      status: "streaming",
    };

    appendMessage(session.id, userMsg);
    appendMessage(session.id, assistantMsg);

    setIsStreaming(true);
    const ac = new AbortController();
    abortRef.current = ac;

    let aborted = false;

    try {
      const res = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          tickers: session.tickers,
          top_k: 8,
          rerank_top_n: 30,
          passage_max_chars: 600,
          rerank_backend: "fastembed",
        }),
        signal: ac.signal,
      });

      for await (const evt of streamSse(res)) {
        handleEvent(session.id, assistantMsg.id, evt);
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") {
        aborted = true;
        patchMessage(session.id, assistantMsg.id, { status: "stopped" });
        return;
      }
      const msg = e instanceof Error ? e.message : String(e);
      patchMessage(session.id, assistantMsg.id, { error: msg, status: "done" });
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
      if (!aborted) patchMessage(session.id, assistantMsg.id, { status: "done" });
    }
  };

  useEffect(() => {
    requestAnimationFrame(scrollToBottom);
  }, [activeId]);

  const selectedCitations = citationsPayload;

  return (
    <div className="flex h-dvh">
      {/* Sidebar */}
      <aside
        className={[
          "hidden h-full w-[320px] shrink-0 border-r border-border/70 bg-panel/60 lg:block",
          sidebarOpen ? "lg:block" : "lg:hidden",
        ].join(" ")}
      >
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between gap-2 border-b border-border/60 px-3 py-3">
            <button
              type="button"
              onClick={onNew}
              className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl border border-border/70 bg-bg/20 px-3 py-2 text-sm font-semibold text-text hover:bg-bg/35 transition"
            >
              <Plus size={16} className="text-primary" />
              New chat
            </button>
            <button
              type="button"
              onClick={() => setSidebarOpen(false)}
              className="rounded-xl border border-border/70 bg-bg/20 p-2 text-muted hover:bg-bg/35 hover:text-text transition"
              aria-label="Hide sidebar"
              title="Hide sidebar"
            >
              <PanelLeft size={16} />
            </button>
          </div>

          <div className="flex-1 overflow-auto p-3 no-scrollbar">
            <ChatSessions
              sessions={sessions}
              activeId={activeId}
              onNew={onNew}
              onSelect={(id) => {
                setActiveId(id);
                setActiveCitationsMessageId(null);
                setIsCitationsOpen(false);
              }}
              onDelete={onDelete}
              showHeader={false}
            />
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between gap-2 border-b border-border/60 bg-bg/40 px-4 py-3 backdrop-blur">
          <div className="flex items-center gap-2">
            {!sidebarOpen && <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              className="hidden rounded-xl border border-border/70 bg-panel/50 p-2 text-muted hover:bg-panel/70 hover:text-text transition lg:inline-flex"
              aria-label="Show sidebar"
              title="Show sidebar"
            >
              <PanelLeft size={16} />
            </button>}
            <Sparkles size={16} className="text-primary" />
            <div className="text-sm font-semibold">TickerLens</div>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/timeline"
              className="rounded-xl border border-border/70 bg-panel/50 px-3 py-2 text-sm font-semibold text-text hover:bg-panel/70 transition"
              title="Open document timeline"
            >
              Timeline
            </Link>

            <div className="hidden items-center gap-2 text-xs text-muted md:flex">
            {tickers.length ? (
              <span className="hidden md:inline">
                Scope: <span className="font-semibold text-text">{tickers.join(", ")}</span>
              </span>
            ) : (
              <span className="hidden md:inline-flex items-center gap-1">
                <Wand2 size={14} className="text-muted" />
                Select tickers to start
              </span>
            )}
            </div>
          </div>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-auto px-4 py-6 no-scrollbar">
          <div className="mx-auto w-full max-w-3xl">
            {activeSession && activeSession.messages.length ? (
              <ChatThread
                messages={activeSession.messages}
                activeCitationsMessageId={activeCitationsMessageId}
                onSelectCitationsMessage={(id) => {
                  setActiveCitationsMessageId(id);
                  setIsCitationsOpen(true);
                }}
              />
            ) : (
              <div className="mx-auto max-w-xl rounded-2xl border border-border/70 bg-panel/40 p-6 text-sm text-muted">
                <div className="text-base font-semibold text-text">Ask an analyst-style question</div>
                <ul className="mt-3 list-disc space-y-1 pl-5">
                  <li>"What risks did the company highlight in FY24?"</li>
                  <li>"Summarize management commentary on AI initiatives."</li>
                  <li>"Show mentions of capex and EV investments."</li>
                </ul>
              </div>
            )}
          </div>
        </div>

        <div className="border-t border-border/60 bg-gradient-to-b from-bg/20 to-bg/60 px-4 pb-5 pt-4 backdrop-blur">
          <div className="mx-auto w-full max-w-3xl">
            <ChatComposer
              value={input}
              onChange={setInput}
              onSend={send}
              onStop={stop}
              isStreaming={isStreaming}
              disabled={tickers.length === 0}
              tickers={tickers}
              onOpenTickerPicker={() => setIsTickerPickerOpen(true)}
              onRemoveTicker={(t) => setSessionTickers(tickers.filter((x) => x !== t))}
            />
          </div>
        </div>
      </main>

      <TickerPicker
        value={tickers}
        onChange={setSessionTickers}
        open={isTickerPickerOpen}
        onOpenChange={setIsTickerPickerOpen}
      />

      <CitationsDrawer open={isCitationsOpen} onOpenChange={setIsCitationsOpen} payload={selectedCitations} />
    </div>
  );
}
