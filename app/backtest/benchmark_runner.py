"""
Benchmark Runner — Evaluasi strategi vs benchmark (IHSG / equal-weight).

Layer 6: app/backtest/ — Risk & Validation.
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """
    Menjalankan benchmark comparison antara strategi dan indeks acuan.

    Args:
        benchmark_ticker: Ticker benchmark (default '^JKSE' untuk IHSG)
    """

    def __init__(self, benchmark_ticker: str = "^JKSE"):
        self.benchmark_ticker = benchmark_ticker

    def compare(
        self,
        strategy_equity: pd.Series,
        benchmark_prices: pd.Series,
    ) -> Dict[str, float]:
        """
        Bandingkan performa strategi vs benchmark.

        Args:
            strategy_equity: Equity curve strategi (index=date, value=NAV)
            benchmark_prices: Close price benchmark (index=date)

        Returns:
            Dict metrik perbandingan
        """
        if strategy_equity.empty or benchmark_prices.empty:
            logger.warning("Empty data — cannot compare")
            return {}

        # Align dates
        common_dates = strategy_equity.index.intersection(benchmark_prices.index)
        if len(common_dates) < 2:
            return {}

        strat = strategy_equity.loc[common_dates]
        bench = benchmark_prices.loc[common_dates]

        # Normalize keduanya ke base 100
        strat_norm = strat / strat.iloc[0] * 100
        bench_norm = bench / bench.iloc[0] * 100

        # Returns
        strat_returns = strat_norm.pct_change().dropna()
        bench_returns = bench_norm.pct_change().dropna()

        # Sharpe
        strat_sharpe = self._sharpe(strat_returns)
        bench_sharpe = self._sharpe(bench_returns)

        # Max drawdown
        strat_mdd = self._max_drawdown(strat_norm)
        bench_mdd = self._max_drawdown(bench_norm)

        # Total return
        strat_total = (strat_norm.iloc[-1] / strat_norm.iloc[0]) - 1
        bench_total = (bench_norm.iloc[-1] / bench_norm.iloc[0]) - 1

        # Alpha & Beta
        beta, alpha = self._alpha_beta(strat_returns, bench_returns)

        return {
            "strategy_total_return": float(strat_total),
            "benchmark_total_return": float(bench_total),
            "excess_return": float(strat_total - bench_total),
            "strategy_sharpe": strat_sharpe,
            "benchmark_sharpe": bench_sharpe,
            "strategy_max_drawdown": strat_mdd,
            "benchmark_max_drawdown": bench_mdd,
            "alpha": alpha,
            "beta": beta,
            "n_days": len(common_dates),
        }

    @staticmethod
    def _sharpe(returns: pd.Series, risk_free: float = 0.0) -> float:
        if returns.std() == 0:
            return 0.0
        return float((returns.mean() - risk_free / 252) / returns.std() * np.sqrt(252))

    @staticmethod
    def _max_drawdown(equity: pd.Series) -> float:
        cum_max = equity.cummax()
        dd = (equity - cum_max) / cum_max
        return float(dd.min())

    @staticmethod
    def _alpha_beta(strat_ret: pd.Series, bench_ret: pd.Series) -> tuple:
        """Return (beta, alpha) dari simple linear regression."""
        if len(strat_ret) < 10:
            return 0.0, 0.0
        cov = np.cov(strat_ret, bench_ret)
        beta = cov[0, 1] / cov[1, 1] if cov[1, 1] != 0 else 0.0
        alpha = float(strat_ret.mean() - beta * bench_ret.mean()) * 252
        return float(beta), float(alpha)

    def __repr__(self) -> str:
        return f"BenchmarkRunner(benchmark={self.benchmark_ticker})"
