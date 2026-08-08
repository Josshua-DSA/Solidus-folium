"""
Scanner Router — Endpoints untuk ML & Momentum scanner.
Layer 5: app/api/routers/scanner_router.py
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any

from app.services.scanner_service import ScannerService
from app.api.schemas.scanner_schemas import (
    ScanRequest,
    SignalItem,
    ScanResponse,
)

router = APIRouter(prefix="/api/v1/scanner", tags=["Scanner Service"])

_scanner_service = ScannerService()


def get_scanner_service() -> ScannerService:
    """Dependency provider untuk ScannerService."""
    return _scanner_service


@router.post("/momentum", response_model=ScanResponse)
def scan_momentum(req: ScanRequest):
    """Menjalankan momentum crossover scanner."""
    service = get_scanner_service()
    service.buy_threshold = req.buy_threshold
    results = service.scan_momentum(tickers=req.tickers)
    
    signals = [SignalItem(**r) for r in results]
    return ScanResponse(count=len(signals), signals=signals)


@router.post("/combined", response_model=ScanResponse)
def scan_combined(req: ScanRequest):
    """Menjalankan combined scanner (momentum + ML jika tersedia)."""
    service = get_scanner_service()
    service.buy_threshold = req.buy_threshold
    results = service.scan_combined(tickers=req.tickers)
    
    signals = [SignalItem(**r) for r in results]
    return ScanResponse(count=len(signals), signals=signals)
