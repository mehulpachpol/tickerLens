export const runtime = "nodejs";
export const dynamic = "force-dynamic";

import { apiBaseUrl, passthroughResponse, upstreamHeaders } from "@/lib/apiProxy";

export async function POST(request: Request, context: { params: Promise<{ docId: string }> }) {
  const { docId } = await context.params;
  const baseUrl = apiBaseUrl();

  const body = await request.text();
  const upstream = await fetch(`${baseUrl}/documents/${encodeURIComponent(docId)}/process`, {
    method: "POST",
    headers: upstreamHeaders(request, { "Content-Type": "application/json", Accept: "application/json" }),
    body,
  });

  return passthroughResponse(upstream);
}
