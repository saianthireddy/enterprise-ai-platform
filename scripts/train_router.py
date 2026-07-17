"""CLI entrypoint: trains the intent-router model and registers/promotes it.
Runnable standalone or from CI (`.github/workflows/ci.yml` calls this on a
schedule) and from the Airflow DAG's retraining step.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.evaluation.train_router_model import train_and_register  # noqa: E402

if __name__ == "__main__":
    result = train_and_register()
    status = "PROMOTED to production" if result["promoted"] else "kept in staging"
    print(
        f"intent_router v{result['version']}: accuracy={result['accuracy']:.3f} "
        f"(champion={result['champion_accuracy']}) -> {status}"
    )
