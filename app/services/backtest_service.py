"""
Backtest Service — Facade untuk menjalankan dan memformat hasil backtest.

Menggabungkan Backtester, Strategy, dan BenchmarkRunner
menjadi satu workflow yang bisa dikonsumsi TUI.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
import logging

from app.backtest.backtester import Backtester
from app.backtest.benchmark_runner import BenchmarkRunner
from app.backtest.walk_forward import WalkForwardValidator
from app.services.data_service import DataService
from app.strategies.momentum_strategy import MomentumStrategy
from app.strategies.ml_signal_strategy import MLSignalStrategy

logger = logging.getLogger(__name__)


class BacktestService:
    """
    Service layer untuk menjalankan backtest end-to-end.

    Args:
        data_service: DataService instance
        initial_capital: Modal awal (Rp)
        commission_pct: Komisi broker
        slippage_pct: Slippage estimate
    """

    def __init__(
        self,
        data_service: Optional[DataService] = None,
        initial_capital: float = 100_000_000,
        commission_pct: float = 0.0015,
        slippage_pct: float = 0.0005,
    ):
        self.data_service = data_service or DataService()
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct

        self.backtester = Backtester(
            initial_capital=initial_capital,
            commission_pct=commission_pct,
            slippage_pct=slippage_pct,
        )
        self.benchmark_runner = BenchmarkRunner()

    def run_momentum_backtest(
        self,
        tickers: Optional[List[str]] = None,
        fast_window: int = 5,
        slow_window: int = 20,
        position_size_pct: float = 0.10,
    ) -> Dict[str, Any]:
        """
        Jalankan backtest menggunakan momentum strategy.

        Args:
            tickers: Ticker yang di-backtest (None = semua di DB)
            fast_window: Momentum fast window
            slow_window: Momentum slow window
            position_size_pct: Target position size per ticker

        Returns:
            Dict hasil backtest (equity_curve, trades, metrics, ...)
        """
        close_prices = self.data_service.get_close_prices(tickers)
        if close_prices.empty:
            logger.warning("No price data for backtest")
            return {"error": "No price data available"}

        strategy = MomentumStrategy(
            fast_window=fast_window,
            slow_window=slow_window,
        )
        signals = strategy.generate_signals(close_prices)

        result = self.backtester.run(
            close_prices, signals,
            position_size_pct=position_size_pct,
        )

        # Add strategy info to result
        result["strategy"] = "momentum"
        result["strategy_params"] = {
            "fast_window": fast_window,
            "slow_window": slow_window,
            "position_size_pct": position_size_pct,
        }

        return result

    def run_ml_backtest(
        self,
        ml_predictions: pd.DataFrame,
        tickers: Optional[List[str]] = None,
        buy_threshold: float = 0.60,
        sell_threshold: float = 0.35,
        position_size_pct: float = 0.10,
    ) -> Dict[str, Any]:
        """
        Jalankan backtest menggunakan ML signal strategy.

        Args:
            ml_predictions: DataFrame P(PROFIT)
            tickers: Filter ticker
            buy_threshold: BUY threshold
            sell_threshold: SELL threshold
            position_size_pct: Position size

        Returns:
            Dict hasil backtest
        """
        close_prices = self.data_service.get_close_prices(tickers)
        if close_prices.empty:
            return {"error": "No price data available"}

        strategy = MLSignalStrategy(
            buy_threshold=buy_threshold,
            sell_threshold=sell_threshold,
        )
        signals = strategy.generate_signals(
            close_prices, ml_predictions=ml_predictions
        )

        result = self.backtester.run(
            close_prices, signals,
            position_size_pct=position_size_pct,
        )

        result["strategy"] = "ml_signal"
        result["strategy_params"] = {
            "buy_threshold": buy_threshold,
            "sell_threshold": sell_threshold,
        }

        return result

    def run_benchmark_comparison(
        self,
        strategy_equity: pd.Series,
        benchmark_ticker: str = "^JKSE",
        tickers: Optional[List[str]] = None,
    ) -> Dict[str, float]:
        """
        Bandingkan strategi vs benchmark.

        Args:
            strategy_equity: Equity curve strategi
            benchmark_ticker: Ticker benchmark (default IHSG)
            tickers: Jika benchmark_ticker ada di DB lokal

        Returns:
            Dict metrik perbandingan
        """
        # Coba load benchmark dari DB
        try:
            benchmark_prices = self.data_service.get_close_prices([benchmark_ticker])
            if not benchmark_prices.empty:
                bench_series = benchmark_prices.iloc[:, 0]
                return self.benchmark_runner.compare(strategy_equity, bench_series)
        except Exception as e:
            logger.warning("Could not load benchmark %s: %s", benchmark_ticker, e)

        return {}

    def __repr__(self) -> str:
        return (
            f"BacktestService(capital={self.initial_capital:,.0f}, "
            f"comm={self.commission_pct:.4f})"
        )
