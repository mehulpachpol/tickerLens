export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const DEFAULT_API_BASE_URL = "http://localhost:8000";

export async function POST(request: Request) {
  const baseUrl = process.env.TICKERLENS_API_BASE_URL ?? DEFAULT_API_BASE_URL;
  const body = await request.text();

  const upstream = await fetch(`${baseUrl}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body,
  });

  // Pass-through SSE stream.
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
