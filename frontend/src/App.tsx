import { useEffect, useRef, useState } from "react";

import {
  API_BASE_URL,
  listDocuments,
  uploadDocument,
  searchChunks,
  chat,
  type DocumentItem,
  type SearchHit,
  type Citation,
} from "./api/client";


function formatScore(score: number) {
  return score.toFixed(3);
}

const ui = {
  panel: { padding: 16, border: "1px solid #333", borderRadius: 12, background: "#1f1f1f" },
  card: { padding: 12, border: "1px solid #333", borderRadius: 12, background: "#1b1b1b" },
  subtleText: { color: "#b5b5b5" },
  input: { padding: 10, borderRadius: 8, border: "1px solid #444", background: "#151515", color: "#f2f2f2" },
  pre: {
    marginTop: 10,
    whiteSpace: "pre-wrap" as const,
    background: "#121212",
    color: "#f2f2f2",
    padding: 10,
    borderRadius: 8,
    border: "1px solid #2a2a2a",
    maxHeight: 220,
    overflow: "auto" as const,
  },
};


export default function App() {
  // Documents
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [selected, setSelected] = useState<File | null>(null);
  const [busyUpload, setBusyUpload] = useState(false);

  // Search
  const [query, setQuery] = useState("C'est quoi FAISS ?");
  const [busySearch, setBusySearch] = useState(false);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [embeddingModel, setEmbeddingModel] = useState<string>("");

  // Chat
  const [chatQuestion, setChatQuestion] = useState("C'est quoi FAISS ?");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatAnswer, setChatAnswer] = useState("");
  const [chatModel, setChatModel] = useState("");
  const [chatLatency, setChatLatency] = useState<number | null>(null);
  const [chatCitations, setChatCitations] = useState<Citation[]>([]);

  // Shared
  const [error, setError] = useState("");

  async function refreshDocs() {
    const items = await listDocuments();
    setDocs(items);
  }

  useEffect(() => {
    refreshDocs().catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  async function onUpload() {
    if (!selected) return;
    setBusyUpload(true);
    setError("");
    try {
      await uploadDocument(selected);
      setSelected(null);
      await refreshDocs();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyUpload(false);
    }
  }

  async function onSearch() {
    if (!query.trim()) return;
    setBusySearch(true);
    setError("");
    try {
      const res = await searchChunks(query.trim(), 5);
      setEmbeddingModel(res.embedding_model);
      setHits(res.hits);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusySearch(false);
    }
  }
  async function onAsk() {
    const q = chatQuestion.trim();
    if (!q) return;

    // stop previous stream if any
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    setChatBusy(true);
    setError("");
    setChatAnswer("");
    setChatCitations([]);
    setChatModel("");
    setChatLatency(null);

    const url =
      `${API_BASE_URL}/v1/chat/stream?question=${encodeURIComponent(q)}&top_k=5`;

    const es = new EventSource(url);
    esRef.current = es;

    es.addEventListener("token", (ev) => {
      const data = JSON.parse((ev as MessageEvent).data) as { text: string };
      setChatAnswer((prev) => prev + data.text);
    });

    es.addEventListener("meta", (ev) => {
      const data = JSON.parse((ev as MessageEvent).data) as {
        provider: string;
        model: string;
        latency_ms: number;
        citations: Citation[];
      };
      setChatModel(`${data.provider} / ${data.model}`);
      setChatLatency(data.latency_ms);
      setChatCitations(data.citations);
    });

    es.addEventListener("done", () => {
      es.close();
      esRef.current = null;
      setChatBusy(false);
    });

    es.onerror = () => {
      es.close();
      esRef.current = null;
      setChatBusy(false);
      setError("Streaming failed (SSE). Check backend logs/CORS.");
    };
  }


  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    return () => {
      esRef.current?.close();
      esRef.current = null;
    };
  }, []);

  return (
    <div style={{ fontFamily: "system-ui", padding: 24, maxWidth: 980, margin: "0 auto" }}>
      <h1>RAG Knowledge Assistant</h1>

      <p style={{ color: "#666" }}>
        Local-first RAG pipeline: upload → chunk → embed → FAISS retrieval → (next) grounded answers with citations.
      </p>

      {error && (
        <div style={{ background: "#ffecec", color: "#a40000", padding: 12, borderRadius: 8, marginTop: 12 }}>
          {error}
        </div>
      )}

      {/* Search */}
      <section style={{ marginTop: 16, ...ui.panel }}>

        <h2 style={{ marginTop: 0 }}>Search</h2>

        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask a question..."
            style={{ flex: 1, padding: 10, borderRadius: 8, border: "1px solid #ddd" }}
            disabled={busySearch}
          />
          <button onClick={onSearch} disabled={busySearch || !query.trim()}>
            {busySearch ? "Searching..." : "Search"}
          </button>
        </div>

        <div style={{ marginTop: 10, color: "#666", fontSize: 14 }}>
          Embedding model: <code>{embeddingModel || "—"}</code>
        </div>

        <div style={{ marginTop: 12 }}>
          {hits.length === 0 ? (
            <p style={{ color: "#666" }}>No results yet. Try searching after indexing a document.</p>
          ) : (
            <div style={{ display: "grid", gap: 12 }}>
              {hits.map((h) => (
                <div key={`${h.document_id}:${h.chunk_id}`} style={{ padding: 12, border: "1px solid #eee", borderRadius: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                    <div>
                      <div style={{ fontWeight: 600 }}>{h.filename}</div>
                      <div style={{ color: "#666", fontSize: 13 }}>
                        chunk #{h.chunk_index} • score {formatScore(h.score)}
                      </div>
                    </div>
                    <div style={{ color: "#666", fontSize: 12, textAlign: "right" }}>
                      {h.created_at}
                    </div>
                  </div>

                  <pre
                    style={{
                      marginTop: 10,
                      whiteSpace: "pre-wrap",
                      background: "#fafafa",
                      padding: 10,
                      borderRadius: 8,
                      border: "1px solid #f0f0f0",
                      maxHeight: 220,
                      overflow: "auto",
                    }}
                  >
                    {h.text}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
      {/* Chat */}
      <section style={{ marginTop: 16, padding: 16, border: "1px solid #eee", borderRadius: 12 }}>
        <h2 style={{ marginTop: 0 }}>Chat (RAG)</h2>

        <div style={{ display: "grid", gap: 10 }}>
          <textarea
            value={chatQuestion}
            onChange={(e) => setChatQuestion(e.target.value)}
            placeholder="Ask a question grounded in your documents..."
            style={{ ...ui.input, width: "100%", minHeight: 70 }}
            disabled={chatBusy}
          />

          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <button onClick={onAsk} disabled={chatBusy || !chatQuestion.trim()}>
              {chatBusy ? "Thinking..." : "Ask"}
            </button>

            <div style={{ ...ui.subtleText, fontSize: 14 }}>
              Model: <code>{chatModel || "—"}</code> • Latency: <code>{chatLatency ?? "—"} ms</code>
            </div>
          </div>

          {chatAnswer && (
            <div style={{ marginTop: 8, ...ui.card }}>
              <div style={{ fontWeight: 600, marginBottom: 6 }}>Answer</div>
              <div style={{ whiteSpace: "pre-wrap" }}>{chatAnswer}</div>
            </div>
          )}

          {chatCitations.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontWeight: 600, marginBottom: 6 }}>Citations</div>
              <div style={{ display: "grid", gap: 10 }}>
                {chatCitations.map((c, idx) => (
                  <div key={`${c.document_id}:${c.chunk_id}:${idx}`} style={ui.card}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                      <div>
                        <div style={{ fontWeight: 600 }}>{c.filename}</div>
                        <div style={{ ...ui.subtleText, fontSize: 13 }}>
                          chunk #{c.chunk_index} • [{idx + 1}]
                        </div>
                      </div>
                    </div>


                    <pre style={{ ...ui.pre, maxHeight: 180 }}>{c.snippet}</pre>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>
      {/* Documents */}
      <section style={{ marginTop: 20 }}>
        <h2>Documents</h2>

        <div style={{ marginTop: 10, display: "flex", gap: 12, alignItems: "center" }}>
          <input type="file" onChange={(e) => setSelected(e.target.files?.[0] ?? null)} disabled={busyUpload} />
          <button onClick={onUpload} disabled={!selected || busyUpload}>
            {busyUpload ? "Uploading..." : "Upload"}
          </button>
          <button onClick={() => refreshDocs()} disabled={busyUpload}>
            Refresh
          </button>
        </div>

        {docs.length === 0 ? (
          <p style={{ color: "#666", marginTop: 12 }}>No documents yet.</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 12 }}>
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
      </section>
    </div>
  );
}
