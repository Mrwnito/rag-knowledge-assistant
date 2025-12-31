from __future__ import annotations

from functools import lru_cache
from sentence_transformers import SentenceTransformer

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

@lru_cache(maxsize=1)
def get_embedder(model_name: str = DEFAULT_MODEL) -> SentenceTransformer:
    # cached so we load the model once
    return SentenceTransformer(model_name)

def embed_texts(texts: list[str], model_name: str = DEFAULT_MODEL) -> list[list[float]]:
    model = get_embedder(model_name)
    vectors = model.encode(texts, normalize_embeddings=True)
    return vectors.tolist()

def embed_query(query: str, model_name: str = DEFAULT_MODEL) -> list[float]:
    return embed_texts([query], model_name=model_name)[0]
