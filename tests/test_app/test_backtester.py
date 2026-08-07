"""
Tests for app/backtest/ — Backtester engine + extended metrics.
"""
import numpy as np
import pandas as pd
import pytest
from decimal import Decimal

from app.backtest.backtester import Backtester
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
from app.backtest.transaction_cost import TransactionCostModel
from app.backtest.benchmark_runner import BenchmarkRunner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_equity_curve():
    """Equity curve sederhana: 100M → naik bertahap dengan sedikit drawdown."""
    dates = pd.date_range("2023-01-02", periods=252, freq="B")
    np.random.seed(42)
    daily_returns = np.random.normal(0.0004, 0.012, size=252)
    prices = 100_000_000 * np.cumprod(1 + daily_returns)
    return pd.Series(prices, index=dates, name="equity")


@pytest.fixture
def flat_equity_curve():
    """Equity curve datar — tidak ada return."""
    dates = pd.date_range("2023-01-02", periods=100, freq="B")
    return pd.Series([100_000_000.0] * 100, index=dates, name="equity")


@pytest.fixture
def sample_trades():
    """List trade dicts untuk trade-level metrics."""
    return [
        {"pnl": 500_000, "commission": 15_000},
        {"pnl": -200_000, "commission": 12_000},
        {"pnl": 800_000, "commission": 18_000},
        {"pnl": -100_000, "commission": 10_000},
        {"pnl": 300_000, "commission": 14_000},
        {"pnl": -50_000, "commission": 8_000},
    ]


@pytest.fixture
def backtest_data():
    """
    Close prices + signals untuk 3 ticker, 60 hari.
    Sinyal: BUY di hari ke-5, SELL di hari ke-30 untuk setiap ticker.
    """
    dates = pd.date_range("2023-01-02", periods=60, freq="B")
    np.random.seed(123)

    tickers = ["BBCA.JK", "BBRI.JK", "TLKM.JK"]
    prices_data = {}
    signals_data = {}

    for ticker in tickers:
        base = 5000 + np.random.randint(0, 5000)
        daily_ret = np.random.normal(0.001, 0.015, size=60)
        prices_data[ticker] = base * np.cumprod(1 + daily_ret)

        sig = np.zeros(60)
        sig[5] = 1    # BUY at day 5
        sig[30] = -1  # SELL at day 30
        signals_data[ticker] = sig

    close_prices = pd.DataFrame(prices_data, index=dates)
    signals = pd.DataFrame(signals_data, index=dates)

    return close_prices, signals


# ---------------------------------------------------------------------------
# Tests: Extended Metrics
# ---------------------------------------------------------------------------

class TestMetrics:
    def test_total_return(self, sample_equity_curve):
        ret = calculate_total_return(sample_equity_curve)
        assert isinstance(ret, float)
        # Should be nonzero for a random walk with positive drift
        assert ret != 0.0

    def test_total_return_empty(self):
        empty = pd.Series(dtype=float)
        assert calculate_total_return(empty) == 0.0

    def test_cagr(self, sample_equity_curve):
        cagr = calculate_cagr(sample_equity_curve)
        assert isinstance(cagr, float)
        # 252 days = ~1 year, so CAGR ≈ total return
        total = calculate_total_return(sample_equity_curve)
        assert abs(cagr - total) < 0.05  # Within 5pp

    def test_sharpe_ratio(self, sample_equity_curve):
        sharpe = calculate_sharpe_ratio(sample_equity_curve)
        assert isinstance(sharpe, float)
        # With positive drift, Sharpe should be positive
        assert sharpe > 0

    def test_sharpe_ratio_flat(self, flat_equity_curve):
        sharpe = calculate_sharpe_ratio(flat_equity_curve)
        assert sharpe == 0.0

    def test_sortino_ratio(self, sample_equity_curve):
        sortino = calculate_sortino_ratio(sample_equity_curve)
        assert isinstance(sortino, float)
        # Sortino >= Sharpe for positive drift (penalizes only downside)
        sharpe = calculate_sharpe_ratio(sample_equity_curve)
        assert sortino >= sharpe - 0.5  # Allow small margin

    def test_max_drawdown(self, sample_equity_curve):
        dd = calculate_max_drawdown(sample_equity_curve)
        assert "max_drawdown" in dd
        assert "max_drawdown_duration" in dd
        assert "recovery_days" in dd
        assert dd["max_drawdown"] <= 0  # Drawdown is negative
        assert dd["max_drawdown_duration"] >= 0

    def test_max_drawdown_flat(self, flat_equity_curve):
        dd = calculate_max_drawdown(flat_equity_curve)
        assert dd["max_drawdown"] == 0.0

    def test_calmar_ratio(self, sample_equity_curve):
        calmar = calculate_calmar_ratio(sample_equity_curve)
        assert isinstance(calmar, float)

    def test_annualized_volatility(self, sample_equity_curve):
        vol = calculate_annualized_volatility(sample_equity_curve)
        assert isinstance(vol, float)
        assert vol > 0

    def test_j_value(self, sample_equity_curve):
        j = calculate_j_value(sample_equity_curve)
        assert isinstance(j, float)

    def test_calculate_all_metrics(self, sample_equity_curve, sample_trades):
        metrics = calculate_all_metrics(
            sample_equity_curve, trades=sample_trades
        )
        # Check all expected keys exist
        expected_keys = [
            "total_return", "cagr", "sharpe_ratio", "sortino_ratio",
            "annualized_volatility", "calmar_ratio", "j_value",
            "max_drawdown", "max_drawdown_duration", "recovery_days",
            "n_days", "n_trades", "win_rate", "profit_factor",
            "avg_win", "avg_loss", "best_trade", "worst_trade",
            "total_commission",
        ]
        for key in expected_keys:
            assert key in metrics, f"Missing key: {key}"

    def test_trade_metrics(self, sample_trades):
        tm = calculate_trade_metrics(sample_trades)
        assert tm["n_trades"] == 6
        assert 0 < tm["win_rate"] < 1  # Mixed wins/losses
        assert tm["profit_factor"] > 0
        assert tm["best_trade"] == 800_000
        assert tm["worst_trade"] == -200_000
        assert tm["total_commission"] == sum(
            t["commission"] for t in sample_trades
        )

    def test_trade_metrics_empty(self):
        tm = calculate_trade_metrics([])
        assert tm["n_trades"] == 0
        assert tm["win_rate"] == 0.0

    def test_trade_metrics_all_winners(self):
        trades = [{"pnl": 100}, {"pnl": 200}]
        tm = calculate_trade_metrics(trades)
        assert tm["win_rate"] == 1.0
        assert tm["profit_factor"] == float("inf")


