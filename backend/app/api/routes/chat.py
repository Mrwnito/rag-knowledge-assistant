from __future__ import annotations

import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.api.routes.search import search_chunks, SearchRequest, SearchResponse
from app.services.llm import generate, get_provider

import json
from fastapi.responses import StreamingResponse
from app.services.llm import generate_stream_ollama

router = APIRouter()

class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=10)

class Citation(BaseModel):
    filename: str
    document_id: str
    chunk_id: int
    chunk_index: int
    start_char: int | None
    end_char: int | None
    snippet: str

class ChatResponse(BaseModel):
    answer: str
    provider: str
    model: str
    latency_ms: int
    citations: list[Citation]

MAX_CHUNK_CHARS = 900          # on tronque chaque chunk pour éviter des prompts énormes
MAX_UNIQUE_HITS = 5            # garde le top-k mais après déduplication

def dedupe_hits(hits):
    """
    Déduplique des hits qui ont le même contenu (souvent fichiers uploadés plusieurs fois).
    On déduplique sur un hash simple du texte tronqué + filename.
    """
    seen = set()
    unique = []
    for h in hits:
        key = (h.filename, h.text[:200])  # assez robuste pour détecter les doublons de glossaire
        if key in seen:
            continue
        seen.add(key)
        unique.append(h)
        if len(unique) >= MAX_UNIQUE_HITS:
            break
    return unique

def build_prompt(question: str, retrieved: SearchResponse) -> str:
    if not retrieved.hits:
        return (
            "You are a knowledge assistant.\n"
            "The user asked a question, but there is no relevant context.\n"
            "Answer: You do not have enough information in the provided documents.\n\n"
            f"Question: {question}\n"
        )

    hits = dedupe_hits(retrieved.hits)

    context_blocks = []
    for i, h in enumerate(hits, start=1):
        context_blocks.append(
            f"[{i}] Source: {h.filename} (doc_id={h.document_id}, chunk={h.chunk_index})\n"
            f"{h.text[:MAX_CHUNK_CHARS]}\n"
        )

    context = "\n".join(context_blocks)

    return (
        "You are a RAG assistant. Answer the question using ONLY the context.\n"
        "If the answer is not in the context, say you don't know based on the documents.\n"
        "Cite sources by referencing [1], [2], ... in your answer.\n\n"
        f"Question: {question}\n\n"
        f"Context:\n{context}\n"
        "Answer:\n"
    )



@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    t0 = time.time()

    retrieved = search_chunks(SearchRequest(query=payload.question, top_k=payload.top_k), db=db)

    hits = dedupe_hits(retrieved.hits)
    retrieved.hits = hits  # on réutilise la même liste partout (prompt + citations)

    # Guardrail: if no hits, don't call LLM (saves time/cost)
    if not retrieved.hits or retrieved.hits[0].score < 0.15:
        return ChatResponse(
            answer="Je n'ai pas assez d'information dans les documents fournis pour répondre.",
            provider=get_provider(),
            model="n/a",
            latency_ms=int((time.time() - t0) * 1000),
            citations=[],
        )

    prompt = build_prompt(payload.question, retrieved)

    provider = get_provider()
    try:
        answer, used_model = await generate(provider, prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Build citations with short snippets (first 240 chars)
    citations: list[Citation] = []
    for h in retrieved.hits:
        snippet = (h.text[:240] + "…") if len(h.text) > 240 else h.text
        citations.append(
            Citation(
                filename=h.filename,
                document_id=h.document_id,
                chunk_id=h.chunk_id,
                chunk_index=h.chunk_index,
                start_char=h.start_char,
                end_char=h.end_char,
                snippet=snippet,
            )
        )

    return ChatResponse(
        answer=answer,
        provider=provider,
        model=used_model,
        latency_ms=int((time.time() - t0) * 1000),
        citations=citations,
    )

@router.get("/chat/stream")
async def chat_stream(question: str, top_k: int = 5, db: Session = Depends(get_db)):
    t0 = time.time()

    retrieved = search_chunks(SearchRequest(query=question, top_k=top_k), db=db)

    # Guardrail
    if not retrieved.hits or retrieved.hits[0].score < 0.15:
        async def gen():
            yield "event: token\ndata: " + json.dumps({"text": "Je n'ai pas assez d'information dans les documents fournis pour répondre."}) + "\n\n"
            yield "event: done\ndata: {}\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")

    prompt = build_prompt(question, retrieved)

    # Build citations (same logic as /chat)
    citations = []
    for h in retrieved.hits:
        snippet = (h.text[:240] + "…") if len(h.text) > 240 else h.text
        citations.append(
            {
                "filename": h.filename,
                "document_id": h.document_id,
                "chunk_id": h.chunk_id,
                "chunk_index": h.chunk_index,
                "start_char": h.start_char,
                "end_char": h.end_char,
                "snippet": snippet,
            }
        )

    async def event_gen():
        # stream tokens
        async for tok in generate_stream_ollama(prompt):
            yield "event: token\ndata: " + json.dumps({"text": tok}) + "\n\n"

        latency_ms = int((time.time() - t0) * 1000)
        yield "event: meta\ndata: " + json.dumps(
            {
                "provider": "ollama",
                "model": "llama3.2:3b",
                "latency_ms": latency_ms,
                "citations": citations,
            }
        ) + "\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
