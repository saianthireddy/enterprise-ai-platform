"""Pure-Python cosine-similarity vector store — the default, zero-dependency backend."""
from __future__ import annotations

from typing import Any

import numpy as np

from base import BaseVectorStore, VectorRecord


class InMemoryVectorStore(BaseVectorStore):
    def __init__(self) -> None:
        self._records: dict[str, VectorRecord] = {}

    def upsert(self, records: list[VectorRecord]) -> None:
        for record in records:
            self._records[record.id] = record

    def query(self, embedding: np.ndarray, top_k: int = 5, filters: dict[str, Any] | None = None) -> list[tuple[VectorRecord, float]]:
        candidates = list(self._records.values())
        if filters:
            candidates = [
                r for r in candidates
                if all(r.metadata.get(k) == v for k, v in filters.items())
            ]
        scored = []
        for record in candidates:
            denom = np.linalg.norm(embedding) * np.linalg.norm(record.embedding)
            score = float(np.dot(embedding, record.embedding) / denom) if denom > 0 else 0.0
            scored.append((record, score))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]

    def delete(self, ids: list[str]) -> None:
        for i in ids:
            self._records.pop(i, None)

    def count(self) -> int:
        return len(self._records)
