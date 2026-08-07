"""
Tests for app/services/ — DataService, ScannerService, BacktestService,
PortfolioService, BrokerService.
"""
import numpy as np
import pandas as pd
import pytest
from decimal import Decimal

from app.services.data_service import DataService
from app.services.scanner_service import ScannerService
from app.services.backtest_service import BacktestService
from app.services.portfolio_service import PortfolioService
from app.services.broker_service import BrokerService, ExecutionMode


# ---------------------------------------------------------------------------
# DataService Tests
# ---------------------------------------------------------------------------

class TestDataService:
    def test_init_default(self):
        ds = DataService()
        assert ds.storage is not None

    def test_get_available_tickers(self):
        ds = DataService()
        tickers = ds.get_available_tickers()
        assert isinstance(tickers, list)

    def test_get_date_range(self):
        ds = DataService()
        dr = ds.get_date_range()
        assert isinstance(dr, tuple)
        assert len(dr) == 2

    def test_is_db_populated(self):
        ds = DataService()
        result = ds.is_db_populated()
        assert isinstance(result, bool)

    def test_get_db_status(self):
        ds = DataService()
        status = ds.get_db_status()
        assert "db_path" in status
        assert "n_tickers" in status
        assert "is_populated" in status

    def test_get_close_prices(self):
        ds = DataService()
        cp = ds.get_close_prices()
        assert isinstance(cp, pd.DataFrame)

    def test_get_latest_prices(self):
        ds = DataService()
        lp = ds.get_latest_prices()
        assert isinstance(lp, dict)

    def test_repr(self):
        ds = DataService()
        r = repr(ds)
        assert "DataService" in r


# ---------------------------------------------------------------------------
# ScannerService Tests
# ---------------------------------------------------------------------------

class TestScannerService:
    def test_init(self):
        ss = ScannerService()
        assert ss.buy_threshold == 0.50

    def test_scan_momentum(self):
        """Momentum scan should return list (may be empty if DB empty)."""
        ss = ScannerService()
        results = ss.scan_momentum()
        assert isinstance(results, list)

    def test_scan_momentum_with_data(self):
        """Test momentum scan with synthetic data via mock DataService."""
        # Create a minimal DataService-like object
        dates = pd.date_range("2023-01-02", periods=60, freq="B")
        np.random.seed(42)
        close = pd.DataFrame({
            "BBCA.JK": 10000 * np.cumprod(1 + np.random.normal(0.001, 0.015, 60)),
            "BBRI.JK": 5000 * np.cumprod(1 + np.random.normal(0.001, 0.015, 60)),
        }, index=dates)

        ss = ScannerService()
        # Override data_service.get_close_prices
        ss.data_service.get_close_prices = lambda tickers=None: close

        results = ss.scan_momentum()
        assert len(results) == 2
        assert all("ticker" in r for r in results)
        assert all("score" in r for r in results)
        assert all("signal" in r for r in results)
        # Should be sorted by score descending
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_scan_combined_no_ml(self):
        """Combined scan without ML predictions should fallback to momentum."""
        dates = pd.date_range("2023-01-02", periods=60, freq="B")
        np.random.seed(42)
        close = pd.DataFrame({
            "BBCA.JK": 10000 * np.cumprod(1 + np.random.normal(0.001, 0.015, 60)),
        }, index=dates)

        ss = ScannerService()
        ss.data_service.get_close_prices = lambda tickers=None: close

        results = ss.scan_combined(ml_predictions=None)
        assert isinstance(results, list)

    def test_repr(self):
        ss = ScannerService()
        assert "ScannerService" in repr(ss)


# ---------------------------------------------------------------------------
# BacktestService Tests
# ---------------------------------------------------------------------------

class TestBacktestService:
    def test_init(self):
        bs = BacktestService()
        assert bs.initial_capital == 100_000_000

    def test_run_momentum_backtest_with_data(self):
        """Test momentum backtest with synthetic data."""
        dates = pd.date_range("2023-01-02", periods=120, freq="B")
        np.random.seed(42)
        close = pd.DataFrame({
            "BBCA.JK": 10000 * np.cumprod(1 + np.random.normal(0.001, 0.015, 120)),
            "BBRI.JK": 5000 * np.cumprod(1 + np.random.normal(0.001, 0.015, 120)),
        }, index=dates)

        bs = BacktestService()
        bs.data_service.get_close_prices = lambda tickers=None: close

        result = bs.run_momentum_backtest()
        assert "equity_curve" in result
        assert "trades" in result
        assert "metrics" in result
        assert "strategy" in result
        assert result["strategy"] == "momentum"
        assert not result["equity_curve"].empty

    def test_run_ml_backtest_with_data(self):
        """Test ML backtest with synthetic data and predictions."""
        dates = pd.date_range("2023-01-02", periods=120, freq="B")
        np.random.seed(42)
        close = pd.DataFrame({
            "BBCA.JK": 10000 * np.cumprod(1 + np.random.normal(0.001, 0.015, 120)),
        }, index=dates)

        np.random.seed(99)
        preds = pd.DataFrame({
            "BBCA.JK": np.random.uniform(0.3, 0.8, size=120),
        }, index=dates)

        bs = BacktestService()
        bs.data_service.get_close_prices = lambda tickers=None: close

        result = bs.run_ml_backtest(ml_predictions=preds)
        assert result["strategy"] == "ml_signal"
        assert "equity_curve" in result

    def test_repr(self):
        bs = BacktestService()
        assert "BacktestService" in repr(bs)


