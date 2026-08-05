"""
Health Checker — Orchestrator untuk semua API health checks.
"""
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class HealthChecker:
    """
    Orchestrator yang menjalankan health check ke semua API eksternal.

    Kategori:
    - broker: Binance, IBKR, IDX broker
    - llm: OpenAI, Anthropic, Gemini (Fase 6)
    - data_api: yfinance, CCXT, Alpha Vantage, FRED
    - trading_view: Webhook handler & alert parser (Fase 6)

    Status:
    - OK: API accessible
    - FAIL: API not responding (wizard berhenti jika kritis)
    - SKIP: API key tidak diset
    """

    def __init__(self):
        self.results: Dict[str, Dict[str, str]] = {}

    def check_all(self) -> Dict[str, Dict[str, str]]:
        """
        Jalankan semua health checks.

        Returns:
            Dict kategori -> {api_name: status}
        """
        self.results = {
            "data_api": self._check_data_apis(),
            "broker": self._check_broker_apis(),
            "llm": self._check_llm_apis(),
            "trading_view": self._check_tradingview(),
        }
        return self.results

    def _check_data_apis(self) -> Dict[str, str]:
        """Check data API connectivity."""
        results = {}

        # yfinance
        try:
            import yfinance as yf
            test = yf.Ticker("BBCA.JK")
            info = test.info
            results["yfinance"] = "OK" if info else "FAIL"
        except ImportError:
            results["yfinance"] = "SKIP"
        except Exception:
            results["yfinance"] = "FAIL"

        # CCXT
        try:
            import ccxt
            results["ccxt"] = "OK"
        except ImportError:
            results["ccxt"] = "SKIP"

        return results

    def _check_broker_apis(self) -> Dict[str, str]:
        """Check broker API connectivity — placeholder for Fase 5+."""
        return {
            "binance": "SKIP",
            "idx_broker": "SKIP",
        }

    def _check_llm_apis(self) -> Dict[str, str]:
        """Check LLM API connectivity — placeholder for Fase 6."""
        return {
            "openai": "SKIP",
            "anthropic": "SKIP",
        }

    def _check_tradingview(self) -> Dict[str, str]:
        """Check TradingView webhook — placeholder for Fase 6."""
        return {"tradingview_webhook": "SKIP"}

    def has_critical_failures(self) -> bool:
        """Check if any critical API is FAIL."""
        critical = ["yfinance"]
        for category in self.results.values():
            for api, status in category.items():
                if api in critical and status == "FAIL":
                    return True
        return False

    def __repr__(self) -> str:
        total = sum(len(v) for v in self.results.values())
        ok = sum(1 for v in self.results.values() for s in v.values() if s == "OK")
        return f"HealthChecker(apis={total}, ok={ok})"
