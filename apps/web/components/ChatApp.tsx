"use client";

import {
  BarChart3,
  ChevronRight,
  FileSearch,
  HelpCircle,
  LogOut,
  PanelLeft,
  Plus,
  Settings,
  ShieldAlert,
  SlidersHorizontal,
  Sparkles,
  UserRound,
} from "lucide-react";
import { useRouter } from "next/navigation";
import type { ComponentType } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import { ChatComposer } from "@/components/ChatComposer";
import { ChatSessions } from "@/components/ChatSessions";
import { ChatThread } from "@/components/ChatThread";
import { CitationsDrawer } from "@/components/CitationsDrawer";
import { TickerPicker } from "@/components/TickerPicker";
import { streamSse } from "@/lib/sse";
import { saveActiveConversationId } from "@/lib/storage";
import type { AgentStep, ChatMessage, ClarificationPayload, Conversation, RagRun, SseEvent } from "@/lib/types";

function uuid() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function initialsFromEmail(email: string | null): string {
  if (!email) return "U";
  const local = email.split("@")[0] ?? email;
  const parts = local.split(/[._-]+/).filter(Boolean);
  if (parts.length >= 2) return `${parts[0][0] ?? "U"}${parts[1][0] ?? ""}`.toUpperCase();
  const s = parts[0] ?? local;
  return s.slice(0, 2).toUpperCase();
}

const STARTER_PROMPTS: Array<{ icon: ComponentType<{ size?: number; className?: string }>; title: string; text: string }> =
  [
    {
      icon: ShieldAlert,
      title: "Risk factors",
      text: "What risks did the company highlight in FY24?",
    },
    {
      icon: FileSearch,
      title: "Management commentary",
      text: "Summarize management commentary on AI initiatives.",
    },
    {
      icon: BarChart3,
      title: "Capex + investments",
      text: "Show mentions of capex and EV investments.",
    },
  ];


function isoToMs(iso: string | undefined | null): number {
  if (!iso) return Date.now();
  const t = Date.parse(iso);
  return Number.isFinite(t) ? t : Date.now();
}

function clarificationFromRun(r: RagRun): ClarificationPayload | undefined {
  const steps = (r.retrieval as any)?.agent?.steps;
  if (!Array.isArray(steps)) return undefined;
  const s = steps.find((x: any) => x && x.step === "ask_clarifying_question");
  if (!s) return undefined;
  return {
    kind: typeof s.kind === "string" ? s.kind : "other",
    question: r.answer ?? "",
    options: Array.isArray(s.options) ? s.options : null,
  };
}

function runsToThread(runs: RagRun[]): ChatMessage[] {
  const ordered = [...runs].sort((a, b) => isoToMs(a.created_at) - isoToMs(b.created_at));
  const out: ChatMessage[] = [];
  for (const r of ordered) {
    const ts = isoToMs(r.created_at);
    out.push({ id: `${r.run_id}:user`, role: "user", content: r.question, createdAt: ts });

    const agentSteps = ((r.retrieval as any)?.agent?.steps ?? undefined) as AgentStep[] | undefined;
    const clarification = clarificationFromRun(r);
    out.push({
      id: `${r.run_id}:assistant`,
      role: "assistant",
      content: r.answer ?? "",
      createdAt: ts + 1,
      citations: r.citations ?? undefined,
      agentSteps,
      clarification,
      meta: r.timings_ms || r.models ? { timings_ms: r.timings_ms ?? undefined, models: r.models ?? undefined } : undefined,
      status: "done",
    });
  }
  return out;
}

