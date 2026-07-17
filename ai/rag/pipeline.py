"""Ties loader -> splitter -> embedder -> hybrid index into one ingestion call."""
from __future__ import annotations

import uuid
from pathlib import Path

from ai.embeddings.embedder import BaseEmbedder
from ai.rag.hybrid_search import HybridRetriever
from ai.rag.loader import load_document
from ai.rag.splitter import chunk_text
from ai.rag.vector_store_factory import VectorRecord


def ingest_document(
    path: str | Path,
    retriever: HybridRetriever,
    embedder: BaseEmbedder,
    doc_id: str | None = None,
    chunk_size: int = 800,
    overlap: int = 150,
) -> tuple[str, int]:
    doc_id = doc_id or str(uuid.uuid4())
    raw_text = load_document(path)
    chunks = chunk_text(raw_text, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        return doc_id, 0

    embeddings = embedder.embed([c.text for c in chunks])
    records = [
        VectorRecord(
            id=f"{doc_id}::{chunk.index}",
            text=chunk.text,
            embedding=embeddings[i],
            metadata={"doc_id": doc_id, "source": Path(path).name, "chunk_index": chunk.index},
        )
        for i, chunk in enumerate(chunks)
    ]
    retriever.index(records)
    return doc_id, len(records)


def ingest_raw_text(
    text: str,
    source: str,
    retriever: HybridRetriever,
    embedder: BaseEmbedder,
    doc_id: str | None = None,
    chunk_size: int = 800,
    overlap: int = 150,
) -> tuple[str, int]:
    doc_id = doc_id or str(uuid.uuid4())
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        return doc_id, 0
    embeddings = embedder.embed([c.text for c in chunks])
    records = [
        VectorRecord(
            id=f"{doc_id}::{chunk.index}",
            text=chunk.text,
            embedding=embeddings[i],
            metadata={"doc_id": doc_id, "source": source, "chunk_index": chunk.index},
        )
        for i, chunk in enumerate(chunks)
    ]
    retriever.index(records)
    return doc_id, len(records)
