"""
Folium Quant Desk — Main Window (QMainWindow + QDockWidget Layout).

Institutional-grade dockable workstation shell inspired by FinceptTerminal.
Multi-panel layout with Nord Theme, toolbar shortcuts, status bar,
and dockable workspace panels integrating all Phase 2 components.
"""
import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from PyQt6.QtWidgets import (
    QMainWindow, QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QToolBar, QStatusBar, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar, QGroupBox,
    QGridLayout, QSplitter, QTextEdit, QPushButton, QComboBox,
    QSpinBox, QMenuBar, QMenu,
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QAction, QFont, QColor

from frontend.gui.workers.signal_bus import SignalBus
from frontend.gui.components.chart_canvas import ChartCanvasWidget
from frontend.gui.components.market_table import MarketTableWidget
from frontend.gui.components.risk_meter import RiskMeterWidget
from frontend.gui.components.backtest_lab import BacktestLabWidget
from frontend.gui.components.portfolio_panel import PortfolioPanelWidget

# ── Nord Palette Constants ───────────────────────────────────────
POLAR_NIGHT_0 = "#2E3440"
POLAR_NIGHT_1 = "#3B4252"
POLAR_NIGHT_2 = "#434C5E"
POLAR_NIGHT_3 = "#4C566A"
SNOW_STORM_0  = "#D8DEE9"
SNOW_STORM_1  = "#E5E9F0"
SNOW_STORM_2  = "#ECEFF4"
FROST_0       = "#8FBCBB"
FROST_1       = "#88C0D0"
FROST_2       = "#81A1C1"
FROST_3       = "#5E81AC"
AURORA_RED    = "#BF616A"
AURORA_ORANGE = "#D08770"
AURORA_YELLOW = "#EBCB8B"
AURORA_GREEN  = "#A3BE8C"
AURORA_PURPLE = "#B48EAD"


def _load_qss() -> str:
    """Load the Nord Theme QSS stylesheet from disk."""
    qss_path = Path(__file__).parent / "styles" / "nord_theme.qss"
    if qss_path.exists():
        return qss_path.read_text()
    return ""


class FoliumMainWindow(QMainWindow):
    """Folium Quant Desk — Primary dockable workstation window."""

    def __init__(self):
        super().__init__()
        self.bus = SignalBus.instance()

        self._setup_window()
        self._create_menu_bar()
        self._create_toolbar()
        self._create_status_bar()
        self._create_dock_panels()
        self._connect_signals()
        self._start_clock()

    # ── Window Setup ─────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowTitle("▲ FOLIUM QUANT DESK — Institutional Trading Workstation")
        self.setMinimumSize(1280, 720)
        self.resize(1600, 900)

        # Apply QSS
        qss = _load_qss()
        if qss:
            self.setStyleSheet(qss)

        # Allow nested docking
        self.setDockNestingEnabled(True)

    # ── Menu Bar ─────────────────────────────────────────────────

    def _create_menu_bar(self):
        menubar = self.menuBar()

        # File
        file_menu = menubar.addMenu("File")
        file_menu.addAction(self._action("New Workspace", "Ctrl+N"))
        file_menu.addAction(self._action("Open Database...", "Ctrl+O"))
        file_menu.addSeparator()
        file_menu.addAction(self._action("Export Report...", "Ctrl+E"))
        file_menu.addSeparator()
        exit_action = self._action("Exit", "Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Navigate
        nav_menu = menubar.addMenu("Navigate")
        nav_menu.addAction(self._action("Dashboard", "Ctrl+1"))
        nav_menu.addAction(self._action("Scanner", "Ctrl+2"))
        nav_menu.addAction(self._action("Portfolio", "Ctrl+3"))
        nav_menu.addAction(self._action("Backtest Lab", "Ctrl+4"))
        nav_menu.addAction(self._action("Model Registry", "Ctrl+5"))

        # View
        view_menu = menubar.addMenu("View")
        view_menu.addAction(self._action("Reset Layout", "Ctrl+Shift+R"))

        # Help
        help_menu = menubar.addMenu("Help")
        help_menu.addAction(self._action("About Folium"))
        help_menu.addAction(self._action("Documentation"))

    def _action(self, text: str, shortcut: str = None) -> QAction:
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        return action

    # ── Toolbar ──────────────────────────────────────────────────

    def _create_toolbar(self):
        toolbar = QToolBar("Workspaces")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(toolbar)

        workspace_buttons = [
            ("📊 Dashboard", self._show_dashboard),
            ("🔍 Scanner", self._show_scanner),
            ("💼 Portfolio", self._show_portfolio),
            ("🧪 Backtest Lab", self._show_backtest),
            ("🤖 Model Registry", self._show_registry),
            ("⚙ Risk Control", self._show_risk),
        ]

        for label, callback in workspace_buttons:
            btn = toolbar.addAction(label)
            btn.triggered.connect(callback)

        toolbar.addSeparator()

        # Place Order button
        order_btn = toolbar.addAction("📋 Place Order")
        order_btn.triggered.connect(self._on_place_order)

        # ML Inference button
        infer_btn = toolbar.addAction("🤖 Run Inference")
        infer_btn.triggered.connect(self._on_run_inference)

        # Sync Data button
        sync_btn = toolbar.addAction("🔄 Sync Data")
        sync_btn.triggered.connect(self._on_sync_data)

    # ── Status Bar ───────────────────────────────────────────────

    def _create_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Clock
        self.clock_label = QLabel()
        self.clock_label.setStyleSheet(f"color: {FROST_1}; font-weight: bold; padding: 0 12px;")
        self.status_bar.addPermanentWidget(self.clock_label)

        # Mode indicator
        self.mode_label = QLabel("● LIVE DATABASE")
        self.mode_label.setStyleSheet(f"color: {AURORA_GREEN}; font-weight: bold; padding: 0 12px;")
        self.status_bar.addPermanentWidget(self.mode_label)

        # DB status
        self.db_label = QLabel("DB: Connecting...")
        self.db_label.setStyleSheet(f"color: {SNOW_STORM_0}; padding: 0 12px;")
        self.status_bar.addWidget(self.db_label)

        self._update_db_status()

    def _update_db_status(self):
        try:
            from pipeline.storage import StorageManager
            storage = StorageManager()
            tickers = storage.get_available_tickers()
            count = len(tickers)
            self.db_label.setText(f"DB: {storage.db_path} ({count} tickers)")
            if count > 0:
                self.mode_label.setText("● LIVE DATABASE ACTIVE")
                self.mode_label.setStyleSheet(f"color: {AURORA_GREEN}; font-weight: bold; padding: 0 12px;")
            else:
                self.mode_label.setText("● SANDBOX MODE")
                self.mode_label.setStyleSheet(f"color: {AURORA_ORANGE}; font-weight: bold; padding: 0 12px;")
        except Exception:
            self.db_label.setText("DB: Unavailable")
            self.mode_label.setText("● OFFLINE")
            self.mode_label.setStyleSheet(f"color: {AURORA_RED}; font-weight: bold; padding: 0 12px;")

    # ── Clock Timer ──────────────────────────────────────────────

    def _start_clock(self):
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()

    def _update_clock(self):
        now = datetime.now().strftime("%d %b %Y  %H:%M:%S").upper()
        self.clock_label.setText(now)

    # ── Dock Panels ──────────────────────────────────────────────

    def _create_dock_panels(self):
        # --- Center: Interactive Candlestick ChartCanvas ---
        self.chart_canvas = ChartCanvasWidget()
        self.setCentralWidget(self.chart_canvas)

        # --- Left Dock: Market Watchlist & Scanner ---
        self.market_dock = QDockWidget("📈 MARKET WATCHLIST & SECTORS", self)
        self.market_table = MarketTableWidget()
        self.market_dock.setWidget(self.market_table)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.market_dock)

        self.scanner_dock = QDockWidget("🔍 ALPHA SCANNER FEED", self)
        self.scanner_dock.setWidget(self._build_scanner_panel())
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.scanner_dock)
        self.tabifyDockWidget(self.market_dock, self.scanner_dock)
        self.market_dock.raise_()

        # --- Right Dock: Portfolio & Model Registry ---
        self.portfolio_dock = QDockWidget("💼 PORTFOLIO & LEDGER", self)
        self.portfolio_panel = PortfolioPanelWidget()
        self.portfolio_dock.setWidget(self.portfolio_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.portfolio_dock)

        self.registry_dock = QDockWidget("🤖 MODEL REGISTRY", self)
        self.registry_dock.setWidget(self._build_registry_panel())
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.registry_dock)
        self.tabifyDockWidget(self.portfolio_dock, self.registry_dock)
        self.portfolio_dock.raise_()

        # --- Bottom Dock: Backtest Lab & Risk Control ---
        self.backtest_dock = QDockWidget("🧪 BACKTEST LAB & PERFORMANCE VISUALIZER", self)
        self.backtest_lab = BacktestLabWidget()
        self.backtest_dock.setWidget(self.backtest_lab)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.backtest_dock)

        self.risk_dock = QDockWidget("⚙ RISK CONTROL & IDX COMPLIANCE", self)
        self.risk_meter = RiskMeterWidget()
        self.risk_dock.setWidget(self.risk_meter)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.risk_dock)
        self.tabifyDockWidget(self.backtest_dock, self.risk_dock)
        self.backtest_dock.raise_()

    # ── Scanner Panel ────────────────────────────────────────────

    def _build_scanner_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        # Scanner controls
        ctrl_layout = QHBoxLayout()
        scan_btn = QPushButton("▶ Run Scanner")
        scan_btn.clicked.connect(self._on_run_scanner)
        ctrl_layout.addWidget(scan_btn)
        layout.addLayout(ctrl_layout)

        # Scanner table
        self.scanner_table = QTableWidget()
        self.scanner_table.setColumnCount(6)
        self.scanner_table.setHorizontalHeaderLabels(
            ["Ticker", "Price", "Signal", "Score", "SL", "TP"]
        )
        self.scanner_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.scanner_table.setAlternatingRowColors(True)
        self.scanner_table.cellDoubleClicked.connect(self._on_scanner_row_clicked)
        layout.addWidget(self.scanner_table)

        self._populate_scanner_table()
        return widget

    def _populate_scanner_table(self):
        try:
            from app.services.scanner_service import ScannerService
            scanner = ScannerService()
            signals = scanner.scan_momentum()
            self._fill_scanner_table(signals)
        except Exception:
            self.scanner_table.setRowCount(0)

    def _fill_scanner_table(self, signals: list):
        self.scanner_table.setRowCount(len(signals))
        for row, sig in enumerate(signals):
            ticker_item = QTableWidgetItem(sig.get("ticker", ""))
            price_item = QTableWidgetItem(f"Rp {sig.get('price', 0):,.0f}")
            action = sig.get("action", "HOLD")
            action_item = QTableWidgetItem(action)

            if action == "BUY":
                action_item.setForeground(QColor(AURORA_GREEN))
            elif action == "SELL":
                action_item.setForeground(QColor(AURORA_RED))
            else:
                action_item.setForeground(QColor(AURORA_YELLOW))

            score_item = QTableWidgetItem(f"{sig.get('score', 0):.2f}")
            sl_item = QTableWidgetItem(f"Rp {sig.get('sl', 0):,.0f}")
            tp_item = QTableWidgetItem(f"Rp {sig.get('tp', 0):,.0f}")

            self.scanner_table.setItem(row, 0, ticker_item)
            self.scanner_table.setItem(row, 1, price_item)
            self.scanner_table.setItem(row, 2, action_item)
            self.scanner_table.setItem(row, 3, score_item)
            self.scanner_table.setItem(row, 4, sl_item)
            self.scanner_table.setItem(row, 5, tp_item)

    def _on_scanner_row_clicked(self, row, col):
        ticker_item = self.scanner_table.item(row, 0)
        if ticker_item:
            self.chart_canvas.load_ticker(ticker_item.text())

    # ── Portfolio Panel ──────────────────────────────────────────

    def _build_portfolio_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        # Capital display
        self.capital_label = QLabel("RDN Cash: —")
        self.capital_label.setObjectName("headerLabel")
        layout.addWidget(self.capital_label)

        # Portfolio table
        self.portfolio_table = QTableWidget()
        self.portfolio_table.setColumnCount(6)
        self.portfolio_table.setHorizontalHeaderLabels(
            ["Ticker", "Shares", "Avg Price", "Current", "P&L", "P&L %"]
        )
        self.portfolio_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.portfolio_table.setAlternatingRowColors(True)
        self.portfolio_table.cellDoubleClicked.connect(self._on_portfolio_row_clicked)
        layout.addWidget(self.portfolio_table)

        self._populate_portfolio()
        return widget

    def _populate_portfolio(self):
        try:
            from shared.utils.user_profile import ProfileManager
            from pipeline.storage import StorageManager

            pm = ProfileManager()
            prof = pm.load()
            self.capital_label.setText(f"RDN Cash: Rp {float(prof.rdn_balance):,.0f}")

            positions = prof.positions or []
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

            self.portfolio_table.setRowCount(len(positions))
            for row, pos in enumerate(positions):
                cur_price = latest_prices.get(pos.ticker, pos.avg_price)
                pnl = (cur_price - pos.avg_price) * pos.shares
                pnl_pct = ((cur_price / pos.avg_price) - 1) * 100 if pos.avg_price > 0 else 0

                self.portfolio_table.setItem(row, 0, QTableWidgetItem(pos.ticker))
                self.portfolio_table.setItem(row, 1, QTableWidgetItem(f"{pos.shares:,}"))
                self.portfolio_table.setItem(row, 2, QTableWidgetItem(f"Rp {pos.avg_price:,.0f}"))
                self.portfolio_table.setItem(row, 3, QTableWidgetItem(f"Rp {cur_price:,.0f}"))

                pnl_item = QTableWidgetItem(f"Rp {pnl:+,.0f}")
                pnl_pct_item = QTableWidgetItem(f"{pnl_pct:+.2f}%")
                color = QColor(AURORA_GREEN) if pnl >= 0 else QColor(AURORA_RED)
                pnl_item.setForeground(color)
                pnl_pct_item.setForeground(color)
                self.portfolio_table.setItem(row, 4, pnl_item)
                self.portfolio_table.setItem(row, 5, pnl_pct_item)

        except Exception:
            self.capital_label.setText("RDN Cash: N/A")

    def _on_portfolio_row_clicked(self, row, col):
        ticker_item = self.portfolio_panel.positions_table.item(row, 0)
        if ticker_item:
            self.chart_canvas.load_ticker(ticker_item.text())

    # ── Model Registry Panel ─────────────────────────────────────

    def _build_registry_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        self.registry_table = QTableWidget()
        self.registry_table.setColumnCount(5)
        self.registry_table.setHorizontalHeaderLabels(
            ["Model", "Version", "Stage", "F1 Score", "Registered"]
        )
        self.registry_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.registry_table.setAlternatingRowColors(True)
        layout.addWidget(self.registry_table)

        self._populate_registry()
        return widget

    def _populate_registry(self):
        try:
            from model.registry import ModelRegistry
            registry = ModelRegistry()
            models = registry.list_models()

            self.registry_table.setRowCount(len(models))
            for row, m in enumerate(models):
                self.registry_table.setItem(row, 0, QTableWidgetItem(m.get("model_type", "")))
                self.registry_table.setItem(row, 1, QTableWidgetItem(str(m.get("version", ""))))
                stage = m.get("stage", "staging")
                stage_item = QTableWidgetItem(stage)
                if stage == "production":
                    stage_item.setForeground(QColor(AURORA_GREEN))
                elif stage == "archived":
                    stage_item.setForeground(QColor(POLAR_NIGHT_3))
                self.registry_table.setItem(row, 2, stage_item)
                f1 = m.get("metrics", {}).get("f1_score", 0)
                self.registry_table.setItem(row, 3, QTableWidgetItem(f"{f1:.4f}" if f1 else "—"))
                self.registry_table.setItem(row, 4, QTableWidgetItem(m.get("registered_at", "")))
        except Exception:
            self.registry_table.setRowCount(0)

    # ── Signal Connections ───────────────────────────────────────

    def _connect_signals(self):
        bus = self.bus

        # Connect Market Table selection to Chart Canvas
        self.market_table.ticker_selected.connect(self.chart_canvas.load_ticker)

        # Scanner signals
        bus.scanner_updated.connect(self._fill_scanner_table)

        # Fetch signals
        bus.fetch_progress.connect(lambda p: self._show_status(f"Fetch progress: {p}%"))
        bus.fetch_completed.connect(lambda n: self._show_status(f"Fetch complete: {n} rows"))
        bus.fetch_completed.connect(self.market_table.refresh_data)

        # Status
        bus.status_message.connect(self.status_bar.showMessage)

        # Profile
        bus.profile_updated.connect(self._populate_portfolio)

    # ── Toolbar Actions / Slots ──────────────────────────────────

    def _show_dashboard(self):
        self.market_dock.show()
        self.market_dock.raise_()
        self.portfolio_dock.show()

    def _show_scanner(self):
        self.scanner_dock.show()
        self.scanner_dock.raise_()

    def _show_portfolio(self):
        self.portfolio_dock.show()
        self.portfolio_dock.raise_()

    def _show_backtest(self):
        self.backtest_dock.show()
        self.backtest_dock.raise_()

    def _show_registry(self):
        self.registry_dock.show()
        self.registry_dock.raise_()

    def _show_risk(self):
        self.risk_dock.show()
        self.risk_dock.raise_()

    def _on_sync_data(self):
        from frontend.gui.workers.async_workers import DataFetchWorker
        try:
            from pipeline.storage import StorageManager
            tickers = StorageManager().get_available_tickers()
            if not tickers:
                from pipeline.universe import UniverseManager
                tickers = UniverseManager(universe_name="lq45").get_tickers()
        except Exception:
            tickers = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "TLKM.JK", "ASII.JK"]

        self._fetch_worker = DataFetchWorker(tickers=tickers[:10])
        self._fetch_worker.error_occurred.connect(
            lambda msg: self._show_status(f"Fetch Error: {msg}", 5000)
        )
        self._fetch_worker.start()
        self._show_status("Data sync started...")

    def _on_place_order(self):
        """Open the Order Execution Dialog from toolbar."""
        from frontend.gui.components.order_dialog import OrderExecutionDialog
        ticker = self.chart_canvas.current_ticker
        dialog = OrderExecutionDialog(ticker=ticker, parent=self)
        dialog.exec()

    def _on_run_inference(self):
        """Run ML inference scanner on background thread."""
        from frontend.gui.workers.inference_worker import InferenceWorker
        try:
            from pipeline.storage import StorageManager
            tickers = StorageManager().get_available_tickers()
        except Exception:
            tickers = None

        self._inference_worker = InferenceWorker(tickers=tickers)
        self._inference_worker.error_occurred.connect(
            lambda msg: self._show_status(f"Inference Error: {msg}", 5000)
        )
        self._inference_worker.start()
        self._show_status("ML Inference running (loading production model)...")

    def _on_run_scanner(self):
        from frontend.gui.workers.async_workers import ScannerWorker
        try:
            from pipeline.storage import StorageManager
            tickers = StorageManager().get_available_tickers()
        except Exception:
            tickers = None

        self._scanner_worker = ScannerWorker(tickers=tickers)
        self._scanner_worker.error_occurred.connect(
            lambda msg: self._show_status(f"Scanner Error: {msg}", 5000)
        )
        self._scanner_worker.start()
        self._show_status("Scanner running...")

    def _show_status(self, msg: str, timeout: int = 3000):
        self.status_bar.showMessage(msg, timeout)
