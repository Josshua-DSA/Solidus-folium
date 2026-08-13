"""
Tests for model/registry.py — Model Registry CRUD, lifecycle, and loading.
"""
import os
import pickle
import tempfile
import pytest

from model.registry import (
    ModelRegistry, ModelVersion,
    STAGE_STAGING, STAGE_PRODUCTION, STAGE_ARCHIVED,
)


@pytest.fixture
def tmp_registry(tmp_path):
    """Create a temporary registry with temp dirs."""
    artifacts_dir = str(tmp_path / "saved_models")
    db_path = str(tmp_path / "registry.db")
    return ModelRegistry(artifacts_dir=artifacts_dir, db_path=db_path)


@pytest.fixture
def sample_artifact(tmp_path):
    """Create a dummy .pkl artifact."""
    model_dir = tmp_path / "saved_models"
    model_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = str(model_dir / "test_model.pkl")
    with open(artifact_path, "wb") as f:
        pickle.dump({"model": "dummy", "config": {}, "feature_names": ["f1"], "best_params": {}}, f)
    return artifact_path


class TestModelRegistryInit:
    def test_init_creates_db(self, tmp_registry):
        assert os.path.exists(tmp_registry.db_path)

    def test_repr(self, tmp_registry):
        assert "ModelRegistry" in repr(tmp_registry)


class TestModelRegistryRegister:
    def test_register_model(self, tmp_registry, sample_artifact):
        mv = tmp_registry.register(
            model_type="xgboost",
            artifact_path=sample_artifact,
            metrics={"accuracy": 0.75, "f1_macro": 0.72, "auc_ovr": 0.80, "log_loss": 0.90},
            description="Test model v1",
        )
        assert mv.version_id == "xgboost_v001"
        assert mv.stage == STAGE_STAGING
        assert mv.metrics["accuracy"] == 0.75

    def test_register_increments_version(self, tmp_registry, sample_artifact):
        tmp_registry.register("xgboost", sample_artifact, {"accuracy": 0.70})
        mv2 = tmp_registry.register("xgboost", sample_artifact, {"accuracy": 0.75})
        assert mv2.version_id == "xgboost_v002"

    def test_register_different_types(self, tmp_registry, sample_artifact):
        mv1 = tmp_registry.register("xgboost", sample_artifact, {"accuracy": 0.70})
        mv2 = tmp_registry.register("lightgbm", sample_artifact, {"accuracy": 0.72})
        assert mv1.version_id == "xgboost_v001"
        assert mv2.version_id == "lightgbm_v001"


class TestModelRegistryQuery:
    def test_list_all(self, tmp_registry, sample_artifact):
        tmp_registry.register("xgboost", sample_artifact, {"accuracy": 0.70})
        tmp_registry.register("lightgbm", sample_artifact, {"accuracy": 0.72})
        assert len(tmp_registry.list_versions()) == 2

    def test_list_by_type(self, tmp_registry, sample_artifact):
        tmp_registry.register("xgboost", sample_artifact, {"accuracy": 0.70})
        tmp_registry.register("lightgbm", sample_artifact, {"accuracy": 0.72})
        xgb = tmp_registry.list_versions(model_type="xgboost")
        assert len(xgb) == 1
        assert xgb[0].model_type == "xgboost"

    def test_list_by_stage(self, tmp_registry, sample_artifact):
        tmp_registry.register("xgboost", sample_artifact, {"accuracy": 0.70}, stage=STAGE_PRODUCTION)
        tmp_registry.register("xgboost", sample_artifact, {"accuracy": 0.72})
        prod = tmp_registry.list_versions(stage=STAGE_PRODUCTION)
        assert len(prod) == 1

    def test_get_version(self, tmp_registry, sample_artifact):
        tmp_registry.register("xgboost", sample_artifact, {"accuracy": 0.70})
        mv = tmp_registry.get_version("xgboost_v001")
        assert mv is not None
        assert mv.model_type == "xgboost"

    def test_get_version_not_found(self, tmp_registry):
        assert tmp_registry.get_version("nonexistent_v999") is None

    def test_get_latest(self, tmp_registry, sample_artifact):
        tmp_registry.register("xgboost", sample_artifact, {"accuracy": 0.70})
        tmp_registry.register("xgboost", sample_artifact, {"accuracy": 0.75})
        latest = tmp_registry.get_latest(model_type="xgboost")
        assert latest.version_id == "xgboost_v002"


class TestModelRegistryLifecycle:
    def test_promote_to_production(self, tmp_registry, sample_artifact):
        tmp_registry.register("xgboost", sample_artifact, {"accuracy": 0.70})
        mv = tmp_registry.promote("xgboost_v001", STAGE_PRODUCTION)
        assert mv.stage == STAGE_PRODUCTION
        prod = tmp_registry.get_production_model("xgboost")
        assert prod.version_id == "xgboost_v001"

    def test_promote_demotes_old_production(self, tmp_registry, sample_artifact):
        tmp_registry.register("xgboost", sample_artifact, {"accuracy": 0.70})
        tmp_registry.register("xgboost", sample_artifact, {"accuracy": 0.75})
        tmp_registry.promote("xgboost_v001", STAGE_PRODUCTION)
        tmp_registry.promote("xgboost_v002", STAGE_PRODUCTION)

        old = tmp_registry.get_version("xgboost_v001")
        assert old.stage == STAGE_ARCHIVED

        new = tmp_registry.get_production_model("xgboost")
        assert new.version_id == "xgboost_v002"

    def test_archive(self, tmp_registry, sample_artifact):
        tmp_registry.register("xgboost", sample_artifact, {"accuracy": 0.70})
        tmp_registry.archive("xgboost_v001")
        mv = tmp_registry.get_version("xgboost_v001")
        assert mv.stage == STAGE_ARCHIVED

    def test_delete(self, tmp_registry, sample_artifact):
        tmp_registry.register("xgboost", sample_artifact, {"accuracy": 0.70})
        tmp_registry.delete("xgboost_v001")
        assert tmp_registry.get_version("xgboost_v001") is None

    def test_promote_nonexistent_raises(self, tmp_registry):
        with pytest.raises(ValueError):
            tmp_registry.promote("nonexistent_v999")


class TestModelRegistryLoad:
    def test_load_model_by_version(self, tmp_registry, sample_artifact):
        tmp_registry.register("xgboost", sample_artifact, {"accuracy": 0.70})
        data = tmp_registry.load_model(version_id="xgboost_v001")
        assert data is not None
        assert data["model"] == "dummy"

    def test_load_production_model(self, tmp_registry, sample_artifact):
        tmp_registry.register("xgboost", sample_artifact, {"accuracy": 0.70})
        tmp_registry.promote("xgboost_v001", STAGE_PRODUCTION)
        data = tmp_registry.load_model(model_type="xgboost")
        assert data is not None

    def test_load_returns_none_when_empty(self, tmp_registry):
        data = tmp_registry.load_model(model_type="xgboost")
        assert data is None


class TestModelRegistryCompare:
    def test_compare_sorted_by_f1(self, tmp_registry, sample_artifact):
        tmp_registry.register("xgboost", sample_artifact, {"accuracy": 0.70, "f1_macro": 0.65})
        tmp_registry.register("xgboost", sample_artifact, {"accuracy": 0.72, "f1_macro": 0.80})
        rows = tmp_registry.compare()
        assert rows[0]["f1_macro"] > rows[1]["f1_macro"]
        assert rows[0]["version_id"] == "xgboost_v002"
