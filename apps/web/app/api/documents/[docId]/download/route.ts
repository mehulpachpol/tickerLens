export const runtime = "nodejs";
export const dynamic = "force-dynamic";

import { apiBaseUrl, passthroughResponse, upstreamHeaders } from "@/lib/apiProxy";

export async function GET(_request: Request, context: { params: Promise<{ docId: string }> }) {
  const { docId } = await context.params;
  const baseUrl = apiBaseUrl();

  const upstream = await fetch(`${baseUrl}/documents/${encodeURIComponent(docId)}/download`, {
    method: "GET",
    headers: upstreamHeaders(_request, { Accept: "application/json" }),
  });

  return passthroughResponse(upstream);
}
