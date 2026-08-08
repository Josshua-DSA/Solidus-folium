"""
FastAPI Server Application — Entry Point REST API & WebSocket Server.
Layer 5: app/api/main.py

Mendukung REST API endpoints + Realtime WebSocket updates untuk TUI & GUI.

Usage:
    uvicorn app.api.main:app --reload --port 8000
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import asyncio
import logging
import json

from app.api.routers import (
    data_router,
    scanner_router,
    backtest_router,
    portfolio_router,
    broker_router,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Finance-Pro Quant & Execution API",
    description="REST & WebSocket API Gateway untuk Trading Kuantitatif Saham IDX",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS untuk Web GUI & TUI IPC
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include All API Routers
app.include_router(data_router)
app.include_router(scanner_router)
app.include_router(backtest_router)
app.include_router(portfolio_router)
app.include_router(broker_router)


# ---------------------------------------------------------------------------
# WebSocket Manager (Realtime Price & Portfolio Updates)
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Mengelola koneksi WebSocket aktif (TUI/GUI client subscribers)."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket client connected. Total: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("WebSocket client disconnected. Remaining: %d", len(self.active_connections))

    async def broadcast(self, message: dict):
        """Broadcast pesan JSON ke semua client terhubung."""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning("Error broadcasting WS message: %s", e)


ws_manager = ConnectionManager()


@app.websocket("/ws/realtime")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint untuk realtime price & trade updates.
    Client bisa mendengarkan event STREAM_PRICE, TRADE_EXECUTION, NAV_UPDATE.
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo heartbeat / ping
            await websocket.send_json({"type": "PONG", "received": data})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# System Health Check Endpoint
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint untuk load balancer / process supervisor."""
    return {
        "status": "online",
        "service": "Finance-Pro Quant Backend",
        "api_version": "v1",
        "websocket_active_connections": len(ws_manager.active_connections),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=8000, reload=True)
