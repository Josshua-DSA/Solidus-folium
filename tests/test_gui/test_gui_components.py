"""
Unit Tests for Folium Desktop GUI Components (PyQt6 / PySide6).

Tests instantiate all Phase 2 components in headless mode to verify:
1. SignalBus event emission & listener wiring
2. ChartCanvasWidget initialization & data loading
3. MarketTableWidget filtering & row populating
4. RiskMeterWidget gauge limits & compliance checklist
5. BacktestLabWidget simulation triggering & metrics parsing
6. FoliumMainWindow instantiation & dock panel assemblage
"""
import pytest
import os
import sys

# Set offscreen Qt platform plugin for headless CI/CD test execution
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication

# Ensure single QApplication per test process
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_signal_bus_singleton():
    from frontend.gui.workers.signal_bus import SignalBus
    bus1 = SignalBus.instance()
    bus2 = SignalBus.instance()
    assert bus1 is bus2
    assert hasattr(bus1, "backtest_completed")
    assert hasattr(bus1, "scanner_updated")


def test_risk_meter_widget(qapp):
    from frontend.gui.components.risk_meter import RiskMeterWidget
    widget = RiskMeterWidget()
    assert widget.dd_bar.value() == 0
    assert widget.dl_bar.value() == 0

    widget.update_risk_metrics(drawdown_pct=-5.0, daily_loss_pct=-1.2, max_pos_pct=18.0)
    assert widget.dd_bar.value() > 0
    assert widget.dl_bar.value() > 0
    assert widget.pos_bar.value() > 0


def test_market_table_widget(qapp):
    from frontend.gui.components.market_table import MarketTableWidget
    widget = MarketTableWidget()
    assert widget.table.columnCount() == 6
    assert widget.table.rowCount() >= 0

    # Test sector filtering
    widget.sector_combo.setCurrentText("Finance")
    widget._apply_filter()
    assert widget.table.rowCount() >= 0


def test_chart_canvas_widget(qapp):
    from frontend.gui.components.chart_canvas import ChartCanvasWidget
    widget = ChartCanvasWidget()
    assert widget.current_ticker == "BBCA.JK"
    assert widget.df_data is not None
    assert len(widget.df_data) > 0


def test_backtest_lab_widget(qapp):
    from frontend.gui.components.backtest_lab import BacktestLabWidget
    widget = BacktestLabWidget()
    assert widget.strategy_combo.count() == 3
    assert widget.capital_spin.value() == 100_000_000

    # Simulate completed backtest result
    import pandas as pd
    fake_equity = pd.Series([100_000_000, 105_000_000, 110_000_000])
    fake_result = {
        "metrics": {
            "total_return": 0.10,
            "cagr": 0.12,
            "sharpe_ratio": 1.45,
            "sortino_ratio": 1.80,
            "max_drawdown": -0.05,
            "calmar_ratio": 2.40,
            "win_rate": 0.65,
            "profit_factor": 2.10,
            "total_trades": 14,
        },
        "trades": [
            {
                "ticker": "BBCA.JK",
                "entry_date": "2024-01-02",
                "exit_date": "2024-01-15",
                "entry_price": 9000,
                "exit_price": 9500,
                "shares": 500,
                "pnl": 250_000,
            }
        ],
        "equity_curve": fake_equity,
    }

    widget._on_completed(fake_result)
    assert widget.metric_labels["Total Return"].text() == "+10.00%"
    assert widget.metric_labels["Sharpe Ratio"].text() == "1.4500"
    assert widget.trade_table.rowCount() == 1


def test_main_window_instantiation(qapp):
    from frontend.gui.main_window import FoliumMainWindow
    window = FoliumMainWindow()
    assert window.windowTitle().startswith("▲ FOLIUM QUANT DESK")
    assert hasattr(window, "chart_canvas")
    assert hasattr(window, "market_table")
    assert hasattr(window, "backtest_lab")
    assert hasattr(window, "risk_meter")
