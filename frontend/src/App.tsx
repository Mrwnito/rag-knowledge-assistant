import { useEffect, useState } from "react";
import { listDocuments, uploadDocument, type DocumentItem } from "./api/client";

export default function App() {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [selected, setSelected] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function refresh() {
    const items = await listDocuments();
    setDocs(items);
  }

  useEffect(() => {
    refresh().catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  async function onUpload() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      await uploadDocument(selected);
      setSelected(null);
      await refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ fontFamily: "system-ui", padding: 24, maxWidth: 900, margin: "0 auto" }}>
      <h1>RAG Knowledge Assistant</h1>

      <p style={{ color: "#666" }}>
        Upload documents (TXT/PDF/DOCX next) and see them listed below.
      </p>

      {error && (
        <div style={{ background: "#ffecec", color: "#a40000", padding: 12, borderRadius: 8, marginTop: 12 }}>
          {error}
        </div>
      )}

      <div style={{ marginTop: 16, display: "flex", gap: 12, alignItems: "center" }}>
        <input
          type="file"
          onChange={(e) => setSelected(e.target.files?.[0] ?? null)}
          disabled={busy}
        />
        <button onClick={onUpload} disabled={!selected || busy}>
          {busy ? "Uploading..." : "Upload"}
        </button>
        <button onClick={() => refresh()} disabled={busy}>
          Refresh
        </button>
      </div>

      <h2 style={{ marginTop: 24 }}>Documents</h2>

      {docs.length === 0 ? (
        <p style={{ color: "#666" }}>No documents yet.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 8 }}>
          <thead>
            <tr>
              <th align="left" style={{ borderBottom: "1px solid #ddd", paddingBottom: 8 }}>Filename</th>
              <th align="left" style={{ borderBottom: "1px solid #ddd", paddingBottom: 8 }}>Type</th>
              <th align="left" style={{ borderBottom: "1px solid #ddd", paddingBottom: 8 }}>Created</th>
            </tr>
          </thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.id}>
                <td style={{ padding: "10px 0", borderBottom: "1px solid #f0f0f0" }}>{d.filename}</td>
                <td style={{ padding: "10px 0", borderBottom: "1px solid #f0f0f0" }}>{d.content_type}</td>
                <td style={{ padding: "10px 0", borderBottom: "1px solid #f0f0f0" }}>{d.created_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
