"""
Walk-Forward Validator — DI-based, tidak import model/ langsung.
Terpisah dari backtester.py per ARCHITECTURE.md.

Layer 6: app/backtest/ — Risk & Validation.
"""
import numpy as np
import pandas as pd
from typing import Any, Callable, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class WalkForwardValidator:
    """
    Walk-Forward Validation — rolling train/test split untuk evaluasi model.

    Menggunakan Dependency Injection: menerima model_factory dari cli.py,
    sehingga app/ tidak perlu import model/ langsung.

    Args:
        n_splits: Jumlah fold
        train_window: Panjang window training (hari bursa)
        test_window: Panjang window testing (hari bursa)
        model_factory: Callable yang return model instance (injected dari cli.py)
    """

    def __init__(
        self,
        n_splits: int = 5,
        train_window: int = 504,
        test_window: int = 126,
        model_factory: Optional[Callable] = None,
    ):
        self.n_splits = n_splits
        self.train_window = train_window
        self.test_window = test_window
        self.model_factory = model_factory

    def split(self, data: pd.DataFrame) -> List[tuple]:
        """
        Generate train/test indices.

        Args:
            data: DataFrame yang akan di-split

        Returns:
            List of (train_indices, test_indices)
        """
        n = len(data)
        splits = []
        step = self.train_window + self.test_window

        for i in range(self.n_splits):
            start = i * step
            train_end = start + self.train_window
            test_end = min(train_end + self.test_window, n)

            if train_end >= n:
                break

            train_idx = list(range(start, min(train_end, n)))
            test_idx = list(range(train_end, test_end))

            if test_idx:
                splits.append((train_idx, test_idx))

        logger.info("WalkForward: %d splits generated", len(splits))
        return splits

    def validate(
        self,
        dataset: pd.DataFrame,
        feature_cols: Optional[List[str]] = None,
        label_col: str = "label",
        **kwargs,
    ) -> List[Dict[str, float]]:
        """
        Jalankan validasi walk-forward pada model.

        Args:
            dataset: DataFrame dengan kolom features dan label
            feature_cols: List nama kolom fitur
            label_col: Nama kolom label
            **kwargs: Parameter tambahan untuk model

        Returns:
            List metrics per fold
        """
        if self.model_factory is None:
            logger.warning("model_factory not set — inject via cli.py DI")
            return []

        splits = self.split(dataset)
        fold_metrics = []

        for fold_idx, (train_idx, test_idx) in enumerate(splits):
            logger.info("Fold %d: train=%d, test=%d", fold_idx, len(train_idx), len(test_idx))

            train_data = dataset.iloc[train_idx]
            test_data = dataset.iloc[test_idx]

            # Create fresh model via factory (DI)
            model = self.model_factory(**kwargs)

            # Train
            if feature_cols:
                X_train = train_data[feature_cols]
                y_train = train_data[label_col]
                X_test = test_data[feature_cols]
                y_test = test_data[label_col]
            else:
                # Assume last column is label
                X_train = train_data.drop(columns=[label_col])
                y_train = train_data[label_col]
                X_test = test_data.drop(columns=[label_col])
                y_test = test_data[label_col]

            try:
                model.fit(X_train, y_train)
                y_pred = model.predict(X_test)

                # Basic metrics
                from sklearn.metrics import accuracy_score, f1_score
                metrics = {
                    "fold": fold_idx,
                    "accuracy": accuracy_score(y_test, y_pred),
                    "f1_macro": f1_score(y_test, y_pred, average="macro", zero_division="warn"),
                    "train_size": len(train_idx),
                    "test_size": len(test_idx),
                }
                fold_metrics.append(metrics)
                logger.info("Fold %d: acc=%.4f, f1=%.4f", fold_idx, metrics["accuracy"], metrics["f1_macro"])

            except Exception as e:
                logger.error("Fold %d failed: %s", fold_idx, e)
                fold_metrics.append({"fold": fold_idx, "error": str(e)})

        return fold_metrics

    def __repr__(self) -> str:
        return (
            f"WalkForwardValidator(splits={self.n_splits}, "
            f"train={self.train_window}d, test={self.test_window}d)"
        )
