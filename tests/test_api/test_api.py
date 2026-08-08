"""
Integration Tests untuk FastAPI REST API Endpoints & WebSockets.
Layer 5: tests/test_api/test_api.py
"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
import pandas as pd
import numpy as np

from app.api.main import app

client = TestClient(app)


class TestHealthAndSystem:
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert "api_version" in data


class TestDataEndpoints:
    def test_get_db_status(self):
        response = client.get("/api/v1/data/status")
        assert response.status_code == 200
        data = response.json()
        assert "db_path" in data
        assert "is_populated" in data

    def test_get_tickers(self):
        response = client.get("/api/v1/data/tickers")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_latest_prices(self):
        response = client.get("/api/v1/data/prices/latest")
        assert response.status_code == 200
        data = response.json()
        assert "prices" in data

    def test_get_fundamentals_not_found(self):
        response = client.get("/api/v1/data/fundamentals/NONEXISTENT.JK")
        assert response.status_code == 404


class TestScannerEndpoints:
    def test_scan_momentum(self):
        payload = {"buy_threshold": 0.50}
        response = client.post("/api/v1/scanner/momentum", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "signals" in data
        assert isinstance(data["signals"], list)

    def test_scan_combined(self):
        payload = {"buy_threshold": 0.50}
        response = client.post("/api/v1/scanner/combined", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "signals" in data


class TestBacktestEndpoints:
    def test_run_momentum_backtest(self):
        mock_result = {
            "strategy": "momentum",
            "metrics": {
                "total_return": 0.15,
                "cagr": 0.10,
                "sharpe_ratio": 1.5,
                "sortino_ratio": 2.0,
                "max_drawdown": -0.05,
                "calmar_ratio": 2.0,
                "j_value": 1.2,
                "win_rate": 0.60,
                "profit_factor": 1.8,
                "n_trades": 10,
                "initial_capital": 100_000_000,
                "final_nav": 115_000_000,
            },
            "equity_curve": pd.Series([100000000.0, 105000000.0, 115000000.0], index=pd.date_range("2024-01-01", periods=3)),
            "trades": [{"id": 1}],
            "open_positions": {},
        }
        with patch("app.services.backtest_service.BacktestService.run_momentum_backtest", return_value=mock_result):
            payload = {
                "fast_window": 5,
                "slow_window": 20,
                "position_size_pct": 0.10,
                "initial_capital": 100000000.0,
            }
            response = client.post("/api/v1/backtest/momentum", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["strategy"] == "momentum"
            assert "metrics" in data
            assert "equity_curve" in data

    def test_invalid_backtest_params(self):
        payload = {
            "fast_window": -5,  # Invalid window
        }
        response = client.post("/api/v1/backtest/momentum", json=payload)
        assert response.status_code == 422  # Validation error


class TestPortfolioEndpoints:
    def test_execute_buy_trade(self):
        payload = {
            "ticker": "BBCA.JK",
            "side": "BUY",
            "lots": 5,
            "current_price": 10000.0,
        }
        response = client.post("/api/v1/portfolio/trade", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["ticker"] == "BBCA.JK"
        assert data["side"] == "BUY"

    def test_get_portfolio_summary(self):
        response = client.get("/api/v1/portfolio/summary")
        assert response.status_code == 200
        data = response.json()
        assert "cash" in data
        assert "total_value" in data
        assert "positions" in data

    def test_get_transaction_history(self):
        response = client.get("/api/v1/portfolio/history?limit=10")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestBrokerEndpoints:
    def test_get_broker_status(self):
        response = client.get("/api/v1/broker/status")
        assert response.status_code == 200
        data = response.json()
        assert "mode" in data
        assert "accounts" in data

    def test_connect_broker(self):
        payload = {
            "broker_name": "Stockbit",
            "api_key": "test_api_key_123",
            "env": "SANDBOX",
        }
        response = client.post("/api/v1/broker/connect", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_connect_unknown_broker(self):
        payload = {
            "broker_name": "InvalidBroker",
            "api_key": "key",
        }
        response = client.post("/api/v1/broker/connect", json=payload)
        assert response.status_code == 400

    def test_toggle_mode(self):
        response = client.post("/api/v1/broker/toggle-mode")
        assert response.status_code == 200
        assert "mode" in response.json()

    def test_clear_credentials(self):
        response = client.post("/api/v1/broker/clear-credentials")
        assert response.status_code == 200
        assert response.json()["success"] is True


class TestWebSocket:
    def test_websocket_ping_pong(self):
        with client.websocket_connect("/ws/realtime") as websocket:
            websocket.send_text("PING")
            data = websocket.receive_json()
            assert data["type"] == "PONG"
            assert data["received"] == "PING"
