"""
Backtest Engine — Simulasi trading historis.
Layer 6: app/backtest/ — Risk & Validation.

WalkForwardValidator dipindah ke walk_forward.py (per ARCHITECTURE.md).
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class Backtester:
    """
    Engine backtesting simulasi trading historis.

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
        # TODO: Implementasi penuh di Fase 5
        logger.info("Backtest skeleton — implementasi penuh di Fase 5")
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
