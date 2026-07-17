export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

const TOKEN_KEY = "eap_access_token";

export function saveToken(token: string) {
  if (typeof window !== "undefined") window.localStorage.setItem(TOKEN_KEY, token);
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function clearToken() {
  if (typeof window !== "undefined") window.localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    ...init,
    headers: {
      ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export interface Token {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export async function login(email: string, password: string): Promise<Token> {
  const params = new URLSearchParams({ email, password });
  const res = await fetch(`${API_BASE}/api/v1/auth/login?${params.toString()}`, { method: "POST" });
  if (!res.ok) throw new Error("Invalid email or password");
  return res.json();
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
}

export interface Citation {
  source: string;
  snippet: string;
  score: number;
}

export interface ChatResponse {
  conversation_id: string;
  agent_used: string;
  message: ChatMessage;
  citations: Citation[];
  latency_ms: number;
  tokens_used: number;
}

export function sendChatMessage(message: string, conversationId?: string, agent?: string) {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ message, conversation_id: conversationId, agent }),
  });
}

export interface AgentInfo {
  name: string;
  description: string;
  capabilities: string[];
}

export function listAgents() {
  return request<AgentInfo[]>("/agents");
}

export interface AnalyticsSnapshot {
  active_users: number;
  ai_requests_total: number;
  token_usage_total: number;
  estimated_cost_usd: number;
  avg_latency_ms: number;
  search_accuracy: number;
  requests_by_agent: Record<string, number>;
  generated_at: string;
}

export function fetchAnalytics() {
  return request<AnalyticsSnapshot>("/admin/analytics");
}

export function uploadDocument(file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<{ doc_id: string; filename: string; chunk_count: number }>("/documents/upload", {
    method: "POST",
    body: form,
  });
}
