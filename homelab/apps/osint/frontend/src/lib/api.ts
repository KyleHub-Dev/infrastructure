/* ------------------------------------------------------------------ */
/*  Types (matching API response schemas)                             */
/* ------------------------------------------------------------------ */

export interface Investigation {
  id: string;
  query: string;
  observable_type: string;
  legal_basis: string;
  purpose: string;
  justification: string;
  ttl_days: number;
  status: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  node_count: number;
  edge_count: number;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  x: number;
  y: number;
  size: number;
  tool_source?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface InvestigationStats {
  investigation_id: string;
  status: string;
  node_count: number;
  edge_count: number;
  by_type: Record<string, number>;
  by_tool: Record<string, number>;
}

export interface Observable {
  id: string;
  entity_type: string;
  value: string;
  metadata: Record<string, any>;
  tool_source: string;
  confidence: number;
  investigation_id: string;
  created_at: string;
  expires_at: string;
}

/* ------------------------------------------------------------------ */
/*  API helper                                                        */
/* ------------------------------------------------------------------ */

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

/* Map frontend "ip" type to API "ip_address" */
export const OBSERVABLE_TYPE_MAP: Record<string, string> = {
  username: "username",
  email: "email",
  domain: "domain",
  ip: "ip_address",
};
