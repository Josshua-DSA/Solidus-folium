"""
Backtest Engine — Simulasi trading historis dengan Walk-Forward Validation.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class Backtester:
    """
    Engine backtesting dengan Walk-Forward Validation.

    Args:
        initial_capital: Modal awal (default Rp100 juta)
        commission_pct: Komisi broker per transaksi (default 0.15%)
        slippage_pct: Slippage estimate (default 0.05%)
    """

    def __init__(
        self,
        initial_capital: float = 100_000_000,
        commission_pct: float = 0.0015,
        slippage_pct: float = 0.0005,
    ):
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct

    def run(
        self,
        close_prices: pd.DataFrame,
        signals: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Jalankan backtest sederhana (baseline Fase 1).

        Args:
            close_prices: DataFrame wide (index=date, columns=ticker)
            signals: DataFrame sinyal trading (same shape as close_prices)
                     1 = BUY, -1 = SELL, 0 = HOLD

        Returns:
            Dict berisi: equity_curve, trades, metrics
        """
        # TODO: Implementasi penuh di Fase 2
        logger.info("Backtest skeleton — implementasi penuh di Fase 2")
        return {
            "equity_curve": pd.Series(dtype=float),
            "trades": [],
            "metrics": {},
        }

    def calculate_metrics(
        self, equity_curve: pd.Series
    ) -> Dict[str, float]:
        """
        Hitung metrik performa dari equity curve.

        Args:
            equity_curve: Series nilai portofolio per tanggal

        Returns:
            Dict metrik: sharpe_ratio, max_drawdown, total_return, dll
        """
        if equity_curve.empty:
            return {}

        returns = equity_curve.pct_change().dropna()

        # Total return
        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1

        # Annualized Sharpe (asumsi 252 hari bursa)
        if returns.std() > 0:
            sharpe = (returns.mean() / returns.std()) * np.sqrt(252)
        else:
            sharpe = 0.0

        # Max drawdown
        cum_max = equity_curve.cummax()
        drawdown = (equity_curve - cum_max) / cum_max
        max_drawdown = drawdown.min()

        return {
            "total_return": total_return,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_drawdown,
            "n_days": len(equity_curve),
        }

    def __repr__(self) -> str:
        return (
            f"Backtester(capital={self.initial_capital:,.0f}, "
            f"commission={self.commission_pct:.4f})"
        )


class WalkForwardValidator:
    """
    Walk-Forward Validation — rolling train/test split untuk evaluasi model.

    Args:
        n_splits: Jumlah fold
        train_window: Panjang window training (hari)
        test_window: Panjang window testing (hari)
    """

    def __init__(
        self,
        n_splits: int = 5,
        train_window: int = 504,
        test_window: int = 126,
    ):
        self.n_splits = n_splits
        self.train_window = train_window
        self.test_window = test_window

    def split(self, data: pd.DataFrame) -> List[tuple]:
        """
        Generate train/test indices.

        Args:
            data: DataFrame yang akan di-split

        Returns:
            List of (train_indices, test_indices)
        """
        n = len(data)
        total_needed = self.n_splits * (self.train_window + self.test_window)

        if n < total_needed:
            logger.warning(
                "Data terlalu pendek (%d rows) untuk %d splits. "
                "Menggunakan sisa data sebagai test terakhir.",
                n, self.n_splits,
            )

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

    def validate(self, model: Any, dataset: pd.DataFrame, **kwargs) -> List[Dict[str, float]]:
        """
        Jalankan validasi walk-forward pada model.

        Args:
            model: Model yang memiliki method fit() dan predict_proba()
            dataset: DataFrame dengan kolom features dan label
            **kwargs: Parameter tambahan

        Returns:
            List metrics per fold
        """
        # TODO: Implementasi penuh di Fase 3
        logger.info("WalkForward.validate() — implementasi penuh di Fase 3")
        return []

    def __repr__(self) -> str:
        return (
            f"WalkForwardValidator(splits={self.n_splits}, "
            f"train={self.train_window}d, test={self.test_window}d)"
        )
