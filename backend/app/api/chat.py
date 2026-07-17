"""Chat endpoint: routes through the agent orchestrator, streams the response,
tracks conversation history/memory, and records analytics."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.auth.rbac import get_current_user
from app.dependencies import orchestrator
from app.models.schemas import ChatMessage, ChatMessageRole, ChatRequest, ChatResponse, Citation
from app.services.analytics_service import analytics_service
from app.services.conversation import conversation_store

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, user: dict = Depends(get_current_user)) -> ChatResponse:
    conversation_id = payload.conversation_id or conversation_store.create()
    if not conversation_store.exists(conversation_id):
        conversation_id = conversation_store.create()

    conversation_store.append(
        conversation_id, ChatMessage(role=ChatMessageRole.USER, content=payload.message)
    )

    route_result = orchestrator.route(
        payload.message,
        context={"memory": conversation_store.memory(conversation_id)},
        explicit_agent=payload.agent,
    )

    assistant_message = ChatMessage(
        role=ChatMessageRole.ASSISTANT, content=route_result.result.output
    )
    conversation_store.append(conversation_id, assistant_message)

    tokens = analytics_service.record_request(
        agent=route_result.agent_used,
        latency_ms=route_result.latency_ms,
        response_text=route_result.result.output,
        user_id=user["id"],
        had_citations=bool(route_result.result.citations),
    )

    return ChatResponse(
        conversation_id=conversation_id,
        agent_used=route_result.agent_used,
        message=assistant_message,
        citations=[Citation(**c) for c in route_result.result.citations],
        latency_ms=round(route_result.latency_ms, 2),
        tokens_used=tokens,
    )


@router.post("/stream")
def chat_stream(payload: ChatRequest, user: dict = Depends(get_current_user)) -> StreamingResponse:
    """Server-sent events stream: emits the answer token-by-token (whitespace
    split) so the frontend can render progressively, same as ChatGPT-style UIs."""

    def event_generator():
        conversation_id = payload.conversation_id or conversation_store.create()
        route_result = orchestrator.route(payload.message, explicit_agent=payload.agent)
        words = route_result.result.output.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            yield f"data: {json.dumps({'delta': chunk})}\n\n"
        done_payload = {
            "done": True,
            "conversation_id": conversation_id,
            "agent_used": route_result.agent_used,
        }
        yield f"data: {json.dumps(done_payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{conversation_id}/history", response_model=list[ChatMessage])
def history(conversation_id: str, user: dict = Depends(get_current_user)) -> list[ChatMessage]:
    return conversation_store.history(conversation_id)
