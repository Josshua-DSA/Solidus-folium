"""
Data Fetcher Module — Layer 1: pipeline/ — Data Ingestion.
Fetches OHLCV data for Indonesian stocks using Yahoo Finance.

Menyediakan dua mode:
  - fetch_single(): Satu ticker at a time (digunakan oleh cli.py orchestrator)
  - fetch_batch():  Bulk download semua ticker sekaligus (lebih efisien)
  - fetch_historical(): Per-ticker dict (legacy compat)

Caching: Pickle-based per-request cache dengan expiry (default 7 hari).
"""
import yfinance as yf
import pandas as pd
import os
import time
import pickle
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict
import logging

logger = logging.getLogger(__name__)


class DataFetcher:
    """
    Fetches stock data from Yahoo Finance for Indonesian stocks.
    Indonesian stocks use .JK suffix (e.g., BBCA.JK for Bank Central Asia).

    Args:
        tickers: Optional list of tickers (for batch mode)
        cache_dir: Directory for caching fetched data
        cache_days: Cache validity in days (default 7)
    """

    def __init__(
        self,
        tickers: Optional[List[str]] = None,
        cache_dir: str = ".cache",
        cache_days: int = 7,
    ):
        self.tickers = sorted(tickers) if tickers else []
        self.cache_dir = cache_dir
        self.cache_days = cache_days
        os.makedirs(self.cache_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _cache_path(self, key: str) -> str:
        """Generate cache file path dari key."""
        safe_key = hashlib.md5(key.encode()).hexdigest()[:12]
        return os.path.join(self.cache_dir, f"fetch_{safe_key}.pkl")

    def _load_cache(self, cache_path: str) -> Optional[pd.DataFrame]:
        """Load dari cache jika masih valid."""
        if not os.path.exists(cache_path):
            return None

        # Cek expiry
        mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
        if datetime.now() - mtime > timedelta(days=self.cache_days):
            logger.debug("Cache expired: %s", cache_path)
            return None

        try:
            with open(cache_path, "rb") as f:
                df = pickle.load(f)
            logger.info("✓ Cache hit: %s (%d rows)", cache_path, len(df))
            return df
        except Exception as e:
            logger.warning("Failed to load cache: %s", e)
            return None

    def _save_cache(self, cache_path: str, df: pd.DataFrame) -> None:
        """Simpan ke cache."""
        try:
            with open(cache_path, "wb") as f:
                pickle.dump(df, f)
        except Exception as e:
            logger.warning("Failed to save cache: %s", e)

    # ------------------------------------------------------------------
    # Core: fetch single ticker
    # ------------------------------------------------------------------

    def fetch_single(
        self,
        ticker: str,
        start: str = "2015-01-01",
        end: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV data untuk satu ticker.

        Args:
            ticker: Stock ticker (e.g. 'BBCA.JK')
            start: Start date string (YYYY-MM-DD)
            end: End date string (default: hari ini)

        Returns:
            DataFrame dengan kolom: date, open, high, low, close, volume, ticker
            None jika gagal/kosong
        """
        if end is None:
            end = datetime.now().strftime("%Y-%m-%d")

        # Check cache
        cache_key = f"{ticker}_{start}_{end}"
        cache_path = self._cache_path(cache_key)
        cached = self._load_cache(cache_path)
        if cached is not None:
            return cached

        try:
            stock = yf.Ticker(ticker)
            df = stock.history(start=start, end=end, auto_adjust=True)

            if df is None or df.empty:
                logger.warning("✗ %s: no data returned", ticker)
                return None

            # Standardize column names
            df = df.rename(columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            })

            # Keep only OHLCV columns
            keep_cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
            df = df[keep_cols]

            # Add ticker + reset index
            df["ticker"] = ticker
            df = df.reset_index()
            df = df.rename(columns={"Date": "date", "index": "date"})

            # Ensure date is timezone-naive datetime
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)

            # Cache result
            self._save_cache(cache_path, df)

            logger.info("✓ %s: %d rows (%s → %s)", ticker, len(df), start, end)
            return df

        except Exception as e:
            logger.error("✗ %s: %s", ticker, e)
            return None

    # ------------------------------------------------------------------
    # Batch: fetch multiple tickers at once (yf.download)
    # ------------------------------------------------------------------

    def fetch_batch(
        self,
        tickers: Optional[List[str]] = None,
        days: int = 730,
        end_date: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Fetch all tickers sekaligus via yf.download (lebih efisien).

        Args:
            tickers: List ticker (override self.tickers)
            days: Number of days of history
            end_date: End date (default: today)

        Returns:
            Combined DataFrame (long format) semua ticker
        """
        ticker_list = tickers or self.tickers
        if not ticker_list:
            logger.warning("No tickers provided for batch fetch")
            return pd.DataFrame()

        if end_date is None:
            end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Check cache
        ticker_hash = hashlib.md5("".join(sorted(ticker_list)).encode()).hexdigest()[:8]
        cache_key = f"batch_{start_date.date()}_{end_date.date()}_{ticker_hash}"
        cache_path = self._cache_path(cache_key)
        cached = self._load_cache(cache_path)
        if cached is not None:
            return cached

        logger.info(
            "Batch fetching %d tickers: %s → %s",
            len(ticker_list), start_date.date(), end_date.date(),
        )

        try:
            df = yf.download(
                ticker_list,
                start=start_date,
                end=end_date,
                auto_adjust=True,
                group_by="ticker",
                threads=False,  # Avoid NoneType error in some environments
                progress=True,
            )

            if df is None or df.empty:
                logger.error("Batch download returned empty DataFrame")
                return pd.DataFrame()

            # Restructure multi-level columns → long format
            records = []
            for ticker in ticker_list:
                try:
                    if ticker in df.columns.get_level_values(0):
                        ticker_df = df[ticker].copy().dropna()
                        if len(ticker_df) > 0:
                            ticker_df = ticker_df.reset_index()
                            ticker_df.columns = [c.lower() for c in ticker_df.columns]
                            rename_map = {"price": "close", "adj close": "close"}
                            ticker_df = ticker_df.rename(columns=rename_map)
                            ticker_df["ticker"] = ticker
                            ticker_df["date"] = pd.to_datetime(
                                ticker_df["date"]
                            ).dt.tz_localize(None)
                            records.append(ticker_df)
                except Exception as e:
                    logger.warning("Error processing %s: %s", ticker, e)

            if records:
                combined = pd.concat(records, ignore_index=True)
                combined = combined[["date", "ticker", "open", "high", "low", "close", "volume"]]
                self._save_cache(cache_path, combined)
                logger.info("Batch fetch complete: %d total rows", len(combined))
                return combined

            return pd.DataFrame()

        except Exception as e:
            logger.error("Batch fetch failed: %s", e)
            # Fallback to individual fetching
            return self._fallback_individual(ticker_list, start_date, end_date)

    def _fallback_individual(
        self,
        tickers: List[str],
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Fallback: fetch satu per satu jika batch gagal."""
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        frames = []
        for ticker in tickers:
            df = self.fetch_single(ticker, start=start_str, end=end_str)
            if df is not None and not df.empty:
                frames.append(df)
        if frames:
            return pd.concat(frames, ignore_index=True)
        return pd.DataFrame()

    # ------------------------------------------------------------------
    # Legacy compat: fetch_historical (returns dict)
    # ------------------------------------------------------------------

    def fetch_historical(
        self,
        days: int = 730,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch historical OHLCV data per-ticker (returns dict).

        Args:
            days: Number of days of history to fetch
            end_date: End date (default: today)

        Returns:
            Dict mapping ticker → DataFrame
        """
        if end_date is None:
            end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        logger.info(
            "Fetching data for %d tickers from %s to %s",
            len(self.tickers), start_str, end_str,
        )

        data = {}
        failed = []
        for ticker in self.tickers:
            df = self.fetch_single(ticker, start=start_str, end=end_str)
            if df is not None and not df.empty:
                data[ticker] = df
            else:
                failed.append(ticker)

        if failed:
            logger.warning("Failed to fetch: %s", failed)
        logger.info("Successfully fetched %d/%d tickers", len(data), len(self.tickers))
        return data

    def fetch_latest(self, days: int = 5) -> Dict[str, pd.DataFrame]:
        """Fetch latest data (for daily updates)."""
        return self.fetch_historical(days=days)

    def __repr__(self) -> str:
        return (
            f"DataFetcher(tickers={len(self.tickers)}, "
            f"cache_dir='{self.cache_dir}', cache_days={self.cache_days})"
        )


# ---------------------------------------------------------------------------
# Sector mapping (standalone function)
# ---------------------------------------------------------------------------

def get_sector_mapping() -> Dict[str, str]:
    """
    Returns sector mapping for Indonesian stocks.
    Useful for sector diversification.
    """
    return {
        # Banking
        "BBCA.JK": "Banking", "BBRI.JK": "Banking", "BMRI.JK": "Banking",
        "BBNI.JK": "Banking", "BRIS.JK": "Banking",
        # Telco
        "TLKM.JK": "Telecom", "EXCL.JK": "Telecom", "ISAT.JK": "Telecom",
        # Consumer
        "UNVR.JK": "Consumer", "ICBP.JK": "Consumer", "INDF.JK": "Consumer",
        "MYOR.JK": "Consumer", "KLBF.JK": "Healthcare",
        # Mining & Energy
        "ADRO.JK": "Mining", "PTBA.JK": "Mining", "ITMG.JK": "Mining",
        "MEDC.JK": "Energy", "PGAS.JK": "Energy",
        "MDKA.JK": "Mining", "ANTM.JK": "Mining", "INCO.JK": "Mining",
        "TINS.JK": "Mining",
        # Industrials
        "ASII.JK": "Automotive", "UNTR.JK": "Machinery", "SRIL.JK": "Textile",
        # Property & Construction
        "SMGR.JK": "Materials", "WIKA.JK": "Construction",
        "PTPP.JK": "Construction", "BSDE.JK": "Property",
        # Others
        "GGRM.JK": "Tobacco", "HMSP.JK": "Tobacco",
        "ERAA.JK": "Retail", "ACES.JK": "Retail", "MAPI.JK": "Retail",
        "AKRA.JK": "Energy", "TOWR.JK": "Infrastructure",
        "TBIG.JK": "Infrastructure", "JSMR.JK": "Infrastructure",
        # Technology
        "GOTO.JK": "Technology", "BUKA.JK": "Technology",
        "EMTK.JK": "Media", "SCMA.JK": "Media",
    }
