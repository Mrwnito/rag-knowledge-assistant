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
