# Airflow

`dags/reindex_and_retrain_dag.py` runs daily at 03:00 UTC:

1. **Reindex** — ingests any new files in `data/uploads/` into the vector store.
2. **Evaluate** — runs the routing-accuracy eval suite from `ai/evaluation/`.
3. **Alert** — logs (and in production, Slack-notifies) if quality drops below threshold.

## Local run

```bash
pip install apache-airflow
export AIRFLOW_HOME=~/airflow
airflow db init
airflow dags test reindex_and_retrain 2026-01-01
```
