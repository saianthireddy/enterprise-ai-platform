# MLOps

## What's "learned" here vs. rule-based

The agent router (`ai/agents/orchestrator.py::classify`) is rule-based by default — regex intent matching that scores 100% on the routing eval suite (`ai/evaluation/agent_routing_eval.py`) and requires no training data or GPU.

`ai/evaluation/train_router_model.py` trains an optional **learned** upgrade: a TF-IDF + Logistic Regression classifier, registered through a file-backed, MLflow-style `ModelRegistry` (`ai/evaluation/model_registry.py`) with the same champion/challenger promotion logic used in the [enterprise-mlops-platform](https://github.com/saianthireddy/enterprise-mlops-platform) repo — a new version is only promoted to `production` if it beats the current champion's held-out accuracy.

## Registry

```python
from ai.evaluation.model_registry import ModelRegistry

registry = ModelRegistry()               # artifacts/registry/ by default
registry.list_versions("intent_router")  # every trained version + metrics + stage
registry.load_production("intent_router")  # the current champion, or None
```

## Retraining pipeline

- **Manual**: `python scripts/train_router.py`
- **Scheduled**: `.github/workflows/train.yml` (weekly) and `airflow/dags/reindex_and_retrain_dag.py` (daily reindex + quality gate)
- **Drift signal**: the daily DAG re-runs the routing eval suite and alerts (Slack in production, stdout locally) if accuracy drops below `ROUTING_ACCURACY_THRESHOLD`

## Migrating to real MLflow

Swap `ModelRegistry` for `mlflow.sklearn.log_model(...)` + `mlflow.register_model(...)` — the call sites in `train_router_model.py` are the only place that needs to change; `ai/agents/orchestrator.py` never imports the registry directly, so the router stays decoupled from how models are versioned.
