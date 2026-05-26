export const runtime = "nodejs";
export const dynamic = "force-dynamic";

import { apiBaseUrl, upstreamHeaders } from "@/lib/apiProxy";

export async function POST(request: Request) {
  const baseUrl = apiBaseUrl();
  const body = await request.text();

  const upstream = await fetch(`${baseUrl}/chat/stream`, {
    method: "POST",
    headers: upstreamHeaders(request, { "Content-Type": "application/json", Accept: "text/event-stream" }),
    body,
  });

  const ct = upstream.headers.get("content-type") ?? "";
  if (!ct.includes("text/event-stream")) {
    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: { "Content-Type": ct || "text/plain; charset=utf-8", "Cache-Control": "no-store" },
    });
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
