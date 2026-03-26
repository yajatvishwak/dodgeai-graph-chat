import { derived, writable } from "svelte/store";
import type { ChatMessage, GraphDataPayload } from "$lib/types";

export const messages = writable<ChatMessage[]>([
  {
    role: "assistant",
    content: "Hi! I can help you analyze the Order to Cash process."
  }
]);

export const loading = writable(false);
export const graphData = writable<GraphDataPayload>({ nodes: [], edges: [] });
export const selectedNodeId = writable<string | null>(null);
export const showOverlay = writable(true);
export const minimized = writable(false);

export const statusText = derived(loading, ($loading) =>
  $loading ? "Dodge AI is analyzing" : "Dodge AI is awaiting instructions"
);

export function appendMessage(message: ChatMessage): void {
  messages.update((items) => [...items, message]);
}

export function recentHistoryWindow(items: ChatMessage[]): ChatMessage[] {
  const conversational = items.filter((m) => m.role === "user" || m.role === "assistant");
  return conversational.slice(-14);
}
