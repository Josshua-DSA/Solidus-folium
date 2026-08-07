"""
Data Service — Facade untuk query data dari pipeline/ storage.

Menyediakan API bersih untuk TUI dan consumer lainnya
tanpa perlu tahu detail internal StorageManager.
"""
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging

from pipeline.storage import StorageManager
from shared.utils.config_loader import load_config

logger = logging.getLogger(__name__)


class DataService:
    """
    Service layer untuk akses data harga dan fundamentals.

    Args:
        db_path: Path ke SQLite database (None = default)
        config_path: Path ke config.yaml (None = default)
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        config_path: Optional[str] = None,
    ):
        self._config = load_config(config_path) if config_path else {}
        if db_path is None:
            db_path = self._config.get("data", {}).get("db_path")
        self.storage = StorageManager(db_path=db_path)

    # ------------------------------------------------------------------
    # Tickers & availability
    # ------------------------------------------------------------------

    def get_available_tickers(self) -> List[str]:
        """Return list ticker yang tersedia di database."""
        return self.storage.get_available_tickers()

    def get_date_range(self) -> Tuple[Optional[str], Optional[str]]:
        """Return (min_date, max_date) dari database."""
        return self.storage.get_date_range()

    def is_db_populated(self) -> bool:
        """Cek apakah database sudah punya data."""
        tickers = self.get_available_tickers()
        return len(tickers) > 0

    # ------------------------------------------------------------------
    # Price data
    # ------------------------------------------------------------------

    def get_prices(
        self,
        tickers: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Load data harga (long format).

        Args:
            tickers: Filter ticker. None = semua.

        Returns:
            DataFrame: date, ticker, open, high, low, close, volume, log_return
        """
        return self.storage.load_prices(tickers)

    def get_close_prices(
        self,
        tickers: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Load close prices (wide format: index=date, columns=ticker).

        Args:
            tickers: Filter ticker. None = semua.

        Returns:
            DataFrame wide format close prices
        """
        return self.storage.load_close_prices(tickers)

    def get_volume(
        self,
        tickers: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Load volume (wide format)."""
        return self.storage.load_volume(tickers)

    def get_latest_prices(
        self,
        tickers: Optional[List[str]] = None,
    ) -> Dict[str, float]:
        """
        Return harga close terakhir per ticker.

        Returns:
            Dict {ticker: last_close_price}
        """
        close = self.get_close_prices(tickers)
        if close.empty:
            return {}
        last = close.iloc[-1]
        return {ticker: float(price) for ticker, price in last.items() if pd.notna(price)}

    # ------------------------------------------------------------------
    # Fundamentals
    # ------------------------------------------------------------------

    def get_fundamentals(self, ticker: str) -> Optional[Dict]:
        """Load data fundamental untuk satu ticker."""
        return self.storage.load_fundamentals(ticker)

    def get_all_fundamentals(self) -> pd.DataFrame:
        """Load semua data fundamental."""
        return self.storage.load_all_fundamentals()

    # ------------------------------------------------------------------
    # Status / info
    # ------------------------------------------------------------------

    def get_db_status(self) -> Dict:
        """Return ringkasan status database."""
        tickers = self.get_available_tickers()
        date_range = self.get_date_range()
        return {
            "db_path": self.storage.db_path,
            "n_tickers": len(tickers),
            "tickers": tickers,
            "date_start": date_range[0],
            "date_end": date_range[1],
            "is_populated": len(tickers) > 0,
        }

    def __repr__(self) -> str:
        status = self.get_db_status()
        return (
            f"DataService(tickers={status['n_tickers']}, "
            f"range={status['date_start']}→{status['date_end']})"
        )
