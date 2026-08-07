"""
Momentum Strategy — Tier 1 Quantifiable Strategy.

Sinyal BUY/SELL berdasarkan momentum cross:
  - BUY: Return jangka pendek (fast) > Return jangka panjang (slow) DAN positif
  - SELL: Return jangka pendek < 0 ATAU crossover negatif

Configurable windows:
  - fast_window: Momentum cepat (default 5 hari)
  - slow_window: Momentum lambat (default 20 hari)
  - entry_threshold: Minimum momentum positif untuk BUY (default 0.0)

Reference:
  Jegadeesh & Titman (1993). "Returns to Buying Winners and Selling Losers."
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

from app.strategies.base_strategy import BaseStrategy
from app.strategies.strategy_registry import register_strategy

logger = logging.getLogger(__name__)


@register_strategy
class MomentumStrategy(BaseStrategy):
    """
    Momentum crossover strategy — Tier 1 (bot-eligible).

    Menggunakan dual-momentum: fast vs slow window.
    BUY ketika fast momentum crossover di atas slow momentum
    dan keduanya positif. SELL ketika crossover negatif.

    Args:
        fast_window: Window momentum cepat (default 5)
        slow_window: Window momentum lambat (default 20)
        entry_threshold: Minimum fast momentum untuk entry (default 0.0)
        config: Optional additional config dict
    """

    def __init__(
        self,
        fast_window: int = 5,
        slow_window: int = 20,
        entry_threshold: float = 0.0,
        config: Optional[Dict] = None,
    ):
        super().__init__(tier=1, mode="day_trading", config=config)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.entry_threshold = entry_threshold

    @property
    def name(self) -> str:
        return "momentum"

    def generate_signals(
        self,
        prices: pd.DataFrame,
        features: Optional[pd.DataFrame] = None,
        ml_predictions: Optional[pd.Series] = None,
    ) -> pd.DataFrame:
        """
        Generate sinyal BUY/SELL/HOLD dari momentum crossover.

        Args:
            prices: DataFrame wide format (index=date, columns=ticker)
                    berisi close prices.
            features: Tidak digunakan oleh strategy ini
            ml_predictions: Tidak digunakan oleh strategy ini

        Returns:
            DataFrame sinyal (same shape as prices)
            Values: 1 (BUY), -1 (SELL), 0 (HOLD)
        """
        if prices.empty:
            return pd.DataFrame()

        signals = pd.DataFrame(0, index=prices.index, columns=prices.columns)

        for ticker in prices.columns:
            close = prices[ticker].dropna()
            if len(close) < self.slow_window + 1:
                continue

            # Hitung momentum (rate of change)
            fast_mom = close.pct_change(self.fast_window)
            slow_mom = close.pct_change(self.slow_window)

            # BUY: fast > slow, fast > threshold, keduanya positif
            buy_mask = (
                (fast_mom > slow_mom)
                & (fast_mom > self.entry_threshold)
                & (slow_mom > 0)
            )

            # SELL: fast < 0 dan fast cross below slow
            sell_mask = (fast_mom < 0) & (fast_mom < slow_mom)

            # Apply: hanya transisi (avoid repeated BUY/SELL)
            in_position = False
            for i, date in enumerate(close.index):
                if date not in signals.index:
                    continue

                if not in_position and buy_mask.get(date, False):
                    signals.loc[date, ticker] = 1
                    in_position = True
                elif in_position and sell_mask.get(date, False):
                    signals.loc[date, ticker] = -1
                    in_position = False

        logger.info(
            "MomentumStrategy signals: %d BUY, %d SELL across %d tickers",
            (signals == 1).sum().sum(),
            (signals == -1).sum().sum(),
            len(prices.columns),
        )

        return signals

    def score_ticker(self, close: pd.Series) -> float:
        """
        Hitung momentum score untuk satu ticker (0-1 range).

        Berguna untuk ranking di scanner.

        Args:
            close: Close price series

        Returns:
            Score 0-1 (1 = very bullish momentum)
        """
        if len(close) < self.slow_window + 1:
            return 0.0

        fast_mom = close.pct_change(self.fast_window).iloc[-1]
        slow_mom = close.pct_change(self.slow_window).iloc[-1]

        if pd.isna(fast_mom) or pd.isna(slow_mom):
            return 0.0

        # Normalize: sigmoid-like mapping to 0-1
        raw_score = (fast_mom + slow_mom) / 2
        score = 1 / (1 + np.exp(-raw_score * 100))
        return float(np.clip(score, 0.0, 1.0))
