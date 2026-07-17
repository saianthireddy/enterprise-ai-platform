"""Answers questions grounded in a specific uploaded document via hybrid RAG."""
from __future__ import annotations

from typing import Any

from ai.agents.base import AgentResult, BaseAgent
from ai.prompts.templates import DOCUMENT_QA_SYSTEM
from ai.rag.hybrid_search import HybridRetriever


class DocumentAgent(BaseAgent):
    name = "document"
    description = "Answers questions grounded in a specific uploaded document."
    capabilities = ["pdf", "docx", "xlsx", "pptx", "citation-grounded-answers"]

    def __init__(self, retriever: HybridRetriever, **kwargs) -> None:
        super().__init__(**kwargs)
        self.retriever = retriever

    def run(self, query: str, context: dict[str, Any] | None = None) -> AgentResult:
        context = context or {}
        filters = {"doc_id": context["doc_id"]} if context.get("doc_id") else None
        hits = self.retriever.search(query, top_k=context.get("top_k", 4), filters=filters)

        if not hits:
            return AgentResult(
                output="I couldn't find that in the indexed document(s). "
                "Try uploading the source or rephrasing your question.",
                metadata={"hits": 0},
            )

        context_block = "\n\n".join(f"[{h.source}] {h.text}" for h in hits)
        prompt = (
            f"Context:\n{context_block}\n\nQuestion: {query}\n\n"
            "Answer using only the context above, citing sources as [source]."
        )
        answer = self.llm.complete(DOCUMENT_QA_SYSTEM, prompt)
        if not answer or answer == prompt.strip():
            # FakeLLM fallback: compose a deterministic extractive answer.
            top = hits[0]
            answer = f"Based on [{top.source}]: {top.text[:400]}"

        citations = [
            {"source": h.source, "snippet": h.text[:200], "score": h.score} for h in hits
        ]
        return AgentResult(output=answer, citations=citations, metadata={"hits": len(hits)})
