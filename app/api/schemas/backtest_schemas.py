"""
Pydantic Schemas — Validasi Backtest Service API.
Layer 5: app/api/schemas/ — Request/Response models.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any


class MomentumBacktestRequest(BaseModel):
    """Request model untuk backtest momentum strategy."""
    tickers: Optional[List[str]] = Field(default=None, description="List ticker (None = semua)")
    fast_window: int = Field(default=5, gt=0, description="Window momentum cepat")
    slow_window: int = Field(default=20, gt=0, description="Window momentum lambat")
    position_size_pct: float = Field(default=0.10, gt=0.0, le=1.0, description="Target bobot per posisi")
    initial_capital: float = Field(default=100_000_000, gt=0, description="Modal awal (Rp)")


class BacktestMetrics(BaseModel):
    """Model metrik performa hasil backtest."""
    total_return: float
    cagr: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float
    j_value: float
    win_rate: float
    profit_factor: float
    n_trades: int
    initial_capital: float
    final_nav: float


class BacktestResponse(BaseModel):
    """Response model hasil backtest."""
    strategy: str
    metrics: Dict[str, Any]
    equity_curve: Dict[str, float] = Field(description="Date string → NAV value")
    trades_count: int
    open_positions: Dict[str, Any]
