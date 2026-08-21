"""
Folium Risk Meter Widget — Real-Time Risk Gauges & IDX Rules Compliance.

Displays:
- Max Drawdown visual dial / gauge (breach threshold at 15%)
- Daily Loss visual gauge (breach threshold at 3%)
- Position Concentration gauge (breach threshold at 25%)
- IDX Regulatory Compliance checklist:
  - 100 share lot size constraint (Enforced)
  - 0.15% Buy / 0.25% Sell commission + levy (Enforced)
  - 0.05% slippage estimation model (Enforced)
  - IDX Trading Hours (JATS sessions 09:00-11:30, 13:30-15:49)
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QGroupBox, QGridLayout, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from frontend.gui.workers.signal_bus import SignalBus

AURORA_GREEN  = "#A3BE8C"
AURORA_YELLOW = "#EBCB8B"
AURORA_RED    = "#BF616A"
FROST_BLUE    = "#88C0D0"
POLAR_NIGHT_1 = "#3B4252"
POLAR_NIGHT_3 = "#4C566A"


class RiskMeterWidget(QWidget):
    """Institutional Risk Management & IDX Compliance Dashboard Widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bus = SignalBus.instance()

        self._build_ui()
        self.update_risk_metrics(drawdown_pct=0.0, daily_loss_pct=0.0, max_pos_pct=0.0)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # ── Title ────────────────────────────────────────────────
        title = QLabel("⚙ RISK CONTROL CENTER & IDX COMPLIANCE")
        title.setObjectName("headerLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        main_layout.addWidget(title)

        # ── Gauges Grid ──────────────────────────────────────────
        gauges_group = QGroupBox("Live Risk Limits (RiskManager State)")
        grid = QGridLayout(gauges_group)
        grid.setSpacing(10)

        # 1. Max Drawdown Gauge
        grid.addWidget(QLabel("Portfolio Drawdown:"), 0, 0)
        self.dd_bar = QProgressBar()
        self.dd_bar.setRange(0, 100)
        self.dd_bar.setValue(0)
        self.dd_label = QLabel("0.0% / 15.0% Max")
        self.dd_label.setStyleSheet(f"color: {AURORA_GREEN}; font-weight: bold;")
        grid.addWidget(self.dd_bar, 0, 1)
        grid.addWidget(self.dd_label, 0, 2)

        # 2. Daily Loss Gauge
        grid.addWidget(QLabel("Daily P&L Loss:"), 1, 0)
        self.dl_bar = QProgressBar()
        self.dl_bar.setRange(0, 100)
        self.dl_bar.setValue(0)
        self.dl_label = QLabel("0.0% / 3.0% Limit")
        self.dl_label.setStyleSheet(f"color: {AURORA_GREEN}; font-weight: bold;")
        grid.addWidget(self.dl_bar, 1, 1)
        grid.addWidget(self.dl_label, 1, 2)

        # 3. Position Concentration Gauge
        grid.addWidget(QLabel("Max Single Position:"), 2, 0)
        self.pos_bar = QProgressBar()
        self.pos_bar.setRange(0, 100)
        self.pos_bar.setValue(0)
        self.pos_label = QLabel("0.0% / 25.0% Limit")
        self.pos_label.setStyleSheet(f"color: {AURORA_GREEN}; font-weight: bold;")
        grid.addWidget(self.pos_bar, 2, 1)
        grid.addWidget(self.pos_label, 2, 2)

        main_layout.addWidget(gauges_group)

        # ── IDX Rules Compliance Checklist ───────────────────────
        idx_group = QGroupBox("IDX Market Rules Enforcer (Hard Constraints)")
        idx_layout = QGridLayout(idx_group)
        idx_layout.setSpacing(8)

        rules = [
            ("Minimum Lot Size", "100 Lembar (Kelipatan Penuh)", "ENFORCED ✓", AURORA_GREEN),
            ("Broker Commission", "0.15% Buy / 0.25% Sell (Inc. PPh)", "ENFORCED ✓", AURORA_GREEN),
            ("Slippage Estimation", "0.05% Fixed Slippage Model", "ENFORCED ✓", AURORA_GREEN),
            ("JATS Trading Session", "S1: 09:00-11:30 | S2: 13:30-15:49", "ACTIVE ●", FROST_BLUE),
            ("Auto-Rejection on Breach", "RiskManager Concentration Stop", "ACTIVE ●", FROST_BLUE),
        ]

        for row, (rule_name, detail, status, color) in enumerate(rules):
            r_lbl = QLabel(f"• {rule_name}:")
            r_lbl.setStyleSheet("font-weight: bold;")
            d_lbl = QLabel(detail)
            s_lbl = QLabel(status)
            s_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")

            idx_layout.addWidget(r_lbl, row, 0)
            idx_layout.addWidget(d_lbl, row, 1)
            idx_layout.addWidget(s_lbl, row, 2)

        main_layout.addWidget(idx_group)
        main_layout.addStretch()

    def update_risk_metrics(
        self,
        drawdown_pct: float = 0.0,
        daily_loss_pct: float = 0.0,
        max_pos_pct: float = 0.0
    ):
        """Update the visual risk meters based on real PortfolioService / RiskManager state."""
        # 1. Drawdown (0 to 15%)
        dd_ratio = min(abs(drawdown_pct) / 15.0, 1.0) * 100
        self.dd_bar.setValue(int(dd_ratio))
        dd_col = AURORA_GREEN if abs(drawdown_pct) < 8 else (AURORA_YELLOW if abs(drawdown_pct) < 15 else AURORA_RED)
        self.dd_label.setText(f"{abs(drawdown_pct):.1f}% / 15.0% Max")
        self.dd_label.setStyleSheet(f"color: {dd_col}; font-weight: bold;")

        # 2. Daily Loss (0 to 3%)
        dl_ratio = min(abs(daily_loss_pct) / 3.0, 1.0) * 100
        self.dl_bar.setValue(int(dl_ratio))
        dl_col = AURORA_GREEN if abs(daily_loss_pct) < 1.5 else (AURORA_YELLOW if abs(daily_loss_pct) < 3.0 else AURORA_RED)
        self.dl_label.setText(f"{abs(daily_loss_pct):.1f}% / 3.0% Limit")
        self.dl_label.setStyleSheet(f"color: {dl_col}; font-weight: bold;")

        # 3. Position Concentration (0 to 25%)
        pos_ratio = min(max_pos_pct / 25.0, 1.0) * 100
        self.pos_bar.setValue(int(pos_ratio))
        pos_col = AURORA_GREEN if max_pos_pct < 15 else (AURORA_YELLOW if max_pos_pct < 25 else AURORA_RED)
        self.pos_label.setText(f"{max_pos_pct:.1f}% / 25.0% Limit")
        self.pos_label.setStyleSheet(f"color: {pos_col}; font-weight: bold;")
