"""Broad, org-wide knowledge-base search across every indexed source (docs,
tickets, wiki pages) — distinct from DocumentAgent, which is scoped to one
uploaded document via context.doc_id."""
from __future__ import annotations

from typing import Any

from ai.agents.base import AgentResult, BaseAgent
from ai.prompts.templates import DOCUMENT_QA_SYSTEM
from ai.rag.hybrid_search import HybridRetriever


class KnowledgeBaseAgent(BaseAgent):
    name = "knowledge_base"
    description = "Searches the entire organizational knowledge base (all sources, no doc filter)."
    capabilities = ["org-wide-search", "cross-document-synthesis"]

    def __init__(self, retriever: HybridRetriever, **kwargs) -> None:
        super().__init__(**kwargs)
        self.retriever = retriever

    def run(self, query: str, context: dict[str, Any] | None = None) -> AgentResult:
        top_k = (context or {}).get("top_k", 6)
        hits = self.retriever.search(query, top_k=top_k)
        if not hits:
            return AgentResult(
                output="Nothing in the knowledge base matches that yet. "
                "Try a broader query or check that the relevant documents were ingested.",
                metadata={"hits": 0},
            )

        sources = sorted({h.source for h in hits})
        context_block = "\n\n".join(f"[{h.source}] {h.text}" for h in hits)
        prompt = (
            f"Context from {len(sources)} source(s):\n{context_block}\n\n"
            f"Question: {query}\n\nSynthesize an answer citing sources as [source]."
        )
        answer = self.llm.complete(DOCUMENT_QA_SYSTEM, prompt)
        if not answer or answer == prompt.strip():
            answer = "Found relevant material across " + ", ".join(sources) + ". " + hits[0].text[:300]

        citations = [{"source": h.source, "snippet": h.text[:200], "score": h.score} for h in hits]
        return AgentResult(output=answer, citations=citations, metadata={"sources": sources})
