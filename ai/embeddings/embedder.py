"""Embedding backends behind one interface.

HashingEmbedder is deterministic and dependency-free, so ingestion, retrieval,
and the full test suite run without any API keys. OpenAIEmbedder is a drop-in
swap for production (config-selected via EMBEDDING_BACKEND).
"""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

import numpy as np


class BaseEmbedder(ABC):
    dimensions: int

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray: ...

    def embed_one(self, text: str) -> np.ndarray:
        return self.embed([text])[0]


class HashingEmbedder(BaseEmbedder):
    """Deterministic bag-of-hashed-tokens embedder normalized to unit length."""

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def _embed_one(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dimensions, dtype=np.float32)
        for token in text.lower().split():
            h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
            vec[h % self.dimensions] += 1.0
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._embed_one(t) for t in texts])


class OpenAIEmbedder(BaseEmbedder):
    """Wraps OpenAI's embeddings API. Requires OPENAI_API_KEY and network access."""

    def __init__(self, model: str = "text-embedding-3-small", api_key: str = "") -> None:
        self.model = model
        self.api_key = api_key
        self.dimensions = 1536

    def embed(self, texts: list[str]) -> np.ndarray:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAIEmbedder")
        from openai import OpenAI  # imported lazily so it's an optional dependency

        client = OpenAI(api_key=self.api_key)
        response = client.embeddings.create(model=self.model, input=texts)
        return np.array([d.embedding for d in response.data], dtype=np.float32)


def build_embedder(backend: str = "hashing", **kwargs) -> BaseEmbedder:
    if backend == "hashing":
        return HashingEmbedder(**kwargs)
    if backend == "openai":
        return OpenAIEmbedder(**kwargs)
    raise ValueError(f"Unknown embedding backend: {backend}")
