"""
Triple Barrier Labeling (TBL) — Labeling berdasar Kang & Kim (2025).

Menggunakan harga LOW dan HIGH (bukan hanya close) untuk mengurangi
ketidakpastian intraday. Jika LOW dan HIGH keduanya menyentuh barrier
pada hari yang sama → label sebagai NEUTRAL (Class 1).

Parameter optimal (Kang & Kim, Korean market):
  - Horizon: 29 hari bursa
  - Barrier (TP/SL): 9%
  - Label distribution: ~36% NEUTRAL, ~35% PROFIT, ~29% LOSS

Untuk IDX: disarankan mulai dengan horizon=5 hari, barrier=3%
sesuai karakteristik pasar yang lebih volatile.

Classes:
  0 = LOSS (stop-loss hit first)
  1 = NEUTRAL (time horizon reached without touching barriers)
  2 = PROFIT (take-profit hit first)
"""
import numpy as np
import pandas as pd
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class TripleBarrierLabeler:
    """
    Triple Barrier Labeling menggunakan OHLC data.

    Args:
        barrier_pct: Persentase barrier untuk TP dan SL (default 0.03 = 3%)
        horizon: Jumlah hari bursa maksimum (default 5)
        use_high_low: Gunakan HIGH/LOW untuk barrier detection (default True)
    """

    def __init__(
        self,
        barrier_pct: float = 0.03,
        horizon: int = 5,
        use_high_low: bool = True,
    ):
        self.barrier_pct = barrier_pct
        self.horizon = horizon
        self.use_high_low = use_high_low

        logger.info(
            "TripleBarrierLabeler: barrier=%.1f%%, horizon=%d, use_high_low=%s",
            barrier_pct * 100, horizon, use_high_low,
        )

    def label(
        self,
        ohlc: pd.DataFrame,
        start_idx: int,
    ) -> int:
        """
        Label satu entry point menggunakan triple barrier.

        Args:
            ohlc: DataFrame dengan kolom 'open', 'high', 'low', 'close'
            start_idx: Index baris entry point

        Returns:
            0 = LOSS, 1 = NEUTRAL, 2 = PROFIT
        """
        if start_idx >= len(ohlc):
            return 1  # NEUTRAL (no data)

        entry_price = ohlc.iloc[start_idx]["close"]
        upper_barrier = entry_price * (1 + self.barrier_pct)
        lower_barrier = entry_price * (1 - self.barrier_pct)

        # Window dari entry+1 sampai entry+horizon
        end_idx = min(start_idx + self.horizon, len(ohlc))
        window = ohlc.iloc[start_idx + 1: end_idx]

        if window.empty:
            return 1  # NEUTRAL (insufficient data)

        if self.use_high_low:
            return self._label_high_low(window, upper_barrier, lower_barrier)
        else:
            return self._label_close_only(window, upper_barrier, lower_barrier)

    def _label_high_low(
        self,
        window: pd.DataFrame,
        upper: float,
        lower: float,
    ) -> int:
        """
        Labeling menggunakan HIGH dan LOW.

        Rules (Kang & Kim):
          - Jika HIGH >= upper barrier → PROFIT (2)
          - Jika LOW <= lower barrier → LOSS (0)
          - Jika keduanya pada hari yang sama → NEUTRAL (1)
          - Jika tidak ada yang tersentuh sampai horizon → NEUTRAL (1)
        """
        profit_hit = window["high"] >= upper
        loss_hit = window["low"] <= lower

        # Cek apakah keduanya terjadi pada hari yang sama
        both_hit = (profit_hit & loss_hit).any()
        if both_hit:
            return 1  # NEUTRAL (Kang & Kim rule)

        # Cari yang mana terjadi duluan
        for i in range(len(window)):
            row = window.iloc[i]
            if row["high"] >= upper:
                return 2  # PROFIT
            if row["low"] <= lower:
                return 0  # LOSS

        return 1  # NEUTRAL (horizon reached without hitting barriers)

    def _label_close_only(
        self,
        window: pd.DataFrame,
        upper: float,
        lower: float,
    ) -> int:
        """Labeling menggunakan close price saja (fallback)."""
        profit_hit = window["close"] >= upper
        loss_hit = window["close"] <= lower

        for i in range(len(window)):
            close = window.iloc[i]["close"]
            if close >= upper:
                return 2  # PROFIT
            if close <= lower:
                return 0  # LOSS

        return 1  # NEUTRAL

    def label_all(
        self,
        ohlc: pd.DataFrame,
        ticker: str = "",
    ) -> np.ndarray:
        """
        Label semua entry point dalam satu DataFrame.

        Args:
            ohlc: DataFrame OHLC lengkap
            ticker: Nama ticker (untuk logging)

        Returns:
            np.ndarray of labels (0, 1, 2)
        """
        n = len(ohlc)
        labels = np.full(n, np.nan, dtype=float)

        for i in range(n - self.horizon):
            labels[i] = self.label(ohlc, i)

        # Statistik label
        if ticker:
            valid_labels = labels[~np.isnan(labels)]
            if len(valid_labels) > 0:
                dist = pd.Series(valid_labels).value_counts(normalize=True).sort_index()
                logger.info(
                    "TBL %s: %d labels → Class 0: %.1f%%, Class 1: %.1f%%, Class 2: %.1f%%",
                    ticker, len(valid_labels),
                    dist.get(0, 0) * 100,
                    dist.get(1, 0) * 100,
                    dist.get(2, 0) * 100,
                )

        return labels

    def optimize_parameters(
        self,
        ohlc: pd.DataFrame,
        horizons: list = None,
        barriers: list = None,
        target_balance: float = 0.30,
    ) -> Tuple[int, float, float]:
        """
        Optimasi parameter TBL untuk mendapatkan label yang balanced.

        Mencari kombinasi horizon dan barrier yang menghasilkan
        proporsi label terdistribusi paling merata.

        Args:
            ohlc: DataFrame OHLC
            horizons: List horizon yang dicoba (default [5, 10, 20, 29])
            barriers: List barrier yang dicoba (default [0.03, 0.05, 0.07, 0.09])
            target_balance: Proporsi minimum per kelas

        Returns:
            (best_horizon, best_barrier, best_score)
        """
        if horizons is None:
            horizons = [5, 10, 20, 29]
        if barriers is None:
            barriers = [0.03, 0.05, 0.07, 0.09]

        best_score = -1
        best_horizon = self.horizon
        best_barrier = self.barrier_pct

        for h in horizons:
            for b in barriers:
                lbl = TripleBarrierLabeler(barrier_pct=b, horizon=h)
                labels = lbl.label_all(ohlc)
                valid = labels[~np.isnan(labels)]

                if len(valid) < 100:
                    continue

                # Hitung proporsi per kelas
                counts = pd.Series(valid).value_counts(normalize=True)
                min_prop = min(
                    counts.get(0, 0),
                    counts.get(1, 0),
                    counts.get(2, 0),
                )

                # Score: semakin balanced semakin baik
                score = min_prop
                if score > best_score:
                    best_score = score
                    best_horizon = h
                    best_barrier = b

        logger.info(
            "TBL parameter optimization: best horizon=%d, barrier=%.1f%%, "
            "min_class_prop=%.1f%%",
            best_horizon, best_barrier * 100, best_score * 100,
        )

        return best_horizon, best_barrier, best_score

    def __repr__(self) -> str:
        return (
            f"TripleBarrierLabeler(barrier={self.barrier_pct:.1%}, "
            f"horizon={self.horizon}, use_high_low={self.use_high_low})"
        )
