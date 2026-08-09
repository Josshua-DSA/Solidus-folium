"""
Tests for app/execution/drift_monitor.py and PaperExecutor drift integration.
"""
import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta

from app.execution.drift_monitor import DriftMonitor, DriftEvent
from app.execution.paper_executor import PaperExecutor


# ===========================================================================
# DriftMonitor Unit Tests
# ===========================================================================

class TestDriftEvent:
    def test_dataclass_creation(self):
        """DriftEvent harus bisa dibuat dengan semua field."""
        event = DriftEvent(
            timestamp=datetime(2026, 1, 1),
            event_type="DRAWDOWN_BREACH",
            severity="WARNING",
            equity=90_000_000,
            metric_value=-0.10,
            threshold=-0.15,
            message="Test event",
        )
        assert event.event_type == "DRAWDOWN_BREACH"
        assert event.severity == "WARNING"
        assert event.equity == 90_000_000


class TestDriftMonitor:
    def test_init_defaults(self):
        """DriftMonitor harus init dengan defaults dari config."""
        dm = DriftMonitor()
        assert dm.max_drawdown_stop == -0.15
        assert dm.daily_loss_limit == -0.03
        assert dm.max_position_pct == 0.10
        assert dm.total_events == 0
        assert len(dm._equity_points) == 0

    def test_init_custom_params(self):
        """DriftMonitor harus accept custom risk limits."""
        dm = DriftMonitor(
            max_drawdown_stop=-0.20,
            daily_loss_limit=-0.05,
            max_position_pct=0.15,
        )
        assert dm.max_drawdown_stop == -0.20
        assert dm.daily_loss_limit == -0.05
        assert dm.max_position_pct == 0.15

    def test_update_no_breach(self):
        """Update tanpa breach harus return empty list."""
        dm = DriftMonitor()
        ts = pd.Timestamp("2026-01-01 09:00:00")

        events = dm.update(100_000_000, ts)
        assert events == []
        assert dm.total_events == 0
        assert len(dm._equity_points) == 1

    def test_update_tracks_equity(self):
        """Equity points harus dilacak setelah update."""
        dm = DriftMonitor()
        base = pd.Timestamp("2026-01-01 09:00:00")

        dm.update(100_000_000, base)
        dm.update(101_000_000, base + pd.Timedelta(hours=1))
        dm.update(102_000_000, base + pd.Timedelta(hours=2))

        assert len(dm._equity_points) == 3
        assert dm._peak_equity == 102_000_000

    def test_drawdown_breach_detected(self):
        """Drawdown breach harus ter-detect ketika melebihi limit."""
        dm = DriftMonitor(max_drawdown_stop=-0.10, daily_loss_limit=-0.50)  # relax daily
        base = pd.Timestamp("2026-01-01 09:00:00")

        # Equity naik ke 100M lalu turun 12% -> breach
        dm.update(100_000_000, base)
        events = dm.update(88_000_000, base + pd.Timedelta(hours=2))

        dd_events = [e for e in events if e.event_type == "DRAWDOWN_BREACH"]
        assert len(dd_events) == 1
        assert dd_events[0].severity in ("WARNING", "CRITICAL")
        assert dd_events[0].metric_value < -0.10
        assert dm.total_events >= 1

    def test_drawdown_no_false_positive(self):
        """Drawdown -5% tidak boleh trigger drawdown breach -15%."""
        dm = DriftMonitor(max_drawdown_stop=-0.15, daily_loss_limit=-0.50)  # relax daily
        base = pd.Timestamp("2026-01-01 09:00:00")

        dm.update(100_000_000, base)
        events = dm.update(95_000_000, base + pd.Timedelta(hours=1))

        dd_events = [e for e in events if e.event_type == "DRAWDOWN_BREACH"]
        assert dd_events == []
        assert dm.current_drawdown == pytest.approx(-0.05)

    def test_daily_loss_breach_detected(self):
        """Daily loss breach harus ter-detect pada hari yang sama."""
        dm = DriftMonitor(daily_loss_limit=-0.02)  # 2% limit
        base = pd.Timestamp("2026-01-15 09:00:00")

        # Day open di 100M
        dm.update(100_000_000, base)
        # Turun 3% pada hari yang sama
        events = dm.update(97_000_000, base + pd.Timedelta(hours=3))

        assert len(events) == 1
        assert events[0].event_type == "DAILY_LOSS_BREACH"
        assert events[0].metric_value < -0.02

    def test_daily_loss_cross_day_no_breach(self):
        """Daily loss harus di-reset tiap hari baru."""
        dm = DriftMonitor(daily_loss_limit=-0.05)
        day1 = pd.Timestamp("2026-01-15 09:00:00")
        day2 = pd.Timestamp("2026-01-16 09:00:00")

        dm.update(100_000_000, day1)
        dm.update(96_000_000, day1 + pd.Timedelta(hours=3))  # -4% hari 1 (OK)

        # Hari baru, equity 96M jadi baseline baru
        events = dm.update(95_000_000, day2)  # -1% dari 96M (OK)
        assert events == []

    def test_concentration_breach_detected(self):
        """Position concentration harus ter-detect."""
        dm = DriftMonitor(max_position_pct=0.10)
        base = pd.Timestamp("2026-01-01 09:00:00")

        dm.update(100_000_000, base)
        events = dm.update(
            100_000_000,
            base + pd.Timedelta(hours=1),
            positions_weights={"BBCA.JK": 0.25, "BBRI.JK": 0.08},
        )

        # BBCA.JK melebihi 10%
        assert len(events) == 1
        assert events[0].event_type == "POSITION_CONCENTRATION"
        assert events[0].metric_value == 0.25

    def test_multiple_events_single_update(self):
        """Bisa ada multiple events dalam satu update."""
        dm = DriftMonitor(
            max_drawdown_stop=-0.05,
            daily_loss_limit=-0.02,
            max_position_pct=0.10,
        )
        base = pd.Timestamp("2026-01-01 09:00:00")

        dm.update(100_000_000, base)
        events = dm.update(
            90_000_000,  # -10% drawdown + -10% daily loss
            base + pd.Timedelta(hours=2),
            positions_weights={"BBCA.JK": 0.50},  # 50% concentration
        )

        event_types = {e.event_type for e in events}
        assert "DRAWDOWN_BREACH" in event_types
        assert "DAILY_LOSS_BREACH" in event_types
        assert "POSITION_CONCENTRATION" in event_types

    def test_recent_events(self):
        """recent_events harus return N event terbaru."""
        dm = DriftMonitor(max_drawdown_stop=-0.01)
        base = pd.Timestamp("2026-01-01 09:00:00")

        dm.update(100_000_000, base)
        for i in range(5):
            dm.update(
                100_000_000 - (i + 1) * 2_000_000,
                base + pd.Timedelta(hours=i + 1),
            )

        recent = dm.recent_events(3)
        assert len(recent) <= 3
        # Events harus terurut secara kronologis
        for j in range(len(recent) - 1):
            assert recent[j].timestamp <= recent[j + 1].timestamp

    def test_events_by_type(self):
        """Filter events by type harus bekerja."""
        dm = DriftMonitor(max_drawdown_stop=-0.05, max_position_pct=0.10)
        base = pd.Timestamp("2026-01-01 09:00:00")

        dm.update(100_000_000, base)
        dm.update(
            90_000_000,
            base + pd.Timedelta(hours=1),
            positions_weights={"BBCA.JK": 0.30},
        )

        dd_events = dm.events_by_type("DRAWDOWN_BREACH")
        conc_events = dm.events_by_type("POSITION_CONCENTRATION")
        assert len(dd_events) >= 1
        assert len(conc_events) >= 1

    def test_critical_events(self):
        """Critical events harus ter-filter."""
        dm = DriftMonitor(max_drawdown_stop=-0.05)
        base = pd.Timestamp("2026-01-01 09:00:00")

        dm.update(100_000_000, base)
        # -25% drawdown -> CRITICAL (> 1.5x threshold)
        dm.update(75_000_000, base + pd.Timedelta(hours=1))

        critical = dm.critical_events()
        assert len(critical) >= 1
        assert all(e.severity == "CRITICAL" for e in critical)

    def test_equity_series_property(self):
        """equity_series harus return pd.Series yang valid."""
        dm = DriftMonitor()
        base = pd.Timestamp("2026-01-01 09:00:00")

        dm.update(100_000_000, base)
        dm.update(101_000_000, base + pd.Timedelta(hours=1))
        dm.update(99_000_000, base + pd.Timedelta(hours=2))

        series = dm.equity_series
        assert isinstance(series, pd.Series)
        assert len(series) == 3
        assert series.name == "equity"
        assert isinstance(series.index, pd.DatetimeIndex)

    def test_equity_series_empty(self):
        """equity_series harus return Series kosong jika belum ada data."""
        dm = DriftMonitor()
        series = dm.equity_series
        assert isinstance(series, pd.Series)
        assert len(series) == 0

    def test_current_drawdown(self):
        """current_drawdown harus menghitung drawdown dari peak."""
        dm = DriftMonitor()
        base = pd.Timestamp("2026-01-01 09:00:00")

        dm.update(100_000_000, base)
        dm.update(110_000_000, base + pd.Timedelta(hours=1))  # new peak
        dm.update(99_000_000, base + pd.Timedelta(hours=2))   # drawdown

        # DD dari peak 110M -> 99M = -10%
        assert dm.current_drawdown == pytest.approx(-0.10, abs=0.001)

    def test_get_summary(self):
        """get_summary harus return dict dengan semua field."""
        dm = DriftMonitor()
        base = pd.Timestamp("2026-01-01 09:00:00")

        dm.update(100_000_000, base)
        summary = dm.get_summary()

        required_keys = {
            "total_events", "critical_count", "drawdown_breaches",
            "daily_loss_breaches", "concentration_warnings",
            "current_drawdown", "peak_equity", "latest_equity",
            "n_equity_points",
        }
        assert required_keys.issubset(summary.keys())
        assert summary["n_equity_points"] == 1
        assert summary["peak_equity"] == 100_000_000

    def test_repr(self):
        """Repr harus informatif."""
        dm = DriftMonitor()
        r = repr(dm)
        assert "DriftMonitor" in r
        assert "events=" in r


