"""
Base Strategy — Abstract base class untuk semua trading strategy.

Setiap strategy (Tier 1 & Tier 2 dari STRATEGY.md) harus extend class ini.
Tier 1: Dapat dikuantifikasi, diizinkan di bot mode.
Tier 2: Diskresioner, hanya advisory layer di mode manual.
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """
    Abstract base class untuk trading strategies.

    Subclass harus mengimplementasikan:
        - generate_signals(): menghasilkan sinyal BUY/SELL/HOLD
        - name (property): nama unik strategy

    Attributes:
        tier: 1 (quantifiable, bot-ready) atau 2 (discretionary, advisory only)
        mode: 'day_trading' atau 'investment'
    """

    def __init__(
        self,
        tier: int = 1,
        mode: str = "day_trading",
        config: Optional[Dict[str, Any]] = None,
    ):
        if tier not in (1, 2):
            raise ValueError(f"Tier harus 1 atau 2, got: {tier}")
        if mode not in ("day_trading", "investment"):
            raise ValueError(f"Mode harus 'day_trading' atau 'investment', got: {mode}")

        self.tier = tier
        self.mode = mode
        self.config = config or {}

    @property
    @abstractmethod
    def name(self) -> str:
        """Nama unik strategy (dipakai oleh StrategyRegistry)."""
        ...

    @abstractmethod
    def generate_signals(
        self,
        prices: pd.DataFrame,
        features: Optional[pd.DataFrame] = None,
        ml_predictions: Optional[pd.Series] = None,
    ) -> pd.DataFrame:
        """
        Generate trading signals.

        Args:
            prices: DataFrame OHLCV (long atau wide format)
            features: Optional fitur teknikal/fundamental
            ml_predictions: Optional ML model predictions (P(PROFIT))

        Returns:
            DataFrame dengan kolom: ticker, date, signal, score
            signal: 'BUY', 'SELL', 'HOLD'
            score: confidence score 0-1
        """
        ...

    def is_bot_eligible(self) -> bool:
        """Apakah strategy ini boleh dipakai di bot mode (hanya Tier 1)."""
        return self.tier == 1

    def __repr__(self) -> str:
        return f"{self.name}(tier={self.tier}, mode={self.mode})"
