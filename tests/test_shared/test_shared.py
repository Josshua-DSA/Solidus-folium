"""
Tests for shared/ — CashflowMetrics, DCFValuation, FundamentalFeatureBuilder,
helpers, config_loader, logger, ui_renderer.
"""
import numpy as np
import pandas as pd
import pytest
from decimal import Decimal

from shared.financial_math.cashflow_metrics import CashflowMetrics
from shared.financial_math.valuation import DCFValuation
from shared.features.fundamental_features import FundamentalFeatureBuilder
from shared.utils.helper import (
    is_trading_day,
    get_last_trading_day,
    format_currency,
    format_percentage,
    lot_to_shares,
    shares_to_lot,
)
from shared.utils.config_loader import load_config
from shared.utils.logger import setup_logger
from shared.utils.ui_renderer import render_table, render_metrics, render_portfolio


# ---------------------------------------------------------------------------
# Tests: CashflowMetrics
# ---------------------------------------------------------------------------

class TestCashflowMetrics:
    def test_log_return(self):
        ret = CashflowMetrics.log_return(110.0, 100.0)
        assert abs(ret - np.log(1.1)) < 1e-6

    def test_log_return_zero_prev(self):
        assert CashflowMetrics.log_return(100.0, 0.0) == 0.0

    def test_simple_return(self):
        ret = CashflowMetrics.simple_return(110.0, 100.0)
        assert abs(ret - 0.10) < 1e-6

    def test_simple_return_zero_prev(self):
        assert CashflowMetrics.simple_return(100.0, 0.0) == 0.0

    def test_annualized_return(self):
        ret = CashflowMetrics.annualized_return(0.25, 252, periods_per_year=252)
        assert abs(ret - 0.25) < 1e-6

    def test_annualized_return_zero_periods(self):
        assert CashflowMetrics.annualized_return(0.25, 0) == 0.0

    def test_sharpe_ratio(self):
        returns = np.array([0.01, 0.02, -0.01, 0.015, 0.005])
        sharpe = CashflowMetrics.sharpe_ratio(returns)
        assert isinstance(sharpe, float)
        assert sharpe > 0

    def test_sharpe_ratio_flat(self):
        returns = np.array([0.01, 0.01, 0.01])
        assert CashflowMetrics.sharpe_ratio(returns) == 0.0

    def test_sortino_ratio(self):
        returns = np.array([0.01, 0.02, -0.01, 0.015, -0.005])
        sortino = CashflowMetrics.sortino_ratio(returns)
        assert isinstance(sortino, float)
        assert sortino > 0

    def test_max_drawdown(self):
        equity = np.array([100, 110, 105, 90, 115])
        mdd = CashflowMetrics.max_drawdown(equity)
        # Peak=110, Trough=90 → (90-110)/110 = -20/110 = -0.1818
        assert abs(mdd - (-20 / 110)) < 1e-4

    def test_value_at_risk(self):
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 100)
        var_95 = CashflowMetrics.value_at_risk(returns, confidence=0.95)
        assert var_95 < 0  # VaR 95% is a negative return in left tail

    def test_value_at_risk_small_sample(self):
        assert CashflowMetrics.value_at_risk(np.array([0.01] * 5)) == 0.0

    def test_fundamental_ratios(self):
        assert CashflowMetrics.price_to_earnings(1000, 50) == 20.0
        assert CashflowMetrics.price_to_earnings(1000, -10) is None

        assert CashflowMetrics.price_to_book(5000, 2500) == 2.0
        assert CashflowMetrics.price_to_book(5000, 0) is None

        assert CashflowMetrics.peg_ratio(20.0, 0.15) == pytest.approx(1.3333, abs=1e-3)
        assert CashflowMetrics.peg_ratio(20.0, -0.05) is None

        assert CashflowMetrics.return_on_equity(100, 500) == 0.20
        assert CashflowMetrics.return_on_equity(100, 0) is None

        assert CashflowMetrics.debt_to_equity(400, 500) == 0.80
        assert CashflowMetrics.debt_to_equity(400, 0) is None

        assert CashflowMetrics.dividend_yield(200, 5000) == 0.04
        assert CashflowMetrics.dividend_yield(200, 0) is None

        assert CashflowMetrics.earnings_per_share(100_000_000, 10_000_000) == 10.0
        assert CashflowMetrics.earnings_per_share(100_000_000, 0) == 0.0

    def test_repr(self):
        assert "CashflowMetrics" in repr(CashflowMetrics())


# ---------------------------------------------------------------------------
# Tests: DCFValuation
# ---------------------------------------------------------------------------

