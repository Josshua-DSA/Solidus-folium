"""
Scanner Service — ML signal generation untuk TUI scanner panel.

Menggabungkan:
  - DataService untuk load harga
  - MomentumStrategy / MLSignalStrategy untuk generate sinyal
  - SignalCombiner untuk combine/rank

Design: Dependency Injection — model predictions di-inject dari luar
atau menggunakan momentum fallback jika model belum trained.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
import logging

from app.services.data_service import DataService
from app.strategies.momentum_strategy import MomentumStrategy
from app.strategies.ml_signal_strategy import MLSignalStrategy
from app.strategies.signal_combiner import SignalCombiner

logger = logging.getLogger(__name__)


class ScannerService:
    """
    Service layer untuk scanning dan ranking saham.

    Menggunakan strategy yang tersedia untuk generate dan rank sinyal.

    Args:
        data_service: DataService instance (atau None, auto-create)
        buy_threshold: Threshold minimum untuk sinyal BUY (0-1)
    """

    def __init__(
        self,
        data_service: Optional[DataService] = None,
        buy_threshold: float = 0.50,
    ):
        self.data_service = data_service or DataService()
        self.buy_threshold = buy_threshold

        # Strategies
        self.momentum = MomentumStrategy(fast_window=5, slow_window=20)
        self.ml_signal = MLSignalStrategy(
            buy_threshold=buy_threshold + 0.10,  # ML needs higher confidence
            sell_threshold=buy_threshold - 0.15,
        )
        self.combiner = SignalCombiner(buy_threshold=buy_threshold)
        self._loaded_model = None
        self._load_latest_model()

    def _load_latest_model(self) -> None:
        """Load model ML dari ModelRegistry (production → latest → glob fallback)."""
        import os
        import glob

        # Strategy 1: Load dari ModelRegistry (production model prioritas)
        try:
            from model.registry import ModelRegistry
            registry = ModelRegistry()
            data = registry.load_model(model_type="xgboost")
            if data is not None and "model" in data:
                from model.xgboost_trainer import XGBoostTrainer
                trainer = XGBoostTrainer()
                trainer.model = data["model"]
                trainer.config = data.get("config", trainer.config)
                trainer.feature_names = data.get("feature_names")
                trainer.best_params = data.get("best_params")
                self._loaded_model = trainer
                logger.info("ScannerService loaded model from ModelRegistry (production/latest)")
                return
        except Exception as e:
            logger.debug("ModelRegistry load failed, falling back to glob: %s", e)

        # Strategy 2: Fallback ke glob artifacts/saved_models/*.pkl
        model_dir = "artifacts/saved_models"
        if not os.path.exists(model_dir):
            return

        files = glob.glob(os.path.join(model_dir, "*.pkl"))
        if not files:
            return

        files.sort(key=os.path.getmtime, reverse=True)
        latest_file = files[0]
        try:
            from model.xgboost_trainer import XGBoostTrainer
            trainer = XGBoostTrainer()
            self._loaded_model = trainer.load(latest_file)
            logger.info("ScannerService loaded model from glob fallback: %s", latest_file)
        except Exception as e:
            logger.warning("Failed to load model artifact %s: %s", latest_file, e)

    def scan_momentum(
        self,
        tickers: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Scan semua ticker menggunakan momentum strategy.

        Args:
            tickers: Filter ticker (None = semua di DB)

        Returns:
            List of signal dicts sorted by score descending:
            [{"ticker", "price", "score", "signal", "fast_mom", "slow_mom"}, ...]
        """
        close_prices = self.data_service.get_close_prices(tickers)
        if close_prices.empty:
            logger.warning("No price data available for scanning")
            return []

        signals_df = self.momentum.generate_signals(close_prices)
        results = []

        for ticker in close_prices.columns:
            close = close_prices[ticker].dropna()
            if len(close) < 21:
                continue

            score = self.momentum.score_ticker(close)
            last_price = float(close.iloc[-1])

            # Hitung momentum values
            fast_mom = float(close.pct_change(self.momentum.fast_window).iloc[-1])
            slow_mom = float(close.pct_change(self.momentum.slow_window).iloc[-1])

            # Determine signal
            last_signal = int(signals_df[ticker].iloc[-1]) if ticker in signals_df else 0
            if last_signal == 1:
                action = "BUY"
            elif last_signal == -1:
                action = "SELL"
            else:
                action = "HOLD"

            results.append({
                "ticker": ticker,
                "price": last_price,
                "score": score,
                "signal": action,
                "fast_mom": fast_mom,
                "slow_mom": slow_mom,
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def scan_ml(
        self,
        ml_predictions: pd.DataFrame,
        tickers: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Scan menggunakan ML predictions.

        Args:
            ml_predictions: DataFrame P(PROFIT) (index=date, columns=ticker)
            tickers: Filter ticker (None = semua)

        Returns:
            List of signal dicts sorted by P(PROFIT) descending
        """
        close_prices = self.data_service.get_close_prices(tickers)
        if close_prices.empty or ml_predictions.empty:
            return []

        signals_df = self.ml_signal.generate_signals(
            close_prices, ml_predictions=ml_predictions
        )
        ranked = self.ml_signal.rank_by_probability(ml_predictions)

        results = []
        for _, row in ranked.iterrows():
            ticker = row["ticker"]
            close = close_prices.get(ticker)
            if close is None:
                continue

            last_price = float(close.dropna().iloc[-1]) if not close.dropna().empty else 0.0

            results.append({
                "ticker": ticker,
                "price": last_price,
                "score": float(row["p_profit"]),
                "signal": row["signal"],
            })

        return results

    def scan_combined(
        self,
        ml_predictions: Optional[pd.DataFrame] = None,
        tickers: Optional[List[str]] = None,
        momentum_weight: float = 0.40,
        ml_weight: float = 0.60,
    ) -> List[Dict[str, Any]]:
        """
        Scan gabungan momentum + ML (jika tersedia).
        Jika ml_predictions None tapi _loaded_model ada, generate ML predictions otomatis.
        """
        if ml_predictions is None and self._loaded_model is not None:
            try:
                from shared.features.feature_builder import FeatureBuilder
                close_prices = self.data_service.get_close_prices(tickers)
                if not close_prices.empty:
                    fb = FeatureBuilder()
                    ml_preds_dict = {}
                    for t in close_prices.columns:
                        ohlc = pd.DataFrame({
                            "open": close_prices[t],
                            "high": close_prices[t] * 1.002,
                            "low": close_prices[t] * 0.998,
                            "close": close_prices[t],
                            "volume": 1000000
                        })
                        tf = fb.build_technical_features(ohlc).dropna()
                        if not tf.empty:
                            probas = self._loaded_model.predict_proba(tf.values[-1:])
                            # proba PROFIT index 2 or 1
                            p_profit = probas[0][-1] if probas.shape[1] > 1 else probas[0][0]
                            ml_preds_dict[t] = p_profit
                    if ml_preds_dict:
                        ml_predictions = pd.DataFrame([ml_preds_dict], index=[close_prices.index[-1]])
            except Exception as e:
                logger.warning("Auto inference failed: %s", e)

        mom_results = self.scan_momentum(tickers)

        if ml_predictions is not None and not ml_predictions.empty:
            ml_results = self.scan_ml(ml_predictions, tickers)
            ml_scores = {r["ticker"]: r["score"] for r in ml_results}
        else:
            ml_scores = {}

        combined = []
        for item in mom_results:
            ticker = item["ticker"]
            mom_score = item["score"]
            ml_score = ml_scores.get(ticker, 0.5)  # neutral default

            if ml_scores:
                combined_score = momentum_weight * mom_score + ml_weight * ml_score
            else:
                combined_score = mom_score

            # Determine final action based on combined score
            if combined_score >= self.buy_threshold + 0.10:
                action = "BUY"
            elif combined_score <= self.buy_threshold - 0.15:
                action = "SELL"
            else:
                action = "HOLD"

            combined.append({
                "ticker": ticker,
                "price": item["price"],
                "score": combined_score,
                "momentum_score": mom_score,
                "ml_score": ml_score,
                "signal": action,
            })

        combined.sort(key=lambda x: x["score"], reverse=True)
        return combined

    def __repr__(self) -> str:
        return f"ScannerService(threshold={self.buy_threshold})"
