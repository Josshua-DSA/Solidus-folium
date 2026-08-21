"""
Folium Inference Worker — Load Production Model & Generate Live Predictions.

Runs ScannerService.scan_combined() with auto-loaded production model
from ModelRegistry on a background QThread. Results are emitted through
SignalBus.scanner_updated for GUI consumption.

Usage:
    worker = InferenceWorker(tickers=["BBCA.JK", "BBRI.JK"])
    worker.start()
    # Results arrive via SignalBus.instance().scanner_updated
"""
import sys
import os
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from PyQt6.QtCore import QThread, pyqtSignal

from frontend.gui.workers.signal_bus import SignalBus


class InferenceWorker(QThread):
    """Background thread: load production ML model and run live inference."""

    error_occurred = pyqtSignal(str)

    def __init__(self, tickers: list = None, parent=None):
        super().__init__(parent)
        self.bus = SignalBus.instance()
        self.tickers = tickers
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self._do_inference()
        except Exception as e:
            tb = traceback.format_exc()
            self.error_occurred.emit(f"{e}\n{tb}")
            self.bus.scanner_error.emit(str(e))

    def _do_inference(self):
        self.bus.scanner_started.emit()

        # 1. Load tickers
        tickers = self.tickers
        if not tickers:
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

        if self._cancelled:
            return

        # 2. Attempt to load production model from ModelRegistry
        ml_predictions = None
        model_info = "No production model"
        try:
            from model.registry import ModelRegistry
            registry = ModelRegistry()
            model_artifact = registry.load_model(stage="production")

            if model_artifact is not None:
                model = model_artifact
                model_info = "Production model loaded"

                # Build features for prediction
                from pipeline.storage import StorageManager
                from model.features import FeatureBuilder

                storage = StorageManager()
                closes = storage.load_close_prices(tickers=tickers)

                if not closes.empty:
                    import pandas as pd
                    fb = FeatureBuilder()
                    predictions_list = []

                    for ticker in tickers:
                        if self._cancelled:
                            return
                        if ticker not in closes.columns:
                            continue
                        try:
                            series = closes[ticker].dropna()
                            if len(series) < 30:
                                continue
                            features = fb.build_features_dict(series)
                            feat_df = pd.DataFrame([features])

                            if hasattr(model, 'predict_proba'):
                                proba = model.predict_proba(feat_df)[0]
                                pred_class = proba.argmax()
                                confidence = float(proba.max())
                            elif hasattr(model, 'predict'):
                                pred = model.predict(feat_df)[0]
                                pred_class = int(pred)
                                confidence = 0.5
                            else:
                                continue

                            predictions_list.append({
                                "ticker": ticker,
                                "prediction": pred_class,
                                "confidence": confidence,
                            })
                        except Exception:
                            continue

                    if predictions_list:
                        ml_predictions = pd.DataFrame(predictions_list)
                        model_info = f"Production model: {len(predictions_list)} predictions"
        except Exception:
            pass

        if self._cancelled:
            return

        # 3. Run ScannerService.scan_combined (momentum + ML hybrid)
        from app.services.scanner_service import ScannerService
        scanner = ScannerService()

        try:
            signals = scanner.scan_combined(
                ml_predictions=ml_predictions,
                tickers=tickers,
            )
        except Exception:
            # Fallback to momentum-only scan
            signals = scanner.scan_momentum(tickers=tickers)

        if self._cancelled:
            return

        # Annotate signals with model info
        for sig in signals:
            sig["model_info"] = model_info

        self.bus.scanner_updated.emit(signals)
        self.bus.status_message.emit(f"Inference complete: {len(signals)} signals ({model_info})", 5000)
