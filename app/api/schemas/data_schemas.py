"""
Pydantic Schemas — Validasi Data Service API.
Layer 5: app/api/schemas/ — Request/Response models.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any


class DBStatusResponse(BaseModel):
    """Response model untuk status database."""
    db_path: str
    n_tickers: int
    tickers: List[str]
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    is_populated: bool


class LatestPriceResponse(BaseModel):
    """Response model untuk harga penutupan terakhir per ticker."""
    prices: Dict[str, float]


class FundamentalMetrics(BaseModel):
    """Model data fundamental satu ticker."""
    ticker: str
    pe: Optional[float] = None
    pb: Optional[float] = None
    dividend_yield: Optional[float] = None
    roe: Optional[float] = None
    der: Optional[float] = None
    eps: Optional[float] = None
    market_cap: Optional[float] = None
    last_updated: Optional[str] = None
