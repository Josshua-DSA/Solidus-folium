"""
Test Layer 3: Models — XGBoost, LightGBM, WalkForward, Evaluator, Ensemble, Autoencoder.
"""
import numpy as np
import pandas as pd
import pytest
import os
import tempfile

from model.walk_forward import WalkForwardValidator, FoldResult, WalkForwardResult
from model.evaluator import ModelEvaluator, EvaluationResult
from model.xgboost_trainer import XGBoostTrainer, XGBoostConfig
from model.lightgbm_trainer import LightGBMTrainer, LightGBMConfig
from model.ensemble import EnsembleModel, EnsembleConfig
from model.autoencoder import SupervisedAutoencoder, AutoencoderConfig
from model.trainer import ModelTrainer, TrainingConfig


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def sample_classification_data():
    """Generate sample classification data."""
    np.random.seed(42)
    n_samples = 1000
    n_features = 20

    X = np.random.randn(n_samples, n_features)
    # Make classes somewhat separable
    y = np.zeros(n_samples, dtype=int)
    y[X[:, 0] + X[:, 1] > 0.5] = 2
    y[(X[:, 0] + X[:, 1] < -0.5) & (y == 0)] = 0
    y[y == 0] = 1  # Neutral

    return X, y


@pytest.fixture
def sample_sequence_data():
    """Generate sample sequence data for LSTM."""
    np.random.seed(42)
    n_samples = 500
    seq_len = 100
    n_features = 5

    X_seq = np.random.randn(n_samples, seq_len, n_features)
    y = np.random.randint(0, 3, n_samples)

    return X_seq, y


# ===========================================================================
# Walk-Forward Validator Tests
# ===========================================================================

class TestWalkForwardValidator:
    def test_split_indices_expanding(self, sample_classification_data):
        """Expanding window harus menambah train size setiap fold."""
        X, y = sample_classification_data
        wf = WalkForwardValidator(
            mode="expanding", train_size=200, test_size=100, step=100,
        )
        splits = wf.split_indices(len(X))

        assert len(splits) > 0
        # First fold: train starts at 0
        assert splits[0][0][0] == 0
        # Train size should expand
        if len(splits) > 1:
            assert len(splits[1][0]) > len(splits[0][0])

    def test_split_indices_rolling(self, sample_classification_data):
        """Rolling window harus fixed train size."""
        X, y = sample_classification_data
        wf = WalkForwardValidator(
            mode="rolling", train_size=200, test_size=100, step=100,
        )
        splits = wf.split_indices(len(X))

        assert len(splits) > 0
        # All folds should have same train size
        train_sizes = [len(s[0]) for s in splits]
        assert all(ts == 200 for ts in train_sizes)

    def test_validate_with_xgboost(self, sample_classification_data):
        """Walk-forward harus bisa validate XGBoost model."""
        X, y = sample_classification_data
        wf = WalkForwardValidator(
            mode="expanding", train_size=300, test_size=100, step=100, max_folds=3,
        )

        model = XGBoostTrainer(XGBoostConfig(n_estimators=50))
        result = wf.validate(model, X, y)

        assert result.n_folds == 3
        assert len(result.folds) == 3
        assert "accuracy" in result.aggregate_metrics
        assert "f1_macro" in result.aggregate_metrics

    def test_fold_result_structure(self, sample_classification_data):
        """FoldResult harus punya semua field yang diperlukan."""
        X, y = sample_classification_data
        wf = WalkForwardValidator(
            mode="expanding", train_size=300, test_size=100, max_folds=2,
        )

        model = XGBoostTrainer(XGBoostConfig(n_estimators=50))
        result = wf.validate(model, X, y)

        fold = result.folds[0]
        assert fold.fold_id == 1
        assert fold.train_size > 0
        assert fold.test_size > 0
        assert fold.fit_time > 0
        assert "accuracy" in fold.metrics

    def test_repr(self):
        """Repr harus informatif."""
        wf = WalkForwardValidator(mode="expanding", train_size=500)
        repr_str = repr(wf)
        assert "expanding" in repr_str
        assert "500" in repr_str


# ===========================================================================
# Model Evaluator Tests
# ===========================================================================

