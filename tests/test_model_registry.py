import pytest

from ai.evaluation.model_registry import ModelRegistry
from ai.evaluation.train_router_model import train_and_register


@pytest.fixture()
def registry(tmp_path):
    return ModelRegistry(root=tmp_path / "registry")


def test_first_version_is_promoted(registry):
    result = train_and_register(registry)
    assert result["version"] == 1
    assert result["promoted"] is True
    versions = registry.list_versions("intent_router")
    assert versions[0].stage == "production"


def test_load_production_returns_a_fitted_pipeline(registry):
    train_and_register(registry)
    model = registry.load_production("intent_router")
    assert model is not None
    prediction = model.predict(["How many open tickets are there?"])
    assert prediction[0] in {"sql", "email", "report", "code", "document", "knowledge_base"}


def test_second_version_registers_as_new_entry(registry):
    train_and_register(registry)
    result2 = train_and_register(registry)
    assert result2["version"] == 2
    assert len(registry.list_versions("intent_router")) == 2


def test_promote_archives_previous_champion(registry):
    train_and_register(registry)
    train_and_register(registry)
    versions = registry.list_versions("intent_router")
    production = [v for v in versions if v.stage == "production"]
    assert len(production) == 1
