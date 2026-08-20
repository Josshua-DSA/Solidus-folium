"""
Tests for TUI App — Frontend TUI application initialization & backtest integration.
"""
from frontend.cli.app import TUIApp


def test_tui_app_init():
    app = TUIApp()
    assert app.active_screen == "dashboard"
    assert app.capital > 0
    assert hasattr(app, "portfolio")
    assert hasattr(app, "scanner_signals")


def test_tui_app_backtest_service_binding():
    from app.services.backtest_service import BacktestService
    assert BacktestService is not None

    bt_service = BacktestService()
    res = bt_service.run_momentum_backtest(tickers=["BBCA.JK"])
    assert "metrics" in res
    assert "total_return" in res["metrics"]
    assert "sharpe_ratio" in res["metrics"]
