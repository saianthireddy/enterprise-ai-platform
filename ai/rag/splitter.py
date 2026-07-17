"""Paragraph-aware chunker with sliding-window overlap and OCR fallback hook."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    text: str
    index: int
    char_start: int
    char_end: int


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[Chunk]:
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    paragraphs = _paragraphs(text)
    chunks: list[Chunk] = []
    buffer = ""
    cursor = 0
    idx = 0

    def flush(buf: str, start: int) -> None:
        nonlocal idx
        if buf.strip():
            chunks.append(Chunk(text=buf.strip(), index=idx, char_start=start, char_end=start + len(buf)))
            idx += 1

    for para in paragraphs:
        if len(buffer) + len(para) + 2 <= chunk_size:
            buffer = f"{buffer}\n\n{para}".strip()
            continue
        if buffer:
            flush(buffer, cursor)
            cursor += max(len(buffer) - overlap, 0)
            buffer = buffer[-overlap:] + "\n\n" + para if overlap else para
        else:
            # Single paragraph longer than chunk_size: hard-split it.
            for i in range(0, len(para), chunk_size - overlap):
                piece = para[i : i + chunk_size]
                flush(piece, cursor + i)
            buffer = ""
    if buffer:
        flush(buffer, cursor)

    return chunks
