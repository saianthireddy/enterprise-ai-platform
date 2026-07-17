from ai.embeddings.embedder import HashingEmbedder
from ai.evaluation.agent_routing_eval import DEFAULT_ROUTING_SUITE, evaluate_routing
from ai.evaluation.retrieval_eval import EvalCase, evaluate_retrieval
from ai.rag.hybrid_search import HybridRetriever
from ai.rag.vector_store_factory import VectorRecord, build_vector_store


def test_routing_suite_achieves_full_accuracy():
    accuracy = evaluate_routing(DEFAULT_ROUTING_SUITE)
    assert accuracy == 1.0


def test_evaluate_routing_handles_empty_suite():
    assert evaluate_routing([]) == 0.0


def test_retrieval_eval_precision_and_recall():
    embedder = HashingEmbedder(dimensions=64)
    store = build_vector_store("memory")
    retriever = HybridRetriever(store, embedder)
    docs = {
        "refund-policy": "Customers can request a refund within 30 days of purchase.",
        "shipping-policy": "Standard shipping takes 5-7 business days within the US.",
    }
    for doc_id, text in docs.items():
        record = VectorRecord(
            id=doc_id, text=text, embedding=embedder.embed_one(text),
            metadata={"doc_id": doc_id, "source": doc_id},
        )
        retriever.index([record])

    cases = [
        EvalCase(query="How long do I have to request a refund?", relevant_doc_ids={"refund-policy"}),
        EvalCase(query="How long does shipping take?", relevant_doc_ids={"shipping-policy"}),
    ]
    report = evaluate_retrieval(retriever, cases, k=1)
    assert report.precision_at_k >= 0.5
    assert report.cases == 2
