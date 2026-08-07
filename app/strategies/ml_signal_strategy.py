"""
ML Signal Strategy — Tier 1 Quantifiable Strategy.

Sinyal BUY/SELL berdasarkan output prediksi model ML:
  - Input: P(PROFIT) dari model ensemble (XGBoost + LSTM)
  - BUY: P(PROFIT) > buy_threshold
  - SELL: P(PROFIT) < sell_threshold ATAU P(LOSS) > loss_threshold

Design: Dependency Injection — menerima predictions dari luar,
TIDAK import model/ langsung (sesuai ARCHITECTURE.md).

Layer 4-6: app/strategies/ — Strategy Engine.
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

from app.strategies.base_strategy import BaseStrategy
from app.strategies.strategy_registry import register_strategy

logger = logging.getLogger(__name__)


@register_strategy
class MLSignalStrategy(BaseStrategy):
    """
    ML-based signal strategy — Tier 1 (bot-eligible).

    Menggunakan output probabilitas dari ML model untuk generate sinyal.
    Predictions di-inject dari luar via generate_signals(ml_predictions=...).

    Args:
        buy_threshold: Minimum P(PROFIT) untuk BUY (default 0.60)
        sell_threshold: P(PROFIT) di bawah ini → SELL (default 0.35)
        min_holding_days: Minimum holding period sebelum boleh SELL (default 1)
        config: Optional additional config dict
    """

    def __init__(
        self,
        buy_threshold: float = 0.60,
        sell_threshold: float = 0.35,
        min_holding_days: int = 1,
        config: Optional[Dict] = None,
    ):
        super().__init__(tier=1, mode="day_trading", config=config)
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.min_holding_days = min_holding_days

    @property
    def name(self) -> str:
        return "ml_signal"

    def generate_signals(
        self,
        prices: pd.DataFrame,
        features: Optional[pd.DataFrame] = None,
        ml_predictions: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Generate sinyal BUY/SELL/HOLD dari ML predictions.

        Args:
            prices: DataFrame wide format (index=date, columns=ticker)
            features: Tidak digunakan langsung
            ml_predictions: DataFrame P(PROFIT) same shape as prices.
                           Values 0-1 (probabilitas kelas PROFIT).
                           Bisa juga pd.Series jika single ticker.

        Returns:
            DataFrame sinyal (same shape as prices)
            Values: 1 (BUY), -1 (SELL), 0 (HOLD)
        """
        if prices.empty:
            return pd.DataFrame()

        signals = pd.DataFrame(0, index=prices.index, columns=prices.columns)

        if ml_predictions is None:
            logger.warning("ml_predictions is None — no signals generated")
            return signals

        # Handle Series → DataFrame conversion
        if isinstance(ml_predictions, pd.Series):
            ml_predictions = ml_predictions.to_frame()

        for ticker in prices.columns:
            if ticker not in ml_predictions.columns:
                continue

            probs = ml_predictions[ticker]

            # Align to price index
            common_idx = prices.index.intersection(probs.index)
            if len(common_idx) == 0:
                continue

            in_position = False
            entry_idx = None

            for i, date in enumerate(common_idx):
                prob = probs.loc[date]
                if pd.isna(prob):
                    continue

                if not in_position and prob >= self.buy_threshold:
                    signals.loc[date, ticker] = 1
                    in_position = True
                    entry_idx = i
                elif in_position and prob <= self.sell_threshold:
                    # Check minimum holding period
                    if entry_idx is not None and (i - entry_idx) >= self.min_holding_days:
                        signals.loc[date, ticker] = -1
                        in_position = False
                        entry_idx = None

        logger.info(
            "MLSignalStrategy signals: %d BUY, %d SELL (threshold=%.2f/%.2f)",
            (signals == 1).sum().sum(),
            (signals == -1).sum().sum(),
            self.buy_threshold,
            self.sell_threshold,
        )

        return signals

    def rank_by_probability(
        self,
        ml_predictions: pd.DataFrame,
        top_n: int = 10,
    ) -> pd.DataFrame:
        """
        Rank tickers berdasarkan P(PROFIT) terbaru.

        Args:
            ml_predictions: DataFrame P(PROFIT) (index=date, columns=ticker)
            top_n: Jumlah top picks

        Returns:
            DataFrame ranked descending by latest P(PROFIT)
        """
        if ml_predictions.empty:
            return pd.DataFrame()

        latest = ml_predictions.iloc[-1].dropna()
        ranked = latest.sort_values(ascending=False).head(top_n)

        result = pd.DataFrame({
            "ticker": ranked.index,
            "p_profit": ranked.values,
            "signal": ["BUY" if p >= self.buy_threshold else "HOLD" for p in ranked.values],
        })

        return result
