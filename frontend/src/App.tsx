import { useEffect, useState } from "react";

type HealthResponse = { status: string };

export default function App() {
  const [status, setStatus] = useState<string>("loading...");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    async function run() {
      try {
        const res = await fetch("http://127.0.0.1:8000/health");
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = (await res.json()) as HealthResponse;
        setStatus(data.status);
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
      }
    }

    run();
  }, []);

  return (
    <div style={{ fontFamily: "system-ui", padding: 24 }}>
      <h1>RAG Knowledge Assistant</h1>

      <p>
        Backend health:{" "}
        {error ? <span style={{ color: "crimson" }}>{error}</span> : <b>{status}</b>}
      </p>

      <p style={{ color: "#666" }}>
        If you see <b>ok</b>, the frontend is successfully calling the backend.
      </p>
    </div>
  );
}
