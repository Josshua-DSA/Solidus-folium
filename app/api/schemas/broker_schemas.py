"""
Pydantic Schemas — Validasi Broker Service API.
Layer 5: app/api/schemas/ — Request/Response models.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any


class BrokerConnectRequest(BaseModel):
    """Request model untuk menghubungkan akun broker."""
    broker_name: str = Field(description="Nama broker: Stockbit, Ajaib, Nanovest")
    api_key: str = Field(description="API Key sandbox/live broker")
    env: str = Field(default="SANDBOX", description="Mode environment: SANDBOX atau LIVE")


class BrokerAccountStatus(BaseModel):
    """Status koneksi satu broker."""
    status: str
    env: str
    api_key_set: bool
    latency_ms: Optional[int] = None
    balance: float
    supported_markets: str


class BrokerStatusResponse(BaseModel):
    """Response model status semua koneksi broker."""
    mode: str
    active_broker: Optional[str] = None
    active_connections: int
    accounts: Dict[str, BrokerAccountStatus]


class BrokerActionResponse(BaseModel):
    """Response model untuk aksi broker (connect/disconnect/clear)."""
    success: bool
    message: str
