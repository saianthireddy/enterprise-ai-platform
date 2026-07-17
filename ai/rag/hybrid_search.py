"""Hybrid retrieval: semantic (embedding cosine) + keyword (TF-IDF) + metadata filters.

Scores are combined with a configurable weight (default 60% semantic / 40%
keyword), which consistently outperforms either signal alone on queries that
mix natural language with exact identifiers (ticket numbers, product codes).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ai.embeddings.embedder import BaseEmbedder
from ai.rag.vector_store_factory import BaseVectorStore, VectorRecord


@dataclass
class HybridResult:
    doc_id: str
    chunk_id: str
    text: str
    score: float
    source: str
    method: str


class HybridRetriever:
    def __init__(
        self,
        vector_store: BaseVectorStore,
        embedder: BaseEmbedder,
        semantic_weight: float = 0.6,
    ) -> None:
        self.vector_store = vector_store
        self.embedder = embedder
        self.semantic_weight = semantic_weight
        self._keyword_corpus: list[VectorRecord] = []
        self._vectorizer: TfidfVectorizer | None = None
        self._tfidf_matrix = None

    def index(self, records: list[VectorRecord]) -> None:
        self.vector_store.upsert(records)
        self._keyword_corpus.extend(records)
        self._rebuild_keyword_index()

    def _rebuild_keyword_index(self) -> None:
        if not self._keyword_corpus:
            return
        self._vectorizer = TfidfVectorizer(stop_words="english")
        self._tfidf_matrix = self._vectorizer.fit_transform(
            [r.text for r in self._keyword_corpus]
        )

    def _keyword_search(self, query: str, top_k: int) -> list[tuple[VectorRecord, float]]:
        if self._vectorizer is None or self._tfidf_matrix is None:
            return []
        query_vec = self._vectorizer.transform([query])
        sims = cosine_similarity(query_vec, self._tfidf_matrix)[0]
        ranked = sorted(
            zip(self._keyword_corpus, sims, strict=True), key=lambda pair: pair[1], reverse=True
        )
        return [(rec, float(score)) for rec, score in ranked[:top_k] if score > 0]

    def search(
        self, query: str, top_k: int = 5, filters: dict[str, Any] | None = None
    ) -> list[HybridResult]:
        query_embedding = self.embedder.embed_one(query)
        semantic_hits = self.vector_store.query(query_embedding, top_k=top_k * 2, filters=filters)
        keyword_hits = self._keyword_search(query, top_k=top_k * 2)

        combined: dict[str, dict[str, Any]] = {}
        for record, score in semantic_hits:
            combined[record.id] = {
                "record": record,
                "semantic": score,
                "keyword": 0.0,
            }
        for record, score in keyword_hits:
            if filters and not all(record.metadata.get(k) == v for k, v in filters.items()):
                continue
            entry = combined.setdefault(record.id, {"record": record, "semantic": 0.0, "keyword": 0.0})
            entry["keyword"] = max(entry["keyword"], score)

        results: list[HybridResult] = []
        for entry in combined.values():
            record: VectorRecord = entry["record"]
            blended = (
                self.semantic_weight * entry["semantic"]
                + (1 - self.semantic_weight) * entry["keyword"]
            )
            method = "hybrid" if entry["semantic"] > 0 and entry["keyword"] > 0 else (
                "semantic" if entry["semantic"] > 0 else "keyword"
            )
            results.append(
                HybridResult(
                    doc_id=str(record.metadata.get("doc_id", record.id)),
                    chunk_id=record.id,
                    text=record.text,
                    score=round(blended, 4),
                    source=str(record.metadata.get("source", "unknown")),
                    method=method,
                )
            )
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]
