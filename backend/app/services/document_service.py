"""Bridges uploaded files to the AI-layer ingestion pipeline and tracks metadata."""
from __future__ import annotations

import threading
import uuid
from pathlib import Path

from ai.embeddings.embedder import BaseEmbedder
from ai.rag.hybrid_search import HybridRetriever
from ai.rag.pipeline import ingest_document
from app.models.schemas import DocumentMetadata

UPLOAD_DIR = Path(__file__).resolve().parents[3] / "data" / "uploads"


class DocumentService:
    def __init__(self, retriever: HybridRetriever, embedder: BaseEmbedder) -> None:
        self.retriever = retriever
        self.embedder = embedder
        self._lock = threading.Lock()
        self._documents: dict[str, DocumentMetadata] = {}
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    def ingest(self, filename: str, content: bytes, content_type: str, uploaded_by: str) -> DocumentMetadata:
        doc_id = str(uuid.uuid4())
        dest = UPLOAD_DIR / f"{doc_id}_{filename}"
        dest.write_bytes(content)

        _, chunk_count = ingest_document(dest, self.retriever, self.embedder, doc_id=doc_id)

        metadata = DocumentMetadata(
            doc_id=doc_id,
            filename=filename,
            content_type=content_type,
            chunk_count=chunk_count,
            uploaded_by=uploaded_by,
        )
        with self._lock:
            self._documents[doc_id] = metadata
        return metadata

    def list_documents(self) -> list[DocumentMetadata]:
        with self._lock:
            return list(self._documents.values())

    def get(self, doc_id: str) -> DocumentMetadata | None:
        return self._documents.get(doc_id)
