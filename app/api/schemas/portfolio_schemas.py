"""
Pydantic Schemas — Validasi Portfolio Service API.
Layer 5: app/api/schemas/ — Request/Response models.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any


class TradeRequest(BaseModel):
    """Request model untuk eksekusi trade (BUY/SELL)."""
    ticker: str = Field(description="Ticker saham (misal BBCA.JK)")
    side: str = Field(description="Aksi: BUY atau SELL")
    lots: int = Field(gt=0, description="Jumlah lot (1 lot = 100 lembar)")
    current_price: float = Field(gt=0, description="Harga eksekusi per lembar")


class TradeExecutionResponse(BaseModel):
    """Response model setelah eksekusi order."""
    success: bool
    message: str
    ticker: str
    side: str
    lots: int
    execution_price: Optional[float] = None
    commission: Optional[float] = None


class PositionDetail(BaseModel):
    """Detail satu posisi aktif."""
    ticker: str
    shares: int
    lots: int
    avg_price: float
    current_price: float
    market_value: float
    cost_basis: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    entry_date: Optional[Any] = None


class PortfolioSummaryResponse(BaseModel):
    """Response model ringkasan portofolio."""
    cash: float
    total_value: float
    total_unrealized_pnl: float
    positions_count: int
    positions: List[PositionDetail]
    transaction_count: int
