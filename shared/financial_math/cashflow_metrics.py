"""
Cashflow Metrics — Pure math untuk cashflow, ratio, dan return calculation.
Refactored dari backend/financial_engine/ dan backend/fundamental_component/.

Stateless, zero external layer dependency.
"""
import numpy as np
from decimal import Decimal, ROUND_HALF_UP
from typing import Union, Optional
import logging

logger = logging.getLogger(__name__)


class CashflowMetrics:
    """
    Pure-math module untuk financial ratio dan return calculation.
    Semua method bersifat stateless (static / classmethod).
    """

    # ------------------------------------------------------------------
    # Return calculations
    # ------------------------------------------------------------------

    @staticmethod
    def log_return(price_current: float, price_previous: float) -> float:
        """Hitung log return: ln(P_t / P_{t-1})."""
        if price_previous <= 0 or price_current <= 0:
            return 0.0
        return float(np.log(price_current / price_previous))

    @staticmethod
    def simple_return(price_current: float, price_previous: float) -> float:
        """Hitung simple return: (P_t - P_{t-1}) / P_{t-1}."""
        if price_previous <= 0:
            return 0.0
        return (price_current - price_previous) / price_previous

    @staticmethod
    def annualized_return(total_return: float, n_periods: int, periods_per_year: int = 252) -> float:
        """
        Annualize a total return.

        Args:
            total_return: Total return (e.g. 0.25 = 25%)
            n_periods: Number of periods observed
            periods_per_year: Trading days per year

        Returns:
            Annualized return
        """
        if n_periods <= 0:
            return 0.0
        years = n_periods / periods_per_year
        return (1 + total_return) ** (1 / years) - 1

    # ------------------------------------------------------------------
    # Risk metrics
    # ------------------------------------------------------------------

    @staticmethod
    def sharpe_ratio(
        returns: np.ndarray,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
    ) -> float:
        """Annualized Sharpe Ratio."""
        if len(returns) < 2 or np.std(returns) == 0:
            return 0.0
        excess = returns - risk_free_rate / periods_per_year
        return float(np.mean(excess) / np.std(excess) * np.sqrt(periods_per_year))

    @staticmethod
    def sortino_ratio(
        returns: np.ndarray,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
    ) -> float:
        """Annualized Sortino Ratio (downside deviation only)."""
        if len(returns) < 2:
            return 0.0
        excess = returns - risk_free_rate / periods_per_year
        downside = np.minimum(excess, 0)
        downside_std = np.std(downside)
        if downside_std == 0:
            return 0.0
        return float(np.mean(excess) / downside_std * np.sqrt(periods_per_year))

    @staticmethod
    def max_drawdown(equity_curve: np.ndarray) -> float:
        """Hitung maximum drawdown dari equity curve."""
        if len(equity_curve) < 2:
            return 0.0
        cum_max = np.maximum.accumulate(equity_curve)
        drawdowns = (equity_curve - cum_max) / cum_max
        return float(np.min(drawdowns))

    @staticmethod
    def value_at_risk(returns: np.ndarray, confidence: float = 0.95) -> float:
        """Historical VaR pada confidence level tertentu."""
        if len(returns) < 20:
            return 0.0
        alpha = 1 - confidence
        return float(np.percentile(returns, alpha * 100))

    # ------------------------------------------------------------------
    # Fundamental ratios (IDX)
    # ------------------------------------------------------------------

    @staticmethod
    def price_to_earnings(price: float, eps: float) -> Optional[float]:
        """P/E Ratio = Price / EPS."""
        if eps <= 0:
            return None
        return price / eps

    @staticmethod
    def price_to_book(price: float, book_value_per_share: float) -> Optional[float]:
        """P/BV Ratio = Price / Book Value per Share."""
        if book_value_per_share <= 0:
            return None
        return price / book_value_per_share

    @staticmethod
    def peg_ratio(pe: float, earnings_growth: float) -> Optional[float]:
        """PEG Ratio = P/E / Earnings Growth Rate (%)."""
        if earnings_growth <= 0:
            return None
        return pe / (earnings_growth * 100)

    @staticmethod
    def return_on_equity(net_income: float, equity: float) -> Optional[float]:
        """ROE = Net Income / Equity."""
        if equity <= 0:
            return None
        return net_income / equity

    @staticmethod
    def debt_to_equity(total_debt: float, equity: float) -> Optional[float]:
        """DER = Total Debt / Equity."""
        if equity <= 0:
            return None
        return total_debt / equity

    @staticmethod
    def dividend_yield(dividend_per_share: float, price: float) -> Optional[float]:
        """Dividend Yield = DPS / Price."""
        if price <= 0:
            return None
        return dividend_per_share / price

    @staticmethod
    def earnings_per_share(net_income: float, shares_outstanding: int) -> float:
        """EPS = Net Income / Shares Outstanding."""
        if shares_outstanding <= 0:
            return 0.0
        return net_income / shares_outstanding

    def __repr__(self) -> str:
        return "CashflowMetrics()"
