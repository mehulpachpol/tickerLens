const DEFAULT_API_BASE_URL = "http://localhost:8000";

export function apiBaseUrl() {
  return process.env.TICKERLENS_API_BASE_URL ?? DEFAULT_API_BASE_URL;
}

export function upstreamHeaders(request: Request, extra?: Record<string, string>) {
  const h = new Headers();
  const cookie = request.headers.get("cookie");
  if (cookie) h.set("cookie", cookie);
  const authz = request.headers.get("authorization");
  if (authz) h.set("authorization", authz);
  if (extra) {
    for (const [k, v] of Object.entries(extra)) h.set(k, v);
  }
  return h;
}

export async function passthroughResponse(upstream: Response) {
  const body = upstream.body ?? (await upstream.text());
  const headers = new Headers();
  const contentType = upstream.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  headers.set("Cache-Control", "no-store");

  const anyHeaders = upstream.headers as any;
  if (typeof anyHeaders.getSetCookie === "function") {
    const cookies: string[] = anyHeaders.getSetCookie();
    for (const c of cookies) headers.append("set-cookie", c);
  } else {
    const setCookie = upstream.headers.get("set-cookie");
    if (setCookie) headers.set("set-cookie", setCookie);
  }

  return new Response(body as any, { status: upstream.status, headers });
}
