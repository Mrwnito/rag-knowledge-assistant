from __future__ import annotations

import re
import uuid
from pathlib import Path
import datetime as dt

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.db.models import Document

from app.db.models import Document, Chunk
from app.services.parsing import extract_text_from_txt
from app.services.chunking import chunk_text

from app.db.models import ChunkVector
from app.services.embeddings import embed_texts, DEFAULT_MODEL
from app.services.faiss_index import load_or_create_index, save_index, add_vectors
import numpy as np

router = APIRouter()

DATA_DIR = Path("data")
FILES_DIR = DATA_DIR / "files"
FILES_DIR.mkdir(parents=True, exist_ok=True)

def sanitize_filename(name: str) -> str:
    # Prevent path traversal and keep filenames simple
    base = Path(name).name
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    return (base[:200] or "file")

class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    content_type: str
    storage_path: str
    created_at: dt.datetime


@router.post("/documents", response_model=DocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Document:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    doc_id = str(uuid.uuid4())
    safe_name = sanitize_filename(file.filename)
    stored_name = f"{doc_id}_{safe_name}"
    abs_path = FILES_DIR / stored_name
    rel_path = f"data/files/{stored_name}"

    # Stream to disk (avoid reading entire file into RAM)
    try:
        with abs_path.open("wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
    finally:
        await file.close()

    doc = Document(
        id=doc_id,
        filename=safe_name,
        content_type=file.content_type or "application/octet-stream",
        storage_path=rel_path,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
        # Create chunks (TXT only for now)
    if (file.content_type or "").startswith("text/") or safe_name.lower().endswith(".txt"):
        text = extract_text_from_txt(abs_path)
        chunks = chunk_text(text)
        for ch in chunks:
            db.add(
                Chunk(
                    document_id=doc.id,
                    chunk_index=ch.index,
                    text=ch.text,
                    start_char=ch.start_char,
                    end_char=ch.end_char,
                )
            )
        db.commit()

    return doc

@router.get("/documents", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)) -> list[Document]:
    stmt = select(Document).order_by(Document.created_at.desc())
    return db.scalars(stmt).all()

class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_id: str
    chunk_index: int
    text: str
    start_char: int | None
    end_char: int | None

@router.get("/documents/{doc_id}/chunks", response_model=list[ChunkOut])
def list_chunks(doc_id: str, db: Session = Depends(get_db)) -> list[Chunk]:
    stmt = select(Chunk).where(Chunk.document_id == doc_id).order_by(Chunk.chunk_index.asc())
    return db.scalars(stmt).all()

@router.post("/documents/{doc_id}/index")
def index_document(doc_id: str, db: Session = Depends(get_db)) -> dict[str, int]:
    chunks = db.scalars(
        select(Chunk).where(Chunk.document_id == doc_id).order_by(Chunk.chunk_index.asc())
    ).all()

    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not chunks:
        # Backfill chunks from stored file (TXT only for now)
        p = Path(doc.storage_path)
        if p.exists() and (doc.content_type.startswith("text/") or p.suffix.lower() == ".txt"):
            text = extract_text_from_txt(p)
            new_chunks = chunk_text(text)
            for ch in new_chunks:
                db.add(
                    Chunk(
                        document_id=doc.id,
                        chunk_index=ch.index,
                        text=ch.text,
                        start_char=ch.start_char,
                        end_char=ch.end_char,
                    )
                )
            db.commit()

            chunks = db.scalars(
                select(Chunk).where(Chunk.document_id == doc_id).order_by(Chunk.chunk_index.asc())
            ).all()

        if not chunks:
            raise HTTPException(status_code=404, detail="No chunks found for document")

    # Filter already indexed chunks
    existing = db.scalars(select(ChunkVector.chunk_id).where(ChunkVector.chunk_id.in_([c.id for c in chunks]))).all()
    existing_set = set(existing)
    to_index = [c for c in chunks if c.id not in existing_set]

    if not to_index:
        return {"indexed": 0}

    texts = [c.text for c in to_index]
    vectors = embed_texts(texts, model_name=DEFAULT_MODEL)

    dim = len(vectors[0])
    index = load_or_create_index(dim)
    faiss_ids = add_vectors(index, vectors)
    save_index(index)

    for c, fid in zip(to_index, faiss_ids, strict=True):
        db.add(ChunkVector(chunk_id=c.id, faiss_id=fid, embedding_model=DEFAULT_MODEL))

    db.commit()
    return {"indexed": len(to_index)}
