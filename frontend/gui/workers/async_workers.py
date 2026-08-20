"""
Folium Async Workers — QThread-based background workers for heavy engine tasks.

Workers emit progress/result signals through the global SignalBus so the
GUI main thread never freezes. Each worker wraps an existing backend service
from app/ or pipeline/.

Usage:
    worker = BacktestWorker(strategy="momentum", tickers=["BBCA.JK"])
    worker.start()
    # Results arrive via SignalBus.instance().backtest_completed signal
"""
import sys
import os
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from PyQt6.QtCore import QThread, QRunnable, QObject, pyqtSignal, pyqtSlot

from frontend.gui.workers.signal_bus import SignalBus


# ═══════════════════════════════════════════════════════════════════
# Base Worker
# ═══════════════════════════════════════════════════════════════════

class BaseWorker(QThread):
    """Abstract base for threaded engine workers."""

    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bus = SignalBus.instance()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self.do_work()
        except Exception as e:
            tb = traceback.format_exc()
            self.error_occurred.emit(f"{e}\n{tb}")


# ═══════════════════════════════════════════════════════════════════
# Backtest Worker
# ═══════════════════════════════════════════════════════════════════

class BacktestWorker(BaseWorker):
    """Run BacktestService.run_momentum_backtest() off the main thread."""

    def __init__(
        self,
        strategy: str = "momentum",
        tickers: list = None,
        initial_capital: float = 100_000_000,
        parent=None,
    ):
        super().__init__(parent)
        self.strategy = strategy
        self.tickers = tickers or []
        self.initial_capital = initial_capital

    def do_work(self):
        self.bus.backtest_started.emit(self.strategy)
        self.bus.backtest_progress.emit(5)

        from app.services.backtest_service import BacktestService

        bt = BacktestService(initial_capital=self.initial_capital)
        self.bus.backtest_progress.emit(15)

        if self._cancelled:
            return

        if self.strategy == "momentum":
            result = bt.run_momentum_backtest(tickers=self.tickers)
        elif self.strategy == "ml_signal":
            # ML backtest requires predictions — fallback to momentum
            result = bt.run_momentum_backtest(tickers=self.tickers)
        else:
            result = bt.run_momentum_backtest(tickers=self.tickers)

        self.bus.backtest_progress.emit(95)

        if self._cancelled:
            return

        self.bus.backtest_completed.emit(result)
        self.bus.backtest_progress.emit(100)


# ═══════════════════════════════════════════════════════════════════
# Scanner Worker
# ═══════════════════════════════════════════════════════════════════

class ScannerWorker(BaseWorker):
    """Run ScannerService.scan_momentum() off the main thread."""

    def __init__(self, tickers: list = None, parent=None):
        super().__init__(parent)
        self.tickers = tickers

    def do_work(self):
        self.bus.scanner_started.emit()

        from app.services.scanner_service import ScannerService

        scanner = ScannerService()
        signals = scanner.scan_momentum(tickers=self.tickers)

        if self._cancelled:
            return

        self.bus.scanner_updated.emit(signals)


# ═══════════════════════════════════════════════════════════════════
# Data Fetch Worker
# ═══════════════════════════════════════════════════════════════════

class DataFetchWorker(BaseWorker):
    """Fetch market data via DataFetcher + StorageManager off the main thread."""

    def __init__(self, tickers: list = None, period: str = "max", parent=None):
        super().__init__(parent)
        self.tickers = tickers or []
        self.period = period

    def do_work(self):
        self.bus.fetch_started.emit(f"Fetching {len(self.tickers)} tickers")
        self.bus.fetch_progress.emit(5)

        from pipeline.fetcher import DataFetcher
        from pipeline.storage import StorageManager

        fetcher = DataFetcher(tickers=self.tickers)
        storage = StorageManager()
        total_rows = 0

        for i, ticker in enumerate(self.tickers):
            if self._cancelled:
                return

            pct = int((i / max(len(self.tickers), 1)) * 90) + 5
            self.bus.fetch_progress.emit(pct)

            try:
                df = fetcher.fetch_single(ticker, period=self.period)
                if df is not None and not df.empty:
                    storage.save_prices(df, ticker)
                    total_rows += len(df)
            except Exception:
                pass

        self.bus.fetch_progress.emit(100)
        self.bus.fetch_completed.emit(total_rows)


# ═══════════════════════════════════════════════════════════════════
# ML Training Worker
# ═══════════════════════════════════════════════════════════════════

class TrainingWorker(BaseWorker):
    """Run ML model training off the main thread."""

    def __init__(self, model_type: str = "xgboost", parent=None):
        super().__init__(parent)
        self.model_type = model_type

    def do_work(self):
        self.bus.training_started.emit(self.model_type)
        self.bus.training_progress.emit(5, "Loading data...")

        from model.trainer import ModelTrainer
        from pipeline.storage import StorageManager

        storage = StorageManager()
        tickers = storage.get_available_tickers()

        if not tickers:
            self.bus.training_error.emit("No ticker data in database")
            return

        self.bus.training_progress.emit(15, "Building features...")

        trainer = ModelTrainer(model_type=self.model_type)

        if self._cancelled:
            return

        self.bus.training_progress.emit(30, f"Training {self.model_type}...")

        try:
            result = trainer.train(tickers=tickers[:10])
        except Exception as e:
            self.bus.training_error.emit(str(e))
            return

        if self._cancelled:
            return

        self.bus.training_progress.emit(95, "Registering model...")
        self.bus.training_completed.emit({
            "model_type": self.model_type,
            "result": str(result),
        })
        self.bus.training_progress.emit(100, "Done")
