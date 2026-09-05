const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface Product {
  id: string;
  name: string;
  description: string | null;
  key_prefix: string;
  created_at: string;
  updated_at: string;
}

export interface Initiative {
  id: string;
  product_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Epic {
  id: string;
  initiative_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  product_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Sprint {
  id: string;
  product_id: string;
  name: string;
  start_date: string | null;
  end_date: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Feature {
  id: string;
  epic_id: string;
  name: string;
  requirements: string | null;
  status: string;
  acceptance_criteria_format: string;
  issue_number: number;
  issue_key: string;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeItem {
  id: string;
  type: string;
  scope: string;
  scope_ref_id: string;
  content: Record<string, unknown>;
  confidence: number | null;
  provenance: string;
  status: string;
  created_at: string;
  updated_at: string;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`Request to ${path} failed with status ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  listProducts: () => request<Product[]>("/products"),
  createProduct: (data: { name: string; description?: string; key_prefix: string }) =>
    request<Product>("/products", { method: "POST", body: JSON.stringify(data) }),
  getProduct: (id: string) => request<Product>(`/products/${id}`),

  listInitiatives: (productId: string) =>
    request<Initiative[]>(`/initiatives?product_id=${productId}`),
  createInitiative: (data: { product_id: string; name: string; description?: string }) =>
    request<Initiative>("/initiatives", { method: "POST", body: JSON.stringify(data) }),
  getInitiative: (id: string) => request<Initiative>(`/initiatives/${id}`),

  listEpics: (initiativeId: string) => request<Epic[]>(`/epics?initiative_id=${initiativeId}`),
  createEpic: (data: { initiative_id: string; name: string; description?: string }) =>
    request<Epic>("/epics", { method: "POST", body: JSON.stringify(data) }),
  getEpic: (id: string) => request<Epic>(`/epics/${id}`),

  listFeatures: (epicId: string) => request<Feature[]>(`/features?epic_id=${epicId}`),
  createFeature: (data: { epic_id: string; name: string; requirements?: string }) =>
    request<Feature>("/features", { method: "POST", body: JSON.stringify(data) }),

  listProjects: (productId: string) => request<Project[]>(`/projects?product_id=${productId}`),
  createProject: (data: { product_id: string; name: string; description?: string }) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify(data) }),

  listSprints: (productId: string) => request<Sprint[]>(`/sprints?product_id=${productId}`),
  createSprint: (data: {
    product_id: string;
    name: string;
    start_date?: string;
    end_date?: string;
  }) => request<Sprint>("/sprints", { method: "POST", body: JSON.stringify(data) }),

  listKnowledgeItems: (scope: string, scopeRefId: string) =>
    request<KnowledgeItem[]>(`/knowledge-items?scope=${scope}&scope_ref_id=${scopeRefId}`),
  createKnowledgeItem: (data: {
    scope: string;
    scope_ref_id: string;
    content: Record<string, unknown>;
  }) => request<KnowledgeItem>("/knowledge-items", { method: "POST", body: JSON.stringify(data) }),
};
