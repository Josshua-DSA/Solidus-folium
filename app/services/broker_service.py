"""
Broker Service — Abstraksi koneksi broker (paper/sandbox/live).

Mengelola:
  - Mode eksekusi (PAPER, SANDBOX, LIVE)
  - Koneksi API broker (Stockbit, Ajaib, Nanovest)
  - Credential management (tanpa menyimpan secrets di code)
  - Order routing fallback

Layer 5: app/services/ — Execution abstraction.
"""
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Mode eksekusi order."""
    PAPER = "PAPER"
    SANDBOX = "SANDBOX"
    LIVE = "LIVE"


@dataclass
class BrokerAccount:
    """Status koneksi satu akun broker."""
    name: str
    status: str = "DISCONNECTED"  # CONNECTED | DISCONNECTED
    env: str = "SANDBOX"          # SANDBOX | LIVE
    api_key_set: bool = False     # True jika credential sudah di-set
    latency_ms: Optional[int] = None
    balance: float = 0.0
    supported_markets: str = "IDX Equity"


class BrokerService:
    """
    Service layer untuk manajemen koneksi broker.

    Mengelola lifecycle koneksi broker dan order routing.
    Default mode: PAPER (semua order ke paper simulator).

    Args:
        mode: Mode eksekusi awal (default PAPER)
    """

    def __init__(self, mode: ExecutionMode = ExecutionMode.PAPER):
        self.mode = mode

        # Registered brokers
        self.accounts: Dict[str, BrokerAccount] = {
            "Stockbit": BrokerAccount(
                name="Stockbit",
                supported_markets="IDX Equity & Derivatives",
            ),
            "Ajaib": BrokerAccount(
                name="Ajaib",
                supported_markets="IDX Equity",
            ),
            "Nanovest": BrokerAccount(
                name="Nanovest",
                supported_markets="IDX & US Equities / Crypto",
            ),
        }

        self.connection_log: List[Dict[str, str]] = []
        self._log("SYS", "Broker service initialized in PAPER TRADING mode")

    def _log(self, tag: str, message: str) -> None:
        """Append ke internal connection log."""
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        entry = {"timestamp": ts, "tag": tag, "message": message}
        self.connection_log.append(entry)
        logger.info("[%s] %s", tag, message)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(
        self,
        broker_name: str,
        api_key: str,
        env: str = "SANDBOX",
    ) -> Dict[str, Any]:
        """
        Hubungkan ke broker API.

        Args:
            broker_name: Nama broker (Stockbit/Ajaib/Nanovest)
            api_key: API key (validated, not stored in plain text)
            env: SANDBOX atau LIVE

        Returns:
            Dict: {"success": bool, "message": str}
        """
        if broker_name not in self.accounts:
            return {
                "success": False,
                "message": f"Unknown broker: {broker_name}. Available: {list(self.accounts.keys())}",
            }

        if not api_key:
            return {"success": False, "message": "API key cannot be empty"}

        account = self.accounts[broker_name]
        account.status = "CONNECTED"
        account.env = env
        account.api_key_set = True
        account.latency_ms = 14  # Simulated latency

        self._log(broker_name[:3].upper(), f"Connected to {broker_name} ({env} mode)")

        return {
            "success": True,
            "message": f"Connected to {broker_name} ({env})",
        }

    def disconnect(self, broker_name: str) -> Dict[str, Any]:
        """Putuskan koneksi broker."""
        if broker_name not in self.accounts:
            return {"success": False, "message": f"Unknown broker: {broker_name}"}

        account = self.accounts[broker_name]
        account.status = "DISCONNECTED"
        account.api_key_set = False
        account.latency_ms = None
        account.balance = 0.0

        self._log(broker_name[:3].upper(), f"Disconnected from {broker_name}")

        return {"success": True, "message": f"Disconnected from {broker_name}"}

    def set_mode(self, mode: ExecutionMode) -> None:
        """Switch execution mode."""
        old_mode = self.mode
        self.mode = mode
        self._log("SYS", f"Mode changed: {old_mode.value} → {mode.value}")

    def toggle_mode(self) -> ExecutionMode:
        """Toggle antara PAPER ↔ SANDBOX ↔ LIVE."""
        cycle = [ExecutionMode.PAPER, ExecutionMode.SANDBOX, ExecutionMode.LIVE]
        current_idx = cycle.index(self.mode)
        new_mode = cycle[(current_idx + 1) % len(cycle)]
        self.set_mode(new_mode)
        return new_mode

    # ------------------------------------------------------------------
    # Status & info
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return status semua broker connections."""
        return {
            "mode": self.mode.value,
            "accounts": {
                name: {
                    "status": acct.status,
                    "env": acct.env,
                    "api_key_set": acct.api_key_set,
                    "latency_ms": acct.latency_ms,
                    "balance": acct.balance,
                    "supported_markets": acct.supported_markets,
                }
                for name, acct in self.accounts.items()
            },
            "active_connections": sum(
                1 for a in self.accounts.values() if a.status == "CONNECTED"
            ),
        }

    def get_connection_log(self, last_n: int = 20) -> List[Dict[str, str]]:
        """Return N entri terakhir dari connection log."""
        return self.connection_log[-last_n:]

    def get_active_broker(self) -> Optional[str]:
        """
        Return nama broker yang aktif (CONNECTED).
        None jika tidak ada (fallback ke paper).
        """
        for name, acct in self.accounts.items():
            if acct.status == "CONNECTED":
                return name
        return None

    def is_paper_mode(self) -> bool:
        """Cek apakah dalam mode paper trading."""
        return self.mode == ExecutionMode.PAPER

    def clear_credentials(self) -> Dict[str, Any]:
        """Wipe semua credential (security: revoke)."""
        for name, acct in self.accounts.items():
            acct.status = "DISCONNECTED"
            acct.api_key_set = False
            acct.latency_ms = None
            acct.balance = 0.0

        self._log("SEC", "All broker credentials cleared (security wipe)")
        return {"success": True, "message": "All credentials cleared"}

    def __repr__(self) -> str:
        active = self.get_active_broker()
        return (
            f"BrokerService(mode={self.mode.value}, "
            f"active={active or 'PAPER'})"
        )
