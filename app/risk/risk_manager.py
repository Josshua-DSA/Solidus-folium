"""
Risk Manager — Kontrol risiko pre-trade dan post-trade.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Manajemen risiko portofolio dengan constraint IDX.

    Args:
        max_position_pct: Bobot maksimum per posisi (default 10%)
        max_sector_pct: Bobot maksimum per sektor (default 30%)
        max_drawdown_stop: Trigger stop-loss pada drawdown (default -15%)
        daily_loss_limit: Batas kerugian harian (default -3%)
        max_portfolio_var_95: Value at Risk 95% maksimum (default -2%)
    """

    def __init__(
        self,
        max_position_pct: float = 0.10,
        max_sector_pct: float = 0.30,
        max_drawdown_stop: float = -0.15,
        daily_loss_limit: float = -0.03,
        max_portfolio_var_95: float = -0.02,
    ):
        self.max_position_pct = max_position_pct
        self.max_sector_pct = max_sector_pct
        self.max_drawdown_stop = max_drawdown_stop
        self.daily_loss_limit = daily_loss_limit
        self.max_portfolio_var_95 = max_portfolio_var_95

    # ------------------------------------------------------------------
    # Pre-trade checks
    # ------------------------------------------------------------------

    def check_position_limit(
        self, weights: np.ndarray, tickers: List[str]
    ) -> Dict[str, bool]:
        """
        Cek apakah ada posisi yang melebihi batas.

        Returns:
            Dict ticker -> True jika lolos, False jika melanggar
        """
        results = {}
        for i, ticker in enumerate(tickers):
            results[ticker] = weights[i] <= self.max_position_pct

        violations = {t: w for t, w in zip(tickers, weights) if w > self.max_position_pct}
        if violations:
            logger.warning("Position limit violated: %s", violations)

        return results

    def check_daily_loss(
        self, daily_return: float
    ) -> bool:
        """
        Cek apakah kerugian harian melebihi batas.

        Returns:
            True jika aman, False jika stop triggered
        """
        if daily_return < self.daily_loss_limit:
            logger.warning(
                "Daily loss limit triggered: %.2f%% (limit: %.2f%%)",
                daily_return * 100, self.daily_loss_limit * 100,
            )
            return False
        return True

    def check_drawdown(
        self, equity_curve: pd.Series
    ) -> bool:
        """
        Cek apakah max drawdown melebihi batas.

        Returns:
            True jika aman, False jika stop triggered
        """
        if equity_curve.empty or len(equity_curve) < 2:
            return True

        cum_max = equity_curve.cummax()
        drawdown = (equity_curve - cum_max) / cum_max
        current_dd = drawdown.iloc[-1]

        if current_dd < self.max_drawdown_stop:
            logger.warning(
                "Max drawdown stop triggered: %.2f%% (limit: %.2f%%)",
                current_dd * 100, self.max_drawdown_stop * 100,
            )
            return False
        return True

    def calculate_var_95(
        self, returns: np.ndarray
    ) -> float:
        """
        Hitung Value at Risk 95% menggunakan historical method.

        Args:
            returns: Array return historis

        Returns:
            VaR 95% (negatif = loss)
        """
        if len(returns) < 20:
            return 0.0
        return float(np.percentile(returns, 5))

    def validate_portfolio(
        self,
        weights: np.ndarray,
        tickers: List[str],
        equity_curve: Optional[pd.Series] = None,
        daily_return: Optional[float] = None,
    ) -> Dict[str, bool]:
        """
        Validasi komprehensif seluruh constraint risiko.

        Returns:
            Dict check_name -> True/False
        """
        results = {
            "position_limits": all(
                self.check_position_limit(weights, tickers).values()
            ),
        }

        if daily_return is not None:
            results["daily_loss"] = self.check_daily_loss(daily_return)

        if equity_curve is not None:
            results["drawdown"] = self.check_drawdown(equity_curve)

        all_passed = all(results.values())
        if not all_passed:
            logger.warning("Risk check FAILED: %s", results)
        else:
            logger.info("All risk checks passed")

        return results

    def __repr__(self) -> str:
        return (
            f"RiskManager(max_pos={self.max_position_pct:.0%}, "
            f"max_dd={self.max_drawdown_stop:.0%}, "
            f"daily_limit={self.daily_loss_limit:.0%})"
        )
