"""Process-wide singletons: embedder, vector store, retriever, orchestrator,
document service. Built once at import time so every request shares the same
in-memory index — swap `build_embedder`/`build_vector_store` backends via env vars only."""
from __future__ import annotations

from ai.agents.orchestrator import AgentOrchestrator
from ai.embeddings.embedder import build_embedder
from ai.rag.hybrid_search import HybridRetriever
from ai.rag.vector_store_factory import build_vector_store
from app.config import settings
from app.services.document_service import DocumentService

embedder = build_embedder("hashing")
vector_store = build_vector_store(
    settings.vector_backend if settings.vector_backend == "memory" else "memory"
)
retriever = HybridRetriever(vector_store, embedder)
orchestrator = AgentOrchestrator(retriever)
document_service = DocumentService(retriever, embedder)
