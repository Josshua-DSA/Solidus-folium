"""
Folium Chart Canvas — Interactive Candlestick & Volume Chart Widget.

Built with PyQtGraph for high-performance 60 FPS rendering.
Supports:
- Candlestick OHLC bars (green/red Nord theme)
- Volume histogram linked to price X-axis
- SMA overlays (fast 5, slow 20)
- Interactive crosshair with price/date readout
- Ticker selector & timeframe switcher
"""
import sys
import os
from typing import Optional, List, Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QCheckBox, QSplitter,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPen, QBrush, QPainter, QPicture

from frontend.gui.workers.signal_bus import SignalBus

# ── Nord Colors for Charts ─────────────────────────────────────────
BG_COLOR       = "#2E3440"
PANEL_BG       = "#3B4252"
GRID_COLOR     = "#434C5E"
TEXT_COLOR     = "#D8DEE9"
CANDLE_BULL    = "#A3BE8C"   # Aurora Green
CANDLE_BEAR    = "#BF616A"   # Aurora Red
SMA_FAST_COLOR = "#88C0D0"   # Frost Cyan (SMA 5)
SMA_SLOW_COLOR = "#EBCB8B"   # Aurora Yellow (SMA 20)
VOLUME_BULL    = "#4C6B50"
VOLUME_BEAR    = "#703C42"
CROSSHAIR_COL  = "#81A1C1"   # Frost Blue
FROST_0        = "#8FBCBB"



# ═══════════════════════════════════════════════════════════════════
# Custom Candlestick Graphics Item (PyQtGraph)
# ═══════════════════════════════════════════════════════════════════

class CandlestickItem(pg.GraphicsObject):
    """Custom GraphicsObject to render OHLC candlesticks in a single draw pass."""

    def __init__(self, data=None):
        super().__init__()
        self.data = data  # list of (t, open, high, low, close)
        self.picture = QPicture()
        if data is not None:
            self.generatePicture()

    def set_data(self, data):
        self.data = data
        self.generatePicture()
        self.informViewBoundsChanged()
        self.update()

    def generatePicture(self):
        self.picture = QPicture()
        p = QPainter(self.picture)
        w = 0.35  # bar half-width

        pen_bull = QPen(QColor(CANDLE_BULL), 1.2)
        pen_bear = QPen(QColor(CANDLE_BEAR), 1.2)
        brush_bull = QBrush(QColor(CANDLE_BULL))
        brush_bear = QBrush(QColor(CANDLE_BEAR))

        for row in self.data:
            t, o, h, l, c = row[0], row[1], row[2], row[3], row[4]
            if c >= o:
                p.setPen(pen_bull)
                p.setBrush(brush_bull)
            else:
                p.setPen(pen_bear)
                p.setBrush(brush_bear)

            # Wick
            p.drawLine(pg.QtCore.QPointF(t, l), pg.QtCore.QPointF(t, h))

            # Body
            body_top = max(o, c)
            body_bot = min(o, c)
            body_h = max(body_top - body_bot, 0.001 * (h - l if h > l else 1))
            p.drawRect(pg.QtCore.QRectF(t - w, body_bot, w * 2, body_h))

        p.end()

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return pg.QtCore.QRectF(self.picture.boundingRect())


# ═══════════════════════════════════════════════════════════════════
# Chart Canvas Widget
# ═══════════════════════════════════════════════════════════════════

