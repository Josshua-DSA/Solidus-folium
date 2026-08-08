"""
Pydantic Schemas — Validasi Scanner Service API.
Layer 5: app/api/schemas/ — Request/Response models.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any


class ScanRequest(BaseModel):
    """Request model untuk menjalankan scanner."""
    tickers: Optional[List[str]] = Field(default=None, description="List ticker (None = semua)")
    buy_threshold: float = Field(default=0.50, ge=0.0, le=1.0, description="Minimum threshold BUY")


class SignalItem(BaseModel):
    """Model untuk satu hasil sinyal scanner."""
    ticker: str
    price: float
    score: float
    signal: str = Field(description="BUY, SELL, atau HOLD")
    fast_mom: Optional[float] = None
    slow_mom: Optional[float] = None
    momentum_score: Optional[float] = None
    ml_score: Optional[float] = None


class ScanResponse(BaseModel):
    """Response model hasil scanning."""
    count: int
    signals: List[SignalItem]
