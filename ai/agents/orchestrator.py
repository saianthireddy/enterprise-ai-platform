"""Lightweight, dependency-free state-graph orchestrator in the spirit of
LangGraph: a router node classifies intent, then dispatches to exactly one
specialist-agent node. Swapping in real `langgraph.StateGraph` later is a
drop-in change — this module is the seam.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

from ai.agents.base import AgentResult
from ai.agents.code_agent import CodeAssistantAgent
from ai.agents.document_agent import DocumentAgent
from ai.agents.email_agent import EmailAgent
from ai.agents.knowledge_base_agent import KnowledgeBaseAgent
from ai.agents.report_agent import ReportGeneratorAgent
from ai.agents.sql_agent import SQLAgent
from ai.rag.hybrid_search import HybridRetriever

# Keyword scoring is deterministic and offline; swap for an embedding- or
# LLM-based router in production by replacing `classify()` only.
ROUTING_RULES: list[tuple[str, re.Pattern]] = [
    ("sql", re.compile(r"\b(how many|count|total|revenue|sales|sql|database|query)\b", re.I)),
    ("email", re.compile(r"\b(draft|reply|email|respond to|write back)\b", re.I)),
    ("report", re.compile(r"\b(report|summary|summarize|weekly|dashboard)\b", re.I)),
    ("code", re.compile(r"\b(code|function|bug|review this|refactor|python|javascript)\b", re.I)),
    ("document", re.compile(r"\b(this document|the pdf|the file|uploaded)\b", re.I)),
]


def classify(query: str, explicit_agent: str | None = None) -> str:
    if explicit_agent:
        return explicit_agent
    for agent_name, pattern in ROUTING_RULES:
        if pattern.search(query):
            return agent_name
    return "knowledge_base"


@dataclass
class RouteResult:
    agent_used: str
    result: AgentResult
    latency_ms: float


class AgentOrchestrator:
    """The graph: a single router node fanning out to 6 leaf agent nodes."""

    def __init__(self, retriever: HybridRetriever, db_path: str | None = None) -> None:
        self.retriever = retriever
        kwargs = {"db_path": db_path} if db_path else {}
        self.agents = {
            "document": DocumentAgent(retriever),
            "sql": SQLAgent(**kwargs),
            "email": EmailAgent(retriever),
            "report": ReportGeneratorAgent(),
            "code": CodeAssistantAgent(),
            "knowledge_base": KnowledgeBaseAgent(retriever),
        }

    def list_agents(self) -> list[dict[str, Any]]:
        return [
            {"name": a.name, "description": a.description, "capabilities": a.capabilities}
            for a in self.agents.values()
        ]

    def route(
        self, query: str, context: dict[str, Any] | None = None, explicit_agent: str | None = None
    ) -> RouteResult:
        agent_name = classify(query, explicit_agent)
        agent = self.agents.get(agent_name, self.agents["knowledge_base"])
        start = time.perf_counter()
        result = agent.run(query, context)
        latency_ms = (time.perf_counter() - start) * 1000
        return RouteResult(agent_used=agent.name, result=result, latency_ms=latency_ms)
