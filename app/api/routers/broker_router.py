"""
Broker Router — Endpoints untuk manajemen koneksi broker (PAPER/SANDBOX/LIVE).
Layer 5: app/api/routers/broker_router.py
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any

from app.services.broker_service import BrokerService, ExecutionMode
from app.api.schemas.broker_schemas import (
    BrokerConnectRequest,
    BrokerAccountStatus,
    BrokerStatusResponse,
    BrokerActionResponse,
)

router = APIRouter(prefix="/api/v1/broker", tags=["Broker Service"])

_broker_service = BrokerService()


def get_broker_service() -> BrokerService:
    """Dependency provider untuk BrokerService."""
    return _broker_service


@router.get("/status", response_model=BrokerStatusResponse)
def get_broker_status():
    """Mendapatkan status semua koneksi broker."""
    service = get_broker_service()
    status = service.get_status()
    
    accounts = {
        name: BrokerAccountStatus(**acct)
        for name, acct in status["accounts"].items()
    }
    
    return BrokerStatusResponse(
        mode=status["mode"],
        active_broker=service.get_active_broker(),
        active_connections=status["active_connections"],
        accounts=accounts,
    )


@router.post("/connect", response_model=BrokerActionResponse)
def connect_broker(req: BrokerConnectRequest):
    """Menghubungkan akun broker (Stockbit, Ajaib, Nanovest)."""
    service = get_broker_service()
    res = service.connect(
        broker_name=req.broker_name,
        api_key=req.api_key,
        env=req.env,
    )
    if not res["success"]:
        raise HTTPException(status_code=400, detail=res["message"])
    return BrokerActionResponse(**res)


@router.post("/disconnect/{broker_name}", response_model=BrokerActionResponse)
def disconnect_broker(broker_name: str):
    """Memutuskan koneksi broker."""
    service = get_broker_service()
    res = service.disconnect(broker_name)
    if not res["success"]:
        raise HTTPException(status_code=400, detail=res["message"])
    return BrokerActionResponse(**res)


@router.post("/toggle-mode", response_model=Dict[str, str])
def toggle_execution_mode():
    """Toggle execution mode (PAPER ↔ SANDBOX ↔ LIVE)."""
    service = get_broker_service()
    new_mode = service.toggle_mode()
    return {"mode": new_mode.value}


@router.post("/clear-credentials", response_model=BrokerActionResponse)
def clear_credentials():
    """Menghapus semua credential broker tersimpan (Security Wipe)."""
    service = get_broker_service()
    res = service.clear_credentials()
    return BrokerActionResponse(**res)
