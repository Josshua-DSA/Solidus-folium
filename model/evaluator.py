"""
Model Evaluator — Metrics, Feature Importance, Calibration.

Berdasarkan:
  - Malla et al.: Accuracy, Precision, Recall, F1, AUC-ROC
  - Singh et al.: Confusion matrix per class (LOSS/NEUTRAL/PROFIT)
  - Bieganowski: Calibration curves untuk probabilitas

Untuk klasifikasi 3-kelas (TBL):
  - Class 0: LOSS
  - Class 1: NEUTRAL
  - Class 2: PROFIT
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Hasil evaluasi model lengkap."""
    metrics: Dict[str, float]
    confusion_matrix: Optional[np.ndarray] = None
    class_report: Optional[Dict] = None
    feature_importance: Optional[Dict[str, float]] = None
    calibration_data: Optional[Dict] = None


class ModelEvaluator:
    """
    Evaluator untuk model klasifikasi multi-kelas.

    Metrics utama:
      - accuracy: Proporsi prediksi benar
      - precision_macro: Rata-rata precision per kelas
      - recall_macro: Rata-rata recall per kelas
      - f1_macro: Rata-rata F1 per kelas
      - f1_weighted: F1 tertimbang jumlah sampel per kelas
      - auc_ovr: AUC One-vs-Rest (jika proba tersedia)
      - log_loss: Cross-entropy loss
    """

    CLASS_NAMES = {0: "LOSS", 1: "NEUTRAL", 2: "PROFIT"}

    def evaluate(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_proba: Optional[np.ndarray] = None,
    ) -> Dict[str, float]:
        """
        Hitung semua metrics evaluasi.

        Args:
            y_true: True labels (n_samples,)
            y_pred: Predicted labels (n_samples,)
            y_proba: Predicted probabilities (n_samples, n_classes)

        Returns:
            Dict dengan semua metrics
        """
        from sklearn.metrics import (
            accuracy_score, precision_score, recall_score,
            f1_score, log_loss, roc_auc_score,
        )

        metrics = {}

        # Basic metrics
        metrics["accuracy"] = float(accuracy_score(y_true, y_pred))
        metrics["precision_macro"] = float(precision_score(
            y_true, y_pred, average="macro", zero_division=0
        ))
        metrics["recall_macro"] = float(recall_score(
            y_true, y_pred, average="macro", zero_division=0
        ))
        metrics["f1_macro"] = float(f1_score(
            y_true, y_pred, average="macro", zero_division=0
        ))
        metrics["f1_weighted"] = float(f1_score(
            y_true, y_pred, average="weighted", zero_division=0
        ))

        # Per-class F1
        unique_classes = np.unique(np.concatenate([y_true, y_pred]))
        for cls in unique_classes:
            cls_f1 = float(f1_score(
                (y_true == cls).astype(int),
                (y_pred == cls).astype(int),
                zero_division=0,
            ))
            cls_name = self.CLASS_NAMES.get(int(cls), f"class_{cls}")
            metrics[f"f1_{cls_name}"] = cls_f1

        # AUC (jika proba tersedia)
        if y_proba is not None:
            try:
                metrics["auc_ovr"] = float(roc_auc_score(
                    y_true, y_proba, multi_class="ovr", average="macro",
                ))
            except ValueError:
                metrics["auc_ovr"] = 0.0

            try:
                metrics["log_loss"] = float(log_loss(y_true, y_proba))
            except ValueError:
                metrics["log_loss"] = float("inf")

        return metrics

    def confusion_matrix(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> np.ndarray:
        """
        Hitung confusion matrix.

        Returns:
            np.ndarray shape (n_classes, n_classes)
        """
        from sklearn.metrics import confusion_matrix as sk_cm
        return sk_cm(y_true, y_pred)

    def class_report(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> Dict:
        """
        Laporan per kelas (precision, recall, f1, support).

        Returns:
            Dict dengan metrics per kelas
        """
        from sklearn.metrics import classification_report
        report_str = classification_report(
            y_true, y_pred,
            target_names=[self.CLASS_NAMES.get(i, f"class_{i}")
                         for i in sorted(np.unique(y_true))],
            zero_division=0,
        )
        return {"report": report_str}

    def feature_importance(
        self,
        model,
        feature_names: Optional[List[str]] = None,
        top_n: int = 20,
    ) -> Dict[str, float]:
        """
        Ekstrak feature importance dari model.

        Support:
          - XGBoost: model.feature_importances_ atau get_score()
          - LightGBM: model.feature_importances_
          - sklearn: model.feature_importances_

        Args:
            model: Trained model
            feature_names: Nama fitur (jika None, pakai index)
            top_n: Jumlah fitur teratas

        Returns:
            Dict {feature_name: importance}
        """
        importance = None

        # Try feature_importances_ attribute
        if hasattr(model, "feature_importances_"):
            importance = model.feature_importances_

        # Try get_score() (XGBoost)
        elif hasattr(model, "get_score"):
            score_dict = model.get_score(importance_type="gain")
            # Convert to array
            n_features = len(feature_names) if feature_names else len(score_dict)
            importance = np.zeros(n_features)
            for key, val in score_dict.items():
                # Handle both "f0" format and actual feature names
                if key.startswith("f") and key[1:].isdigit():
                    idx = int(key[1:])
                elif feature_names and key in feature_names:
                    idx = feature_names.index(key)
                else:
                    continue

                if idx < n_features:
                    importance[idx] = val

        if importance is None:
            logger.warning("Model tidak memiliki feature importance")
            return {}

        # Sort dan ambil top_n
        if feature_names is None:
            feature_names = [f"f{i}" for i in range(len(importance))]

        sorted_idx = np.argsort(importance)[::-1][:top_n]
        return {
            feature_names[i]: float(importance[i])
            for i in sorted_idx
            if importance[i] > 0
        }

    def calibration_curve(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        n_bins: int = 10,
        class_idx: int = 2,
    ) -> Dict[str, np.ndarray]:
        """
        Hitung calibration curve untuk satu kelas.

        Args:
            y_true: True labels
            y_proba: Predicted probabilities
            n_bins: Jumlah bins
            class_idx: Index kelas yang ingin dikalibrasi

        Returns:
            Dict dengan 'fraction_of_positives' dan 'mean_predicted_value'
        """
        from sklearn.calibration import calibration_curve as sk_cal

        y_binary = (y_true == class_idx).astype(int)
        y_prob_class = y_proba[:, class_idx] if y_proba.ndim > 1 else y_proba

        fraction, mean_pred = sk_cal(
            y_binary, y_prob_class, n_bins=n_bins, strategy="uniform"
        )

        return {
            "fraction_of_positives": fraction,
            "mean_predicted_value": mean_pred,
        }

    def evaluate_full(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_proba: Optional[np.ndarray] = None,
        model=None,
        feature_names: Optional[List[str]] = None,
    ) -> EvaluationResult:
        """
        Evaluasi lengkap: metrics + confusion matrix + feature importance.

        Returns:
            EvaluationResult dataclass
        """
        metrics = self.evaluate(y_true, y_pred, y_proba)
        cm = self.confusion_matrix(y_true, y_pred)
        cr = self.class_report(y_true, y_pred)

        fi = None
        if model is not None:
            fi = self.feature_importance(model, feature_names)

        cal = None
        if y_proba is not None:
            cal = self.calibration_curve(y_true, y_proba)

        return EvaluationResult(
            metrics=metrics,
            confusion_matrix=cm,
            class_report=cr,
            feature_importance=fi,
            calibration_data=cal,
        )

    def __repr__(self) -> str:
        return "ModelEvaluator(classes=LOSS/NEUTRAL/PROFIT)"
