from __future__ import annotations

from pathlib import Path

def extract_text_from_txt(path: Path) -> str:
    # Try UTF-8 first; fallback for Windows encodings
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="ignore")
