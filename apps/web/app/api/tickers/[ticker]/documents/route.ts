export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const DEFAULT_API_BASE_URL = "http://localhost:8000";

export async function GET(request: Request, context: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await context.params;
  const baseUrl = process.env.TICKERLENS_API_BASE_URL ?? DEFAULT_API_BASE_URL;

  const url = new URL(request.url);
  const upstreamUrl = new URL(`${baseUrl}/tickers/${encodeURIComponent(ticker)}/documents`);
  upstreamUrl.search = url.searchParams.toString();

  const upstream = await fetch(upstreamUrl.toString(), {
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

