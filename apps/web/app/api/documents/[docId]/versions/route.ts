export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const DEFAULT_API_BASE_URL = "http://localhost:8000";

export async function GET(_request: Request, context: { params: Promise<{ docId: string }> }) {
  const { docId } = await context.params;
  const baseUrl = process.env.TICKERLENS_API_BASE_URL ?? DEFAULT_API_BASE_URL;

  const upstream = await fetch(`${baseUrl}/documents/${encodeURIComponent(docId)}/versions`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/json",
      "Cache-Control": "no-store",
    },
  });
}

