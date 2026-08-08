"""
Portfolio Router — Endpoints untuk eksekusi trade & portofolio management.
Layer 5: app/api/routers/portfolio_router.py
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any

from app.services.portfolio_service import PortfolioService
from app.services.data_service import DataService
from app.api.schemas.portfolio_schemas import (
    TradeRequest,
    TradeExecutionResponse,
    PortfolioSummaryResponse,
    PositionDetail,
)

router = APIRouter(prefix="/api/v1/portfolio", tags=["Portfolio Service"])

_portfolio_service = PortfolioService()
_data_service = DataService()


def get_portfolio_service() -> PortfolioService:
    """Dependency provider untuk PortfolioService."""
    return _portfolio_service


@router.post("/trade", response_model=TradeExecutionResponse)
def execute_trade(req: TradeRequest):
    """Mengeksekusi order paper trading (BUY/SELL)."""
    service = get_portfolio_service()
    
    # Get current prices for risk evaluation
    latest_prices = _data_service.get_latest_prices()
    
    res = service.execute_order(
        ticker=req.ticker,
        side=req.side,
        lots=req.lots,
        current_price=req.current_price,
        current_prices=latest_prices,
    )
    
    trade_obj = res.get("trade")
    return TradeExecutionResponse(
        success=res["success"],
        message=res["message"],
        ticker=req.ticker,
        side=req.side,
        lots=req.lots,
        execution_price=trade_obj.execution_price if trade_obj else None,
        commission=trade_obj.commission if trade_obj else None,
    )


@router.get("/summary", response_model=PortfolioSummaryResponse)
def get_portfolio_summary():
    """Mendapatkan ringkasan portofolio terkini."""
    service = get_portfolio_service()
    latest_prices = _data_service.get_latest_prices()
    
    summary = service.get_portfolio_summary(current_prices=latest_prices)
    
    positions = [PositionDetail(**p) for p in summary.get("positions", [])]
    
    return PortfolioSummaryResponse(
        cash=float(summary.get("cash", 0)),
        total_value=float(summary.get("total_value", 0)),
        total_unrealized_pnl=float(summary.get("total_unrealized_pnl", 0)),
        positions_count=len(positions),
        positions=positions,
        transaction_count=summary.get("transaction_count", 0),
    )


@router.get("/history", response_model=List[Dict[str, Any]])
def get_transaction_history(limit: int = Query(20, ge=1, le=100)):
    """Mendapatkan riwayat transaksi."""
    service = get_portfolio_service()
    return service.get_transaction_history(last_n=limit)
