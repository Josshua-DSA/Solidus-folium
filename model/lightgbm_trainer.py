"""
LightGBM Trainer — Per Malla et al. (2024).

LightGBM untuk klasifikasi multi-kelas TBL dengan:
  - Expanding window walk-forward validation
  - Hyperparameter tuning
  - Class imbalance handling

Reference:
  Malla et al. (2024). "Forecasting Stock Market Using XGBoost and
  LightGBM in Nepal Stock Exchange."
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
import logging
import pickle
import os

logger = logging.getLogger(__name__)


@dataclass
class LightGBMConfig:
    """Konfigurasi LightGBM Trainer."""
    n_estimators: int = 500
    max_depth: int = 6
    learning_rate: float = 0.1
    num_leaves: int = 31
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    min_child_samples: int = 20
    reg_alpha: float = 0.0
    reg_lambda: float = 0.0
    objective: str = "multiclass"
    num_class: int = 3
    metric: str = "multi_logloss"
    early_stopping_rounds: int = 50
    random_state: int = 42
    use_optuna: bool = False
    optuna_n_trials: int = 100


class LightGBMTrainer:
    """
    LightGBM trainer untuk klasifikasi multi-kelas TBL.

    Args:
        config: Konfigurasi training
    """

    def __init__(self, config: Optional[LightGBMConfig] = None):
        self.config = config or LightGBMConfig()
        self.model = None
        self.feature_names: Optional[List[str]] = None
        self.best_params: Optional[Dict[str, Any]] = None
        self.training_history: Dict[str, Any] = {}

        logger.info("LightGBMTrainer initialized: %s", self.config)

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None,
        **kwargs,
    ) -> "LightGBMTrainer":
        """
        Train LightGBM model.

        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
            feature_names: Nama fitur
            **kwargs: Additional args

        Returns:
            self
        """
        import lightgbm as lgb

        self.feature_names = feature_names

        # Handle class imbalance
        class_weights = self._compute_class_weights(y_train)

        # Optuna tuning
        if self.config.use_optuna:
            self.best_params = self._tune_optuna(X_train, y_train)
            for key, val in self.best_params.items():
                setattr(self.config, key, val)
            logger.info("Optuna best params: %s", self.best_params)

        # Prepare dataset
        train_data = lgb.Dataset(
            X_train, label=y_train,
            feature_name=feature_names,
            weight=np.array([class_weights[int(y)] for y in y_train]),
        )

        params = {
            "objective": self.config.objective,
            "num_class": self.config.num_class,
            "metric": self.config.metric,
            "max_depth": self.config.max_depth,
            "learning_rate": self.config.learning_rate,
            "num_leaves": self.config.num_leaves,
            "subsample": self.config.subsample,
            "colsample_bytree": self.config.colsample_bytree,
            "min_child_samples": self.config.min_child_samples,
            "reg_alpha": self.config.reg_alpha,
            "reg_lambda": self.config.reg_lambda,
            "seed": self.config.random_state,
            "verbose": -1,
        }

        valid_sets = [train_data]
        valid_names = ["train"]

        if X_val is not None and y_val is not None:
            val_data = lgb.Dataset(
                X_val, label=y_val,
                feature_name=feature_names,
                reference=train_data,
            )
            valid_sets.append(val_data)
            valid_names.append("val")

        # Train
        callbacks = [lgb.log_evaluation(period=0)]
        if X_val is not None:
            callbacks.append(lgb.early_stopping(
                stopping_rounds=self.config.early_stopping_rounds,
                verbose=False,
            ))

        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=self.config.n_estimators,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=callbacks,
        )

        self.training_history = {
            "n_train": len(X_train),
            "n_features": X_train.shape[1],
            "best_iteration": self.model.best_iteration if hasattr(self.model, "best_iteration") else self.config.n_estimators,
        }

        logger.info(
            "LightGBM trained: n_train=%d, n_features=%d, best_iter=%d",
            len(X_train), X_train.shape[1],
            self.training_history["best_iteration"],
        )

        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict class labels."""
        if self.model is None:
            raise RuntimeError("Model belum di-train. Panggil fit() dulu.")

        proba = self.model.predict(X)
        return np.argmax(proba, axis=1)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict class probabilities."""
        if self.model is None:
            raise RuntimeError("Model belum di-train. Panggil fit() dulu.")
        return self.model.predict(X)

    @property
    def feature_importances_(self) -> np.ndarray:
        """Feature importances (split-based)."""
        if self.model is None:
            raise RuntimeError("Model belum di-train.")
        return self.model.feature_importance(importance_type="gain")

    def _compute_class_weights(self, y: np.ndarray) -> Dict[int, float]:
        """Hitung class weights untuk handle imbalance."""
        unique, counts = np.unique(y, return_counts=True)
        total = len(y)
        n_classes = len(unique)

        weights = {}
        for cls, count in zip(unique, counts):
            weights[int(cls)] = total / (n_classes * count)

        logger.info("Class weights: %s", weights)
        return weights

    def _tune_optuna(
        self,
        X: np.ndarray,
        y: np.ndarray,
    ) -> Dict[str, Any]:
        """Hyperparameter tuning menggunakan Optuna."""
        import optuna
        import lightgbm as lgb
        from sklearn.model_selection import TimeSeriesSplit

        optuna.logging.set_verbosity(optuna.logging.WARNING)

        def objective(trial):
            params = {
                "max_depth": trial.suggest_int("max_depth", 3, 10),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "num_leaves": trial.suggest_int("num_leaves", 15, 63),
                "subsample": trial.suggest_float("subsample", 0.5, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "min_child_samples": trial.suggest_int("min_child_samples", 10, 50),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
                "objective": "multiclass",
                "num_class": self.config.num_class,
                "metric": "multi_logloss",
                "seed": self.config.random_state,
                "verbose": -1,
            }

            tscv = TimeSeriesSplit(n_splits=3)
            scores = []

            for train_idx, val_idx in tscv.split(X):
                X_tr, X_val = X[train_idx], X[val_idx]
                y_tr, y_val = y[train_idx], y[val_idx]

                train_data = lgb.Dataset(X_tr, label=y_tr)
                val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

                model = lgb.train(
                    params, train_data,
                    num_boost_round=200,
                    valid_sets=[val_data],
                    callbacks=[lgb.early_stopping(30), lgb.log_evaluation(0)],
                )

                pred = model.predict(X_val)
                pred_labels = np.argmax(pred, axis=1)
                from sklearn.metrics import f1_score
                scores.append(f1_score(y_val, pred_labels, average="macro"))

            return np.mean(scores)

        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=self.config.optuna_n_trials, show_progress_bar=False)

        return study.best_params

    def save(self, path: str) -> None:
        """Simpan model ke file."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "model": self.model,
                "config": self.config,
                "feature_names": self.feature_names,
                "best_params": self.best_params,
                "training_history": self.training_history,
            }, f)
        logger.info("Model saved to %s", path)

    def load(self, path: str) -> "LightGBMTrainer":
        """Load model dari file."""
        with open(path, "rb") as f:
            data = pickle.load(f)

        self.model = data["model"]
        self.config = data["config"]
        self.feature_names = data["feature_names"]
        self.best_params = data["best_params"]
        self.training_history = data["training_history"]

        logger.info("Model loaded from %s", path)
        return self

    def __repr__(self) -> str:
        status = "trained" if self.model else "untrained"
        return f"LightGBMTrainer(status={status}, config={self.config})"
