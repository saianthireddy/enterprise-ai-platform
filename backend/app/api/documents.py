"""Document upload + search endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.auth.rbac import get_current_user
from app.config import settings
from app.dependencies import document_service, retriever
from app.models.schemas import DocumentMetadata, SearchRequest, SearchResult

router = APIRouter(prefix="/documents", tags=["documents"])

SUPPORTED_TYPES = {".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md"}


@router.post("/upload", response_model=DocumentMetadata, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile, user: dict = Depends(get_current_user)
) -> DocumentMetadata:
    suffix = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if suffix not in SUPPORTED_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported file type '{suffix}'. Supported: {sorted(SUPPORTED_TYPES)}",
        )
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File exceeds max upload size")

    return document_service.ingest(
        filename=file.filename,
        content=content,
        content_type=file.content_type or "application/octet-stream",
        uploaded_by=user["id"],
    )


@router.get("", response_model=list[DocumentMetadata])
def list_documents(user: dict = Depends(get_current_user)) -> list[DocumentMetadata]:
    return document_service.list_documents()


@router.post("/search", response_model=list[SearchResult])
def search_documents(payload: SearchRequest, user: dict = Depends(get_current_user)) -> list[SearchResult]:
    hits = retriever.search(payload.query, top_k=payload.top_k, filters=payload.filters or None)
    return [
        SearchResult(
            doc_id=h.doc_id, chunk_id=h.chunk_id, text=h.text, score=h.score, source=h.source, method=h.method
        )
        for h in hits
    ]
