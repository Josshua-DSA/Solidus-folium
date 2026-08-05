"""
Risk Model — Semi-covariance dan risk factor model.

Layer 4: app/optimization/ — Portfolio Optimizer.
"""
import numpy as np
import pandas as pd
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class RiskModel:
    """
    Risk model untuk portfolio optimization.
    Menggunakan semi-covariance (downside only) sesuai ARCHITECTURE.md.
    """

    @staticmethod
    def semi_covariance_matrix(
        returns: pd.DataFrame,
        threshold: float = 0.0,
    ) -> np.ndarray:
        """
        Hitung semi-covariance matrix (downside only).

        Hanya memperhitungkan return di bawah threshold (biasanya 0).
        Investor asimetris: hanya volatilitas ke bawah yang relevan.

        Args:
            returns: DataFrame returns (T x N assets)
            threshold: Threshold downside (default 0)

        Returns:
            Semi-covariance matrix (N x N)
        """
        downside = returns.copy()
        downside[downside > threshold] = 0.0
        return downside.cov().values

    @staticmethod
    def full_covariance_matrix(returns: pd.DataFrame) -> np.ndarray:
        """Hitung full covariance matrix."""
        return returns.cov().values

    @staticmethod
    def exponential_covariance(
        returns: pd.DataFrame,
        halflife: int = 63,
    ) -> np.ndarray:
        """
        Exponentially-weighted covariance matrix.

        Args:
            returns: DataFrame returns
            halflife: Halflife in periods (default ~3 months)

        Returns:
            EW covariance matrix
        """
        return returns.ewm(halflife=halflife).cov().iloc[-len(returns.columns):].values

    def __repr__(self) -> str:
        return "RiskModel()"
