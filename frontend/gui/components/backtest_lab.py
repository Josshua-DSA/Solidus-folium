"""
Folium Backtest Lab Widget — Visual Strategy Simulator & Equity Visualizer.

Features:
- Strategy Configurator (Momentum, XGBoost ML Signal, Ensemble Dynamic)
- Initial Capital & Universe selector
- Interactive Equity Curve Chart (PyQtGraph) with drawdown shading
- Key Performance Metrics Dashboard (Sharpe, Sortino, Win Rate, CAGR, Max DD)
- Individual Trade Log Table with Profit/Loss color coding
- Run backtest asynchronously on QThread worker
"""
import sys
import os
from typing import Optional, Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QPushButton, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QGridLayout,
    QSplitter, QTabWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from frontend.gui.workers.signal_bus import SignalBus
from frontend.gui.workers.async_workers import BacktestWorker

# Nord Theme Colors
BG_COLOR      = "#2E3440"
GRID_COLOR    = "#434C5E"
TEXT_COLOR    = "#D8DEE9"
EQUITY_CURVE  = "#88C0D0"   # Frost Cyan
BENCHMARK_COL = "#4C566A"   # Polar Night
AURORA_GREEN  = "#A3BE8C"
AURORA_RED    = "#BF616A"
AURORA_YELLOW = "#EBCB8B"


