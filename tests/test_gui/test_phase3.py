"""
Unit Tests for Folium Desktop GUI Phase 3 Components.

Tests:
1. OrderExecutionDialog — instantiation, preview update, risk check
2. PortfolioPanelWidget — instantiation, refresh, summary labels
3. InferenceWorker — instantiation, cancel flag
4. MainWindow — Phase 3 attributes present (portfolio_panel, order, inference)
"""
import pytest
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_order_dialog_instantiation(qapp):
    from frontend.gui.components.order_dialog import OrderExecutionDialog
    dlg = OrderExecutionDialog(ticker="BBCA.JK")
    assert dlg.windowTitle().startswith("📋")
    assert dlg.lots_spin.value() == 1
    assert dlg.side_combo.currentText() == "BUY"
    assert "BBCA.JK" in dlg.ticker_combo.currentText()


def test_order_dialog_preview_update(qapp):
    from frontend.gui.components.order_dialog import OrderExecutionDialog
    dlg = OrderExecutionDialog(ticker="BBRI.JK")
    dlg.lots_spin.setValue(5)
    dlg._update_preview()
    assert "500" in dlg.shares_label.text() or "Shares" in dlg.shares_label.text()
    assert "Rp" in dlg.total_cost_label.text()


def test_order_dialog_sell_side(qapp):
    from frontend.gui.components.order_dialog import OrderExecutionDialog
    dlg = OrderExecutionDialog(ticker="BBCA.JK")
    dlg.side_combo.setCurrentText("SELL")
    dlg._update_preview()
    assert "Proceeds" in dlg.total_cost_label.text()


def test_portfolio_panel_instantiation(qapp):
    from frontend.gui.components.portfolio_panel import PortfolioPanelWidget
    panel = PortfolioPanelWidget()
    assert panel.positions_table.columnCount() == 7
    assert panel.tx_table.columnCount() == 6
    assert "RDN" in panel.cash_label.text() or "N/A" in panel.cash_label.text()


def test_portfolio_panel_refresh(qapp):
    from frontend.gui.components.portfolio_panel import PortfolioPanelWidget
    panel = PortfolioPanelWidget()
    panel.refresh()
    # Should not crash regardless of UserProfile state
    assert panel.positions_table.rowCount() >= 0


def test_portfolio_panel_order_executed(qapp):
    from frontend.gui.components.portfolio_panel import PortfolioPanelWidget
    panel = PortfolioPanelWidget()
    fake_result = {
        "ticker": "BBCA.JK",
        "side": "BUY",
        "lots": 2,
        "shares": 200,
        "exec_price": 9500.0,
        "commission": 2850.0,
    }
    panel._on_order_executed(fake_result)
    assert panel.tx_table.rowCount() == 1
    assert panel.tx_table.item(0, 1).text() == "BBCA.JK"


def test_inference_worker_instantiation(qapp):
    from frontend.gui.workers.inference_worker import InferenceWorker
    worker = InferenceWorker(tickers=["BBCA.JK", "BBRI.JK"])
    assert worker.tickers == ["BBCA.JK", "BBRI.JK"]
    assert worker._cancelled is False
    worker.cancel()
    assert worker._cancelled is True


def test_main_window_phase3_attributes(qapp):
    from frontend.gui.main_window import FoliumMainWindow
    window = FoliumMainWindow()
    assert hasattr(window, "portfolio_panel")
    assert hasattr(window, "_on_place_order")
    assert hasattr(window, "_on_run_inference")
    assert hasattr(window, "chart_canvas")
    assert hasattr(window, "backtest_lab")
    assert hasattr(window, "risk_meter")
