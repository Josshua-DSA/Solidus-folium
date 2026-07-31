"""
Layer 4: Portfolio Optimizer Module

Implements various portfolio optimization strategies based on research papers:
- Semi-Covariance (downside risk) optimization
- Multi-Period MPC with Drawdown Control
- Resampled Efficiency (bootstrap)
- Mean-MDD with NSGA-II Evolutionary Algorithm
- Risk Parity with dynamic risk budgeting

References:
- Zhu & Wu: Dynamic Transformer for Semi-Covariance Prediction
- Nystrup et al.: Multi-period portfolio selection with drawdown control
- Michaud: Forecast Confidence Level and Portfolio Optimization
- Drenovak et al.: Mean-MDD optimization using NSGA-II
- Agal et al.: ML approach to risk-based asset allocation
"""

from .base import BasePortfolioOptimizer, OptimizationResult
from .semi_covariance import SemiCovarianceOptimizer
from .mpc_drawdown import MPCDrawdownOptimizer
from .resampled_efficiency import ResampledEfficiencyOptimizer
from .mean_mdd_nsga2 import MeanMDDNSGA2Optimizer
from .risk_parity import RiskParityOptimizer

__all__ = [
    "BasePortfolioOptimizer",
    "OptimizationResult",
    "SemiCovarianceOptimizer",
    "MPCDrawdownOptimizer",
    "ResampledEfficiencyOptimizer",
    "MeanMDDNSGA2Optimizer",
    "RiskParityOptimizer",
]
