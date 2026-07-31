"""
XGBoost Trainer — Per Malla et al. (2024).

NEPSE stock market prediction menggunakan XGBoost dengan:
  - 20 lagged log-returns sebagai fitur utama
  - Expanding window walk-forward validation
  - Optuna hyperparameter optimization
  - Multi-class classification (LOSS/NEUTRAL/PROFIT)

Reference:
  Malla et al. (2024). "Forecasting Stock Market Using XGBoost and
  LightGBM in Nepal Stock Exchange."
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional, Any, List, Tuple
from dataclasses import dataclass
import logging
import pickle
import os

logger = logging.getLogger(__name__)


@dataclass
class XGBoostConfig:
    """Konfigurasi XGBoost Trainer."""
    n_estimators: int = 500
    max_depth: int = 6
    learning_rate: float = 0.1
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    min_child_weight: int = 3
    gamma: float = 0.0
    reg_alpha: float = 0.0
    reg_lambda: float = 1.0
    scale_pos_weight: float = 1.0
    objective: str = "multi:softprob"
    num_class: int = 3
    eval_metric: str = "mlogloss"
    early_stopping_rounds: int = 50
    random_state: int = 42
    use_optuna: bool = False
    optuna_n_trials: int = 100


class XGBoostTrainer:
    """
    XGBoost trainer untuk klasifikasi multi-kelas TBL.

    Args:
        config: Konfigurasi training
    """

    def __init__(self, config: Optional[XGBoostConfig] = None):
        self.config = config or XGBoostConfig()
        self.model = None
        self.feature_names: Optional[List[str]] = None
        self.best_params: Optional[Dict[str, Any]] = None
        self.training_history: Dict[str, Any] = {}

        logger.info("XGBoostTrainer initialized: %s", self.config)

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None,
        **kwargs,
    ) -> "XGBoostTrainer":
        """
        Train XGBoost model.

        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features (untuk early stopping)
            y_val: Validation labels
            feature_names: Nama fitur
            **kwargs: Additional args untuk xgb.train

        Returns:
            self
        """
        import xgboost as xgb

        self.feature_names = feature_names

        # Handle class imbalance
        class_weights = self._compute_class_weights(y_train)
        sample_weights = np.array([class_weights[int(y)] for y in y_train])

        # Optuna tuning
        if self.config.use_optuna:
            self.best_params = self._tune_optuna(X_train, y_train)
            for key, val in self.best_params.items():
                setattr(self.config, key, val)
            logger.info("Optuna best params: %s", self.best_params)

        # Prepare DMatrix
        dtrain = xgb.DMatrix(
            X_train, label=y_train,
            feature_names=feature_names,
            weight=sample_weights,
        )

        params = {
            "max_depth": self.config.max_depth,
            "learning_rate": self.config.learning_rate,
            "subsample": self.config.subsample,
            "colsample_bytree": self.config.colsample_bytree,
            "min_child_weight": self.config.min_child_weight,
            "gamma": self.config.gamma,
            "reg_alpha": self.config.reg_alpha,
            "reg_lambda": self.config.reg_lambda,
            "objective": self.config.objective,
            "num_class": self.config.num_class,
            "eval_metric": self.config.eval_metric,
            "seed": self.config.random_state,
            "tree_method": "hist",  # Faster than exact
        }

        evals = [(dtrain, "train")]
        if X_val is not None and y_val is not None:
            dval = xgb.DMatrix(X_val, label=y_val, feature_names=feature_names)
            evals.append((dval, "val"))

        # Train
        self.model = xgb.train(
            params,
            dtrain,
            num_boost_round=self.config.n_estimators,
            evals=evals,
            early_stopping_rounds=self.config.early_stopping_rounds if X_val is not None else None,
            verbose_eval=False,
        )

        self.training_history = {
            "n_train": len(X_train),
            "n_features": X_train.shape[1],
            "best_iteration": self.model.best_iteration if hasattr(self.model, "best_iteration") else self.config.n_estimators,
        }

        logger.info(
            "XGBoost trained: n_train=%d, n_features=%d, best_iter=%d",
            len(X_train), X_train.shape[1],
            self.training_history["best_iteration"],
        )

        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict class labels."""
        import xgboost as xgb

        if self.model is None:
            raise RuntimeError("Model belum di-train. Panggil fit() dulu.")

        dtest = xgb.DMatrix(X, feature_names=self.feature_names)
        proba = self.model.predict(dtest)
        return np.argmax(proba, axis=1)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict class probabilities."""
        import xgboost as xgb

        if self.model is None:
            raise RuntimeError("Model belum di-train. Panggil fit() dulu.")

        dtest = xgb.DMatrix(X, feature_names=self.feature_names)
        return self.model.predict(dtest)

    @property
    def feature_importances_(self) -> np.ndarray:
        """Feature importances (gain-based)."""
        if self.model is None:
            raise RuntimeError("Model belum di-train.")

        score_dict = self.model.get_score(importance_type="gain")
        n_features = len(self.feature_names) if self.feature_names else len(score_dict)
        importance = np.zeros(max(n_features, 1))

        for key, val in score_dict.items():
            # Handle both "f0" format and actual feature names
            if key.startswith("f") and key[1:].isdigit():
                idx = int(key[1:])
            elif self.feature_names and key in self.feature_names:
                idx = self.feature_names.index(key)
            else:
                continue

            if idx < len(importance):
                importance[idx] = val

        return importance

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
        """
        Hyperparameter tuning menggunakan Optuna.

        Berdasarkan Malla et al.: tune max_depth, learning_rate,
        subsample, colsample_bytree, min_child_weight.
        """
        import optuna
        import xgboost as xgb
        from sklearn.model_selection import TimeSeriesSplit

        optuna.logging.set_verbosity(optuna.logging.WARNING)

        def objective(trial):
            params = {
                "max_depth": trial.suggest_int("max_depth", 3, 10),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "subsample": trial.suggest_float("subsample", 0.5, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
                "gamma": trial.suggest_float("gamma", 0.0, 5.0),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
                "objective": "multi:softprob",
                "num_class": self.config.num_class,
                "eval_metric": "mlogloss",
                "seed": self.config.random_state,
                "tree_method": "hist",
            }

            tscv = TimeSeriesSplit(n_splits=3)
            scores = []

            for train_idx, val_idx in tscv.split(X):
                X_tr, X_val = X[train_idx], X[val_idx]
                y_tr, y_val = y[train_idx], y[val_idx]

                dtrain = xgb.DMatrix(X_tr, label=y_tr)
                dval = xgb.DMatrix(X_val, label=y_val)

                model = xgb.train(
                    params, dtrain,
                    num_boost_round=200,
                    evals=[(dval, "val")],
                    early_stopping_rounds=30,
                    verbose_eval=False,
                )

                pred = model.predict(dval)
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

    def load(self, path: str) -> "XGBoostTrainer":
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
        return f"XGBoostTrainer(status={status}, config={self.config})"