class TestModelEvaluator:
    def test_evaluate_basic_metrics(self):
        """Evaluator harus hitung accuracy, precision, recall, f1."""
        evaluator = ModelEvaluator()
        y_true = np.array([0, 0, 1, 1, 2, 2])
        y_pred = np.array([0, 0, 1, 1, 2, 2])

        metrics = evaluator.evaluate(y_true, y_pred)

        assert metrics["accuracy"] == 1.0
        assert metrics["f1_macro"] == 1.0

    def test_evaluate_with_proba(self):
        """Evaluator harus hitung AUC dan log_loss jika proba tersedia."""
        evaluator = ModelEvaluator()
        y_true = np.array([0, 1, 2, 0, 1, 2])
        y_pred = np.array([0, 1, 2, 0, 1, 2])
        y_proba = np.array([
            [0.9, 0.05, 0.05],
            [0.1, 0.8, 0.1],
            [0.05, 0.05, 0.9],
            [0.8, 0.1, 0.1],
            [0.1, 0.7, 0.2],
            [0.1, 0.1, 0.8],
        ])

        metrics = evaluator.evaluate(y_true, y_pred, y_proba)

        assert "auc_ovr" in metrics
        assert "log_loss" in metrics
        assert metrics["auc_ovr"] > 0.5

    def test_confusion_matrix(self):
        """Confusion matrix harus shape (n_classes, n_classes)."""
        evaluator = ModelEvaluator()
        y_true = np.array([0, 1, 2, 0, 1, 2])
        y_pred = np.array([0, 1, 2, 0, 1, 1])

        cm = evaluator.confusion_matrix(y_true, y_pred)

        assert cm.shape == (3, 3)
        assert cm[0, 0] == 2  # True positives for class 0

    def test_feature_importance(self):
        """Feature importance harus return dict."""
        evaluator = ModelEvaluator()

        # Mock model with feature_importances_
        class MockModel:
            feature_importances_ = np.array([0.5, 0.3, 0.2])

        fi = evaluator.feature_importance(MockModel(), ["f1", "f2", "f3"])

        assert "f1" in fi
        assert fi["f1"] > fi["f3"]

    def test_evaluate_full(self):
        """evaluate_full harus return EvaluationResult."""
        evaluator = ModelEvaluator()
        y_true = np.array([0, 1, 2, 0, 1, 2])
        y_pred = np.array([0, 1, 2, 0, 1, 2])

        result = evaluator.evaluate_full(y_true, y_pred)

        assert isinstance(result, EvaluationResult)
        assert result.metrics is not None
        assert result.confusion_matrix is not None


# ===========================================================================
# XGBoost Trainer Tests
# ===========================================================================

class TestXGBoostTrainer:
    def test_fit_predict(self, sample_classification_data):
        """XGBoost harus bisa fit dan predict."""
        X, y = sample_classification_data
        X_train, X_test = X[:700], X[700:]
        y_train, y_test = y[:700], y[700:]

        trainer = XGBoostTrainer(XGBoostConfig(n_estimators=50))
        trainer.fit(X_train, y_train)

        y_pred = trainer.predict(X_test)
        assert len(y_pred) == len(X_test)
        assert set(y_pred).issubset({0, 1, 2})

    def test_predict_proba(self, sample_classification_data):
        """predict_proba harus return probabilities."""
        X, y = sample_classification_data
        trainer = XGBoostTrainer(XGBoostConfig(n_estimators=50))
        trainer.fit(X[:700], y[:700])

        proba = trainer.predict_proba(X[700:])
        assert proba.shape == (300, 3)
        assert np.allclose(proba.sum(axis=1), 1.0)

    def test_feature_importances(self, sample_classification_data):
        """Feature importances harus tersedia setelah training."""
        X, y = sample_classification_data
        trainer = XGBoostTrainer(XGBoostConfig(n_estimators=50))
        trainer.fit(X[:700], y[:700], feature_names=[f"f{i}" for i in range(20)])

        fi = trainer.feature_importances_
        assert len(fi) == 20

    def test_save_load(self, sample_classification_data):
        """Model harus bisa save dan load."""
        X, y = sample_classification_data
        trainer = XGBoostTrainer(XGBoostConfig(n_estimators=50))
        trainer.fit(X[:700], y[:700])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "model.pkl")
            trainer.save(path)

            trainer2 = XGBoostTrainer()
            trainer2.load(path)

            y_pred1 = trainer.predict(X[700:])
            y_pred2 = trainer2.predict(X[700:])
            np.testing.assert_array_equal(y_pred1, y_pred2)

    def test_repr(self):
        """Repr harus informatif."""
        trainer = XGBoostTrainer()
        assert "untrained" in repr(trainer)


# ===========================================================================
# LightGBM Trainer Tests
# ===========================================================================

class TestLightGBMTrainer:
    def test_fit_predict(self, sample_classification_data):
        """LightGBM harus bisa fit dan predict."""
        X, y = sample_classification_data
        X_train, X_test = X[:700], X[700:]
        y_train, y_test = y[:700], y[700:]

        trainer = LightGBMTrainer(LightGBMConfig(n_estimators=50))
        trainer.fit(X_train, y_train)

        y_pred = trainer.predict(X_test)
        assert len(y_pred) == len(X_test)
        assert set(y_pred).issubset({0, 1, 2})

    def test_predict_proba(self, sample_classification_data):
        """predict_proba harus return probabilities."""
        X, y = sample_classification_data
        trainer = LightGBMTrainer(LightGBMConfig(n_estimators=50))
        trainer.fit(X[:700], y[:700])

        proba = trainer.predict_proba(X[700:])
        assert proba.shape == (300, 3)


# ===========================================================================
# Ensemble Model Tests
# ===========================================================================

