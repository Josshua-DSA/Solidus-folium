"""
Helper — Utility functions untuk operasi umum.
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional


# Hari libur IDX (placeholder — update tahunan)
_IDX_HOLIDAYS_2024_2025: List[str] = [
    "2024-01-01", "2024-02-08", "2024-03-11", "2024-03-12",
    "2024-03-29", "2024-04-10", "2024-05-01", "2024-05-23",
    "2024-06-01", "2024-06-17", "2024-08-17", "2024-12-25",
    "2025-01-01", "2025-01-29", "2025-03-29", "2025-03-31",
    "2025-04-18", "2025-05-01", "2025-05-12", "2025-06-01",
    "2025-08-17", "2025-12-25",
]


def is_trading_day(date: pd.Timestamp) -> bool:
    """
    Cek apakah tanggal adalah hari bursa IDX.

    Args:
        date: Tanggal yang dicek

    Returns:
        True jika hari bursa (Senin-Jumat, bukan libur)
    """
    # Weekend
    if date.weekday() >= 5:
        return False

    # Holiday
    date_str = date.strftime("%Y-%m-%d")
    if date_str in _IDX_HOLIDAYS_2024_2025:
        return False

    return True


def get_last_trading_day(date: Optional[pd.Timestamp] = None) -> pd.Timestamp:
    """
    Dapatkan hari bursa terakhir sebelum tanggal tertentu.

    Args:
        date: Tanggal referensi (default: hari ini)

    Returns:
        Timestamp hari bursa terakhir
    """
    if date is None:
        date = pd.Timestamp.now()

    current = date - timedelta(days=1)
    while not is_trading_day(current):
        current -= timedelta(days=1)

    return current


def format_currency(amount: float, prefix: str = "Rp") -> str:
    """Format angka ke format mata uang Indonesia."""
    return f"{prefix}{amount:,.0f}".replace(",", ".")


def format_percentage(value: float, decimals: int = 2) -> str:
    """Format angka ke persentase."""
    return f"{value:.{decimals}f}%"


def lot_to_shares(lot: int) -> int:
    """Konversi lot ke lembar saham (1 lot = 100 lembar di IDX)."""
    return lot * 100


def shares_to_lot(shares: int) -> int:
    """Konversi lembar saham ke lot (bulat ke bawah)."""
    return shares // 100
