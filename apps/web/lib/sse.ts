import type { SseEvent } from "@/lib/types";

type ParsedMessage = { event?: string; data?: string };

function parseSseMessage(raw: string): ParsedMessage {
  const lines = raw.split("\n");
  const dataLines: string[] = [];
  let event: string | undefined;

  for (const line of lines) {
    if (!line.trim()) continue;
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
      continue;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
      continue;
    }
  }

  return { event, data: dataLines.join("\n") };
}

export async function* streamSse(response: Response): AsyncGenerator<SseEvent> {
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    yield { event: "error", data: { error: text || `HTTP ${response.status}` } };
    return;
  }

  if (!response.body) {
    yield { event: "error", data: { error: "Missing response body (stream not available)." } };
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const msg = parseSseMessage(part);
      if (!msg.event || msg.data == null) continue;

      try {
        const parsed = JSON.parse(msg.data);
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        yield { event: msg.event as any, data: parsed } as SseEvent;
      } catch {
        // Non-JSON payloads are treated as error text.
        yield { event: "error", data: { error: msg.data } };
      }
    }
  }
}