class TestEnsembleModel:
    def test_fit_predict_xgb_only(self, sample_classification_data):
        """Ensemble dengan XGBoost saja harus bisa fit dan predict."""
        X, y = sample_classification_data
        X_train, X_test = X[:700], X[700:]
        y_train, y_test = y[:700], y[700:]

        ensemble = EnsembleModel(EnsembleConfig(method="weighted"))
        ensemble.fit(X_train, y_train)

        y_pred = ensemble.predict(X_test)
        assert len(y_pred) == len(X_test)

    def test_fit_predict_with_lstm(self, sample_classification_data, sample_sequence_data):
        """Ensemble dengan LSTM+XGBoost harus bisa fit dan predict."""
        X, y = sample_classification_data
        X_seq, _ = sample_sequence_data

        # Align sizes
        n = min(len(X), len(X_seq))
        X = X[:n]
        y = y[:n]
        X_seq = X_seq[:n]

        X_train, X_test = X[:int(0.7*n)], X[int(0.7*n):]
        y_train, y_test = y[:int(0.7*n)], y[int(0.7*n):]
        X_seq_train, X_seq_test = X_seq[:int(0.7*n)], X_seq[int(0.7*n):]

        ensemble = EnsembleModel(EnsembleConfig(method="weighted", lstm_epochs=2))
        ensemble.fit(
            X_train, y_train,
            X_seq_train=X_seq_train,
        )

        y_pred = ensemble.predict(X_test, X_seq=X_seq_test)
        assert len(y_pred) == len(X_test)


# ===========================================================================
# Supervised Autoencoder Tests
# ===========================================================================

class TestSupervisedAutoencoder:
    def test_fit_transform_sklearn(self, sample_classification_data):
        """Autoencoder sklearn fallback harus bisa fit dan transform."""
        X, y = sample_classification_data

        ae = SupervisedAutoencoder(AutoencoderConfig(encoding_dim=10, epochs=2))
        ae.fit(X, y)

        X_encoded = ae.transform(X)
        assert X_encoded.shape == (len(X), 10)

    def test_predict(self, sample_classification_data):
        """Autoencoder harus bisa predict."""
        X, y = sample_classification_data

        ae = SupervisedAutoencoder(AutoencoderConfig(encoding_dim=10, epochs=2))
        ae.fit(X, y)

        y_pred = ae.predict(X)
        assert len(y_pred) == len(X)
        assert set(y_pred).issubset({0, 1, 2})

    def test_reconstruction_error(self, sample_classification_data):
        """Reconstruction error harus return array."""
        X, y = sample_classification_data

        ae = SupervisedAutoencoder(AutoencoderConfig(encoding_dim=10, epochs=2))
        ae.fit(X, y)

        errors = ae.reconstruction_error(X)
        assert len(errors) == len(X)
        assert np.all(errors >= 0)


# ===========================================================================
# Model Trainer (Orchestrator) Tests
# ===========================================================================

class TestModelTrainer:
    def test_train_xgboost(self, sample_classification_data):
        """ModelTrainer harus bisa train XGBoost dengan WF."""
        X, y = sample_classification_data

        config = TrainingConfig(
            model_type="xgboost",
            train_size=300,
            test_size=100,
            step=100,
            max_folds=2,
            optuna_n_trials=2,
            save_artifacts=False,
        )

        trainer = ModelTrainer(config)
        result = trainer.train(X, y)

        assert "aggregate_metrics" in result
        assert result["n_folds"] == 2
        assert "accuracy" in result["aggregate_metrics"]

    def test_train_lightgbm(self, sample_classification_data):
        """ModelTrainer harus bisa train LightGBM."""
        X, y = sample_classification_data

        config = TrainingConfig(
            model_type="lightgbm",
            train_size=300,
            test_size=100,
            max_folds=2,
            save_artifacts=False,
        )

        trainer = ModelTrainer(config)
        result = trainer.train(X, y)

        assert result["n_folds"] == 2

    def test_predict_after_train(self, sample_classification_data):
        """Setelah train, predict harus bisa dipanggil."""
        X, y = sample_classification_data

        config = TrainingConfig(
            model_type="xgboost",
            train_size=300,
            test_size=100,
            max_folds=2,
            save_artifacts=False,
        )

        trainer = ModelTrainer(config)
        trainer.train(X, y)

        y_pred = trainer.predict(X[:50])
        assert len(y_pred) == 50

    def test_feature_importance(self, sample_classification_data):
        """Feature importance harus tersedia setelah train."""
        X, y = sample_classification_data
        feature_names = [f"feature_{i}" for i in range(20)]

        config = TrainingConfig(
            model_type="xgboost",
            train_size=300,
            test_size=100,
            max_folds=2,
            save_artifacts=False,
        )

        trainer = ModelTrainer(config)
        trainer.train(X, y, feature_names=feature_names)

        fi = trainer.get_feature_importance(top_n=5)
        assert len(fi) <= 5
