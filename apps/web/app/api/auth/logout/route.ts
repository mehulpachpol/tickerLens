export const runtime = "nodejs";
export const dynamic = "force-dynamic";

import { apiBaseUrl, passthroughResponse, upstreamHeaders } from "@/lib/apiProxy";

export async function POST(request: Request) {
  const baseUrl = apiBaseUrl();

  const upstream = await fetch(`${baseUrl}/auth/logout`, {
    method: "POST",
    headers: upstreamHeaders(request, { Accept: "application/json" }),
  });

  return passthroughResponse(upstream);
}

