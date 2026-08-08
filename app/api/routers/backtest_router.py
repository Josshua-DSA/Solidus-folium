"""
Backtest Router — Endpoints untuk simulasi & backtesting.
Layer 5: app/api/routers/backtest_router.py
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any

from app.services.backtest_service import BacktestService
from app.api.schemas.backtest_schemas import (
    MomentumBacktestRequest,
    BacktestResponse,
)

router = APIRouter(prefix="/api/v1/backtest", tags=["Backtest Service"])

_backtest_service = BacktestService()


def get_backtest_service() -> BacktestService:
    """Dependency provider untuk BacktestService."""
    return _backtest_service


@router.post("/momentum", response_model=BacktestResponse)
def run_momentum_backtest(req: MomentumBacktestRequest):
    """Menjalankan backtest strategi momentum."""
    service = get_backtest_service()
    service.initial_capital = req.initial_capital

    result = service.run_momentum_backtest(
        tickers=req.tickers,
        fast_window=req.fast_window,
        slow_window=req.slow_window,
        position_size_pct=req.position_size_pct,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # Convert equity_curve Series -> Dict[str, float] for JSON
    equity_curve = result.get("equity_curve")
    equity_dict = {}
    if equity_curve is not None and not equity_curve.empty:
        equity_dict = {str(k.date() if hasattr(k, "date") else k): float(v) for k, v in equity_curve.items()}

    trades = result.get("trades", [])
    metrics = result.get("metrics", {})
    open_pos = result.get("open_positions", {})

    return BacktestResponse(
        strategy="momentum",
        metrics=metrics,
        equity_curve=equity_dict,
        trades_count=len(trades),
        open_positions=open_pos,
    )
