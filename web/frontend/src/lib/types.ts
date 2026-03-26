export type Role = "user" | "assistant";

export interface ChatMessage {
  role: Role;
  content: string;
  cypherQueries?: string[];
  confidence?: number;
}

export interface GraphNode {
  id: string;
  label: string;
  labels: string[];
  group: string;
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  from: string;
  to: string;
  label: string;
  type: string;
  properties: Record<string, unknown>;
}

export interface GraphDataPayload {
  nodes: GraphNode[];
  edges: GraphEdge[];
}