class ChartCanvasWidget(QWidget):
    """Main interactive charting canvas with OHLCV, indicators & crosshair."""

    ticker_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bus = SignalBus.instance()
        self.current_ticker = "BBCA.JK"
        self.df_data = None
        self.dates = []

        # Configure PyQtGraph global options for Nord theme
        pg.setConfigOptions(antialias=True, background=BG_COLOR, foreground=TEXT_COLOR)

        self._build_ui()
        self._load_available_tickers()
        self.load_ticker(self.current_ticker)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # ── Controls Bar ─────────────────────────────────────────
        ctrl_bar = QHBoxLayout()
        ctrl_bar.setContentsMargins(6, 4, 6, 4)

        ctrl_bar.addWidget(QLabel("Ticker:"))
        self.ticker_combo = QComboBox()
        self.ticker_combo.currentTextChanged.connect(self._on_ticker_selected)
        ctrl_bar.addWidget(self.ticker_combo)

        self.info_label = QLabel("O: —  H: —  L: —  C: —  Vol: —")
        self.info_label.setStyleSheet(f"color: {FROST_0}; font-weight: bold; padding: 0 10px;")
        ctrl_bar.addWidget(self.info_label)

        ctrl_bar.addStretch()

        # Indicators toggles
        self.sma5_cb = QCheckBox("SMA 5")
        self.sma5_cb.setChecked(True)
        self.sma5_cb.setStyleSheet(f"color: {SMA_FAST_COLOR}; font-weight: bold;")
        self.sma5_cb.toggled.connect(self._toggle_indicators)
        ctrl_bar.addWidget(self.sma5_cb)

        self.sma20_cb = QCheckBox("SMA 20")
        self.sma20_cb.setChecked(True)
        self.sma20_cb.setStyleSheet(f"color: {SMA_SLOW_COLOR}; font-weight: bold;")
        self.sma20_cb.toggled.connect(self._toggle_indicators)
        ctrl_bar.addWidget(self.sma20_cb)

        # Refresh button
        refresh_btn = QPushButton("⟳")
        refresh_btn.setToolTip("Reload chart data from database")
        refresh_btn.setFixedWidth(30)
        refresh_btn.clicked.connect(lambda: self.load_ticker(self.current_ticker))
        ctrl_bar.addWidget(refresh_btn)

        layout.addLayout(ctrl_bar)

        # ── PyQtGraph GraphicsLayoutWidget ───────────────────────
        self.glw = pg.GraphicsLayoutWidget()
        self.glw.setBackground(BG_COLOR)

        # 1. Price Plot (Candlestick + SMAs)
        self.price_plot = self.glw.addPlot(row=0, col=0)
        self.price_plot.showGrid(x=True, y=True, alpha=0.3)
        self.price_plot.setLabel('left', 'Price (IDR)')
        self.price_plot.getAxis('left').setTextPen(pg.mkPen(TEXT_COLOR))
        self.price_plot.getAxis('bottom').setTextPen(pg.mkPen(TEXT_COLOR))
        self.price_plot.getAxis('left').setPen(pg.mkPen(GRID_COLOR))
        self.price_plot.getAxis('bottom').setPen(pg.mkPen(GRID_COLOR))

        self.candle_item = CandlestickItem()
        self.price_plot.addItem(self.candle_item)

        # Indicator plot curves
        self.sma5_curve = self.price_plot.plot(pen=pg.mkPen(SMA_FAST_COLOR, width=1.5), name="SMA 5")
        self.sma20_curve = self.price_plot.plot(pen=pg.mkPen(SMA_SLOW_COLOR, width=1.5), name="SMA 20")

        # 2. Volume Plot (Bottom, linked X-axis)
        self.volume_plot = self.glw.addPlot(row=1, col=0)
        self.volume_plot.setMaximumHeight(100)
        self.volume_plot.showGrid(x=True, y=True, alpha=0.3)
        self.volume_plot.setLabel('left', 'Vol')
        self.volume_plot.getAxis('left').setTextPen(pg.mkPen(TEXT_COLOR))
        self.volume_plot.getAxis('bottom').setTextPen(pg.mkPen(TEXT_COLOR))
        self.volume_plot.getAxis('left').setPen(pg.mkPen(GRID_COLOR))
        self.volume_plot.getAxis('bottom').setPen(pg.mkPen(GRID_COLOR))
        self.volume_plot.setXLink(self.price_plot)

        # Crosshair lines
        self.v_line_price = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(CROSSHAIR_COL, width=0.8, style=Qt.PenStyle.DashLine))
        self.h_line_price = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen(CROSSHAIR_COL, width=0.8, style=Qt.PenStyle.DashLine))
        self.price_plot.addItem(self.v_line_price, ignoreBounds=True)
        self.price_plot.addItem(self.h_line_price, ignoreBounds=True)

        self.v_line_vol = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(CROSSHAIR_COL, width=0.8, style=Qt.PenStyle.DashLine))
        self.volume_plot.addItem(self.v_line_vol, ignoreBounds=True)

        # Mouse hover signal
        self.price_plot.scene().sigMouseMoved.connect(self._on_mouse_moved)

        layout.addWidget(self.glw)

    def _load_available_tickers(self):
        """Populate the ticker dropdown from SQLite StorageManager."""
        try:
            from pipeline.storage import StorageManager
            storage = StorageManager()
            tickers = storage.get_available_tickers()
            if not tickers:
                from pipeline.universe import UniverseManager
                tickers = UniverseManager(universe_name="lq45").get_tickers()
        except Exception:
            tickers = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "TLKM.JK", "ASII.JK"]

        self.ticker_combo.blockSignals(True)
        self.ticker_combo.clear()
        self.ticker_combo.addItems(tickers)
        if self.current_ticker in tickers:
            self.ticker_combo.setCurrentText(self.current_ticker)
        self.ticker_combo.blockSignals(False)

    def _on_ticker_selected(self, ticker: str):
        if ticker and ticker != self.current_ticker:
            self.current_ticker = ticker
            self.load_ticker(ticker)
            self.ticker_changed.emit(ticker)

    def load_ticker(self, ticker: str):
        """Fetch data from StorageManager and render candlestick + volume."""
        self.current_ticker = ticker
        df = None

        try:
            from pipeline.storage import StorageManager
            storage = StorageManager()
            df = storage.load_prices([ticker])
        except Exception:
            pass

        if df is None or df.empty:
            df = self._generate_fallback_data(ticker)

        df = df.sort_values("date").reset_index(drop=True)
        self.df_data = df

        # Prepare candlestick data tuples: (index, open, high, low, close)
        candle_data = []
        for i, row in df.iterrows():
            candle_data.append((
                i,
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
            ))

        self.candle_item.set_data(candle_data)

        # Volume bars
        self.volume_plot.clear()
        self.volume_plot.addItem(self.v_line_vol, ignoreBounds=True)

        closes = df["close"].values
        opens = df["open"].values
        vols = df["volume"].values if "volume" in df.columns else np.zeros(len(df))

        bull_idx = np.where(closes >= opens)[0]
        bear_idx = np.where(closes < opens)[0]

        if len(bull_idx) > 0:
            bull_bars = pg.BarGraphItem(
                x=bull_idx, height=vols[bull_idx], width=0.6,
                brush=pg.mkBrush(VOLUME_BULL), pen=pg.mkPen(CANDLE_BULL, width=0.5)
            )
            self.volume_plot.addItem(bull_bars)

        if len(bear_idx) > 0:
            bear_bars = pg.BarGraphItem(
                x=bear_idx, height=vols[bear_idx], width=0.6,
                brush=pg.mkBrush(VOLUME_BEAR), pen=pg.mkPen(CANDLE_BEAR, width=0.5)
            )
            self.volume_plot.addItem(bear_bars)

        # Compute SMAs
        close_s = pd.Series(closes)
        sma5 = close_s.rolling(5).mean().values
        sma20 = close_s.rolling(20).mean().values

        x_vals = np.arange(len(df))
        self.sma5_curve.setData(x_vals, sma5)
        self.sma20_curve.setData(x_vals, sma20)

        # Configure custom date axis strings
        self.dates = [str(d)[:10] for d in df["date"].values]
        x_axis = self.price_plot.getAxis('bottom')
        x_axis_vol = self.volume_plot.getAxis('bottom')

        # Sample ticks every N bars
        step = max(len(df) // 8, 1)
        ticks = [(i, self.dates[i]) for i in range(0, len(df), step)]
        x_axis.setTicks([ticks])
        x_axis_vol.setTicks([ticks])

        # Auto-range
        self.price_plot.autoRange()
        self.volume_plot.autoRange()

        # Update info header with latest candle
        if len(df) > 0:
            last = df.iloc[-1]
            c_val = float(last['close'])
            o_val = float(last['open'])
            diff = c_val - o_val
            diff_pct = (diff / o_val) * 100 if o_val > 0 else 0
            sign = "+" if diff >= 0 else ""
            color = CANDLE_BULL if diff >= 0 else CANDLE_BEAR

            self.info_label.setText(
                f"{ticker}  O: Rp {last['open']:,.0f}  H: Rp {last['high']:,.0f}  "
                f"L: Rp {last['low']:,.0f}  C: Rp {c_val:,.0f} ({sign}{diff_pct:.2f}%)  "
                f"Vol: {int(last.get('volume', 0)):,}"
            )
            self.info_label.setStyleSheet(f"color: {color}; font-weight: bold; padding: 0 10px;")

    def _toggle_indicators(self):
        self.sma5_curve.setVisible(self.sma5_cb.isChecked())
        self.sma20_curve.setVisible(self.sma20_cb.isChecked())

    def _on_mouse_moved(self, pos):
        """Update crosshair and info label on mouse hover."""
        if self.price_plot.sceneBoundingRect().contains(pos):
            mouse_point = self.price_plot.vb.mapSceneToView(pos)
            x = mouse_point.x()
            y = mouse_point.y()

            self.v_line_price.setPos(x)
            self.h_line_price.setPos(y)
            self.v_line_vol.setPos(x)

            idx = int(round(x))
            if self.df_data is not None and 0 <= idx < len(self.df_data):
                row = self.df_data.iloc[idx]
                dt = self.dates[idx] if idx < len(self.dates) else ""
                self.info_label.setText(
                    f"[{dt}] O: Rp {row['open']:,.0f}  H: Rp {row['high']:,.0f}  "
                    f"L: Rp {row['low']:,.0f}  C: Rp {row['close']:,.0f}  Vol: {int(row.get('volume', 0)):,}"
                )

    def _generate_fallback_data(self, ticker: str) -> pd.DataFrame:
        """Generate realistic synthetic OHLCV data if DB has no records."""
        np.random.seed(abs(hash(ticker)) % 10000)
        n = 120
        dates = pd.date_range(end=pd.Timestamp.today(), periods=n, freq="B")

        base_price = 5000.0 + (np.random.rand() - 0.5) * 4000.0
        returns = np.random.normal(0.0005, 0.015, n)
        prices = base_price * np.exp(np.cumsum(returns))

        highs = prices * (1 + np.abs(np.random.normal(0, 0.008, n)))
        lows = prices * (1 - np.abs(np.random.normal(0, 0.008, n)))
        opens = prices * (1 + np.random.normal(0, 0.004, n))
        volumes = np.random.randint(500_000, 20_000_000, n)

        return pd.DataFrame({
            "date": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": prices,
            "volume": volumes,
        })
