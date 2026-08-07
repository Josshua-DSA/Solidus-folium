"""
Backtest sub-package.
Layer 6: Risk & Validation.
"""
from app.backtest.backtester import Backtester
from app.backtest.walk_forward import WalkForwardValidator
from app.backtest.transaction_cost import TransactionCostModel
from app.backtest.benchmark_runner import BenchmarkRunner
from app.backtest.metrics import (
    calculate_all_metrics,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_cagr,
    calculate_max_drawdown,
    calculate_calmar_ratio,
    calculate_j_value,
    calculate_trade_metrics,
    calculate_total_return,
    calculate_annualized_volatility,
)

__all__ = [
    "Backtester",
    "WalkForwardValidator",
    "TransactionCostModel",
    "BenchmarkRunner",
    "calculate_all_metrics",
    "calculate_sharpe_ratio",
    "calculate_sortino_ratio",
    "calculate_cagr",
    "calculate_max_drawdown",
    "calculate_calmar_ratio",
    "calculate_j_value",
    "calculate_trade_metrics",
    "calculate_total_return",
    "calculate_annualized_volatility",
]