class TestDCFValuation:
    def test_present_value(self):
        pv = DCFValuation.present_value(100, rate=0.10, periods=1)
        # 100 / 1.1 = 90.909... → 90.91
        assert pv == Decimal("90.91")

    def test_net_present_value(self):
        # t=0: -100, t=1: 60, t=2: 60, rate=10%
        # -100 + 60/1.1 + 60/1.21 = -100 + 54.545 + 49.586 = 4.13
        npv = DCFValuation.net_present_value([-100, 60, 60], rate=0.10)
        assert isinstance(npv, Decimal)
        assert npv > Decimal("0")

    def test_dcf_intrinsic_value(self):
        fcf = [100, 110, 120]
        val = DCFValuation.dcf_intrinsic_value(
            free_cashflows=fcf,
            terminal_growth_rate=0.03,
            discount_rate=0.10,
            shares_outstanding=10,
        )
        assert isinstance(val, Decimal)
        assert val > Decimal("0")

    def test_repr(self):
        assert "DCFValuation" in repr(DCFValuation())


# ---------------------------------------------------------------------------
# Tests: FundamentalFeatureBuilder
# ---------------------------------------------------------------------------

class TestFundamentalFeatureBuilder:
    def test_build_features(self):
        fund = pd.DataFrame({
            "ticker": ["BBCA.JK", "BBRI.JK"],
            "pe": [20.0, 15.0],
            "pb": [4.0, 2.5],
            "dividend_yield": [0.03, 0.04],
            "roe": [0.20, 0.18],
            "der": [0.8, 1.2],
            "eps": [500, 350],
            "market_cap": [1_000_000_000, 800_000_000],
        })

        fb = FundamentalFeatureBuilder()
        df = fb.build_features(fund)
        assert "ticker" in df.columns
        assert "pe_ratio" in df.columns
        assert "market_cap_log" in df.columns
        assert len(df) == 2

    def test_build_features_empty(self):
        fb = FundamentalFeatureBuilder()
        df = fb.build_features(pd.DataFrame())
        assert df.empty

    def test_compute_fundamental_score(self):
        good = {"pe_ratio": 8.0, "roe": 0.25, "der": 0.4, "dividend_yield": 0.06}
        bad = {"pe_ratio": 50.0, "roe": -0.05, "der": 3.0, "dividend_yield": 0.0}

        good_score = FundamentalFeatureBuilder.compute_fundamental_score(good)
        bad_score = FundamentalFeatureBuilder.compute_fundamental_score(bad)

        assert good_score > bad_score
        assert 0.0 <= good_score <= 100.0
        assert 0.0 <= bad_score <= 100.0

    def test_repr(self):
        assert "FundamentalFeatureBuilder" in repr(FundamentalFeatureBuilder())


# ---------------------------------------------------------------------------
# Tests: Helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_is_trading_day_weekday(self):
        # Monday
        mon = pd.Timestamp("2024-01-15")
        assert is_trading_day(mon) is True

    def test_is_trading_day_weekend(self):
        # Saturday
        sat = pd.Timestamp("2024-01-13")
        assert is_trading_day(sat) is False

    def test_is_trading_day_holiday(self):
        # New Year 2024
        ny = pd.Timestamp("2024-01-01")
        assert is_trading_day(ny) is False

    def test_get_last_trading_day(self):
        # Sunday → Should return Friday
        sun = pd.Timestamp("2024-01-14")
        last = get_last_trading_day(sun)
        assert last.weekday() == 4  # Friday

    def test_format_currency(self):
        formatted = format_currency(1000000)
        assert "Rp1.000.000" in formatted or "1.000.000" in formatted

    def test_format_percentage(self):
        assert format_percentage(12.345, decimals=2) == "12.35%"

    def test_lot_to_shares(self):
        assert lot_to_shares(5) == 500

    def test_shares_to_lot(self):
        assert shares_to_lot(550) == 5


# ---------------------------------------------------------------------------
# Tests: ConfigLoader & Logger
# ---------------------------------------------------------------------------

class TestConfigLoaderAndLogger:
    def test_load_config(self):
        config = load_config()
        assert isinstance(config, dict)
        assert "trading" in config or "data" in config

    def test_setup_logger(self):
        log = setup_logger("test_logger")
        assert log is not None


# ---------------------------------------------------------------------------
# Tests: UIRenderer
# ---------------------------------------------------------------------------

class TestUIRenderer:
    def test_render_table(self, capsys):
        data = [{"ticker": "BBCA.JK", "price": 10000}]
        render_table(data, title="Test Table")

    def test_render_table_empty(self, capsys):
        render_table([])

    def test_render_metrics(self, capsys):
        metrics = {"sharpe": 1.5, "return": 0.20}
        render_metrics(metrics, title="Metrics Test")

    def test_render_portfolio(self, capsys):
        positions = [{"ticker": "BBCA.JK", "lot": 5, "avg_price": 9500, "current_price": 10000, "pnl": 250000, "pnl_pct": 5.26}]
        render_portfolio(positions, total_capital=100_000_000)
