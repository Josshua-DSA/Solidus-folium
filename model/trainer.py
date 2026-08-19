"""
Model Trainer — Orchestrator untuk semua model ML.

Menggunakan Dependency Injection (DI) untuk decouple dari model spesifik.
Support:
  - XGBoost (Malla et al.)
  - LightGBM (Malla et al.)
  - Ensemble LSTM+XGBoost (Chojnacki et al.)
  - Supervised Autoencoder (Bieganowski et al.)

Workflow:
  1. Load data & features
  2. Split train/val (Walk-Forward)
  3. Train model
  4. Evaluate
  5. Save artifacts
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional, Any, List, Type, Union
from dataclasses import dataclass
import logging
import os
import json
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Konfigurasi training pipeline."""
    model_type: str = "xgboost"  # 'xgboost', 'lightgbm', 'ensemble', 'autoencoder'
    walk_forward_mode: str = "expanding"
    train_size: int = 504  # ~2 tahun bursa
    test_size: int = 126   # ~6 bulan bursa
    step: int = 126
    max_folds: Optional[int] = None
    use_optuna: bool = False
    optuna_n_trials: int = 50
    save_artifacts: bool = True
    artifact_dir: str = "artifacts/saved_models"


class ModelTrainer:
    """
    Orchestrator untuk training model ML.

    Args:
        config: Konfigurasi training
    """

    def __init__(self, config: Optional[TrainingConfig] = None):
        self.config = config or TrainingConfig()
        self.model = None
        self.evaluator = None
        self.walk_forward = None
        self.results = None
        self.feature_names: Optional[List[str]] = None

        logger.info("ModelTrainer initialized: model_type=%s", self.config.model_type)

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[List[str]] = None,
        X_seq: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """
        Jalankan training pipeline lengkap.

        Args:
            X: Features matrix (n_samples, n_features)
            y: Labels (n_samples,)
            feature_names: Nama fitur
            X_seq: Sequence features untuk LSTM (optional)

        Returns:
            Dict dengan results dan metrics
        """
        from model.walk_forward import WalkForwardValidator
        from model.evaluator import ModelEvaluator

        self.feature_names = feature_names
        self.evaluator = ModelEvaluator()

        # Initialize model
        self.model = self._create_model()

        # Initialize Walk-Forward Validator
        self.walk_forward = WalkForwardValidator(
            mode=self.config.walk_forward_mode,
            train_size=self.config.train_size,
            test_size=self.config.test_size,
            step=self.config.step,
            max_folds=self.config.max_folds,
        )

        # Run Walk-Forward Validation
        logger.info("Starting Walk-Forward Validation...")
        self.results = self.walk_forward.validate(
            self.model, X, y,
            fit_kwargs={"feature_names": feature_names},
        )

        # MLflow Experiment Tracking (skip during pytest / unit tests to prevent IO blocking)
        if os.environ.get("PYTEST_CURRENT_TEST") is None:
            try:
                import mlflow
                mlflow.set_experiment("Finance-Pro_Quant_Training")
                with mlflow.start_run(run_name=f"{self.config.model_type}_{datetime.now():%Y%m%d_%H%M%S}"):
                    # Log params
                    mlflow.log_params({
                        "model_type": self.config.model_type,
                        "train_size": self.config.train_size,
                        "test_size": self.config.test_size,
                        "step": self.config.step,
                        "walk_forward_mode": self.config.walk_forward_mode,
                        "use_optuna": self.config.use_optuna,
                    })
                    # Log metrics
                    if self.results and self.results.aggregate_metrics:
                        for metric_name, val in self.results.aggregate_metrics.items():
                            if isinstance(val, (int, float)):
                                mlflow.log_metric(f"oos_{metric_name}", float(val))
            except Exception as e:
                logger.warning("MLflow logging skipped or failed: %s", e)

        # Final training on all data
        logger.info("Training final model on all data...")
        self.model.fit(X, y, feature_names=feature_names)

        # Save artifacts
        if self.config.save_artifacts:
            self._save_artifacts()

        # Compile results
        output = {
            "model_type": self.config.model_type,
            "n_folds": self.results.n_folds,
            "aggregate_metrics": self.results.aggregate_metrics,
            "fold_metrics": [f.metrics for f in self.results.folds],
            "timestamp": datetime.now().isoformat(),
        }

        logger.info("Training complete: %s", output["aggregate_metrics"])
        return output

    def _create_model(self):
        """Create model instance berdasarkan config."""
        if self.config.model_type == "xgboost":
            from model.xgboost_trainer import XGBoostTrainer, XGBoostConfig
            config = XGBoostConfig(use_optuna=self.config.use_optuna)
            return XGBoostTrainer(config)

        elif self.config.model_type == "lightgbm":
            from model.lightgbm_trainer import LightGBMTrainer, LightGBMConfig
            return LightGBMTrainer(LightGBMConfig())

        elif self.config.model_type == "ensemble":
            from model.ensemble import EnsembleModel, EnsembleConfig
            return EnsembleModel(EnsembleConfig())

        elif self.config.model_type == "autoencoder":
            from model.autoencoder import SupervisedAutoencoder, AutoencoderConfig
            return SupervisedAutoencoder(AutoencoderConfig())

        else:
            raise ValueError(f"Unknown model_type: {self.config.model_type}")

    def _save_artifacts(self) -> None:
        """Simpan model artifacts."""
        os.makedirs(self.config.artifact_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = os.path.join(
            self.config.artifact_dir,
            f"{self.config.model_type}_{timestamp}.pkl",
        )

        if hasattr(self.model, "save"):
            self.model.save(model_path)
            logger.info("Model saved to %s", model_path)

        # Save metadata
        metadata = {
            "model_type": self.config.model_type,
            "timestamp": timestamp,
            "n_folds": self.results.n_folds if self.results else 0,
            "aggregate_metrics": self.results.aggregate_metrics if self.results else {},
        }

        meta_path = os.path.join(
            self.config.artifact_dir,
            f"{self.config.model_type}_{timestamp}_metadata.json",
        )
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info("Metadata saved to %s", meta_path)

        # Auto-register ke ModelRegistry
        try:
            from model.registry import ModelRegistry
            registry = ModelRegistry(artifacts_dir=self.config.artifact_dir)
            registry.register(
                model_type=self.config.model_type,
                artifact_path=model_path,
                metrics=self.results.aggregate_metrics if self.results else {},
                config={
                    "train_size": self.config.train_size,
                    "test_size": self.config.test_size,
                    "walk_forward_mode": self.config.walk_forward_mode,
                    "use_optuna": self.config.use_optuna,
                },
                description=f"Auto-registered from ModelTrainer ({timestamp})",
            )
            logger.info("Model auto-registered to ModelRegistry as %s", self.config.model_type)
        except Exception as e:
            logger.warning("Failed to auto-register model to registry: %s", e)

    def evaluate(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray,
    ) -> Dict[str, float]:
        """
        Evaluate model pada test set.

        Args:
            X_test: Test features
            y_test: Test labels

        Returns:
            Dict metrics
        """
        if self.model is None:
            raise RuntimeError("Model belum di-train. Panggil train() dulu.")

        y_pred = self.model.predict(X_test)

        y_proba = None
        try:
            y_proba = self.model.predict_proba(X_test)
        except (AttributeError, NotImplementedError):
            pass

        return self.evaluator.evaluate(y_test, y_pred, y_proba)

    def get_feature_importance(self, top_n: int = 20) -> Dict[str, float]:
        """
        Get feature importance dari model.

        Args:
            top_n: Jumlah fitur teratas

        Returns:
            Dict {feature_name: importance}
        """
        if self.model is None:
            raise RuntimeError("Model belum di-train.")

        return self.evaluator.feature_importance(
            self.model, self.feature_names, top_n
        )

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict class labels."""
        if self.model is None:
            raise RuntimeError("Model belum di-train.")
        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict class probabilities."""
        if self.model is None:
            raise RuntimeError("Model belum di-train.")
        return self.model.predict_proba(X)

    def __repr__(self) -> str:
        status = "trained" if self.model else "untrained"
        return f"ModelTrainer(model_type={self.config.model_type!r}, status={status})"
