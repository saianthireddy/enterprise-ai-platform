"""Pydantic schemas shared across the API."""
from __future__ import annotations

from datetime import datetime, timezone  # noqa: UP017 - datetime.UTC requires py3.11+
from enum import Enum
from typing import Any

from pydantic import BaseModel, EmailStr, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)  # noqa: UP017


class Role(str, Enum):
    ADMIN = "admin"
    USER = "user"


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=120)


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: Role
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class OAuthLoginRequest(BaseModel):
    provider: str = "google"
    code: str


class ChatMessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    role: ChatMessageRole
    content: str
    created_at: datetime = Field(default_factory=utcnow)


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(min_length=1)
    agent: str | None = None  # explicit agent override; None => auto-route


class Citation(BaseModel):
    source: str
    snippet: str
    score: float


class ChatResponse(BaseModel):
    conversation_id: str
    agent_used: str
    message: ChatMessage
    citations: list[Citation] = Field(default_factory=list)
    latency_ms: float
    tokens_used: int


class DocumentMetadata(BaseModel):
    doc_id: str
    filename: str
    content_type: str
    chunk_count: int
    uploaded_at: datetime = Field(default_factory=utcnow)
    uploaded_by: str


class SearchResult(BaseModel):
    doc_id: str
    chunk_id: str
    text: str
    score: float
    source: str
    method: str  # "semantic" | "keyword" | "hybrid"


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = 5
    filters: dict[str, Any] = Field(default_factory=dict)


class AgentInfo(BaseModel):
    name: str
    description: str
    capabilities: list[str]


class AgentInvokeRequest(BaseModel):
    query: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)


class AgentInvokeResponse(BaseModel):
    agent: str
    output: str
    citations: list[Citation] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float


class AnalyticsSnapshot(BaseModel):
    active_users: int
    ai_requests_total: int
    token_usage_total: int
    estimated_cost_usd: float
    avg_latency_ms: float
    search_accuracy: float
    requests_by_agent: dict[str, int]
    generated_at: datetime = Field(default_factory=utcnow)
