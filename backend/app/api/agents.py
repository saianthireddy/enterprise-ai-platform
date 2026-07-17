"""Agent catalog + direct-invoke endpoints (bypassing the chat/history wrapper)."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.rbac import get_current_user
from app.dependencies import orchestrator
from app.models.schemas import AgentInfo, AgentInvokeRequest, AgentInvokeResponse, Citation

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentInfo])
def list_agents(user: dict = Depends(get_current_user)) -> list[AgentInfo]:
    return [AgentInfo(**a) for a in orchestrator.list_agents()]


@router.post("/{agent_name}/invoke", response_model=AgentInvokeResponse)
def invoke_agent(
    agent_name: str, payload: AgentInvokeRequest, user: dict = Depends(get_current_user)
) -> AgentInvokeResponse:
    if agent_name not in orchestrator.agents:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown agent '{agent_name}'")
    start = time.perf_counter()
    result = orchestrator.agents[agent_name].run(payload.query, payload.context)
    latency_ms = (time.perf_counter() - start) * 1000
    return AgentInvokeResponse(
        agent=agent_name,
        output=result.output,
        citations=[Citation(**c) for c in result.citations],
        metadata=result.metadata,
        latency_ms=round(latency_ms, 2),
    )
