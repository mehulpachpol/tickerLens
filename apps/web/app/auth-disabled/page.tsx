export default function AuthDisabledPage() {
  return (
    <div className="min-h-dvh bg-gradient-to-b from-bg to-bg/90 px-4 py-10">
      <div className="mx-auto w-full max-w-xl">
        <div className="rounded-2xl border border-border/70 bg-panel/40 p-6 shadow-soft backdrop-blur">
          <div className="text-lg font-semibold text-text">Authentication is not enabled</div>
          <div className="mt-2 text-sm text-muted">
            The API responded with <span className="font-semibold text-text">Auth is disabled</span>, so TickerLens Web
            cannot sign you in.
          </div>

          <div className="mt-5 text-sm text-muted">
            Enable auth in <code className="rounded bg-bg/30 px-1 py-0.5">infra/compose/.env</code> and restart the
            API:
          </div>

          <pre className="mt-3 overflow-auto rounded-xl border border-border/70 bg-bg/30 p-3 text-xs text-text">
{`TICKERLENS_AUTH_ENABLED=true
TICKERLENS_AUTH_ALLOW_REGISTER=true`}
          </pre>

          <div className="mt-4 text-sm text-muted">
            After that, open <code className="rounded bg-bg/30 px-1 py-0.5">/signup</code> to create an account, or{" "}
            <code className="rounded bg-bg/30 px-1 py-0.5">/login</code> to sign in.
          </div>
        </div>
      </div>
    </div>
  );
}

