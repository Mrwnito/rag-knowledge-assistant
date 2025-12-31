from __future__ import annotations

from pathlib import Path
import faiss
import numpy as np

INDEX_PATH = Path("data") / "faiss.index"

def load_or_create_index(dim: int) -> faiss.Index:
    if INDEX_PATH.exists():
        return faiss.read_index(str(INDEX_PATH))
    # Inner Product index (works with normalized vectors == cosine)
    return faiss.IndexFlatIP(dim)

def save_index(index: faiss.Index) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_PATH))

def add_vectors(index: faiss.Index, vectors: list[list[float]]) -> list[int]:
    arr = np.array(vectors, dtype="float32")
    start_id = index.ntotal
    index.add(arr)
    # faiss ids are implicit for IndexFlat: 0..ntotal-1
    return list(range(start_id, start_id + arr.shape[0]))

def search(index: faiss.Index, query_vec: list[float], top_k: int = 5) -> tuple[list[int], list[float]]:
    q = np.array([query_vec], dtype="float32")
    scores, ids = index.search(q, top_k)
    return ids[0].tolist(), scores[0].tolist()
