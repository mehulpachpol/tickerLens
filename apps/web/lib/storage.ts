const ACTIVE_KEY = "tickerlens.active_conversation_id.v1";

export function loadActiveConversationId(): string | null {
  return localStorage.getItem(ACTIVE_KEY);
}

export function saveActiveConversationId(id: string) {
  localStorage.setItem(ACTIVE_KEY, id);
}
