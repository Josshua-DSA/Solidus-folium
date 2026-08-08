"""
Data Router — Endpoints untuk data harga, tickers, dan fundamentals.
Layer 5: app/api/routers/data_router.py
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any

from app.services.data_service import DataService
from app.api.schemas.data_schemas import (
    DBStatusResponse,
    LatestPriceResponse,
    FundamentalMetrics,
)

router = APIRouter(prefix="/api/v1/data", tags=["Data Service"])

# Singleton DataService instance (In-process cache)
_data_service = DataService()


def get_data_service() -> DataService:
    """Dependency provider untuk DataService."""
    return _data_service


@router.get("/status", response_model=DBStatusResponse)
def get_db_status():
    """Mendapatkan status database SQLite."""
    service = get_data_service()
    status = service.get_db_status()
    return DBStatusResponse(**status)


@router.get("/tickers", response_model=List[str])
def get_available_tickers():
    """Mendapatkan daftar ticker yang tersedia di database."""
    service = get_data_service()
    return service.get_available_tickers()


@router.get("/prices/latest", response_model=LatestPriceResponse)
def get_latest_prices(
    tickers: Optional[List[str]] = Query(None, description="Filter list ticker")
):
    """Mendapatkan harga penutupan terakhir per ticker."""
    service = get_data_service()
    prices = service.get_latest_prices(tickers)
    return LatestPriceResponse(prices=prices)


@router.get("/fundamentals/{ticker}", response_model=FundamentalMetrics)
def get_fundamentals(ticker: str):
    """Mendapatkan metrik fundamental untuk satu ticker."""
    service = get_data_service()
    data = service.get_fundamentals(ticker)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Data fundamental untuk ticker '{ticker}' tidak ditemukan"
        )
    return FundamentalMetrics(**data)
