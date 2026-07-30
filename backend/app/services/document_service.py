"""Bridges uploaded files to the AI-layer ingestion pipeline and tracks metadata.

The uploaded bytes always went to disk; only the metadata was in a dict, so after
a restart the files existed but the platform had no record of them. Metadata now
lives in SQLite alongside users and conversations.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from ai.embeddings.embedder import BaseEmbedder
from ai.rag.hybrid_search import HybridRetriever
from ai.rag.pipeline import ingest_document
from app.config import settings
from app.models.schemas import DocumentMetadata
from app.services.db import Database

UPLOAD_DIR = Path(__file__).resolve().parents[3] / "data" / "uploads"


def _row_to_metadata(row) -> DocumentMetadata:
    return DocumentMetadata(
        doc_id=row["doc_id"],
        filename=row["filename"],
        content_type=row["content_type"],
        chunk_count=row["chunk_count"],
        uploaded_at=datetime.fromisoformat(row["uploaded_at"]),
        uploaded_by=row["uploaded_by"],
    )


class DocumentService:
    def __init__(
        self,
        retriever: HybridRetriever,
        embedder: BaseEmbedder,
        db: Database | None = None,
    ) -> None:
        self.retriever = retriever
        self.embedder = embedder
        self.db = db or Database(settings.database_url)
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
        self.db.execute(
            "INSERT INTO documents (doc_id, filename, content_type, chunk_count, uploaded_at, uploaded_by)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                metadata.doc_id,
                metadata.filename,
                metadata.content_type,
                metadata.chunk_count,
                metadata.uploaded_at.isoformat(),
                metadata.uploaded_by,
            ),
        )
        return metadata

    def list_documents(self) -> list[DocumentMetadata]:
        rows = self.db.query("SELECT * FROM documents ORDER BY uploaded_at")
        return [_row_to_metadata(r) for r in rows]

    def get(self, doc_id: str) -> DocumentMetadata | None:
        row = self.db.query_one("SELECT * FROM documents WHERE doc_id = ?", (doc_id,))
        return _row_to_metadata(row) if row else None
