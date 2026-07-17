"""Offline retrieval evaluation: precision@k / recall@k against a fixed,
hand-labeled test set. Used in CI to catch retrieval regressions."""
from __future__ import annotations

from dataclasses import dataclass

from ai.rag.hybrid_search import HybridRetriever


@dataclass
class EvalCase:
    query: str
    relevant_doc_ids: set[str]


@dataclass
class EvalReport:
    precision_at_k: float
    recall_at_k: float
    cases: int


def evaluate_retrieval(retriever: HybridRetriever, cases: list[EvalCase], k: int = 5) -> EvalReport:
    precisions, recalls = [], []
    for case in cases:
        hits = retriever.search(case.query, top_k=k)
        retrieved_ids = {h.doc_id for h in hits}
        true_positives = retrieved_ids & case.relevant_doc_ids
        precisions.append(len(true_positives) / max(len(retrieved_ids), 1))
        recalls.append(len(true_positives) / max(len(case.relevant_doc_ids), 1))

    n = max(len(cases), 1)
    return EvalReport(
        precision_at_k=round(sum(precisions) / n, 4),
        recall_at_k=round(sum(recalls) / n, 4),
        cases=len(cases),
    )
