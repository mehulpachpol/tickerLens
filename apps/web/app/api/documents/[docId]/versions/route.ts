export const runtime = "nodejs";
export const dynamic = "force-dynamic";

import { apiBaseUrl, passthroughResponse, upstreamHeaders } from "@/lib/apiProxy";

export async function GET(request: Request, context: { params: Promise<{ docId: string }> }) {
  const { docId } = await context.params;
  const baseUrl = apiBaseUrl();

  const upstream = await fetch(`${baseUrl}/documents/${encodeURIComponent(docId)}/versions`, {
    method: "GET",
    headers: upstreamHeaders(request, { Accept: "application/json" }),
  });

  return passthroughResponse(upstream);
}
