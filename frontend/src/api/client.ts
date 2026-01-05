export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.toString() ?? "http://127.0.0.1:8000";

export type DocumentItem = {
  id: string;
  filename: string;
  content_type: string;
  storage_path: string;
  created_at: string;
};

export async function listDocuments(): Promise<DocumentItem[]> {
  const r = await fetch(`${API_BASE_URL}/v1/documents`, { method: "GET" });
  if (!r.ok) throw new Error(`List failed: HTTP ${r.status}`);
  return (await r.json()) as DocumentItem[];
}

export async function uploadDocument(file: File): Promise<DocumentItem> {
  const form = new FormData();
  form.append("file", file);

  const r = await fetch(`${API_BASE_URL}/v1/documents`, {
    method: "POST",
    body: form,
  });

  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`Upload failed: HTTP ${r.status} ${text}`);
  }
  return (await r.json()) as DocumentItem;
}

export type SearchHit = {
  score: number;
  chunk_id: number;
  document_id: string;
  filename: string;
  chunk_index: number;
  text: string;
  start_char: number | null;
  end_char: number | null;
  created_at: string;
};

export type SearchResponse = {
  query: string;
  top_k: number;
  embedding_model: string;
  hits: SearchHit[];
};

export async function searchChunks(query: string, topK: number = 5): Promise<SearchResponse> {
  const r = await fetch(`${API_BASE_URL}/v1/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: topK }),
  });

  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`Search failed: HTTP ${r.status} ${text}`);
  }
  return (await r.json()) as SearchResponse;
}

export type Citation = {
  filename: string;
  document_id: string;
  chunk_id: number;
  chunk_index: number;
  start_char: number | null;
  end_char: number | null;
  snippet: string;
};

export type ChatResponse = {
  answer: string;
  provider: string;
  model: string;
  latency_ms: number;
  citations: Citation[];
};

export async function chat(question: string, topK: number = 5): Promise<ChatResponse> {
  const r = await fetch(`${API_BASE_URL}/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k: topK }),
  });

  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`Chat failed: HTTP ${r.status} ${text}`);
  }
  return (await r.json()) as ChatResponse;
}