# ===========================================================================
# PaperExecutor Drift Integration Tests
# ===========================================================================

class TestPaperExecutorDrift:
    def test_executor_has_drift_monitor(self):
        """PaperExecutor harus memiliki DriftMonitor yang aktif."""
        executor = PaperExecutor(initial_capital=100_000_000)
        assert hasattr(executor, "drift_monitor")
        assert isinstance(executor.drift_monitor, DriftMonitor)
        # Initial equity point harus sudah ada
        assert len(executor.drift_monitor._equity_points) == 1

    def test_trade_updates_drift_monitor(self):
        """Setiap trade harus menambah equity point di drift monitor."""
        executor = PaperExecutor(initial_capital=100_000_000)

        executor.execute_signal(
            ticker="BBCA.JK",
            signal="BUY",
            price=9000.0,
            quantity_shares=100,
            timestamp=pd.Timestamp("2026-01-15 09:30:00"),
        )

        # 1 initial + 1 post-trade = 2 equity points
        assert len(executor.drift_monitor._equity_points) == 2

    def test_buy_sell_cycle_drift_tracking(self):
        """BUY dan SELL harus dilacak oleh drift monitor."""
        executor = PaperExecutor(initial_capital=100_000_000)
        ts1 = pd.Timestamp("2026-01-15 09:30:00")
        ts2 = pd.Timestamp("2026-01-15 14:00:00")

        executor.execute_signal("BBCA.JK", "BUY", 9000.0, 100, ts1)
        executor.execute_signal("BBCA.JK", "SELL", 9200.0, 100, ts2)

        # 1 initial + 1 buy + 1 sell = 3 equity points
        assert len(executor.drift_monitor._equity_points) == 3

    def test_drawdown_breach_via_executor(self):
        """Drift events harus muncul ketika trades menyebabkan drawdown."""
        executor = PaperExecutor(
            initial_capital=100_000_000,
            max_drawdown_stop=-0.02,  # 2% stop (tight for testing)
        )
        ts = pd.Timestamp("2026-01-15 09:30:00")

        # BUY 5000 shares @ 5000 = 25M + costs -> fits in 100M
        executor.execute_signal("BBCA.JK", "BUY", 5000.0, 5000, ts)

        # Jual rugi besar @ 3000 -> loss ~10M -> significant drawdown
        executor.execute_signal(
            "BBCA.JK", "SELL", 3000.0, 5000,
            ts + pd.Timedelta(hours=1),
        )

        events = executor.get_drift_events()
        # Harus ada minimal 1 drift event (drawdown or daily loss)
        assert len(events) >= 1

    def test_get_drift_events(self):
        """get_drift_events harus return list DriftEvent."""
        executor = PaperExecutor(initial_capital=100_000_000)
        events = executor.get_drift_events()
        assert isinstance(events, list)

    def test_get_drift_summary(self):
        """get_drift_summary harus return dict status."""
        executor = PaperExecutor(initial_capital=100_000_000)
        summary = executor.get_drift_summary()
        assert isinstance(summary, dict)
        assert "total_events" in summary
        assert "current_drawdown" in summary

    def test_portfolio_status_includes_drift(self):
        """get_portfolio_status harus include drift_summary."""
        executor = PaperExecutor(initial_capital=100_000_000)
        status = executor.get_portfolio_status(current_prices={})
        assert "drift_summary" in status
        assert isinstance(status["drift_summary"], dict)

    def test_repr_includes_drift(self):
        """Repr harus mencantumkan drift_events."""
        executor = PaperExecutor(initial_capital=100_000_000)
        r = repr(executor)
        assert "drift_events=" in r
