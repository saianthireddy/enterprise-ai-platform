"""Pinecone-backed vector store adapter. Requires PINECONE_API_KEY and network access."""
from __future__ import annotations

from typing import Any

import numpy as np

from base import BaseVectorStore, VectorRecord


class PineconeVectorStore(BaseVectorStore):
    def __init__(self, api_key: str, index_name: str, dimensions: int = 256) -> None:
        if not api_key:
            raise RuntimeError("PINECONE_API_KEY is required for PineconeVectorStore")
        from pinecone import Pinecone  # imported lazily; optional dependency

        self._client = Pinecone(api_key=api_key)
        existing = {i.name for i in self._client.list_indexes()}
        if index_name not in existing:
            from pinecone import ServerlessSpec

            self._client.create_index(
                name=index_name,
                dimension=dimensions,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
        self._index = self._client.Index(index_name)

    def upsert(self, records: list[VectorRecord]) -> None:
        vectors = [(r.id, r.embedding.tolist(), r.metadata | {"text": r.text}) for r in records]
        self._index.upsert(vectors=vectors)

    def query(self, embedding: np.ndarray, top_k: int = 5, filters: dict[str, Any] | None = None) -> list[tuple[VectorRecord, float]]:
        result = self._index.query(
            vector=embedding.tolist(), top_k=top_k, include_metadata=True, filter=filters or None
        )
        out = []
        for match in result.matches:
            meta = dict(match.metadata or {})
            text = meta.pop("text", "")
            record = VectorRecord(id=match.id, text=text, embedding=embedding, metadata=meta)
            out.append((record, float(match.score)))
        return out

    def delete(self, ids: list[str]) -> None:
        self._index.delete(ids=ids)

    def count(self) -> int:
        stats = self._index.describe_index_stats()
        return int(stats.get("total_vector_count", 0))
