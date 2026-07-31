"""
Feature Selection Annealing (FSA) — Barbu et al.

Algoritma seleksi fitur yang secara bertahap mengurangi dimensi
dari M fitur awal ke k fitur terpilih menggunakan gradient descent
dengan annealing schedule.

Paper: Pabuccu & Barbu — Feature Selection with Annealing for
Forecasting Financial Time Series.

Kelebihan:
  - Statistically true feature recovery
  - Konvergen dengan annealing schedule
  - Menangani nonlinearitas sampai batas tertentu
  - Mudah diimplementasi

Parameter:
  - learning_rate: 0.01 - 0.1
  - annealing (mu): 0, 1, 20, 50, 100, 300, 500, 1000
  - epochs: 50, 100, 200, 300, 500
"""
import numpy as np
from typing import Tuple, List, Optional
import logging

logger = logging.getLogger(__name__)


class FeatureSelectionAnnealing:
    """
    Feature Selection dengan Annealing.

    Args:
        n_features: Jumlah fitur yang ingin dipilih (k)
        learning_rate: Learning rate untuk gradient descent
        annealing: Parameter annealing (mu)
        epochs: Jumlah epoch training
        loss: 'mse' untuk regression, 'logistic' untuk classification
    """

    def __init__(
        self,
        n_features: int = 10,
        learning_rate: float = 0.05,
        annealing: float = 100,
        epochs: int = 200,
        loss: str = "logistic",
    ):
        self.n_features = n_features
        self.learning_rate = learning_rate
        self.annealing = annealing
        self.epochs = epochs
        self.loss = loss
        self.feature_importance: Optional[np.ndarray] = None

    def _mse_loss_gradient(
        self,
        X: np.ndarray,
        y: np.ndarray,
        beta: np.ndarray,
    ) -> np.ndarray:
        """Gradient untuk MSE loss (regression)."""
        n = X.shape[0]
        predictions = X @ beta
        errors = predictions - y
        gradient = (2 / n) * (X.T @ errors)
        return gradient

    def _logistic_loss_gradient(
        self,
        X: np.ndarray,
        y: np.ndarray,
        beta: np.ndarray,
    ) -> np.ndarray:
        """Gradient untuk logistic loss (classification)."""
        n = X.shape[0]
        z = X @ beta
        # Sigmoid dengan numerical stability
        z = np.clip(z, -500, 500)
        sigmoid = 1 / (1 + np.exp(-z))
        errors = sigmoid - y
        gradient = (1 / n) * (X.T @ errors)
        return gradient

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        beta_init: Optional[np.ndarray] = None,
    ) -> "FeatureSelectionAnnealing":
        """
        Fit FSA pada data training.

        Args:
            X: Matrix fitur (n_samples, n_features)
            y: Target (n_samples,)
            beta_init: Initial coefficient (optional)

        Returns:
            self
        """
        n_features = X.shape[1]

        if beta_init is not None:
            beta = beta_init.copy()
        else:
            beta = np.random.randn(n_features) * 0.01

        mu = self.annealing
        lr = self.learning_rate

        for epoch in range(self.epochs):
            # 1. Gradient descent step
            if self.loss == "mse":
                gradient = self._mse_loss_gradient(X, y, beta)
            else:
                gradient = self._logistic_loss_gradient(X, y, beta)

            beta = beta - lr * gradient

            # 2. Annealing: shrink small coefficients
            # Coefficient magnitude dikalikan factor < 1
            shrink_factor = np.exp(-mu * np.abs(beta))
            beta = beta * shrink_factor

            # Log progress setiap 50 epoch
            if (epoch + 1) % 50 == 0:
                n_selected = np.sum(np.abs(beta) > 1e-6)
                logger.info(
                    "FSA epoch %d/%d: n_selected=%d, ||beta||=%.4f",
                    epoch + 1, self.epochs, n_selected, np.linalg.norm(beta),
                )

        self.feature_importance = np.abs(beta)
        return self

    def get_selected_features(
        self,
        feature_names: Optional[List[str]] = None,
    ) -> List[int]:
        """
        Dapatkan index fitur yang terpilih.

        Args:
            feature_names: Nama fitur (optional, untuk logging)

        Returns:
            List index fitur terpilih
        """
        if self.feature_importance is None:
            raise RuntimeError("fit() harus dipanggil terlebih dahulu")

        # Pilih top-k features
        indices = np.argsort(self.feature_importance)[::-1]
        selected = indices[:self.n_features].tolist()

        if feature_names:
            selected_names = [feature_names[i] for i in selected]
            logger.info("FSA selected features: %s", selected_names)

        return selected

    def transform(self, X: np.ndarray) -> np.ndarray:
        """
        Transform X dengan hanya保留 fitur terpilih.

        Args:
            X: Matrix fitur

        Returns:
            X_transformed dengan kolom terpilih saja
        """
        if self.feature_importance is None:
            raise RuntimeError("fit() harus dipanggil terlebih dahulu")

        indices = self.get_selected_features()
        return X[:, indices]

    def fit_transform(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[List[str]] = None,
    ) -> np.ndarray:
        """Fit dan transform sekaligus."""
        self.fit(X, y)
        return self.transform(X)

    def __repr__(self) -> str:
        return (
            f"FeatureSelectionAnnealing(n_features={self.n_features}, "
            f"lr={self.learning_rate}, annealing={self.annealing}, "
            f"epochs={self.epochs})"
        )


# ---------------------------------------------------------------------------
# Lasso Feature Selection (baseline per Pabuccu)
# ---------------------------------------------------------------------------

class LassoFeatureSelector:
    """
    Feature selection menggunakan Lasso (L1 regularization).

    Baseline untuk comparison dengan FSA dan Boruta.

    Args:
        alpha: Regularization strength
        n_features: Jumlah fitur yang ingin dipilih
    """

    def __init__(self, alpha: float = 0.01, n_features: int = 10):
        self.alpha = alpha
        self.n_features = n_features
        self.feature_importance: Optional[np.ndarray] = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "LassoFeatureSelector":
        """Fit Lasso dan dapatkan feature importance."""
        try:
            from sklearn.linear_model import Lasso
        except ImportError:
            raise ImportError("scikit-learn diperlukan. pip install scikit-learn")

        model = Lasso(alpha=self.alpha, max_iter=10000, random_state=42)
        model.fit(X, y)
        self.feature_importance = np.abs(model.coef_)
        return self

    def get_selected_features(
        self,
        feature_names: Optional[List[str]] = None,
    ) -> List[int]:
        """Dapatkan index fitur terpilih."""
        if self.feature_importance is None:
            raise RuntimeError("fit() harus dipanggil terlebih dahulu")

        indices = np.argsort(self.feature_importance)[::-1]
        selected = indices[:self.n_features].tolist()

        if feature_names:
            selected_names = [feature_names[i] for i in selected]
            logger.info("Lasso selected features: %s", selected_names)

        return selected

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Transform X."""
        if self.feature_importance is None:
            raise RuntimeError("fit() harus dipanggil terlebih dahulu")

        indices = self.get_selected_features()
        return X[:, indices]

    def fit_transform(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Fit dan transform."""
        self.fit(X, y)
        return self.transform(X)

    def __repr__(self) -> str:
        return f"LassoFeatureSelector(alpha={self.alpha}, n_features={self.n_features})"
