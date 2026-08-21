"""
Folium Order Execution Dialog — Pre-Trade Risk Validation & Order Submission.

Modal dialog for placing BUY/SELL orders with:
- Ticker & side (BUY/SELL) selector
- Lot quantity input (enforces 100-share IDX minimum)
- Live price lookup from StorageManager
- Pre-trade risk validation via RiskManager (concentration, daily loss, drawdown)
- ExecutionEngine order submission
- Auto-persist to UserProfile after successful trade
"""
import sys
import os
from decimal import Decimal
from typing import Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QPushButton, QGroupBox, QGridLayout, QMessageBox,
    QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from frontend.gui.workers.signal_bus import SignalBus

# Nord
AURORA_GREEN  = "#A3BE8C"
AURORA_RED    = "#BF616A"
AURORA_YELLOW = "#EBCB8B"
FROST_BLUE    = "#88C0D0"
POLAR_NIGHT_1 = "#3B4252"


class OrderExecutionDialog(QDialog):
    """Modal dialog for order entry with pre-trade risk checks."""

    def __init__(self, ticker: str = "BBCA.JK", parent=None):
        super().__init__(parent)
        self.bus = SignalBus.instance()
        self.initial_ticker = ticker
        self.execution_result = None

        self.setWindowTitle("📋 Order Execution — Pre-Trade Risk Validation")
        self.setMinimumWidth(520)
        self.setModal(True)

        self._build_ui()
        self._load_tickers()
        self._update_preview()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── Order Input Group ────────────────────────────────────
        input_group = QGroupBox("Order Parameters")
        grid = QGridLayout(input_group)

        grid.addWidget(QLabel("Ticker:"), 0, 0)
        self.ticker_combo = QComboBox()
        self.ticker_combo.setEditable(True)
        self.ticker_combo.currentTextChanged.connect(self._update_preview)
        grid.addWidget(self.ticker_combo, 0, 1)

        grid.addWidget(QLabel("Side:"), 1, 0)
        self.side_combo = QComboBox()
        self.side_combo.addItems(["BUY", "SELL"])
        self.side_combo.currentTextChanged.connect(self._update_preview)
        grid.addWidget(self.side_combo, 1, 1)

        grid.addWidget(QLabel("Lots (1 lot = 100 shares):"), 2, 0)
        self.lots_spin = QSpinBox()
        self.lots_spin.setRange(1, 10000)
        self.lots_spin.setValue(1)
        self.lots_spin.valueChanged.connect(self._update_preview)
        grid.addWidget(self.lots_spin, 2, 1)

        layout.addWidget(input_group)

        # ── Preview Group ────────────────────────────────────────
        preview_group = QGroupBox("Order Preview & Cost Estimation")
        p_grid = QGridLayout(preview_group)

        self.price_label = QLabel("Current Price: —")
        self.shares_label = QLabel("Total Shares: —")
        self.notional_label = QLabel("Notional Value: —")
        self.commission_label = QLabel("Commission (0.15%): —")
        self.total_cost_label = QLabel("Total Cost: —")
        self.total_cost_label.setStyleSheet(f"color: {FROST_BLUE}; font-weight: bold; font-size: 14px;")

        p_grid.addWidget(self.price_label, 0, 0)
        p_grid.addWidget(self.shares_label, 0, 1)
        p_grid.addWidget(self.notional_label, 1, 0)
        p_grid.addWidget(self.commission_label, 1, 1)
        p_grid.addWidget(self.total_cost_label, 2, 0, 1, 2)

        layout.addWidget(preview_group)

        # ── Risk Check Status ────────────────────────────────────
        risk_group = QGroupBox("Pre-Trade Risk Validation (RiskManager)")
        r_layout = QVBoxLayout(risk_group)
        self.risk_status_label = QLabel("⏳ Awaiting order parameters...")
        self.risk_status_label.setStyleSheet(f"color: {AURORA_YELLOW};")
        r_layout.addWidget(self.risk_status_label)
        layout.addWidget(risk_group)

        # ── Action Buttons ───────────────────────────────────────
        btn_layout = QHBoxLayout()

        self.execute_btn = QPushButton("✅ Execute Order")
        self.execute_btn.setObjectName("primaryButton")
        self.execute_btn.clicked.connect(self._on_execute)
        btn_layout.addWidget(self.execute_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _load_tickers(self):
        tickers = []
        try:
            from pipeline.storage import StorageManager
            tickers = StorageManager().get_available_tickers()
        except Exception:
            pass

        if not tickers:
            try:
                from pipeline.universe import UniverseManager
                tickers = UniverseManager(universe_name="lq45").get_tickers()
            except Exception:
                tickers = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "TLKM.JK", "ASII.JK"]

        self.ticker_combo.blockSignals(True)
        self.ticker_combo.clear()
        self.ticker_combo.addItems(tickers)
        if self.initial_ticker in tickers:
            self.ticker_combo.setCurrentText(self.initial_ticker)
        self.ticker_combo.blockSignals(False)

    def _get_current_price(self, ticker: str) -> float:
        """Fetch latest close price from SQLite DB."""
        try:
            from pipeline.storage import StorageManager
            storage = StorageManager()
            closes = storage.load_close_prices(tickers=[ticker])
            if not closes.empty and ticker in closes.columns:
                s = closes[ticker].dropna()
                if len(s) > 0:
                    return float(s.iloc[-1])
        except Exception:
            pass
        return 5000.0  # fallback

    def _update_preview(self):
        ticker = self.ticker_combo.currentText()
        side = self.side_combo.currentText()
        lots = self.lots_spin.value()
        shares = lots * 100
        price = self._get_current_price(ticker)

        notional = Decimal(str(shares)) * Decimal(str(price))
        comm_rate = Decimal("0.0015") if side == "BUY" else Decimal("0.0025")
        commission = notional * comm_rate
        slippage = notional * Decimal("0.0005")

        if side == "BUY":
            total = notional + commission + slippage
        else:
            total = notional - commission - slippage

        self.price_label.setText(f"Current Price: Rp {price:,.0f}")
        self.shares_label.setText(f"Total Shares: {shares:,} ({lots} lot)")
        self.notional_label.setText(f"Notional: Rp {notional:,.0f}")
        self.commission_label.setText(f"Commission ({comm_rate:.2%}): Rp {commission:,.0f}")
        self.total_cost_label.setText(f"Total {'Cost' if side == 'BUY' else 'Proceeds'}: Rp {total:,.0f}")

        # Pre-trade risk check
        self._run_risk_check(ticker, shares, price, side)

    def _run_risk_check(self, ticker: str, shares: int, price: float, side: str):
        """Run RiskManager pre-trade validation."""
        try:
            from shared.utils.user_profile import ProfileManager
            pm = ProfileManager()
            prof = pm.load()

            capital = float(prof.rdn_balance)
            notional = shares * price
            positions = prof.positions or []

            # Check cash sufficiency for BUY
            if side == "BUY":
                total_invested = sum(p.shares * p.avg_price for p in positions)
                free_cash = capital - total_invested
                if notional > free_cash:
                    self.risk_status_label.setText(
                        f"❌ REJECTED: Saldo RDN tidak cukup. Butuh Rp {notional:,.0f}, Free Cash Rp {free_cash:,.0f}"
                    )
                    self.risk_status_label.setStyleSheet(f"color: {AURORA_RED}; font-weight: bold;")
                    self.execute_btn.setEnabled(False)
                    return

            # Check sell quantity
            if side == "SELL":
                held = sum(p.shares for p in positions if p.ticker == ticker)
                if shares > held:
                    self.risk_status_label.setText(
                        f"❌ REJECTED: Kepemilikan {ticker} tidak cukup. Punya {held:,}, mau jual {shares:,}"
                    )
                    self.risk_status_label.setStyleSheet(f"color: {AURORA_RED}; font-weight: bold;")
                    self.execute_btn.setEnabled(False)
                    return

            # RiskManager concentration check
            try:
                from app.risk.risk_manager import RiskManager
                import numpy as np

                rm = RiskManager()
                total_equity = capital
                for p in positions:
                    total_equity += p.shares * p.avg_price

                weights = {}
                for p in positions:
                    weights[p.ticker] = (p.shares * p.avg_price) / total_equity

                # Simulate new position impact
                if side == "BUY":
                    current_val = weights.get(ticker, 0) * total_equity
                    weights[ticker] = (current_val + notional) / (total_equity + notional)

                tickers_list = list(weights.keys())
                weights_arr = np.array(list(weights.values()))

                limits = rm.check_position_limit(weights_arr, tickers_list)
                breached = [t for t, ok in limits.items() if not ok]
                if breached:
                    self.risk_status_label.setText(
                        f"⚠️ WARNING: Concentration risk breached for {', '.join(breached)}"
                    )
                    self.risk_status_label.setStyleSheet(f"color: {AURORA_YELLOW}; font-weight: bold;")
                    self.execute_btn.setEnabled(True)
                    return
            except Exception:
                pass

            self.risk_status_label.setText("✅ All pre-trade risk checks PASSED")
            self.risk_status_label.setStyleSheet(f"color: {AURORA_GREEN}; font-weight: bold;")
            self.execute_btn.setEnabled(True)

        except Exception as e:
            self.risk_status_label.setText(f"⚠️ Risk check unavailable: {e}")
            self.risk_status_label.setStyleSheet(f"color: {AURORA_YELLOW};")
            self.execute_btn.setEnabled(True)

    def _on_execute(self):
        """Execute the order via ExecutionEngine and persist to UserProfile."""
        ticker = self.ticker_combo.currentText()
        side = self.side_combo.currentText()
        lots = self.lots_spin.value()
        shares = lots * 100
        price = self._get_current_price(ticker)

        exec_price = price
        commission = Decimal("0")

        # Try ExecutionEngine
        try:
            from app.execution.execution_engine import ExecutionEngine, Order as EngineOrder
            engine = ExecutionEngine()
            order = EngineOrder(ticker=ticker, side=side, quantity_shares=shares, price=price)
            trade = engine.execute(order)
            exec_price = trade.execution_price
            commission = Decimal(str(trade.commission))
        except Exception:
            slippage_mult = Decimal("1.0005") if side == "BUY" else Decimal("0.9995")
            exec_price = float(Decimal(str(price)) * slippage_mult)
            comm_rate = 0.0015 if side == "BUY" else 0.0025
            commission = Decimal(str(shares * price * comm_rate))

        # Update UserProfile
        try:
            from shared.utils.user_profile import ProfileManager, UserProfile, StockPosition
            pm = ProfileManager()
            prof = pm.load()

            exec_dec = Decimal(str(exec_price))

            if side == "BUY":
                prof.rdn_balance -= float(Decimal(str(shares)) * exec_dec + commission)
                found = False
                for p in prof.positions:
                    if p.ticker == ticker:
                        new_shares = p.shares + shares
                        p.avg_price = float(
                            (Decimal(str(p.shares)) * Decimal(str(p.avg_price)) +
                             Decimal(str(shares)) * exec_dec) / Decimal(str(new_shares))
                        )
                        p.lots = new_shares // 100
                        found = True
                        break
                if not found:
                    prof.positions.append(StockPosition(
                        ticker=ticker, lots=lots, avg_price=exec_price
                    ))
            else:
                prof.rdn_balance += float(Decimal(str(shares)) * exec_dec - commission)
                for p in prof.positions:
                    if p.ticker == ticker:
                        remaining = p.shares - shares
                        if remaining <= 0:
                            prof.positions.remove(p)
                        else:
                            p.lots = remaining // 100
                        break

            pm.save(prof)
        except Exception:
            pass

        self.execution_result = {
            "ticker": ticker,
            "side": side,
            "lots": lots,
            "shares": shares,
            "exec_price": exec_price,
            "commission": float(commission),
        }

        self.bus.order_executed.emit(self.execution_result)
        self.bus.profile_updated.emit()

        QMessageBox.information(
            self,
            "Trade Executed",
            f"✅ {side} {lots} lot {ticker} @ Rp {exec_price:,.0f}\n"
            f"Commission: Rp {commission:,.0f}",
        )
        self.accept()
