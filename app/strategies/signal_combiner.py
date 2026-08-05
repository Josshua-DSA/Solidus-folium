"""
Signal Combiner — Menggabungkan sinyal dari ML model dan strategy.
Refactored dari backend/signals/combiner.py.
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class SignalCombiner:
    """
    Combines signals. In the ML architecture, this primarily
    validates and formats the model output (P(PROFIT)) into actionable signals.
    """

    def __init__(self, buy_threshold: float = 0.5, config: Optional[Dict] = None):
        self.buy_threshold = buy_threshold
        self.config = config or {}

    def calculate_signals(
        self,
        df: pd.DataFrame,
        ml_predictions: Optional[pd.Series] = None,
    ) -> pd.DataFrame:
        """
        Derive final signals from ML predictions.

        Args:
            df: OHLCV DataFrame
            ml_predictions: Series of P(Class 2 = PROFIT) [0-1]

        Returns:
            DataFrame with composite_score and signal columns added
        """
        df = df.copy()
        df["composite_score"] = 0.0
        df["signal"] = "HOLD"

        if ml_predictions is not None:
            common_idx = df.index.intersection(ml_predictions.index)
            if not common_idx.empty:
                probs = ml_predictions.loc[common_idx]
                df.loc[common_idx, "composite_score"] = probs
                df.loc[df["composite_score"] > self.buy_threshold, "signal"] = "BUY"

        return df

    def rank_stocks(
        self,
        data: Dict[str, pd.DataFrame],
        ml_predictions: Optional[Dict[str, pd.Series]] = None,
    ) -> pd.DataFrame:
        """
        Rank stocks based on ML scores.

        Args:
            data: Dict ticker -> OHLCV DataFrame
            ml_predictions: Dict ticker -> prediction Series

        Returns:
            DataFrame ranked by composite_score descending
        """
        rankings = []
        for ticker, df in data.items():
            if len(df) < 20:
                continue

            ml_pred = ml_predictions.get(ticker) if ml_predictions else None

            if ml_pred is not None and not ml_pred.empty:
                latest_score = ml_pred.iloc[-1]
                latest_price = df["close"].iloc[-1]

                rankings.append({
                    "ticker": ticker,
                    "price": latest_price,
                    "composite_score": latest_score,
                    "signal": "BUY" if latest_score > self.buy_threshold else "HOLD",
                    "date": df["date"].iloc[-1],
                })

        if not rankings:
            return pd.DataFrame()

        return pd.DataFrame(rankings).sort_values("composite_score", ascending=False)

    def __repr__(self) -> str:
        return f"SignalCombiner(threshold={self.buy_threshold})"
