"""
Folium Portfolio Panel Widget — Live Positions, Transaction Log & Profile Sync.

Enhanced portfolio widget with:
- Real-time positions table (live prices from SQLite DB)
- RDN Cash & Total Equity summary header
- Transaction history log
- Place Order button triggers OrderExecutionDialog
- Auto-refresh on SignalBus.profile_updated
"""
import sys
import os
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QGroupBox,
    QGridLayout, QTabWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from frontend.gui.workers.signal_bus import SignalBus

AURORA_GREEN  = "#A3BE8C"
AURORA_RED    = "#BF616A"
FROST_BLUE    = "#88C0D0"
FROST_2       = "#81A1C1"


class PortfolioPanelWidget(QWidget):
    """Full-featured Portfolio Panel with positions, equity & trade history."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bus = SignalBus.instance()
        self._build_ui()
        self.refresh()

        # Auto-refresh on profile update
        self.bus.profile_updated.connect(self.refresh)
        self.bus.order_executed.connect(self._on_order_executed)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ── Equity Summary Header ────────────────────────────────
        summary_group = QGroupBox("Account Summary")
        s_grid = QGridLayout(summary_group)

        self.cash_label = QLabel("RDN Cash: —")
        self.cash_label.setStyleSheet(f"color: {FROST_BLUE}; font-size: 15px; font-weight: bold;")
        s_grid.addWidget(self.cash_label, 0, 0)

        self.equity_label = QLabel("Total Equity: —")
        self.equity_label.setStyleSheet(f"color: {FROST_2}; font-size: 15px; font-weight: bold;")
        s_grid.addWidget(self.equity_label, 0, 1)

        self.pnl_label = QLabel("Unrealized P&L: —")
        self.pnl_label.setStyleSheet(f"color: {AURORA_GREEN}; font-size: 15px; font-weight: bold;")
        s_grid.addWidget(self.pnl_label, 0, 2)

        # Place Order button
        order_btn = QPushButton("📋 Place Order")
        order_btn.setObjectName("primaryButton")
        order_btn.clicked.connect(self._on_place_order)
        s_grid.addWidget(order_btn, 0, 3)

        layout.addWidget(summary_group)

        # ── Tabs: Positions / Transaction History ────────────────
        self.tabs = QTabWidget()

        # Tab 1: Positions
        pos_widget = QWidget()
        pos_layout = QVBoxLayout(pos_widget)
        pos_layout.setContentsMargins(0, 0, 0, 0)

        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(7)
        self.positions_table.setHorizontalHeaderLabels(
            ["Ticker", "Lots", "Shares", "Avg Price", "Current", "P&L (Rp)", "P&L %"]
        )
        self.positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.positions_table.setAlternatingRowColors(True)
        pos_layout.addWidget(self.positions_table)
        self.tabs.addTab(pos_widget, "📊 Open Positions")

        # Tab 2: Transaction History
        tx_widget = QWidget()
        tx_layout = QVBoxLayout(tx_widget)
        tx_layout.setContentsMargins(0, 0, 0, 0)

        self.tx_table = QTableWidget()
        self.tx_table.setColumnCount(6)
        self.tx_table.setHorizontalHeaderLabels(
            ["Date", "Ticker", "Side", "Lots", "Price", "Total (Rp)"]
        )
        self.tx_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tx_table.setAlternatingRowColors(True)
        tx_layout.addWidget(self.tx_table)
        self.tabs.addTab(tx_widget, "📋 Transaction History")

        layout.addWidget(self.tabs)

    def refresh(self):
        """Reload all portfolio data from UserProfile + DB live prices."""
        try:
            from shared.utils.user_profile import ProfileManager
            from pipeline.storage import StorageManager

            pm = ProfileManager()
            prof = pm.load()
            capital = float(prof.rdn_balance)
            positions = prof.positions or []

            # Fetch latest prices
            latest_prices = {}
            try:
                storage = StorageManager()
                closes = storage.load_close_prices(tickers=None)
                if not closes.empty:
                    for col in closes.columns:
                        vals = closes[col].dropna()
                        if len(vals) > 0:
                            latest_prices[col] = float(vals.iloc[-1])
            except Exception:
                pass

            # Calculate totals
            total_invested = 0.0
            total_market_value = 0.0
            total_pnl = 0.0

            self.positions_table.setRowCount(len(positions))
            for row, pos in enumerate(positions):
                cur_price = latest_prices.get(pos.ticker, pos.avg_price)
                cost_basis = pos.shares * pos.avg_price
                market_val = pos.shares * cur_price
                pnl = market_val - cost_basis
                pnl_pct = ((cur_price / pos.avg_price) - 1) * 100 if pos.avg_price > 0 else 0

                total_invested += cost_basis
                total_market_value += market_val
                total_pnl += pnl

                color = QColor(AURORA_GREEN) if pnl >= 0 else QColor(AURORA_RED)

                self.positions_table.setItem(row, 0, QTableWidgetItem(pos.ticker))
                self.positions_table.setItem(row, 1, QTableWidgetItem(f"{pos.lots}"))
                self.positions_table.setItem(row, 2, QTableWidgetItem(f"{pos.shares:,}"))
                self.positions_table.setItem(row, 3, QTableWidgetItem(f"Rp {pos.avg_price:,.0f}"))
                self.positions_table.setItem(row, 4, QTableWidgetItem(f"Rp {cur_price:,.0f}"))

                pnl_item = QTableWidgetItem(f"Rp {pnl:+,.0f}")
                pnl_item.setForeground(color)
                self.positions_table.setItem(row, 5, pnl_item)

                pct_item = QTableWidgetItem(f"{pnl_pct:+.2f}%")
                pct_item.setForeground(color)
                self.positions_table.setItem(row, 6, pct_item)

            # Update summary labels
            total_equity = capital + total_market_value
            self.cash_label.setText(f"RDN Cash: Rp {capital:,.0f}")
            self.equity_label.setText(f"Total Equity: Rp {total_equity:,.0f}")

            pnl_sign = "+" if total_pnl >= 0 else ""
            pnl_color = AURORA_GREEN if total_pnl >= 0 else AURORA_RED
            self.pnl_label.setText(f"Unrealized P&L: {pnl_sign}Rp {total_pnl:,.0f}")
            self.pnl_label.setStyleSheet(f"color: {pnl_color}; font-size: 15px; font-weight: bold;")

        except Exception:
            self.cash_label.setText("RDN Cash: N/A")
            self.equity_label.setText("Total Equity: N/A")

    def _on_place_order(self):
        """Open the Order Execution Dialog."""
        from frontend.gui.components.order_dialog import OrderExecutionDialog

        # Pre-select ticker from positions table selection
        ticker = "BBCA.JK"
        selected = self.positions_table.selectedItems()
        if selected:
            row = selected[0].row()
            t_item = self.positions_table.item(row, 0)
            if t_item:
                ticker = t_item.text()

        dialog = OrderExecutionDialog(ticker=ticker, parent=self)
        dialog.exec()

    def _on_order_executed(self, result: dict):
        """Add executed trade to transaction history table."""
        from datetime import datetime

        row = self.tx_table.rowCount()
        self.tx_table.insertRow(row)

        side = result.get("side", "")
        color = QColor(AURORA_GREEN) if side == "BUY" else QColor(AURORA_RED)

        self.tx_table.setItem(row, 0, QTableWidgetItem(datetime.now().strftime("%Y-%m-%d %H:%M")))
        self.tx_table.setItem(row, 1, QTableWidgetItem(result.get("ticker", "")))

        side_item = QTableWidgetItem(side)
        side_item.setForeground(color)
        self.tx_table.setItem(row, 2, side_item)

        self.tx_table.setItem(row, 3, QTableWidgetItem(f"{result.get('lots', 0)}"))
        self.tx_table.setItem(row, 4, QTableWidgetItem(f"Rp {result.get('exec_price', 0):,.0f}"))

        total = result.get("shares", 0) * result.get("exec_price", 0)
        self.tx_table.setItem(row, 5, QTableWidgetItem(f"Rp {total:,.0f}"))
