"""
Base Portfolio Optimizer Interface

Defines the abstract base class and data structures for all portfolio optimizers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


@dataclass
class OptimizationResult:
    """
    Container for portfolio optimization results.
    
    Attributes:
        weights: Optimal portfolio weights (sum to 1)
        expected_return: Expected portfolio return
        expected_risk: Expected portfolio risk (volatility or other measure)
        sharpe_ratio: Risk-adjusted return metric
        max_drawdown: Maximum drawdown of the portfolio
        optimizer_name: Name of the optimizer used
        metadata: Additional optimizer-specific information
    """
    weights: np.ndarray
    expected_return: float
    expected_risk: float
    sharpe_ratio: float
    max_drawdown: float
    optimizer_name: str
    metadata: Optional[Dict] = None
    
    def __post_init__(self):
        """Validate optimization result."""
        if not np.isclose(self.weights.sum(), 1.0, atol=1e-6):
            raise ValueError(f"Weights must sum to 1.0, got {self.weights.sum()}")
        if np.any(self.weights < -1e-6):
            raise ValueError("Negative weights detected (short selling not allowed)")
    
    def to_dict(self) -> Dict:
        """Convert result to dictionary."""
        return {
            "weights": self.weights.tolist(),
            "expected_return": self.expected_return,
            "expected_risk": self.expected_risk,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "optimizer_name": self.optimizer_name,
            "metadata": self.metadata,
        }


class BasePortfolioOptimizer(ABC):
    """
    Abstract base class for portfolio optimizers.
    
    All portfolio optimizers must implement the optimize() method.
    """
    
    def __init__(
        self,
        risk_free_rate: float = 0.0,
        max_weight: float = 1.0,
        min_weight: float = 0.0,
    ):
        """
        Initialize base optimizer.
        
        Args:
            risk_free_rate: Risk-free rate for Sharpe ratio calculation
            max_weight: Maximum weight per asset (for diversification)
            min_weight: Minimum weight per asset (0 = long-only)
        """
        self.risk_free_rate = risk_free_rate
        self.max_weight = max_weight
        self.min_weight = min_weight
    
    @abstractmethod
    def optimize(
        self,
        returns: pd.DataFrame,
        predictions: Optional[pd.DataFrame] = None,
        **kwargs
    ) -> OptimizationResult:
        """
        Optimize portfolio weights.
        
        Args:
            returns: Historical returns DataFrame (T x N assets)
            predictions: Optional ML predictions (e.g., expected returns)
            **kwargs: Optimizer-specific parameters
        
        Returns:
            OptimizationResult with optimal weights and metrics
        """
        pass
    
    @staticmethod
    def compute_portfolio_returns(
        weights: np.ndarray,
        returns: pd.DataFrame
    ) -> pd.Series:
        """
        Compute portfolio returns given weights and asset returns.
        
        Args:
            weights: Portfolio weights (N,)
            returns: Asset returns DataFrame (T x N)
        
        Returns:
            Portfolio returns series (T,)
        """
        return (returns.values @ weights).flatten()
    
    @staticmethod
    def compute_max_drawdown(portfolio_returns: pd.Series) -> float:
        """
        Compute maximum drawdown from portfolio returns.
        
        Args:
            portfolio_returns: Portfolio returns series
        
        Returns:
            Maximum drawdown (positive number, e.g., 0.20 = 20% drawdown)
        """
        cumulative = (1 + portfolio_returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        return abs(drawdown.min())
    
    @staticmethod
    def compute_sharpe_ratio(
        portfolio_returns: pd.Series,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252
    ) -> float:
        """
        Compute annualized Sharpe ratio.
        
        Args:
            portfolio_returns: Portfolio returns series
            risk_free_rate: Annual risk-free rate
            periods_per_year: Number of periods per year (252 for daily)
        
        Returns:
            Annualized Sharpe ratio
        """
        excess_returns = portfolio_returns - risk_free_rate / periods_per_year
        if excess_returns.std() == 0:
            return 0.0
        sharpe = excess_returns.mean() / excess_returns.std()
        return sharpe * np.sqrt(periods_per_year)
    
    def _validate_weights(self, weights: np.ndarray) -> np.ndarray:
        """
        Validate and clip weights to constraints.
        
        Args:
            weights: Raw weights
        
        Returns:
            Clipped and normalized weights
        """
        # Clip to constraints
        weights = np.clip(weights, self.min_weight, self.max_weight)
        # Normalize to sum to 1
        weights = weights / weights.sum()
        return weights
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(risk_free_rate={self.risk_free_rate})"
