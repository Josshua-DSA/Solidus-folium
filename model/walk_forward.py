"""
Walk-Forward Validator — Full implementation (bukan skeleton).

Berdasarkan Malla et al. (XGBoost NEPSE) dan Mroziewicz & Ślepaczuk (WF optimization).

Dua mode:
  1. Expanding window: training set bertambah setiap fold
  2. Rolling window: training set fixed length, slide forward

Design: Dependency Injection (DI) agar decoupled dari model/trainer.
Interface bisa digunakan oleh model apapun yang punya fit() dan predict().
"""
import numpy as np
import pandas as pd
from typing import List, Tuple, Dict, Any, Optional, Protocol, Callable
from dataclasses import dataclass, field
import logging
import time

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FoldResult:
    """Hasil satu fold walk-forward."""
    fold_id: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    train_size: int
    test_size: int
    fit_time: float
    predict_time: float
    metrics: Dict[str, float] = field(default_factory=dict)
    y_true: Optional[np.ndarray] = None
    y_pred: Optional[np.ndarray] = None
    y_proba: Optional[np.ndarray] = None


@dataclass
class WalkForwardResult:
    """Hasil keseluruhan walk-forward validation."""
    folds: List[FoldResult] = field(default_factory=list)
    aggregate_metrics: Dict[str, float] = field(default_factory=dict)
    all_y_true: Optional[np.ndarray] = None
    all_y_pred: Optional[np.ndarray] = None
    all_y_proba: Optional[np.ndarray] = None

    @property
    def n_folds(self) -> int:
        return len(self.folds)

    @property
    def total_train_samples(self) -> int:
        return sum(f.train_size for f in self.folds)

    @property
    def total_test_samples(self) -> int:
        return sum(f.test_size for f in self.folds)


# ---------------------------------------------------------------------------
# Protocol untuk model compatibility (DI)
# ---------------------------------------------------------------------------

class ModelProtocol(Protocol):
    """
    Interface minimal untuk model yang bisa divalidasi.
    Model apapun yang punya method ini bisa digunakan.
    """
    def fit(self, X_train, y_train, **kwargs) -> Any: ...
    def predict(self, X) -> np.ndarray: ...
    def predict_proba(self, X) -> np.ndarray: ...


# ---------------------------------------------------------------------------
# Walk-Forward Validator
# ---------------------------------------------------------------------------

