export const runtime = "nodejs";
export const dynamic = "force-dynamic";

import { apiBaseUrl, passthroughResponse, upstreamHeaders } from "@/lib/apiProxy";

export async function GET(request: Request, context: { params: Promise<{ conversationId: string }> }) {
  const { conversationId } = await context.params;
  const baseUrl = apiBaseUrl();

  const url = new URL(request.url);
  const upstreamUrl = new URL(`${baseUrl}/conversations/${encodeURIComponent(conversationId)}/runs`);
  upstreamUrl.search = url.searchParams.toString();

  const upstream = await fetch(upstreamUrl.toString(), {
    method: "GET",
    headers: upstreamHeaders(request, { Accept: "application/json" }),
  });

  return passthroughResponse(upstream);
}

