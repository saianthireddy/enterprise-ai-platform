"""Drafts professional email replies grounded in thread context + KB citations."""
from __future__ import annotations

from typing import Any

from ai.agents.base import AgentResult, BaseAgent
from ai.prompts.templates import EMAIL_AGENT_SYSTEM
from ai.rag.hybrid_search import HybridRetriever


class EmailAgent(BaseAgent):
    name = "email"
    description = "Drafts context-grounded email replies for support and sales threads."
    capabilities = ["reply-drafting", "tone-matching", "citation-grounded"]

    def __init__(self, retriever: HybridRetriever | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.retriever = retriever

    def run(self, query: str, context: dict[str, Any] | None = None) -> AgentResult:
        context = context or {}
        recipient = context.get("recipient", "there")
        thread = context.get("thread", "")
        citations: list[dict[str, Any]] = []
        grounding = ""

        if self.retriever is not None:
            hits = self.retriever.search(query, top_k=3)
            if hits:
                grounding = "\n".join(f"- {h.text[:180]} [{h.source}]" for h in hits)
                citations = [
                    {"source": h.source, "snippet": h.text[:200], "score": h.score} for h in hits
                ]

        prompt = (
            f"Recipient: {recipient}\nThread so far:\n{thread}\n\n"
            f"Relevant knowledge:\n{grounding}\n\nDraft a reply addressing: {query}"
        )
        draft = self.llm.complete(EMAIL_AGENT_SYSTEM, prompt)
        if not draft or draft == prompt.strip():
            body_lines = [f"Hi {recipient},", "", query.strip()]
            if grounding:
                body_lines += ["", "Relevant details:", grounding]
            body_lines += ["", "Best regards,", "Support Team"]
            draft = "\n".join(body_lines)

        return AgentResult(output=draft, citations=citations, metadata={"recipient": recipient})
