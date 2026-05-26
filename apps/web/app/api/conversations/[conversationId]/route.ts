export const runtime = "nodejs";
export const dynamic = "force-dynamic";

import { apiBaseUrl, passthroughResponse, upstreamHeaders } from "@/lib/apiProxy";

export async function GET(request: Request, context: { params: Promise<{ conversationId: string }> }) {
  const { conversationId } = await context.params;
  const baseUrl = apiBaseUrl();

  const upstream = await fetch(`${baseUrl}/conversations/${encodeURIComponent(conversationId)}`, {
    method: "GET",
    headers: upstreamHeaders(request, { Accept: "application/json" }),
  });

  return passthroughResponse(upstream);
}

export async function PATCH(request: Request, context: { params: Promise<{ conversationId: string }> }) {
  const { conversationId } = await context.params;
  const baseUrl = apiBaseUrl();
  const body = await request.text();

  const upstream = await fetch(`${baseUrl}/conversations/${encodeURIComponent(conversationId)}`, {
    method: "PATCH",
    headers: upstreamHeaders(request, { "Content-Type": "application/json", Accept: "application/json" }),
    body,
  });

  return passthroughResponse(upstream);
}

export async function DELETE(request: Request, context: { params: Promise<{ conversationId: string }> }) {
  const { conversationId } = await context.params;
  const baseUrl = apiBaseUrl();

  const upstream = await fetch(`${baseUrl}/conversations/${encodeURIComponent(conversationId)}`, {
    method: "DELETE",
    headers: upstreamHeaders(request, { Accept: "application/json" }),
  });

  return passthroughResponse(upstream);
}

