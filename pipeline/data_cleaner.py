"""
Data Cleaner — Anomaly removal + forward fill untuk data OHLCV.
"""
import numpy as np
import pandas as pd
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DataCleaner:
    """
    Pipeline pembersihan data: hapus anomali return ekstrem + forward fill NaN.

    Args:
        max_return_threshold: Threshold return anomali (default 25% = 0.25)
        max_anomaly_ratio: Rasio aset anomali per hari agar hari tersebut dihapus
        max_forward_fill: Maksimum hari berturut-turut untuk forward fill
    """

    def __init__(
        self,
        max_return_threshold: float = 0.25,
        max_anomaly_ratio: float = 0.50,
        max_forward_fill: int = 5,
    ):
        self.max_return_threshold = max_return_threshold
        self.max_anomaly_ratio = max_anomaly_ratio
        self.max_forward_fill = max_forward_fill

    def remove_anomaly(self, close_prices: pd.DataFrame) -> pd.DataFrame:
        """
        Hapus tanggal di mana >50% aset memiliki return ekstrem (>25%).
        Ini biasanya menandakan error data atau corporate action masal.

        Args:
            close_prices: DataFrame wide (index=date, columns=ticker)

        Returns:
            DataFrame tanpa baris anomali
        """
        returns = close_prices.pct_change(fill_method=None)
        anomaly_mask = returns.abs() > self.max_return_threshold

        # Hitung rasio anomali per baris (tanggal)
        anomaly_ratio = anomaly_mask.sum(axis=1) / len(close_prices.columns)

        # Tanggal yang harus dihapus
        bad_dates = anomaly_ratio > self.max_anomaly_ratio
        n_removed = bad_dates.sum()

        if n_removed > 0:
            logger.warning(
                "DataCleaner: %d tanggal dihapus karena anomali return ekstrem",
                n_removed,
            )
            return close_prices.loc[~bad_dates]

        return close_prices.copy()

    def fill_missing(
        self, df: pd.DataFrame, max_fill: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Forward fill NaN maksimum N hari berturut-turut.

        Args:
            df: DataFrame wide atau long
            max_fill: Override max_forward_fill

        Returns:
            DataFrame dengan NaN terisi
        """
        limit = max_fill or self.max_forward_fill
        filled = df.ffill(limit=limit)

        n_filled = df.isna().sum().sum() - filled.isna().sum().sum()
        if n_filled > 0:
            logger.info("DataCleaner: %d NaN di-forward-fill (max %d hari)", n_filled, limit)

        return filled

    def clean(self, close_prices: pd.DataFrame) -> pd.DataFrame:
        """
        Pipeline gabungan: remove_anomaly → fill_missing.

        Args:
            close_prices: DataFrame wide (index=date, columns=ticker)

        Returns:
            DataFrame bersih
        """
        cleaned = self.remove_anomaly(close_prices)
        cleaned = self.fill_missing(cleaned)
        logger.info(
            "DataCleaner: pipeline selesai. Shape: %s → %s",
            close_prices.shape, cleaned.shape,
        )
        return cleaned

    def __repr__(self) -> str:
        return (
            f"DataCleaner(max_return={self.max_return_threshold}, "
            f"max_anomaly_ratio={self.max_anomaly_ratio}, "
            f"max_ffill={self.max_forward_fill})"
        )