# ---------------------------------------------------------------------------
# PortfolioService Tests
# ---------------------------------------------------------------------------

class TestPortfolioService:
    def test_init(self):
        ps = PortfolioService(initial_capital=200_000_000)
        assert ps.initial_capital == Decimal("200000000")

    def test_execute_buy(self):
        ps = PortfolioService(initial_capital=200_000_000)
        result = ps.execute_order(
            ticker="BBCA.JK",
            side="BUY",
            lots=5,
            current_price=10000,
        )
        assert result["success"] is True
        assert "BBCA.JK" in ps.position_manager.positions
        assert ps.position_manager.positions["BBCA.JK"].quantity_shares == 500

    def test_execute_sell(self):
        ps = PortfolioService(initial_capital=200_000_000)
        # First buy
        ps.execute_order("BBCA.JK", "BUY", 5, 10000)
        # Then sell
        result = ps.execute_order("BBCA.JK", "SELL", 5, 10500)
        assert result["success"] is True
        assert "BBCA.JK" not in ps.position_manager.positions

    def test_execute_buy_insufficient_cash(self):
        ps = PortfolioService(initial_capital=100_000)
        result = ps.execute_order("BBCA.JK", "BUY", 100, 10000)
        assert result["success"] is False
        assert "Cash" in result["message"] or "cash" in result["message"].lower()

    def test_execute_sell_no_position(self):
        ps = PortfolioService()
        result = ps.execute_order("BBCA.JK", "SELL", 1, 10000)
        assert result["success"] is False

    def test_execute_invalid_side(self):
        ps = PortfolioService()
        result = ps.execute_order("BBCA.JK", "INVALID", 1, 10000)
        assert result["success"] is False

    def test_lot_constraint(self):
        """Shares should always be lots * 100."""
        ps = PortfolioService(initial_capital=200_000_000)
        ps.execute_order("BBCA.JK", "BUY", 3, 10000)
        pos = ps.position_manager.positions["BBCA.JK"]
        assert pos.quantity_shares == 300
        assert pos.quantity_shares % 100 == 0

    def test_get_portfolio_summary(self):
        ps = PortfolioService(initial_capital=200_000_000)
        ps.execute_order("BBCA.JK", "BUY", 5, 10000)

        summary = ps.get_portfolio_summary({"BBCA.JK": 10500})
        assert "total_value" in summary
        assert "positions" in summary
        assert len(summary["positions"]) == 1
        assert summary["positions"][0]["ticker"] == "BBCA.JK"
        assert summary["positions"][0]["shares"] == 500

    def test_transaction_history(self):
        ps = PortfolioService(initial_capital=200_000_000)
        ps.execute_order("BBCA.JK", "BUY", 5, 10000)
        ps.execute_order("BBRI.JK", "BUY", 10, 5000)

        history = ps.get_transaction_history()
        assert len(history) == 2

    def test_repr(self):
        ps = PortfolioService()
        assert "PortfolioService" in repr(ps)


# ---------------------------------------------------------------------------
# BrokerService Tests
# ---------------------------------------------------------------------------

class TestBrokerService:
    def test_init_paper_mode(self):
        bs = BrokerService()
        assert bs.mode == ExecutionMode.PAPER
        assert bs.is_paper_mode()

    def test_connect(self):
        bs = BrokerService()
        result = bs.connect("Stockbit", api_key="test_key_123")
        assert result["success"] is True
        assert bs.accounts["Stockbit"].status == "CONNECTED"

    def test_connect_unknown_broker(self):
        bs = BrokerService()
        result = bs.connect("UnknownBroker", api_key="key")
        assert result["success"] is False

    def test_connect_empty_key(self):
        bs = BrokerService()
        result = bs.connect("Stockbit", api_key="")
        assert result["success"] is False

    def test_disconnect(self):
        bs = BrokerService()
        bs.connect("Ajaib", api_key="test_key")
        result = bs.disconnect("Ajaib")
        assert result["success"] is True
        assert bs.accounts["Ajaib"].status == "DISCONNECTED"

    def test_toggle_mode(self):
        bs = BrokerService()
        assert bs.mode == ExecutionMode.PAPER
        new_mode = bs.toggle_mode()
        assert new_mode == ExecutionMode.SANDBOX
        new_mode = bs.toggle_mode()
        assert new_mode == ExecutionMode.LIVE
        new_mode = bs.toggle_mode()
        assert new_mode == ExecutionMode.PAPER

    def test_get_status(self):
        bs = BrokerService()
        bs.connect("Stockbit", api_key="key")
        status = bs.get_status()
        assert status["mode"] == "PAPER"
        assert "Stockbit" in status["accounts"]
        assert status["active_connections"] == 1

    def test_get_active_broker(self):
        bs = BrokerService()
        assert bs.get_active_broker() is None
        bs.connect("Nanovest", api_key="key")
        assert bs.get_active_broker() == "Nanovest"

    def test_clear_credentials(self):
        bs = BrokerService()
        bs.connect("Stockbit", api_key="key1")
        bs.connect("Ajaib", api_key="key2")
        result = bs.clear_credentials()
        assert result["success"] is True
        assert all(a.status == "DISCONNECTED" for a in bs.accounts.values())

    def test_connection_log(self):
        bs = BrokerService()
        bs.connect("Stockbit", api_key="key")
        log = bs.get_connection_log()
        assert len(log) >= 2  # init + connect

    def test_repr(self):
        bs = BrokerService()
        assert "BrokerService" in repr(bs)
        assert "PAPER" in repr(bs)
