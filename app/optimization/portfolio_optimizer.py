"""
Portfolio Optimizer — Maximization J dengan constraint IDX.

Fungsi objektif J meminimalkan:
  - Downside semi-covariance (risiko downside)
  - Transaction cost (biaya transaksi)
  - Max drawdown (drawdown maksimum)
  - Turnover (perputaran portofolio)

Constraint:
  - Lot minimum IDX: kelipatan 100 lembar
  - Budget constraint: sum(weight) = 1
  - Long-only: weight >= 0
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from scipy.optimize import minimize
import logging

logger = logging.getLogger(__name__)


class PortfolioOptimizer:
    """
    Optimizer portofolio dengan fungsi objektif J.
    
    Args:
        risk_aversion: Koefisien risk aversion (default 1.0)
        transaction_cost_pct: Biaya transaksi dalam persentase (default 0.15%)
        max_drawdown_penalty: Penalty untuk max drawdown (default 2.0)
        turnover_penalty: Penalty untuk turnover (default 0.5)
        min_weight: Bobot minimum per aset (default 0.0 = no short)
        max_weight: Bobot maksimum per aset (default 1.0 = no leverage)
    """
    
    def __init__(
        self,
        risk_aversion: float = 1.0,
        transaction_cost_pct: float = 0.0015,
        max_drawdown_penalty: float = 2.0,
        turnover_penalty: float = 0.5,
        min_weight: float = 0.0,
        max_weight: float = 1.0,
    ):
        self.risk_aversion = risk_aversion
        self.transaction_cost_pct = transaction_cost_pct
        self.max_drawdown_penalty = max_drawdown_penalty
        self.turnover_penalty = turnover_penalty
        self.min_weight = min_weight
        self.max_weight = max_weight
    
    def _objective_j(
        self,
        weights: np.ndarray,
        returns: np.ndarray,
        mu_t: np.ndarray,
        prev_weights: np.ndarray,
    ) -> float:
        """
        Fungsi objektif J (minimize).
        
        J = -mu_t^T * w + lambda * downside_semi_cov(w) 
            + tc * |w - w_prev| + penalty_mdd * max_dd(w) 
            + penalty_turnover * turnover(w, w_prev)
        
        Args:
            weights: Bobot portofolio saat ini
            returns: Matrix returns (n_samples, n_assets)
            mu_t: Expected returns (probabilitas PROFIT dari model)
            prev_weights: Bobot portofolio sebelumnya
        
        Returns:
            Nilai objektif J (scalar)
        """
        # Expected return
        expected_return = np.dot(mu_t, weights)
        
        # Downside semi-covariance (hanya return negatif)
        portfolio_returns = returns @ weights
        downside_returns = np.minimum(portfolio_returns, 0)
        downside_var = np.var(downside_returns)
        
        # Transaction cost
        turnover = np.sum(np.abs(weights - prev_weights))
        tc = self.transaction_cost_pct * turnover
        
        # Max drawdown (approximation)
        cum_returns = np.cumprod(1 + portfolio_returns)
        running_max = np.maximum.accumulate(cum_returns)
        drawdowns = (cum_returns - running_max) / running_max
        max_dd = np.min(drawdowns) if len(drawdowns) > 0 else 0
        
        # Turnover penalty
        turnover_penalty = self.turnover_penalty * turnover
        
        # Total objective
        J = (
            -expected_return
            + self.risk_aversion * downside_var
            + tc
            + self.max_drawdown_penalty * abs(max_dd)
            + turnover_penalty
        )
        
        return J
    
    def optimize(
        self,
        returns: np.ndarray,
        mu_t: np.ndarray,
        prev_weights: Optional[np.ndarray] = None,
    ) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        Optimasi bobot portofolio.
        
        Args:
            returns: Matrix returns (n_samples, n_assets)
            mu_t: Expected returns (probabilitas PROFIT dari model)
            prev_weights: Bobot portofolio sebelumnya (default: zeros)
        
        Returns:
            (optimal_weights, metrics_dict)
        """
        n_assets = returns.shape[1]
        
        if prev_weights is None:
            prev_weights = np.zeros(n_assets)
        
        # Constraints
        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1},  # Budget constraint
        ]
        
        # Bounds
        bounds = [(self.min_weight, self.max_weight) for _ in range(n_assets)]
        
        # Initial guess (equal weight)
        w0 = np.ones(n_assets) / n_assets
        
        # Optimize
        result = minimize(
            self._objective_j,
            w0,
            args=(returns, mu_t, prev_weights),
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000, "ftol": 1e-9},
        )
        
        if not result.success:
            logger.warning("Optimization did not converge: %s", result.message)
        
        optimal_weights = result.x
        
        # Metrics
        metrics = {
            "expected_return": float(np.dot(mu_t, optimal_weights)),
            "turnover": float(np.sum(np.abs(optimal_weights - prev_weights))),
            "n_nonzero": int(np.sum(optimal_weights > 0.01)),
            "objective_j": float(result.fun),
        }
        
        logger.info(
            "Optimization complete: %d assets, turnover=%.3f, J=%.4f",
            metrics["n_nonzero"], metrics["turnover"], metrics["objective_j"],
        )
        
        return optimal_weights, metrics
    
    def adjust_to_lots(
        self,
        weights: np.ndarray,
        prices: np.ndarray,
        total_capital: float,
        lot_size: int = 100,
    ) -> np.ndarray:
        """
        Konversi bobot ke jumlah lot (kelipatan 100 lembar untuk IDX).
        
        Args:
            weights: Bobot portofolio
            prices: Harga per lembar setiap aset
            total_capital: Total modal
            lot_size: Ukuran lot (default 100 untuk IDX)
        
        Returns:
            np.ndarray jumlah lot per aset
        """
        # Hitung nilai per aset
        values = weights * total_capital
        
        # Hitung jumlah lembar
        shares = values / prices
        
        # Bulatkan ke lot
        lots = np.floor(shares / lot_size).astype(int)
        
        return lots
    
    def __repr__(self) -> str:
        return (
            f"PortfolioOptimizer(risk_aversion={self.risk_aversion}, "
            f"tc={self.transaction_cost_pct:.4f}, "
            f"mdd_penalty={self.max_drawdown_penalty})"
        )
