"""
Tests for app/strategies/ — MomentumStrategy, MLSignalStrategy, StrategyRegistry.
"""
import numpy as np
import pandas as pd
import pytest

from app.strategies.momentum_strategy import MomentumStrategy
from app.strategies.ml_signal_strategy import MLSignalStrategy
from app.strategies.strategy_registry import StrategyRegistry
from app.strategies.base_strategy import BaseStrategy


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def price_data():
    """Wide-format close prices: 3 tickers, 120 days."""
    dates = pd.date_range("2023-01-02", periods=120, freq="B")
    np.random.seed(42)
    data = {}
    for ticker in ["BBCA.JK", "BBRI.JK", "TLKM.JK"]:
        base = 5000 + np.random.randint(0, 5000)
        ret = np.random.normal(0.001, 0.015, size=120)
        data[ticker] = base * np.cumprod(1 + ret)
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def ml_predictions(price_data):
    """Simulated P(PROFIT) predictions matching price_data shape."""
    np.random.seed(99)
    preds = pd.DataFrame(
        np.random.uniform(0.2, 0.9, size=price_data.shape),
        index=price_data.index,
        columns=price_data.columns,
    )
    return preds


# ---------------------------------------------------------------------------
# Tests: MomentumStrategy
# ---------------------------------------------------------------------------

class TestMomentumStrategy:
    def test_init(self):
        s = MomentumStrategy()
        assert s.name == "momentum"
        assert s.tier == 1
        assert s.is_bot_eligible()
        assert s.fast_window == 5
        assert s.slow_window == 20

    def test_generate_signals_shape(self, price_data):
        s = MomentumStrategy()
        signals = s.generate_signals(price_data)
        assert signals.shape == price_data.shape
        assert list(signals.columns) == list(price_data.columns)

    def test_generate_signals_values(self, price_data):
        """Signals should only contain -1, 0, 1."""
        s = MomentumStrategy()
        signals = s.generate_signals(price_data)
        unique = set(signals.values.flatten())
        assert unique.issubset({-1, 0, 1})

    def test_generate_signals_produces_trades(self, price_data):
        """Should produce at least some BUY/SELL over 120 days."""
        s = MomentumStrategy(fast_window=5, slow_window=20)
        signals = s.generate_signals(price_data)
        n_buy = (signals == 1).sum().sum()
        n_sell = (signals == -1).sum().sum()
        assert n_buy > 0, "No BUY signals generated"

    def test_generate_signals_no_repeated_buys(self, price_data):
        """Should not have consecutive BUYs without a SELL in between."""
        s = MomentumStrategy()
        signals = s.generate_signals(price_data)

        for ticker in price_data.columns:
            sig_col = signals[ticker]
            active = sig_col[sig_col != 0]
            for i in range(1, len(active)):
                assert not (active.iloc[i] == 1 and active.iloc[i - 1] == 1), (
                    f"Consecutive BUYs for {ticker}"
                )

    def test_empty_prices(self):
        s = MomentumStrategy()
        result = s.generate_signals(pd.DataFrame())
        assert result.empty

    def test_score_ticker(self, price_data):
        s = MomentumStrategy()
        score = s.score_ticker(price_data["BBCA.JK"])
        assert 0.0 <= score <= 1.0

    def test_custom_windows(self, price_data):
        s = MomentumStrategy(fast_window=3, slow_window=10)
        signals = s.generate_signals(price_data)
        assert signals.shape == price_data.shape


# ---------------------------------------------------------------------------
# Tests: MLSignalStrategy
# ---------------------------------------------------------------------------

class TestMLSignalStrategy:
    def test_init(self):
        s = MLSignalStrategy()
        assert s.name == "ml_signal"
        assert s.tier == 1
        assert s.buy_threshold == 0.60
        assert s.sell_threshold == 0.35

    def test_generate_signals_shape(self, price_data, ml_predictions):
        s = MLSignalStrategy()
        signals = s.generate_signals(price_data, ml_predictions=ml_predictions)
        assert signals.shape == price_data.shape

    def test_generate_signals_values(self, price_data, ml_predictions):
        """Signals should only contain -1, 0, 1."""
        s = MLSignalStrategy()
        signals = s.generate_signals(price_data, ml_predictions=ml_predictions)
        unique = set(signals.values.flatten())
        assert unique.issubset({-1, 0, 1})

    def test_generate_signals_with_predictions(self, price_data, ml_predictions):
        """Should produce trades when predictions cross thresholds."""
        s = MLSignalStrategy(buy_threshold=0.60, sell_threshold=0.35)
        signals = s.generate_signals(price_data, ml_predictions=ml_predictions)
        n_buy = (signals == 1).sum().sum()
        assert n_buy > 0

    def test_no_predictions_returns_zeros(self, price_data):
        s = MLSignalStrategy()
        signals = s.generate_signals(price_data, ml_predictions=None)
        assert (signals == 0).all().all()

    def test_rank_by_probability(self, ml_predictions):
        s = MLSignalStrategy()
        ranked = s.rank_by_probability(ml_predictions, top_n=3)
        assert len(ranked) == 3
        assert "ticker" in ranked.columns
        assert "p_profit" in ranked.columns
        assert "signal" in ranked.columns
        # Should be sorted descending
        assert ranked["p_profit"].is_monotonic_decreasing

    def test_rank_empty(self):
        s = MLSignalStrategy()
        ranked = s.rank_by_probability(pd.DataFrame(), top_n=5)
        assert ranked.empty


# ---------------------------------------------------------------------------
# Tests: StrategyRegistry
# ---------------------------------------------------------------------------

class TestStrategyRegistry:
    def test_momentum_registered(self):
        strats = StrategyRegistry.list_strategies()
        assert "momentum" in strats

    def test_ml_signal_registered(self):
        strats = StrategyRegistry.list_strategies()
        assert "ml_signal" in strats

    def test_get_momentum(self):
        s = StrategyRegistry.get("momentum")
        assert isinstance(s, MomentumStrategy)
        assert isinstance(s, BaseStrategy)

    def test_get_ml_signal(self):
        s = StrategyRegistry.get("ml_signal")
        assert isinstance(s, MLSignalStrategy)

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError):
            StrategyRegistry.get("nonexistent_strategy")

    def test_list_bot_eligible(self):
        # Registry lists all registered strategies by name
        all_strats = StrategyRegistry.list_strategies()
        assert len(all_strats) >= 2
        assert "momentum" in all_strats
        assert "ml_signal" in all_strats