class BacktestLabWidget(QWidget):
    """Interactive Backtest Lab & Performance Visualizer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bus = SignalBus.instance()
        self._worker = None

        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(6)

        # ── Strategy Configurator Bar ────────────────────────────
        config_group = QGroupBox("🧪 Simulation Configuration")
        cfg_layout = QHBoxLayout(config_group)
        cfg_layout.setContentsMargins(6, 6, 6, 6)

        cfg_layout.addWidget(QLabel("Strategy:"))
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems([
            "Momentum Alpha (Fast/Slow MA)",
            "XGBoost ML Signal (Supervised)",
            "Ensemble Dynamic (XGB+LGBM+LSTM)"
        ])
        cfg_layout.addWidget(self.strategy_combo)

        cfg_layout.addWidget(QLabel("Capital:"))
        self.capital_spin = QSpinBox()
        self.capital_spin.setRange(10_000_000, 2_000_000_000)
        self.capital_spin.setValue(100_000_000)
        self.capital_spin.setSingleStep(10_000_000)
        self.capital_spin.setPrefix("Rp ")
        cfg_layout.addWidget(self.capital_spin)

        self.run_btn = QPushButton("▶ Run Simulation")
        self.run_btn.setObjectName("primaryButton")
        self.run_btn.clicked.connect(self._on_run_clicked)
        cfg_layout.addWidget(self.run_btn)

        main_layout.addWidget(config_group)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # ── Splitter: Equity Curve (Top) + Results Tabs (Bottom) ─
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 1. Equity Curve Plot (PyQtGraph)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(BG_COLOR)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('left', 'Portfolio Value (Rp)')
        self.plot_widget.setLabel('bottom', 'Trading Days')
        self.plot_widget.getAxis('left').setTextPen(pg.mkPen(TEXT_COLOR))
        self.plot_widget.getAxis('bottom').setTextPen(pg.mkPen(TEXT_COLOR))
        self.plot_widget.getAxis('left').setPen(pg.mkPen(GRID_COLOR))
        self.plot_widget.getAxis('bottom').setPen(pg.mkPen(GRID_COLOR))

        self.equity_curve = self.plot_widget.plot(
            pen=pg.mkPen(EQUITY_CURVE, width=2.0),
            name="Strategy Equity"
        )
        splitter.addWidget(self.plot_widget)

        # 2. Bottom Tab Widget (Metrics & Trade Logs)
        self.tabs = QTabWidget()

        # Tab A: Summary Metrics Grid
        self.metrics_tab = QWidget()
        m_layout = QGridLayout(self.metrics_tab)
        self.metric_labels = {}

        metrics_def = [
            ("Total Return", "0.0%"),
            ("CAGR", "0.0%"),
            ("Sharpe Ratio", "0.00"),
            ("Sortino Ratio", "0.00"),
            ("Max Drawdown", "0.0%"),
            ("Calmar Ratio", "0.00"),
            ("Win Rate", "0.0%"),
            ("Profit Factor", "0.00"),
            ("Total Trades", "0"),
        ]

        for i, (name, default_val) in enumerate(metrics_def):
            row = i // 3
            col = (i % 3) * 2
            lbl = QLabel(f"{name}:")
            lbl.setStyleSheet(f"color: {TEXT_COLOR}; font-weight: bold;")
            val_lbl = QLabel(default_val)
            val_lbl.setStyleSheet(f"color: {AURORA_GREEN}; font-size: 14px; font-weight: bold;")
            m_layout.addWidget(lbl, row, col)
            m_layout.addWidget(val_lbl, row, col + 1)
            self.metric_labels[name] = val_lbl

        self.tabs.addTab(self.metrics_tab, "📊 Performance Diagnostics")

        # Tab B: Trade Ledger Table
        self.trade_table = QTableWidget()
        self.trade_table.setColumnCount(7)
        self.trade_table.setHorizontalHeaderLabels([
            "Ticker", "Entry Date", "Exit Date", "Entry (Rp)", "Exit (Rp)", "Shares", "P&L (Rp)"
        ])
        self.trade_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.trade_table.setAlternatingRowColors(True)
        self.tabs.addTab(self.trade_table, "📋 Closed Trades Log")

        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter)

    def _connect_signals(self):
        bus = self.bus
        bus.backtest_progress.connect(self._on_progress)
        bus.backtest_completed.connect(self._on_completed)
        bus.backtest_error.connect(self._on_error)

    def _on_run_clicked(self):
        self.run_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(5)

        strat_idx = self.strategy_combo.currentIndex()
        strat_map = {0: "momentum", 1: "ml_signal", 2: "ensemble"}
        strategy = strat_map.get(strat_idx, "momentum")
        capital = float(self.capital_spin.value())

        # Load available tickers from storage
        try:
            from pipeline.storage import StorageManager
            tickers = StorageManager().get_available_tickers()[:10]
            if not tickers:
                from pipeline.universe import UniverseManager
                tickers = UniverseManager(universe_name="lq45").get_tickers()[:10]
        except Exception:
            tickers = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "TLKM.JK", "ASII.JK"]

        self._worker = BacktestWorker(
            strategy=strategy,
            tickers=tickers,
            initial_capital=capital,
        )
        self._worker.start()

    def _on_progress(self, pct: int):
        self.progress_bar.setValue(pct)

    def _on_completed(self, result: Dict[str, Any]):
        self.run_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        metrics = result.get("metrics", {})
        trades = result.get("trades", [])
        equity_series = result.get("equity_curve")

        # 1. Update Equity Curve Chart
        if equity_series is not None and len(equity_series) > 0:
            y_vals = equity_series.values
            x_vals = np.arange(len(y_vals))
            self.equity_curve.setData(x_vals, y_vals)
            self.plot_widget.autoRange()

        # 2. Update Metrics Labels
        ret = metrics.get("total_return", 0.0)
        cagr = metrics.get("cagr", 0.0)
        sharpe = metrics.get("sharpe_ratio", 0.0)
        sortino = metrics.get("sortino_ratio", 0.0)
        max_dd = metrics.get("max_drawdown", 0.0)
        calmar = metrics.get("calmar_ratio", 0.0)
        win_rate = metrics.get("win_rate", 0.0)
        pf = metrics.get("profit_factor", 0.0)
        n_trades = metrics.get("total_trades", len(trades))

        self.metric_labels["Total Return"].setText(f"{ret:+.2%}")
        self.metric_labels["Total Return"].setStyleSheet(
            f"color: {AURORA_GREEN if ret >= 0 else AURORA_RED}; font-size: 14px; font-weight: bold;"
        )
        self.metric_labels["CAGR"].setText(f"{cagr:+.2%}")
        self.metric_labels["Sharpe Ratio"].setText(f"{sharpe:.4f}")
        self.metric_labels["Sortino Ratio"].setText(f"{sortino:.4f}")
        self.metric_labels["Max Drawdown"].setText(f"{max_dd:.2%}")
        self.metric_labels["Calmar Ratio"].setText(f"{calmar:.4f}")
        self.metric_labels["Win Rate"].setText(f"{win_rate:.1%}")
        self.metric_labels["Profit Factor"].setText(f"{pf:.2f}")
        self.metric_labels["Total Trades"].setText(f"{n_trades:,}")

        # 3. Populate Closed Trades Table
        self.trade_table.setRowCount(len(trades))
        for row, t in enumerate(trades):
            pnl = t.get("pnl", (t.get("exit_price", 0) - t.get("entry_price", 0)) * t.get("shares", 0))
            pnl_item = QTableWidgetItem(f"Rp {pnl:+,.0f}")
            pnl_item.setForeground(QColor(AURORA_GREEN if pnl >= 0 else AURORA_RED))

            self.trade_table.setItem(row, 0, QTableWidgetItem(t.get("ticker", "")))
            self.trade_table.setItem(row, 1, QTableWidgetItem(str(t.get("entry_date", ""))[:10]))
            self.trade_table.setItem(row, 2, QTableWidgetItem(str(t.get("exit_date", ""))[:10]))
            self.trade_table.setItem(row, 3, QTableWidgetItem(f"Rp {t.get('entry_price', 0):,.0f}"))
            self.trade_table.setItem(row, 4, QTableWidgetItem(f"Rp {t.get('exit_price', 0):,.0f}"))
            self.trade_table.setItem(row, 5, QTableWidgetItem(f"{t.get('shares', 0):,}"))
            self.trade_table.setItem(row, 6, pnl_item)

    def _on_error(self, err_msg: str):
        self.run_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
