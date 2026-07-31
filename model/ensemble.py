"""
Ensembled Model — LSTM + XGBoost per Chojnacki et al. (2024).

Ensemble dua model dengan weighted voting:
  - LSTM: menangkap pattern temporal/sequence
  - XGBoost: menangkap pattern fitur teknikal

Weighting bisa:
  - Equal: 50/50
  - Performance-based: berdasarkan validasi WF
  - Stacking: meta-learner di atas prediksi base models

Reference:
  Chojnacki et al. (2024). "Ensembled Long Short-Term Memory and
  Extreme Gradient Boosting for Stock Market Forecasting."
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional, Any, List, Tuple
from dataclasses import dataclass, field
import logging
import pickle
import os

logger = logging.getLogger(__name__)


@dataclass
class EnsembleConfig:
    """Konfigurasi Ensemble Model."""
    method: str = "weighted"  # 'equal', 'weighted', 'stacking'
    lstm_weight: float = 0.5
    xgb_weight: float = 0.5
    n_lstm_units: int = 64
    n_lstm_layers: int = 2
    lstm_dropout: float = 0.2
    lstm_epochs: int = 50
    lstm_batch_size: int = 32
    lstm_learning_rate: float = 0.001
    xgb_n_estimators: int = 500
    xgb_max_depth: int = 6
    xgb_learning_rate: float = 0.1
    random_state: int = 42


class EnsembleModel:
    """
    Ensemble LSTM + XGBoost.

    Args:
        config: Konfigurasi ensemble
    """

    def __init__(self, config: Optional[EnsembleConfig] = None):
        self.config = config or EnsembleConfig()
        self.lstm_model = None
        self.xgb_model = None
        self.meta_learner = None
        self.weights: Tuple[float, float] = (
            self.config.lstm_weight,
            self.config.xgb_weight,
        )
        self.is_fitted = False

        logger.info("EnsembleModel initialized: method=%s", self.config.method)

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        X_seq_train: Optional[np.ndarray] = None,
        X_seq_val: Optional[np.ndarray] = None,
        **kwargs,
    ) -> "EnsembleModel":
        """
        Train ensemble model.

        Args:
            X_train: Features untuk XGBoost (2D: n_samples, n_features)
            y_train: Labels
            X_val: Validation features
            y_val: Validation labels
            X_seq_train: Sequence features untuk LSTM (3D: n_samples, seq_len, n_features)
            X_seq_val: Validation sequences
            **kwargs: Additional args

        Returns:
            self
        """
        # Train XGBoost
        self._train_xgb(X_train, y_train, X_val, y_val)

        # Train LSTM (jika sequence data tersedia)
        if X_seq_train is not None:
            self._train_lstm(X_seq_train, y_train, X_seq_val, y_val)

        # Optimize weights jika method=weighted dan validation data tersedia
        if self.config.method == "weighted" and X_val is not None:
            self._optimize_weights(X_val, y_val, X_seq_val)

        # Train meta-learner jika method=stacking
        if self.config.method == "stacking" and X_val is not None:
            self._train_meta_learner(X_val, y_val, X_seq_val)

        self.is_fitted = True
        logger.info("EnsembleModel fitted: method=%s, weights=%s",
                     self.config.method, self.weights)

        return self

    def predict(self, X: np.ndarray, X_seq: Optional[np.ndarray] = None) -> np.ndarray:
        """Predict class labels."""
        proba = self.predict_proba(X, X_seq)
        return np.argmax(proba, axis=1)

    def predict_proba(self, X: np.ndarray, X_seq: Optional[np.ndarray] = None) -> np.ndarray:
        """Predict class probabilities via ensemble."""
        probas = []

        # XGBoost prediction
        if self.xgb_model is not None:
            xgb_proba = self.xgb_model.predict_proba(X)
            probas.append(("xgb", xgb_proba))

        # LSTM prediction
        if self.lstm_model is not None and X_seq is not None:
            lstm_proba = self._predict_lstm_proba(X_seq)
            probas.append(("lstm", lstm_proba))

        if not probas:
            raise RuntimeError("Tidak ada model yang ter-train")

        # Ensemble
        if self.config.method == "stacking" and self.meta_learner is not None:
            return self._predict_stacking(probas)
        else:
            return self._predict_weighted(probas)

    def _train_xgb(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray],
        y_val: Optional[np.ndarray],
    ) -> None:
        """Train XGBoost component."""
        from model.xgboost_trainer import XGBoostTrainer, XGBoostConfig

        xgb_config = XGBoostConfig(
            n_estimators=self.config.xgb_n_estimators,
            max_depth=self.config.xgb_max_depth,
            learning_rate=self.config.xgb_learning_rate,
            random_state=self.config.random_state,
        )

        self.xgb_model = XGBoostTrainer(xgb_config)
        self.xgb_model.fit(X_train, y_train, X_val, y_val)

    def _train_lstm(
        self,
        X_seq_train: np.ndarray,
        y_train: np.ndarray,
        X_seq_val: Optional[np.ndarray],
        y_val: Optional[np.ndarray],
    ) -> None:
        """Train LSTM component."""
        try:
            import tensorflow as tf
            from tensorflow.keras.models import Sequential
            from tensorflow.keras.layers import LSTM, Dense, Dropout
            from tensorflow.keras.optimizers import Adam
        except ImportError:
            logger.warning("TensorFlow tidak tersedia. LSTM tidak di-train.")
            return

        # Build model
        model = Sequential([
            LSTM(
                self.config.n_lstm_units,
                return_sequences=(self.config.n_lstm_layers > 1),
                input_shape=(X_seq_train.shape[1], X_seq_train.shape[2]),
            ),
        ])

        for i in range(1, self.config.n_lstm_layers):
            is_last = (i == self.config.n_lstm_layers - 1)
            model.add(LSTM(
                self.config.n_lstm_units,
                return_sequences=not is_last,
            ))
            if self.config.lstm_dropout > 0:
                model.add(Dropout(self.config.lstm_dropout))

        model.add(Dense(3, activation="softmax"))

        model.compile(
            optimizer=Adam(learning_rate=self.config.lstm_learning_rate),
            loss="sparse_categorical_crossentropy",
            metrics=["accuracy"],
        )

        # Train
        callbacks = []
        validation_data = None
        if X_seq_val is not None and y_val is not None:
            validation_data = (X_seq_val, y_val)
            from tensorflow.keras.callbacks import EarlyStopping
            callbacks.append(EarlyStopping(
                patience=10, restore_best_weights=True,
            ))

        model.fit(
            X_seq_train, y_train,
            epochs=self.config.lstm_epochs,
            batch_size=self.config.lstm_batch_size,
            validation_data=validation_data,
            callbacks=callbacks,
            verbose=0,
        )

        self.lstm_model = model
        logger.info("LSTM trained: %d layers, %d units",
                     self.config.n_lstm_layers, self.config.n_lstm_units)

    def _predict_lstm_proba(self, X_seq: np.ndarray) -> np.ndarray:
        """Predict probabilities dari LSTM."""
        if self.lstm_model is None:
            raise RuntimeError("LSTM model belum di-train")
        return self.lstm_model.predict(X_seq, verbose=0)

    def _predict_weighted(
        self,
        probas: List[Tuple[str, np.ndarray]],
    ) -> np.ndarray:
        """Weighted average ensemble."""
        result = None
        total_weight = 0.0

        for name, proba in probas:
            if name == "xgb":
                w = self.weights[1]
            elif name == "lstm":
                w = self.weights[0]
            else:
                w = 1.0 / len(probas)

            if result is None:
                result = proba * w
            else:
                result = result + proba * w
            total_weight += w

        return result / total_weight

    def _optimize_weights(
        self,
        X_val: np.ndarray,
        y_val: np.ndarray,
        X_seq_val: Optional[np.ndarray],
    ) -> None:
        """Optimize ensemble weights berdasarkan validation set."""
        from sklearn.metrics import f1_score

        best_f1 = -1
        best_weights = (0.5, 0.5)

        for lstm_w in np.arange(0.0, 1.05, 0.1):
            xgb_w = 1.0 - lstm_w
            self.weights = (lstm_w, xgb_w)

            probas = []
            if self.xgb_model is not None:
                probas.append(("xgb", self.xgb_model.predict_proba(X_val)))
            if self.lstm_model is not None and X_seq_val is not None:
                probas.append(("lstm", self._predict_lstm_proba(X_seq_val)))

            if probas:
                ensemble_proba = self._predict_weighted(probas)
                ensemble_pred = np.argmax(ensemble_proba, axis=1)
                f1 = f1_score(y_val, ensemble_pred, average="macro")

                if f1 > best_f1:
                    best_f1 = f1
                    best_weights = (lstm_w, xgb_w)

        self.weights = best_weights
        logger.info("Optimized weights: LSTM=%.2f, XGB=%.2f, F1=%.4f",
                     best_weights[0], best_weights[1], best_f1)

    def _train_meta_learner(
        self,
        X_val: np.ndarray,
        y_val: np.ndarray,
        X_seq_val: Optional[np.ndarray],
    ) -> None:
        """Train meta-learner untuk stacking."""
        from sklearn.linear_model import LogisticRegression

        # Get base model predictions
        meta_features = []
        if self.xgb_model is not None:
            meta_features.append(self.xgb_model.predict_proba(X_val))
        if self.lstm_model is not None and X_seq_val is not None:
            meta_features.append(self._predict_lstm_proba(X_seq_val))

        if not meta_features:
            return

        X_meta = np.hstack(meta_features)

        self.meta_learner = LogisticRegression(
            max_iter=1000, random_state=self.config.random_state,
        )
        self.meta_learner.fit(X_meta, y_val)
        logger.info("Meta-learner trained: LogisticRegression")

    def _predict_stacking(
        self,
        probas: List[Tuple[str, np.ndarray]],
    ) -> np.ndarray:
        """Stacking prediction via meta-learner."""
        meta_features = np.hstack([p for _, p in probas])
        return self.meta_learner.predict_proba(meta_features)

    def save(self, path: str) -> None:
        """Simpan ensemble model."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "xgb_model": self.xgb_model,
                "lstm_model": self.lstm_model,
                "meta_learner": self.meta_learner,
                "weights": self.weights,
                "config": self.config,
                "is_fitted": self.is_fitted,
            }, f)
        logger.info("Ensemble model saved to %s", path)

    def load(self, path: str) -> "EnsembleModel":
        """Load ensemble model."""
        with open(path, "rb") as f:
            data = pickle.load(f)

        self.xgb_model = data["xgb_model"]
        self.lstm_model = data["lstm_model"]
        self.meta_learner = data["meta_learner"]
        self.weights = data["weights"]
        self.config = data["config"]
        self.is_fitted = data["is_fitted"]

        logger.info("Ensemble model loaded from %s", path)
        return self

    def __repr__(self) -> str:
        status = "fitted" if self.is_fitted else "unfitted"
        return f"EnsembleModel(method={self.config.method!r}, status={status})"
