from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class TextChunk:
    index: int
    text: str
    start_char: int
    end_char: int

def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[TextChunk]:
    """
    Simple char-based chunking.
    chunk_size: number of characters per chunk
    overlap: how many characters to overlap between consecutive chunks
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be < chunk_size")

    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []

    chunks: list[TextChunk] = []
    start = 0
    idx = 0
    n = len(text)

    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(TextChunk(index=idx, text=chunk, start_char=start, end_char=end))
            idx += 1

        # IMPORTANT: stop when we've reached the end
        if end == n:
            break

        # ensure we always make progress
        start = max(end - overlap, start + 1)


    return chunks
