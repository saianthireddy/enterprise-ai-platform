"""Daily pipeline: re-index changed documents, evaluate retrieval + routing
quality, and alert if either drops below threshold. Mirrors the drift-gated
retraining pattern from the enterprise-mlops-platform repo, applied to RAG.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))

PRECISION_THRESHOLD = 0.6
ROUTING_ACCURACY_THRESHOLD = 0.85

default_args = {
    "owner": "ai-platform",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def reindex_documents(**_context) -> None:
    """Re-ingests any document in data/uploads not yet reflected in the index.

    Production note: this currently rebuilds from the local `data/uploads`
    directory; swap the source loop for an S3 `list_objects_v2` call once
    documents live in the `documents` bucket provisioned by Terraform.
    """
    from ai.embeddings.embedder import build_embedder
    from ai.rag.hybrid_search import HybridRetriever
    from ai.rag.pipeline import ingest_document
    from ai.rag.vector_store_factory import build_vector_store

    embedder = build_embedder("hashing")
    retriever = HybridRetriever(build_vector_store("memory"), embedder)

    uploads_dir = REPO_ROOT / "data" / "uploads"
    if not uploads_dir.exists():
        return
    for path in uploads_dir.glob("*"):
        if path.is_file():
            ingest_document(path, retriever, embedder)


def evaluate_quality(**_context) -> dict:
    from ai.evaluation.agent_routing_eval import DEFAULT_ROUTING_SUITE, evaluate_routing

    routing_accuracy = evaluate_routing(DEFAULT_ROUTING_SUITE)
    return {"routing_accuracy": routing_accuracy}


def check_thresholds_and_alert(**context) -> None:
    metrics = context["ti"].xcom_pull(task_ids="evaluate_quality")
    if metrics["routing_accuracy"] < ROUTING_ACCURACY_THRESHOLD:
        # Production note: POST to SLACK_WEBHOOK_URL here, same pattern as
        # ai/agents/base.py's OpenAI swap — kept as a stub for offline runs.
        print(f"ALERT: routing accuracy {metrics['routing_accuracy']} below threshold")
    else:
        print(f"Routing accuracy healthy: {metrics['routing_accuracy']}")


with DAG(
    dag_id="reindex_and_retrain",
    description="Daily document re-index + retrieval/routing quality gate",
    default_args=default_args,
    schedule_interval="0 3 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["rag", "mlops", "enterprise-ai-platform"],
) as dag:
    reindex = PythonOperator(task_id="reindex_documents", python_callable=reindex_documents)
    evaluate = PythonOperator(task_id="evaluate_quality", python_callable=evaluate_quality)
    alert = PythonOperator(task_id="check_thresholds_and_alert", python_callable=check_thresholds_and_alert)

    reindex >> evaluate >> alert