export function ChatApp() {
  const router = useRouter();

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [threads, setThreads] = useState<Record<string, ChatMessage[]>>({});
  const [draftTickers, setDraftTickers] = useState<string[]>([]);

  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);

  const [authStatus, setAuthStatus] = useState<"unknown" | "disabled" | "authed" | "unauthed">("unknown");
  const [userEmail, setUserEmail] = useState<string | null>(null);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isTickerPickerOpen, setIsTickerPickerOpen] = useState(false);

  const [activeCitationsMessageId, setActiveCitationsMessageId] = useState<string | null>(null);
  const [isCitationsOpen, setIsCitationsOpen] = useState(false);

  const [profileMenuOpen, setProfileMenuOpen] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = () => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  };

  const activeConversation = useMemo(
    () => conversations.find((c) => c.conversation_id === activeId) ?? null,
    [conversations, activeId]
  );

  const activeMessages = useMemo(() => (activeId ? threads[activeId] ?? [] : []), [threads, activeId]);
  const tickers = activeConversation?.tickers ?? draftTickers;

  const citationsPayload = useMemo(() => {
    if (!activeCitationsMessageId) return undefined;
    const msg = activeMessages.find((m) => m.id === activeCitationsMessageId);
    return msg?.citations;
  }, [activeMessages, activeCitationsMessageId]);

  const refreshConversations = async (preferredActiveId?: string | null) => {
    const res = await fetch("/api/conversations?limit=100", { method: "GET", headers: { Accept: "application/json" } });
    if (!res.ok) return;
    const data = (await res.json()) as Conversation[];
    setConversations(data);

    // Default UX: show a "New chat" screen after login (do not auto-open an older conversation).
    // When a specific conversation is requested (e.g. after creating/sending), we set it active.
    if (preferredActiveId) {
      const nextActive = data.some((c) => c.conversation_id === preferredActiveId) ? preferredActiveId : null;
      setActiveId(nextActive);
      if (nextActive) saveActiveConversationId(nextActive);
      return;
    }

    // If the current active conversation was deleted elsewhere, clear it.
    if (activeId && !data.some((c) => c.conversation_id === activeId)) {
      setActiveId(null);
    }
  };

  const loadThread = async (conversationId: string) => {
    const res = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}/runs?limit=200&include_payloads=true`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return;
    const runs = (await res.json()) as RagRun[];
    const thread = runsToThread(runs);
    setThreads((prev) => ({ ...prev, [conversationId]: thread }));
    requestAnimationFrame(scrollToBottom);
  };

  useEffect(() => {
    refreshConversations().catch(() => { });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!activeId) return;
    if (threads[activeId]) return;
    loadThread(activeId).catch(() => { });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId]);

  useEffect(() => {
    if (activeId) saveActiveConversationId(activeId);
  }, [activeId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/auth/me", { method: "GET", headers: { Accept: "application/json" } });
        if (cancelled) return;
        if (res.status === 200) {
          const data = (await res.json()) as { user?: { email?: string } };
          setAuthStatus("authed");
          setUserEmail(data.user?.email ?? null);
          return;
        }
        if (res.status === 400) {
          setAuthStatus("disabled");
          router.replace("/auth-disabled");
          return;
        }
        if (res.status === 401) {
          setAuthStatus("unauthed");
          router.replace(`/login?next=${encodeURIComponent("/")}`);
          return;
        }
        setAuthStatus("disabled");
        router.replace("/auth-disabled");
      } catch {
        setAuthStatus("disabled");
        router.replace("/auth-disabled");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  useEffect(() => {
    if (!profileMenuOpen) return;

    const onMouseDown = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null;
      if (!target) return;
      if (target.closest('[data-profile-menu="true"]')) return;
      setProfileMenuOpen(false);
    };

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setProfileMenuOpen(false);
    };

    window.addEventListener("mousedown", onMouseDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("mousedown", onMouseDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [profileMenuOpen]);

  const doLogout = async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST", headers: { Accept: "application/json" } });
    } finally {
      setProfileMenuOpen(false);
      router.replace("/login?next=%2F");
    }
  };

  const upsertConversationTickers = async (nextTickers: string[]) => {
    if (!activeConversation) {
      // Do not create a DB conversation until the user sends the first message.
      setDraftTickers(nextTickers);
      return;
    }

    // Optimistic update for responsiveness.
    setConversations((prev) =>
      prev.map((c) => (c.conversation_id === activeConversation.conversation_id ? { ...c, tickers: nextTickers } : c))
    );
    await fetch(`/api/conversations/${encodeURIComponent(activeConversation.conversation_id)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ tickers: nextTickers }),
    }).catch(() => { });
  };

  const onNew = async () => {
    // New chat is a local draft. Persist to DB only after the first user message.
    setActiveId(null);
    setDraftTickers([]);
    setActiveCitationsMessageId(null);
    setIsCitationsOpen(false);
    setProfileMenuOpen(false);
    setInput("");
    setSidebarOpen(false);
  };

  const onDelete = async (id: string) => {
    const res = await fetch(`/api/conversations/${encodeURIComponent(id)}`, {
      method: "DELETE",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return;

    setConversations((prev) => prev.filter((c) => c.conversation_id !== id));
    setThreads((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });

    if (activeId === id) {
      const remaining = conversations.filter((c) => c.conversation_id !== id);
      const nextActive = remaining[0]?.conversation_id ?? null;
      setActiveId(nextActive);
      setActiveCitationsMessageId(null);
      setIsCitationsOpen(false);
    }
  };

  const stop = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
  };

  const patchThreadMessage = (
    conversationId: string,
    messageId: string,
    patch: Partial<ChatMessage> | ((prev: ChatMessage) => ChatMessage)
  ) => {
    setThreads((prev) => {
      const cur = prev[conversationId] ?? [];
      return {
        ...prev,
        [conversationId]: cur.map((m) => {
          if (m.id !== messageId) return m;
          if (typeof patch === "function") return patch(m);
          return { ...m, ...patch };
        }),
      };
    });
  };

  const appendDelta = (conversationId: string, messageId: string, delta: string) => {
    setThreads((prev) => {
      const cur = prev[conversationId] ?? [];
      return {
        ...prev,
        [conversationId]: cur.map((m) => (m.id === messageId ? { ...m, content: m.content + delta } : m)),
      };
    });
    requestAnimationFrame(scrollToBottom);
  };

  const handleEvent = (conversationId: string, assistantId: string, evt: SseEvent) => {
    if (evt.event === "meta") {
      patchThreadMessage(conversationId, assistantId, (prev) => ({ ...prev, meta: evt.data }));
      return;
    }
    if (evt.event === "agent_step") {
      patchThreadMessage(conversationId, assistantId, (prev) => ({
        ...prev,
        agentSteps: [...(prev.agentSteps ?? []), evt.data],
      }));
      return;
    }
    if (evt.event === "clarify") {
      patchThreadMessage(conversationId, assistantId, (prev) => ({
        ...prev,
        clarification: evt.data,
        status: "done",
      }));

      // If the agent needs ticker input, open the picker immediately.
      if (evt.data.kind === "tickers" || evt.data.kind === "comparison_scope") {
        setIsTickerPickerOpen(true);
      }
      return;
    }
    if (evt.event === "delta") {
      appendDelta(conversationId, assistantId, evt.data.delta);
      return;
    }
    if (evt.event === "citations") {
      patchThreadMessage(conversationId, assistantId, { citations: evt.data });
      return;
    }
    if (evt.event === "done") {
      patchThreadMessage(conversationId, assistantId, { status: "done" });
      return;
    }
    if (evt.event === "error") {
      patchThreadMessage(conversationId, assistantId, { error: evt.data.error, status: "done" });
      return;
    }
  };

  const send = async () => {
    await sendText(input);
  };

  const sendText = async (question: string) => {
    if (isStreaming) return;
    const q = question.trim();
    if (!q) return;

    let conversationId = activeConversation?.conversation_id ?? null;
    if (!conversationId) {
      // Create a conversation on-demand so the run is persisted.
      const createRes = await fetch("/api/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ title: null, tickers }),
      });
      if (!createRes.ok) return;
      const c = (await createRes.json()) as Conversation;
      setDraftTickers([]);
      setConversations((prev) => [c, ...prev]);
      setActiveId(c.conversation_id);
      setThreads((prev) => ({ ...prev, [c.conversation_id]: prev[c.conversation_id] ?? [] }));
      conversationId = c.conversation_id;
    }

    setInput("");
    setIsCitationsOpen(false);

    const userMsg: ChatMessage = { id: uuid(), role: "user", content: q, createdAt: Date.now() };
    const assistantId = uuid();
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      createdAt: Date.now(),
      status: "streaming",
    };

    setThreads((prev) => {
      const cur = prev[conversationId!] ?? [];
      return { ...prev, [conversationId!]: [...cur, userMsg, assistantMsg] };
    });
    requestAnimationFrame(scrollToBottom);

    setIsStreaming(true);
    const ac = new AbortController();
    abortRef.current = ac;

    let aborted = false;
    try {
      const res = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversation_id: conversationId,
          question: q,
          tickers,
          top_k: 8,
          rerank_top_n: 30,
          passage_max_chars: 600,
          rerank_backend: "fastembed",
        }),
        signal: ac.signal,
      });

      for await (const evt of streamSse(res)) {
        handleEvent(conversationId!, assistantId, evt);
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") {
        aborted = true;
        patchThreadMessage(conversationId!, assistantId, { status: "stopped" });
        return;
      }
      const msg = e instanceof Error ? e.message : String(e);
      patchThreadMessage(conversationId!, assistantId, { error: msg, status: "done" });
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
      if (!aborted) patchThreadMessage(conversationId!, assistantId, { status: "done" });
      setActiveCitationsMessageId(null);
      setIsCitationsOpen(false);

      // Refresh to pick up canonical title/tickers + persisted history.
      await refreshConversations(conversationId);
      await loadThread(conversationId!);
    }
  };

  const onStarterPrompt = async (text: string) => {
    if (isStreaming) return;
    await sendText(text);
  };

  useEffect(() => {
    requestAnimationFrame(scrollToBottom);
  }, [activeId]);

  const selectedCitations = citationsPayload;

  return (
    <div className="flex h-dvh">
      {/* Sidebar */}
      {sidebarOpen ? (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-black/35 backdrop-blur-[2px] lg:hidden"
          aria-label="Close sidebar overlay"
          onClick={() => {
            setSidebarOpen(false);
            setProfileMenuOpen(false);
          }}
        />
      ) : null}

      {/* Mobile sidebar (drawer) */}
      <aside
        className={[
          "fixed inset-y-0 left-0 z-50 w-[320px] border-r border-border/70 bg-panel/85 backdrop-blur transition-transform duration-200 lg:hidden",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
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
              onClick={() => {
                setSidebarOpen(false);
                setProfileMenuOpen(false);
              }}
              className="rounded-xl border border-border/70 bg-bg/20 p-2 text-muted hover:bg-bg/35 hover:text-text transition"
              aria-label="Hide sidebar"
              title="Hide sidebar"
            >
              <PanelLeft size={16} />
            </button>
          </div>

          <div className="flex-1 overflow-auto p-3 no-scrollbar">
            <ChatSessions
              sessions={conversations}
              activeId={activeId}
              onNew={onNew}
              onSelect={(id) => {
                setActiveId(id);
                setSidebarOpen(false);
                setProfileMenuOpen(false);
                setActiveCitationsMessageId(null);
                setIsCitationsOpen(false);
              }}
              onDelete={onDelete}
              showHeader={false}
            />
          </div>

          <div className="border-t border-border/60 p-3" data-profile-menu="true">
            <div className="relative" data-profile-menu="true">
              {profileMenuOpen ? (
                <div
                  role="menu"
                  className="absolute bottom-12 left-0 right-0 z-10 overflow-hidden rounded-2xl border border-border/70 bg-panel/90 shadow-soft backdrop-blur"
                >
                  <div className="flex items-center gap-3 px-3 py-2.5">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-border/70 bg-bg/25 text-xs font-bold text-text">
                      {initialsFromEmail(userEmail)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-semibold text-text">{userEmail ?? "Signed in"}</div>
                      <div className="truncate text-xs text-muted">TickerLens account</div>
                    </div>
                    <ChevronRight size={16} className="text-muted" />
                  </div>

                  <div className="h-px bg-border/50" />

                  <div className="p-1.5">
                    {[
                      { label: "Profile", icon: UserRound },
                      { label: "Personalization", icon: SlidersHorizontal },
                      { label: "Settings", icon: Settings },
                      { label: "Help", icon: HelpCircle },
                    ].map((item) => (
                      <button
                        key={item.label}
                        type="button"
                        disabled
                        className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm text-text hover:bg-bg/20 transition disabled:cursor-not-allowed disabled:opacity-60"
                        title="Coming soon"
                        role="menuitem"
                      >
                        <item.icon size={16} className="text-muted" />
                        <span className="flex-1 text-left">{item.label}</span>
                      </button>
                    ))}
                  </div>

                  <div className="h-px bg-border/50" />

                  <div className="p-1.5">
                    <button
                      type="button"
                      onClick={doLogout}
                      className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm text-dangerFg hover:bg-danger/15 transition"
                      role="menuitem"
                    >
                      <LogOut size={16} className="text-danger" />
                      <span className="flex-1 text-left">Log out</span>
                    </button>
                  </div>
                </div>
              ) : null}

              <button
                type="button"
                onClick={() => setProfileMenuOpen((v) => !v)}
                className="flex w-full items-center justify-between gap-3 rounded-2xl border border-border/70 bg-bg/20 px-3 py-2.5 hover:bg-bg/30 transition"
                aria-haspopup="menu"
                aria-expanded={profileMenuOpen}
              >
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-border/70 bg-bg/25 text-xs font-bold text-text">
                    {initialsFromEmail(userEmail)}
                  </div>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-text">{userEmail ?? "Account"}</div>
                    <div className="truncate text-xs text-muted">Account</div>
                  </div>
                </div>
                <ChevronRight size={16} className="text-muted" />
              </button>
            </div>
          </div>
        </div>
      </aside>

      {/* Desktop sidebar (layout) */}
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
              onClick={() => {
                setSidebarOpen(false);
                setProfileMenuOpen(false);
              }}
              className="rounded-xl border border-border/70 bg-bg/20 p-2 text-muted hover:bg-bg/35 hover:text-text transition"
              aria-label="Hide sidebar"
              title="Hide sidebar"
            >
              <PanelLeft size={16} />
            </button>
          </div>

          <div className="flex-1 overflow-auto p-3 no-scrollbar">
            <ChatSessions
              sessions={conversations}
              activeId={activeId}
              onNew={onNew}
              onSelect={(id) => {
                setActiveId(id);
                setProfileMenuOpen(false);
                setActiveCitationsMessageId(null);
                setIsCitationsOpen(false);
              }}
              onDelete={onDelete}
              showHeader={false}
            />
          </div>

          <div className="border-t border-border/60 p-3" data-profile-menu="true">
            <div className="relative" data-profile-menu="true">
              {profileMenuOpen ? (
                <div
                  role="menu"
                  className="absolute bottom-12 left-0 right-0 z-10 overflow-hidden rounded-2xl border border-border/70 bg-panel/90 shadow-soft backdrop-blur"
                >
                  <div className="flex items-center gap-3 px-3 py-2.5">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-border/70 bg-bg/25 text-xs font-bold text-text">
                      {initialsFromEmail(userEmail)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-semibold text-text">{userEmail ?? "Signed in"}</div>
                      <div className="truncate text-xs text-muted">TickerLens account</div>
                    </div>
                    <ChevronRight size={16} className="text-muted" />
                  </div>

                  <div className="h-px bg-border/50" />

                  <div className="p-1.5">
                    {[
                      { label: "Profile", icon: UserRound },
                      { label: "Personalization", icon: SlidersHorizontal },
                      { label: "Settings", icon: Settings },
                      { label: "Help", icon: HelpCircle },
                    ].map((item) => (
                      <button
                        key={item.label}
                        type="button"
                        disabled
                        className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm text-text hover:bg-bg/20 transition disabled:cursor-not-allowed disabled:opacity-60"
                        title="Coming soon"
                        role="menuitem"
                      >
                        <item.icon size={16} className="text-muted" />
                        <span className="flex-1 text-left">{item.label}</span>
                      </button>
                    ))}
                  </div>

                  <div className="h-px bg-border/50" />

                  <div className="p-1.5">
                    <button
                      type="button"
                      onClick={doLogout}
                      className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm text-dangerFg hover:bg-danger/15 transition"
                      role="menuitem"
                    >
                      <LogOut size={16} className="text-danger" />
                      <span className="flex-1 text-left">Log out</span>
                    </button>
                  </div>
                </div>
              ) : null}

              <button
                type="button"
                onClick={() => setProfileMenuOpen((v) => !v)}
                className="flex w-full items-center justify-between gap-3 rounded-2xl border border-border/70 bg-bg/20 px-3 py-2.5 hover:bg-bg/30 transition"
                aria-haspopup="menu"
                aria-expanded={profileMenuOpen}
              >
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-border/70 bg-bg/25 text-xs font-bold text-text">
                    {initialsFromEmail(userEmail)}
                  </div>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-text">{userEmail ?? "Account"}</div>
                    <div className="truncate text-xs text-muted">Account</div>
                  </div>
                </div>
                <ChevronRight size={16} className="text-muted" />
              </button>
            </div>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between gap-2 border-b border-border/60 bg-bg/40 px-4 py-3 backdrop-blur">
          <div className="flex items-center gap-2">
            {!sidebarOpen && <button
              type="button"
              onClick={() => setSidebarOpen((v) => !v)}
              className="rounded-xl border border-border/70 bg-panel/50 p-2 text-muted hover:bg-panel/70 hover:text-text transition"
              aria-label={sidebarOpen ? "Hide sidebar" : "Show sidebar"}
              title={sidebarOpen ? "Hide sidebar" : "Show sidebar"}
            >
              <PanelLeft size={16} />
            </button>}
            <Sparkles size={16} className="text-primary" />
            <div className="text-sm font-semibold">TickerLens</div>
          </div>

          <div className="flex items-center gap-2">
            {/* <Link
              href="/timeline"
              className="rounded-xl border border-border/70 bg-panel/50 px-3 py-2 text-sm font-semibold text-text hover:bg-panel/70 transition"
              title="Open document timeline"
            >
              Timeline
            </Link> */}

            {/* Profile menu lives in the sidebar (bottom-left). */}

            {/* <div className="hidden items-center gap-2 text-xs text-muted md:flex">
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
            </div> */}
          </div>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-auto px-4 py-6 no-scrollbar">
          {activeMessages.length ? (
            <div className="mx-auto w-full max-w-3xl">
              <ChatThread
                messages={activeMessages}
                activeCitationsMessageId={activeCitationsMessageId}
                onSelectCitationsMessage={(id) => {
                  setActiveCitationsMessageId(id);
                  setIsCitationsOpen(true);
                }}
                onOpenTickerPicker={() => setIsTickerPickerOpen(true)}
                onQuickReply={(text) => onStarterPrompt(text)}
              />
            </div>
          ) : (
            <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col items-center justify-center gap-6">
              <div className="text-center">
                <div className="text-3xl font-semibold tracking-tight text-text">Ready when you are.</div>
                <div className="mt-2 text-sm text-muted">
                  Add tickers (or mention them in your question) for best results. If anything is missing, TickerLens will ask one follow-up.
                </div>
              </div>

              <div className="w-full">
                <ChatComposer
                  value={input}
                  onChange={setInput}
                  onSend={send}
                  onStop={stop}
                  isStreaming={isStreaming}
                  disabled={tickers.length === 0}
                  tickers={tickers}
                  onOpenTickerPicker={() => setIsTickerPickerOpen(true)}
                  onRemoveTicker={(t) => upsertConversationTickers(tickers.filter((x) => x !== t))}
                />
              </div>

              <div className="w-full overflow-hidden rounded-2xl border border-border/70 bg-panel/40 shadow-soft backdrop-blur">
                <ul className="divide-y divide-border/50">
                  {STARTER_PROMPTS.map((p) => (
                    <li key={p.title}>
                      <button
                        type="button"
                        onClick={() => onStarterPrompt(p.text)}
                        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-bg/20 transition disabled:opacity-60"
                        disabled={isStreaming}
                      >
                        <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-border/70 bg-bg/25">
                          <p.icon size={16} className="text-primary" />
                        </div>
                        <div className="min-w-0">
                          <div className="text-sm font-semibold text-text">{p.title}</div>
                          <div className="truncate text-xs text-muted">{p.text}</div>
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>

        {activeMessages.length ? (
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
                onRemoveTicker={(t) => upsertConversationTickers(tickers.filter((x) => x !== t))}
              />
            </div>
          </div>
        ) : null}
      </main>

      <TickerPicker
        value={tickers}
        onChange={upsertConversationTickers}
        open={isTickerPickerOpen}
        onOpenChange={setIsTickerPickerOpen}
      />

      <CitationsDrawer open={isCitationsOpen} onOpenChange={setIsCitationsOpen} payload={selectedCitations} />
    </div>
  );
}
