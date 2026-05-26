"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Sparkles } from "lucide-react";
import { useState } from "react";

function parseError(body: any): string {
  if (!body) return "Signup failed.";
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail) && body.detail[0]?.msg) return String(body.detail[0].msg);
  return "Signup failed.";
}

export function SignupClient({ nextUrl }: { nextUrl: string }) {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async () => {
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        let body: any = null;
        try {
          body = await res.json();
        } catch {
          body = await res.text();
        }
        setError(typeof body === "string" ? body : parseError(body));
        return;
      }
      router.replace(nextUrl);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-dvh bg-gradient-to-b from-bg to-bg/90 px-4 py-10">
      <div className="mx-auto w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-2 text-sm font-semibold text-text">
          <Sparkles size={16} className="text-primary" />
          TickerLens
        </div>

        <div className="rounded-2xl border border-border/70 bg-panel/40 p-6 shadow-soft backdrop-blur">
          <div className="text-lg font-semibold text-text">Create account</div>
          <div className="mt-1 text-sm text-muted">Your workspace for NSE filings and citation-backed answers.</div>

          {error ? (
            <div className="mt-4 rounded-xl border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-dangerFg">
              <div className="font-semibold text-danger">Could not create account</div>
              <div className="mt-1 text-muted">{error}</div>
            </div>
          ) : null}

          <div className="mt-5 space-y-3">
            <label className="block">
              <div className="mb-1 text-xs font-semibold text-muted">Email</div>
              <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                inputMode="email"
                placeholder="you@company.com"
                className="w-full rounded-xl border border-border/70 bg-bg/20 px-3 py-2 text-sm text-text placeholder:text-muted outline-none ring-0 transition focus:border-primary/40 focus:bg-bg/25"
              />
            </label>

            <label className="block">
              <div className="mb-1 text-xs font-semibold text-muted">Password</div>
              <input
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                type="password"
                autoComplete="new-password"
                placeholder="At least 8 characters"
                className="w-full rounded-xl border border-border/70 bg-bg/20 px-3 py-2 text-sm text-text placeholder:text-muted outline-none ring-0 transition focus:border-primary/40 focus:bg-bg/25"
                onKeyDown={(e) => {
                  if (e.key === "Enter") onSubmit();
                }}
              />
            </label>
          </div>

          <button
            type="button"
            onClick={onSubmit}
            disabled={busy || !email.trim() || password.length < 8}
            className="mt-5 inline-flex w-full items-center justify-center rounded-xl border border-primary/40 bg-primary/15 px-3 py-2 text-sm font-semibold text-primaryFg hover:bg-primary/20 transition disabled:opacity-60"
          >
            {busy ? "Creating…" : "Create account"}
          </button>

          <div className="mt-5 text-center text-sm text-muted">
            Already have an account?{" "}
            <Link
              href={`/login?next=${encodeURIComponent(nextUrl)}`}
              className="font-semibold text-text hover:underline"
            >
              Sign in
            </Link>
          </div>

        </div>
      </div>
    </div>
  );
}
