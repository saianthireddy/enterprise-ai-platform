import numpy as np
import pytest

from ai.embeddings.embedder import HashingEmbedder
from ai.rag.hybrid_search import HybridRetriever
from ai.rag.splitter import chunk_text
from ai.rag.vector_store_factory import VectorRecord, build_vector_store


def test_chunk_text_respects_chunk_size():
    text = "\n\n".join([f"Paragraph {i} " + ("word " * 40) for i in range(10)])
    chunks = chunk_text(text, chunk_size=300, overlap=50)
    assert len(chunks) > 1
    assert all(len(c.text) <= 300 + 50 for c in chunks)


def test_chunk_text_rejects_bad_overlap():
    with pytest.raises(ValueError):
        chunk_text("hello", chunk_size=100, overlap=100)


def test_hashing_embedder_is_deterministic():
    embedder = HashingEmbedder(dimensions=64)
    v1 = embedder.embed_one("production RAG pipeline")
    v2 = embedder.embed_one("production RAG pipeline")
    assert np.allclose(v1, v2)
    assert v1.shape == (64,)


def test_hashing_embedder_unit_norm():
    embedder = HashingEmbedder(dimensions=64)
    v = embedder.embed_one("some text with several tokens")
    assert abs(np.linalg.norm(v) - 1.0) < 1e-6


def test_hybrid_retriever_finds_semantic_and_keyword_matches():
    embedder = HashingEmbedder(dimensions=64)
    store = build_vector_store("memory")
    retriever = HybridRetriever(store, embedder)

    docs = [
        ("doc-1", "The refund policy allows returns within 30 days of purchase."),
        ("doc-2", "Kubernetes deployments use readiness and liveness probes."),
        ("doc-3", "Refunds for enterprise contracts require manager approval."),
    ]
    records = [
        VectorRecord(
            id=doc_id, text=text, embedding=embedder.embed_one(text),
            metadata={"doc_id": doc_id, "source": doc_id},
        )
        for doc_id, text in docs
    ]
    retriever.index(records)

    results = retriever.search("What is the refund policy?", top_k=2)
    assert len(results) == 2
    # doc-1 has both the exact keyword match ("refund policy") and strong
    # semantic overlap, so it must rank first regardless of hashing collisions
    # in the other two candidates.
    assert results[0].doc_id == "doc-1"
    assert results[0].method in {"hybrid", "keyword", "semantic"}


def test_hybrid_retriever_respects_metadata_filters():
    embedder = HashingEmbedder(dimensions=32)
    store = build_vector_store("memory")
    retriever = HybridRetriever(store, embedder)
    alpha_text = "alpha content about billing"
    beta_text = "beta content about billing"
    records = [
        VectorRecord(
            id="a", text=alpha_text, embedding=embedder.embed_one(alpha_text),
            metadata={"doc_id": "a", "source": "a", "team": "finance"},
        ),
        VectorRecord(
            id="b", text=beta_text, embedding=embedder.embed_one(beta_text),
            metadata={"doc_id": "b", "source": "b", "team": "engineering"},
        ),
    ]
    retriever.index(records)
    results = retriever.search("billing", top_k=5, filters={"team": "finance"})
    assert all(r.doc_id == "a" for r in results)
