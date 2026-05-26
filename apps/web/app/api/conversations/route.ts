export const runtime = "nodejs";
export const dynamic = "force-dynamic";

import { apiBaseUrl, passthroughResponse, upstreamHeaders } from "@/lib/apiProxy";

export async function GET(request: Request) {
  const baseUrl = apiBaseUrl();
  const url = new URL(request.url);
  const upstreamUrl = new URL(`${baseUrl}/conversations`);
  upstreamUrl.search = url.searchParams.toString();

  const upstream = await fetch(upstreamUrl.toString(), {
    method: "GET",
    headers: upstreamHeaders(request, { Accept: "application/json" }),
  });

  return passthroughResponse(upstream);
}

export async function POST(request: Request) {
  const baseUrl = apiBaseUrl();
  const body = await request.text();

  const upstream = await fetch(`${baseUrl}/conversations`, {
    method: "POST",
    headers: upstreamHeaders(request, { "Content-Type": "application/json", Accept: "application/json" }),
    body,
  });

  return passthroughResponse(upstream);
}

