from __future__ import annotations

import datetime as dt
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.db.models import Chunk, ChunkVector, Document
from app.services.embeddings import embed_query, DEFAULT_MODEL
from app.services.faiss_index import load_or_create_index, search as faiss_search

router = APIRouter()

class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)

class SearchHit(BaseModel):
    score: float
    chunk_id: int
    document_id: str
    filename: str
    chunk_index: int
    text: str
    start_char: int | None
    end_char: int | None
    created_at: dt.datetime

class SearchResponse(BaseModel):
    query: str
    top_k: int
    embedding_model: str
    hits: list[SearchHit]

@router.post("/search", response_model=SearchResponse)
def search_chunks(payload: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    # Ensure FAISS index exists
    index_path = Path("data") / "faiss.index"
    if not index_path.exists():
        raise HTTPException(status_code=400, detail="FAISS index not found. Index at least one document first.")

    # Embed query
    qvec = embed_query(payload.query, model_name=DEFAULT_MODEL)

    # Load index (dim inferred from vector)
    index = load_or_create_index(dim=len(qvec))
    faiss_ids, scores = faiss_search(index, qvec, top_k=payload.top_k)

    # FAISS returns -1 when not enough vectors exist
    pairs = [(fid, sc) for fid, sc in zip(faiss_ids, scores) if fid is not None and fid >= 0]
    if not pairs:
        return SearchResponse(query=payload.query, top_k=payload.top_k, embedding_model=DEFAULT_MODEL, hits=[])

    # Map faiss_id -> chunk_id via ChunkVector
    fid_list = [fid for fid, _ in pairs]
    vectors = db.scalars(select(ChunkVector).where(ChunkVector.faiss_id.in_(fid_list))).all()
    faiss_to_chunk = {v.faiss_id: v.chunk_id for v in vectors}

    chunk_ids = [faiss_to_chunk.get(fid) for fid, _ in pairs]
    chunk_ids = [cid for cid in chunk_ids if cid is not None]
    if not chunk_ids:
        return SearchResponse(query=payload.query, top_k=payload.top_k, embedding_model=DEFAULT_MODEL, hits=[])

    # Load chunks + documents
    chunks = db.scalars(select(Chunk).where(Chunk.id.in_(chunk_ids))).all()
    chunk_by_id = {c.id: c for c in chunks}

    doc_ids = list({c.document_id for c in chunks})
    docs = db.scalars(select(Document).where(Document.id.in_(doc_ids))).all()
    doc_by_id = {d.id: d for d in docs}

    hits: list[SearchHit] = []
    for fid, sc in pairs:
        cid = faiss_to_chunk.get(fid)
        if cid is None:
            continue
        ch = chunk_by_id.get(cid)
        if ch is None:
            continue
        doc = doc_by_id.get(ch.document_id)
        if doc is None:
            continue

        hits.append(
            SearchHit(
                score=float(sc),
                chunk_id=ch.id,
                document_id=doc.id,
                filename=doc.filename,
                chunk_index=ch.chunk_index,
                text=ch.text,
                start_char=ch.start_char,
                end_char=ch.end_char,
                created_at=doc.created_at,
            )
        )

    # Sort by score desc (FAISS already returns sorted but keep safe)
    hits.sort(key=lambda h: h.score, reverse=True)

    return SearchResponse(
        query=payload.query,
        top_k=payload.top_k,
        embedding_model=DEFAULT_MODEL,
        hits=hits,
    )