# ---------------------------------------------------------------------------
# Tests: TransactionCostModel
# ---------------------------------------------------------------------------

class TestTransactionCostModel:
    def test_buy_cost(self):
        tc = TransactionCostModel()
        result = tc.calculate_buy_cost(price=10000, quantity_shares=100)
        assert "notional" in result
        assert "commission" in result
        assert "total_cost" in result
        assert result["notional"] == Decimal("1000000.00")
        assert result["total_cost"] > 0

    def test_sell_cost_includes_tax(self):
        tc = TransactionCostModel()
        result = tc.calculate_sell_cost(price=10000, quantity_shares=100)
        assert result["tax"] > 0  # PPh final on sell
        assert result["effective_proceeds"] < result["notional"]

    def test_round_trip_cost(self):
        tc = TransactionCostModel()
        rt = tc.round_trip_cost_pct()
        assert rt > 0
        # Should be roughly 0.15%*2 + 0.1% + levy*2 + slip*2
        assert 0.003 < rt < 0.01


# ---------------------------------------------------------------------------
# Tests: BenchmarkRunner
# ---------------------------------------------------------------------------

class TestBenchmarkRunner:
    def test_compare(self, sample_equity_curve):
        br = BenchmarkRunner()
        # Create a benchmark that goes up less
        bench = sample_equity_curve * 0.95 + 5_000_000
        result = br.compare(sample_equity_curve, bench)
        assert "strategy_total_return" in result
        assert "benchmark_total_return" in result
        assert "excess_return" in result
        assert "alpha" in result
        assert "beta" in result

    def test_compare_empty(self):
        br = BenchmarkRunner()
        result = br.compare(pd.Series(dtype=float), pd.Series(dtype=float))
        assert result == {}


# ---------------------------------------------------------------------------
# Tests: Backtester End-to-End
# ---------------------------------------------------------------------------

class TestBacktester:
    def test_init(self):
        bt = Backtester()
        assert bt.initial_capital == Decimal("100000000")
        assert bt.lot_size == 100

    def test_run_empty(self):
        bt = Backtester()
        result = bt.run(pd.DataFrame(), pd.DataFrame())
        assert result["trades"] == []
        assert result["metrics"] == {}

    def test_run_basic(self, backtest_data):
        close_prices, signals = backtest_data
        bt = Backtester(initial_capital=100_000_000)
        result = bt.run(close_prices, signals)

        # Should have equity curve
        assert not result["equity_curve"].empty
        assert len(result["equity_curve"]) == 60

        # Should have trades (BUY at day 5, SELL at day 30 for 3 tickers)
        assert len(result["trades"]) > 0

        # Metrics should be populated
        assert "total_return" in result["metrics"]
        assert "sharpe_ratio" in result["metrics"]
        assert "max_drawdown" in result["metrics"]
        assert "n_trades" in result["metrics"]
        assert "win_rate" in result["metrics"]
        assert "initial_capital" in result["metrics"]
        assert "final_nav" in result["metrics"]

    def test_run_lot_constraint(self, backtest_data):
        """Semua trade harus kelipatan lot_size."""
        close_prices, signals = backtest_data
        bt = Backtester(initial_capital=100_000_000, lot_size=100)
        result = bt.run(close_prices, signals)

        for trade in result["trades"]:
            assert trade["shares"] % 100 == 0, (
                f"Trade {trade['ticker']} shares={trade['shares']} "
                f"not multiple of lot_size=100"
            )

    def test_run_capital_preserved(self, backtest_data):
        """Cash + position value should never go negative."""
        close_prices, signals = backtest_data
        bt = Backtester(initial_capital=100_000_000)
        result = bt.run(close_prices, signals)

        # All equity values should be positive
        assert (result["equity_curve"] > 0).all()

    def test_run_no_signals(self, backtest_data):
        """Zero signals → no trades, equity flat."""
        close_prices, _ = backtest_data
        zero_signals = pd.DataFrame(
            0, index=close_prices.index, columns=close_prices.columns
        )
        bt = Backtester(initial_capital=100_000_000)
        result = bt.run(close_prices, zero_signals)

        assert len(result["trades"]) == 0
        # Equity should stay at initial capital
        assert abs(result["equity_curve"].iloc[-1] - 100_000_000) < 1

    def test_calculate_metrics_backward_compat(self, sample_equity_curve):
        """calculate_metrics() should still work (backward compat)."""
        bt = Backtester()
        metrics = bt.calculate_metrics(sample_equity_curve)
        assert "total_return" in metrics
        assert "sharpe_ratio" in metrics
        assert "max_drawdown" in metrics

    def test_repr(self):
        bt = Backtester()
        r = repr(bt)
        assert "Backtester" in r
        assert "100" in r  # lot_size
