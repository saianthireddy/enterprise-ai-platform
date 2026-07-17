"""File-backed, versioned model registry — MLflow-style API (register / list /
promote / load) without requiring a running MLflow server. Swappable for
`mlflow.sklearn.log_model` + the MLflow Model Registry by keeping this same
interface; see `docs/MLOPS.md` for the migration note.
"""
from __future__ import annotations

import json
import pickle
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone  # noqa: UP017
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY_ROOT = Path(__file__).resolve().parents[2] / "artifacts" / "registry"


@dataclass
class ModelVersion:
    name: str
    version: int
    stage: str  # "staging" | "production" | "archived"
    metrics: dict[str, float] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()  # noqa: UP017
    )


class ModelRegistry:
    def __init__(self, root: str | Path = DEFAULT_REGISTRY_ROOT) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _model_dir(self, name: str) -> Path:
        d = self.root / name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _manifest_path(self, name: str) -> Path:
        return self._model_dir(name) / "manifest.json"

    def _load_manifest(self, name: str) -> list[dict[str, Any]]:
        path = self._manifest_path(name)
        if not path.exists():
            return []
        return json.loads(path.read_text())

    def register(self, name: str, model: Any, metrics: dict[str, float]) -> ModelVersion:
        with self._lock:
            manifest = self._load_manifest(name)
            version = len(manifest) + 1
            artifact_path = self._model_dir(name) / f"v{version}.pkl"
            with artifact_path.open("wb") as f:
                pickle.dump(model, f)

            mv = ModelVersion(name=name, version=version, stage="staging", metrics=metrics)
            manifest.append(asdict(mv))
            self._manifest_path(name).write_text(json.dumps(manifest, indent=2))
            return mv

    def promote(self, name: str, version: int, stage: str) -> None:
        with self._lock:
            manifest = self._load_manifest(name)
            for entry in manifest:
                if entry["version"] == version:
                    entry["stage"] = stage
                elif stage == "production" and entry["stage"] == "production":
                    entry["stage"] = "archived"
            self._manifest_path(name).write_text(json.dumps(manifest, indent=2))

    def list_versions(self, name: str) -> list[ModelVersion]:
        return [ModelVersion(**e) for e in self._load_manifest(name)]

    def load(self, name: str, version: int) -> Any:
        artifact_path = self._model_dir(name) / f"v{version}.pkl"
        with artifact_path.open("rb") as f:
            return pickle.load(f)

    def load_production(self, name: str) -> Any | None:
        for mv in self.list_versions(name):
            if mv.stage == "production":
                return self.load(name, mv.version)
        return None
