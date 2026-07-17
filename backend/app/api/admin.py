"""Admin-only analytics dashboard endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.rbac import require_admin
from app.models.schemas import AnalyticsSnapshot
from app.services.analytics_service import analytics_service
from app.services.user_store import user_store

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/analytics", response_model=AnalyticsSnapshot)
def analytics(user: dict = Depends(require_admin)) -> AnalyticsSnapshot:
    return analytics_service.snapshot()


@router.get("/users/count")
def user_count(user: dict = Depends(require_admin)) -> dict:
    return {"total_users": user_store.count()}
