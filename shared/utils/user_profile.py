"""
User Profile Manager — Mengelola profil RDN dan portofolio awal client Folium.

Menyimpan dan memuat profil dari user_profile.json (~/.folium/user_profile.json):
  - rdn_balance: Saldo kas RDN (Rp)
  - positions: List holding {ticker, lots, avg_price}
  - investor_name: Nama investor (opsional)
"""
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

from shared.utils.path_resolver import get_profile_path

logger = logging.getLogger(__name__)


@dataclass
class StockPosition:
    ticker: str
    lots: int
    avg_price: float

    @property
    def shares(self) -> int:
        return self.lots * 100

    @property
    def total_value(self) -> float:
        return self.shares * self.avg_price


@dataclass
class UserProfile:
    investor_name: str = "Client Folium"
    rdn_balance: float = 10_000_000.0  # Default Rp 10 Juta
    positions: List[StockPosition] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        raw_positions = data.get("positions", [])
        positions = [
            StockPosition(
                ticker=p["ticker"],
                lots=int(p["lots"]),
                avg_price=float(p["avg_price"]),
            )
            for p in raw_positions
        ]
        return cls(
            investor_name=data.get("investor_name", "Client Folium"),
            rdn_balance=float(data.get("rdn_balance", 10_000_000.0)),
            positions=positions,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


class ProfileManager:
    """Class penyimpan & pemuat profil user ke JSON."""

    def __init__(self, profile_path: Optional[str] = None):
        self.profile_path = profile_path if profile_path else get_profile_path()

    def exists(self) -> bool:
        """Cek apakah file profil sudah pernah dibuat."""
        return os.path.exists(self.profile_path)

    def load(self) -> UserProfile:
        """Muat profil dari file. Jika belum ada, return profil default."""
        if not self.exists():
            return UserProfile()
        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return UserProfile.from_dict(data)
        except Exception as e:
            logger.warning("Gagal membaca profile JSON (%s), return default.", e)
            return UserProfile()

    def save(self, profile: UserProfile) -> None:
        """Simpan profil ke JSON."""
        now_str = datetime.now().isoformat()
        if not profile.created_at:
            profile.created_at = now_str
        profile.updated_at = now_str

        os.makedirs(os.path.dirname(self.profile_path) if os.path.dirname(self.profile_path) else ".", exist_ok=True)
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, indent=2)
        logger.info("User profile tersimpan di %s", self.profile_path)
