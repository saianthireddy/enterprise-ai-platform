"""Loads the `vector-db/` adapters (hyphenated dir name -> path-based import) and
exposes a single `build_vector_store()` factory used by the retriever and API layer.
"""
from __future__ import annotations

import sys
from pathlib import Path

_VECTOR_DB_DIR = Path(__file__).resolve().parents[2] / "vector-db"
if str(_VECTOR_DB_DIR) not in sys.path:
    sys.path.insert(0, str(_VECTOR_DB_DIR))

from base import BaseVectorStore, VectorRecord  # noqa: E402
from memory_store import InMemoryVectorStore  # noqa: E402


def build_vector_store(backend: str = "memory", **kwargs) -> BaseVectorStore:
    if backend == "memory":
        return InMemoryVectorStore()
    if backend == "pinecone":
        from pinecone_store import PineconeVectorStore

        return PineconeVectorStore(**kwargs)
    raise ValueError(f"Unknown vector backend: {backend}")


__all__ = ["build_vector_store", "BaseVectorStore", "VectorRecord"]
