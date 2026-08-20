"""
Folium Signal Bus — Centralized Qt Signal Relay for inter-widget communication.

All background workers emit signals through this singleton bus.
UI widgets connect to these signals to update state without direct coupling.

Usage:
    from frontend.gui.workers.signal_bus import SignalBus

    bus = SignalBus.instance()
    bus.scanner_updated.connect(my_table.refresh)
    bus.backtest_progress.emit(42)
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from PyQt6.QtCore import QObject, pyqtSignal


class SignalBus(QObject):
    """Global event bus for Folium Quant Desk GUI.

    Singleton — access via ``SignalBus.instance()``.
    """

    # ── Market Data ──────────────────────────────────────────────
    prices_updated = pyqtSignal(dict)        # {ticker: {open, high, low, close, volume}}
    tickers_loaded = pyqtSignal(list)        # [ticker, ...]

    # ── Scanner ──────────────────────────────────────────────────
    scanner_started = pyqtSignal()
    scanner_updated = pyqtSignal(list)       # [signal_dict, ...]
    scanner_error = pyqtSignal(str)

    # ── Backtest ─────────────────────────────────────────────────
    backtest_started = pyqtSignal(str)       # strategy_name
    backtest_progress = pyqtSignal(int)      # 0-100
    backtest_completed = pyqtSignal(dict)    # result dict {metrics, trades, equity_curve}
    backtest_error = pyqtSignal(str)

    # ── ML Training ──────────────────────────────────────────────
    training_started = pyqtSignal(str)       # model_type
    training_progress = pyqtSignal(int, str) # (pct, status_msg)
    training_completed = pyqtSignal(dict)    # {model_type, version, metrics}
    training_error = pyqtSignal(str)

    # ── Model Registry ───────────────────────────────────────────
    registry_updated = pyqtSignal()          # fire after promote/archive/delete

    # ── Portfolio & Execution ────────────────────────────────────
    order_executed = pyqtSignal(dict)        # trade result dict
    portfolio_updated = pyqtSignal(dict)     # {capital, positions, equity}
    risk_alert = pyqtSignal(str, str)        # (alert_type, message)

    # ── Data Fetch ───────────────────────────────────────────────
    fetch_started = pyqtSignal(str)          # description
    fetch_progress = pyqtSignal(int)         # 0-100
    fetch_completed = pyqtSignal(int)        # rows fetched
    fetch_error = pyqtSignal(str)

    # ── Profile ──────────────────────────────────────────────────
    profile_updated = pyqtSignal()           # after save/edit

    # ── Status Bar ───────────────────────────────────────────────
    status_message = pyqtSignal(str, int)    # (message, timeout_ms)

    # ── Singleton ────────────────────────────────────────────────
    _instance = None

    @classmethod
    def instance(cls):
        """Return the global SignalBus singleton."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
