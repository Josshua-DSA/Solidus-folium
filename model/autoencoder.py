"""
Supervised Autoencoder — Feature Extractor per Bieganowski & Grabka (2024).

Autoencoder dengan supervised loss yang menggabungkan:
  - Reconstruction loss (unsupervised): mempertahankan informasi fitur
  - Classification loss (supervised): memastikan fitur berguna untuk prediksi

Reference:
  Bieganowski & Grabka (2024). "Supervised Autoencoders for Stock
  Market Prediction."
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass
import logging
import pickle
import os

logger = logging.getLogger(__name__)


@dataclass
class AutoencoderConfig:
    """Konfigurasi Supervised Autoencoder."""
    encoding_dim: int = 32
    hidden_dims: Tuple[int, ...] = (128, 64)
    alpha: float = 0.5  # Weight untuk classification loss vs reconstruction
    learning_rate: float = 0.001
    epochs: int = 100
    batch_size: int = 64
    dropout: float = 0.2
    random_state: int = 42


class SupervisedAutoencoder:
    """
    Supervised Autoencoder untuk feature extraction.

    Arsitektur:
      Input → Encoder → Latent → Decoder → Reconstruction
                          ↓
                    Classifier → Prediction

    Loss = alpha * classification_loss + (1 - alpha) * reconstruction_loss

    Args:
        config: Konfigurasi autoencoder
    """

    def __init__(self, config: Optional[AutoencoderConfig] = None):
        self.config = config or AutoencoderConfig()
        self.encoder = None
        self.autoencoder = None
        self.classifier = None
        self.is_fitted = False
        self._use_sklearn_fallback = False
        self._scaler = None

        logger.info("SupervisedAutoencoder initialized: encoding_dim=%d",
                     self.config.encoding_dim)

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        **kwargs,
    ) -> "SupervisedAutoencoder":
        """
        Train supervised autoencoder.

        Args:
            X: Input features
            y: Labels
            X_val: Validation features
            y_val: Validation labels
            **kwargs: Additional args

        Returns:
            self
        """
        try:
            return self._fit_tensorflow(X, y, X_val, y_val)
        except ImportError:
            logger.warning("TensorFlow tidak tersedia. Menggunakan sklearn fallback.")
            return self._fit_sklearn(X, y)

    def _fit_tensorflow(
        self,
        X: np.ndarray,
        y: np.ndarray,
        X_val: Optional[np.ndarray],
        y_val: Optional[np.ndarray],
    ) -> "SupervisedAutoencoder":
        """Train dengan TensorFlow/Keras."""
        import tensorflow as tf
        from tensorflow.keras.models import Model
        from tensorflow.keras.layers import (
            Input, Dense, Dropout, BatchNormalization,
        )
        from tensorflow.keras.optimizers import Adam

        input_dim = X.shape[1]
        input_layer = Input(shape=(input_dim,))

        # Encoder
        x = input_layer
        for dim in self.config.hidden_dims:
            x = Dense(dim, activation="relu")(x)
            x = BatchNormalization()(x)
            if self.config.dropout > 0:
                x = Dropout(self.config.dropout)(x)

        latent = Dense(self.config.encoding_dim, activation="relu", name="latent")(x)

        # Decoder
        x = latent
        for dim in reversed(self.config.hidden_dims):
            x = Dense(dim, activation="relu")(x)
            x = BatchNormalization()(x)

        reconstruction = Dense(input_dim, activation="linear", name="reconstruction")(x)

        # Classifier head
        classification = Dense(3, activation="softmax", name="classification")(latent)

        # Build models
        self.autoencoder = Model(input_layer, [reconstruction, classification])
        self.encoder = Model(input_layer, latent)

        # Compile dengan multi-output loss
        self.autoencoder.compile(
            optimizer=Adam(learning_rate=self.config.learning_rate),
            loss={
                "reconstruction": "mse",
                "classification": "sparse_categorical_crossentropy",
            },
            loss_weights={
                "reconstruction": 1.0 - self.config.alpha,
                "classification": self.config.alpha,
            },
        )

        # Train
        validation_data = None
        if X_val is not None and y_val is not None:
            validation_data = (X_val, {"reconstruction": X_val, "classification": y_val})

        self.autoencoder.fit(
            X, {"reconstruction": X, "classification": y},
            epochs=self.config.epochs,
            batch_size=self.config.batch_size,
            validation_data=validation_data,
            verbose=0,
        )

        self.is_fitted = True
        logger.info("Supervised Autoencoder trained (TensorFlow)")
        return self

    def _fit_sklearn(
        self,
        X: np.ndarray,
        y: np.ndarray,
    ) -> "SupervisedAutoencoder":
        """Fallback: PCA + LogisticRegression sebagai proxy."""
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler
        from sklearn.linear_model import LogisticRegression

        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)

        self.encoder = PCA(n_components=self.config.encoding_dim)
        X_encoded = self.encoder.fit_transform(X_scaled)

        self.classifier = LogisticRegression(
            max_iter=1000, random_state=self.config.random_state,
        )
        self.classifier.fit(X_encoded, y)

        self._use_sklearn_fallback = True
        self.is_fitted = True
        logger.info("Supervised Autoencoder trained (sklearn PCA fallback)")
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        """
        Transform features ke latent space.

        Args:
            X: Input features

        Returns:
            Encoded features (n_samples, encoding_dim)
        """
        if not self.is_fitted:
            raise RuntimeError("Autoencoder belum di-train. Panggil fit() dulu.")

        if self._use_sklearn_fallback:
            X_scaled = self._scaler.transform(X)
            return self.encoder.transform(X_scaled)
        else:
            return self.encoder.predict(X, verbose=0)

    def fit_transform(self, X: np.ndarray, y: np.ndarray, **kwargs) -> np.ndarray:
        """Fit dan transform dalam satu langkah."""
        self.fit(X, y, **kwargs)
        return self.transform(X)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict class labels."""
        X_encoded = self.transform(X)

        if self._use_sklearn_fallback:
            return self.classifier.predict(X_encoded)
        else:
            # Use classifier head
            classification_model = self.autoencoder.get_layer("classification")
            # Actually need full model output
            _, class_pred = self.autoencoder.predict(X, verbose=0)
            return np.argmax(class_pred, axis=1)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict class probabilities."""
        if self._use_sklearn_fallback:
            X_encoded = self.transform(X)
            return self.classifier.predict_proba(X_encoded)
        else:
            _, class_pred = self.autoencoder.predict(X, verbose=0)
            return class_pred

    def reconstruction_error(self, X: np.ndarray) -> np.ndarray:
        """Hitung reconstruction error per sample."""
        if self._use_sklearn_fallback:
            X_scaled = self._scaler.transform(X)
            X_encoded = self.encoder.transform(X_scaled)
            X_reconstructed = self.encoder.inverse_transform(X_encoded)
            return np.mean((X_scaled - X_reconstructed) ** 2, axis=1)
        else:
            recon, _ = self.autoencoder.predict(X, verbose=0)
            return np.mean((X - recon) ** 2, axis=1)

    def save(self, path: str) -> None:
        """Simpan model."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "encoder": self.encoder,
                "autoencoder": self.autoencoder,
                "classifier": self.classifier,
                "scaler": self._scaler,
                "config": self.config,
                "is_fitted": self.is_fitted,
                "use_sklearn_fallback": self._use_sklearn_fallback,
            }, f)
        logger.info("Autoencoder saved to %s", path)

    def load(self, path: str) -> "SupervisedAutoencoder":
        """Load model."""
        with open(path, "rb") as f:
            data = pickle.load(f)

        self.encoder = data["encoder"]
        self.autoencoder = data["autoencoder"]
        self.classifier = data["classifier"]
        self._scaler = data["scaler"]
        self.config = data["config"]
        self.is_fitted = data["is_fitted"]
        self._use_sklearn_fallback = data["use_sklearn_fallback"]

        logger.info("Autoencoder loaded from %s", path)
        return self

    def __repr__(self) -> str:
        status = "fitted" if self.is_fitted else "unfitted"
        backend = "sklearn" if self._use_sklearn_fallback else "tensorflow"
        return f"SupervisedAutoencoder(dim={self.config.encoding_dim}, status={status}, backend={backend})"
