from __future__ import annotations

import re
from typing import Callable


def chunk_text(text: str, *, max_chars: int = 2800, overlap: int = 200) -> list[str]:
    """Split long text so each piece fits a ~8k-token local model with prompt overhead."""
    raw = (text or "").strip()
    if not raw:
        return []
    if len(raw) <= max_chars:
        return [raw]
    parts = re.split(r"(?<=[\.!?])\s+|\n{2,}", raw)
    chunks: list[str] = []
    buf = ""
    for part in parts:
        piece = part.strip()
        if not piece:
            continue
        if len(buf) + len(piece) + 1 <= max_chars:
            buf = f"{buf} {piece}".strip()
            continue
        if buf:
            chunks.append(buf)
            tail = buf[-overlap:] if overlap and len(buf) > overlap else ""
            buf = f"{tail} {piece}".strip() if tail else piece
        else:
            for i in range(0, len(piece), max_chars):
                chunks.append(piece[i : i + max_chars])
            buf = ""
    if buf:
        chunks.append(buf)
    return chunks or [raw[:max_chars]]


def map_reduce(
    text: str,
    *,
    map_fn: Callable[[str, int, int], str],
    reduce_fn: Callable[[list[str]], str],
    max_chars: int = 2800,
) -> str:
    pieces = chunk_text(text, max_chars=max_chars)
    if not pieces:
        return ""
    if len(pieces) == 1:
        return map_fn(pieces[0], 1, 1)
    mapped = [map_fn(piece, i + 1, len(pieces)) for i, piece in enumerate(pieces)]
    return reduce_fn(mapped)
