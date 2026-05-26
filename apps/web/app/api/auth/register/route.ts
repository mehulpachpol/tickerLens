export const runtime = "nodejs";
export const dynamic = "force-dynamic";

import { apiBaseUrl, passthroughResponse, upstreamHeaders } from "@/lib/apiProxy";

export async function POST(request: Request) {
  const baseUrl = apiBaseUrl();
  const body = await request.text();

  const upstream = await fetch(`${baseUrl}/auth/register`, {
    method: "POST",
    headers: upstreamHeaders(request, { "Content-Type": "application/json", Accept: "application/json" }),
    body,
  });

  return passthroughResponse(upstream);
}