class WalkForwardValidator:
    """
    Walk-Forward Validation dengan expanding/rolling window.

    Args:
        mode: 'expanding' atau 'rolling'
        train_size: Jumlah minimum training samples
        test_size: Jumlah test samples per fold
        step: Langkah slide antar fold
        max_folds: Maksimum jumlah fold (None = semua yang bisa)
        gap: Gap samples antara train dan test (hindari data leakage)
    """

    def __init__(
        self,
        mode: str = "expanding",
        train_size: int = 504,
        test_size: int = 126,
        step: int = 126,
        max_folds: Optional[int] = None,
        gap: int = 0,
    ):
        if mode not in ("expanding", "rolling"):
            raise ValueError(f"mode harus 'expanding' atau 'rolling', got '{mode}'")

        self.mode = mode
        self.train_size = train_size
        self.test_size = test_size
        self.step = step
        self.max_folds = max_folds
        self.gap = gap

        logger.info(
            "WalkForwardValidator: mode=%s, train=%d, test=%d, step=%d, gap=%d",
            mode, train_size, test_size, step, gap,
        )

    def split_indices(
        self,
        n_samples: int,
    ) -> List[Tuple[List[int], List[int]]]:
        """
        Generate train/test index pairs.

        Args:
            n_samples: Jumlah total samples

        Returns:
            List of (train_indices, test_indices) tuples
        """
        splits = []
        start = 0

        fold_count = 0
        while start + self.train_size + self.gap + self.test_size <= n_samples:
            train_end = start + self.train_size
            test_start = train_end + self.gap
            test_end = test_start + self.test_size

            if self.mode == "expanding":
                train_indices = list(range(0, train_end))
            else:  # rolling
                train_indices = list(range(start, train_end))

            test_indices = list(range(test_start, test_end))
            splits.append((train_indices, test_indices))

            start += self.step
            fold_count += 1

            if self.max_folds and fold_count >= self.max_folds:
                break

        if not splits:
            logger.warning(
                "WalkForward: tidak ada fold yang bisa di-generate. "
                "n_samples=%d, perlu minimum=%d",
                n_samples, self.train_size + self.test_size,
            )
        else:
            logger.info("WalkForward: %d folds generated", len(splits))

        return splits

    def validate(
        self,
        model,
        X: np.ndarray,
        y: np.ndarray,
        fit_kwargs: Optional[Dict[str, Any]] = None,
    ) -> WalkForwardResult:
        """
        Jalankan walk-forward validation.

        Args:
            model: Model dengan fit(), predict(), predict_proba()
            X: Features matrix (n_samples, n_features)
            y: Labels (n_samples,)
            fit_kwargs: Additional kwargs untuk model.fit()

        Returns:
            WalkForwardResult dengan semua fold results
        """
        from model.evaluator import ModelEvaluator

        n_samples = X.shape[0]
        splits = self.split_indices(n_samples)

        if not splits:
            return WalkForwardResult()

        result = WalkForwardResult()
        all_y_true = []
        all_y_pred = []
        all_y_proba = []

        evaluator = ModelEvaluator()

        for fold_id, (train_idx, test_idx) in enumerate(splits, 1):
            X_train = X[train_idx]
            y_train = y[train_idx]
            X_test = X[test_idx]
            y_test = y[test_idx]

            logger.info(
                "Fold %d/%d: train=%d, test=%d",
                fold_id, len(splits), len(train_idx), len(test_idx),
            )

            # Fit
            t0 = time.time()
            fit_kw = fit_kwargs or {}
            model.fit(X_train, y_train, **fit_kw)
            fit_time = time.time() - t0

            # Predict
            t0 = time.time()
            y_pred = model.predict(X_test)
            predict_time = time.time() - t0

            # Predict proba (jika ada)
            y_proba = None
            try:
                y_proba = model.predict_proba(X_test)
            except (AttributeError, NotImplementedError):
                pass

            # Evaluate
            metrics = evaluator.evaluate(y_test, y_pred, y_proba)

            fold_result = FoldResult(
                fold_id=fold_id,
                train_start=train_idx[0],
                train_end=train_idx[-1],
                test_start=test_idx[0],
                test_end=test_idx[-1],
                train_size=len(train_idx),
                test_size=len(test_idx),
                fit_time=fit_time,
                predict_time=predict_time,
                metrics=metrics,
                y_true=y_test,
                y_pred=y_pred,
                y_proba=y_proba,
            )
            result.folds.append(fold_result)

            all_y_true.append(y_test)
            all_y_pred.append(y_pred)
            if y_proba is not None:
                all_y_proba.append(y_proba)

            logger.info(
                "  Fold %d: accuracy=%.4f, f1_macro=%.4f, time=%.1fs",
                fold_id,
                metrics.get("accuracy", 0),
                metrics.get("f1_macro", 0),
                fit_time + predict_time,
            )

        # Aggregate
        result.all_y_true = np.concatenate(all_y_true)
        result.all_y_pred = np.concatenate(all_y_pred)
        if all_y_proba:
            result.all_y_proba = np.concatenate(all_y_proba)

        result.aggregate_metrics = evaluator.evaluate(
            result.all_y_true,
            result.all_y_pred,
            result.all_y_proba,
        )

        logger.info(
            "WalkForward complete: %d folds, aggregate: %s",
            result.n_folds,
            {k: f"{v:.4f}" for k, v in result.aggregate_metrics.items()},
        )

        return result

    def __repr__(self) -> str:
        return (
            f"WalkForwardValidator(mode={self.mode!r}, "
            f"train={self.train_size}, test={self.test_size}, "
            f"step={self.step}, gap={self.gap})"
        )
