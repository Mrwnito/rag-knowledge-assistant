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
    return doc

@router.get("/documents", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)) -> list[Document]:
    stmt = select(Document).order_by(Document.created_at.desc())
    return db.scalars(stmt).all()
