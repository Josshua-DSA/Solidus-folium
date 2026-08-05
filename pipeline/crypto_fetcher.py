"""
Crypto Fetcher — Fetches crypto futures data via CCXT (Binance).
Layer 1: pipeline/ — Data Ingestion.
"""
import pandas as pd
from typing import List, Optional, Dict
import logging

logger = logging.getLogger(__name__)


class CryptoFetcher:
    """
    Fetches crypto futures data from Binance via CCXT.

    Args:
        exchange_id: CCXT exchange identifier (default: 'binanceusdm')
        default_timeframe: Default OHLCV interval (default: '1d')
    """

    def __init__(
        self,
        exchange_id: str = "binanceusdm",
        default_timeframe: str = "1d",
    ):
        self.exchange_id = exchange_id
        self.default_timeframe = default_timeframe
        self._exchange = None

    def _get_exchange(self):
        """Lazy-load CCXT exchange instance."""
        if self._exchange is None:
            try:
                import ccxt
                exchange_class = getattr(ccxt, self.exchange_id)
                self._exchange = exchange_class({
                    "enableRateLimit": True,
                })
            except ImportError:
                raise ImportError(
                    "ccxt is required for CryptoFetcher. "
                    "Install with: pip install ccxt"
                )
        return self._exchange

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: Optional[str] = None,
        since: Optional[int] = None,
        limit: int = 500,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data for a single crypto pair.

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Candle interval ('1h', '4h', '1d')
            since: Start timestamp in ms (Unix epoch)
            limit: Max candles to fetch

        Returns:
            DataFrame with columns: date, open, high, low, close, volume, ticker
        """
        exchange = self._get_exchange()
        tf = timeframe or self.default_timeframe

        try:
            ohlcv = exchange.fetch_ohlcv(symbol, tf, since=since, limit=limit)
        except Exception as e:
            logger.error("Failed to fetch %s: %s", symbol, e)
            return pd.DataFrame()

        if not ohlcv:
            return pd.DataFrame()

        df = pd.DataFrame(
            ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["ticker"] = symbol
        df = df[["date", "ticker", "open", "high", "low", "close", "volume"]]
        return df

    def fetch_multiple(
        self,
        symbols: List[str],
        timeframe: Optional[str] = None,
        limit: int = 500,
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch OHLCV for multiple crypto pairs.

        Args:
            symbols: List of trading pairs
            timeframe: Candle interval
            limit: Max candles per symbol

        Returns:
            Dict mapping symbol to DataFrame
        """
        results = {}
        for symbol in symbols:
            df = self.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if not df.empty:
                results[symbol] = df
                logger.info("✓ %s: %d rows", symbol, len(df))
            else:
                logger.warning("✗ %s: no data", symbol)
        return results

    def __repr__(self) -> str:
        return f"CryptoFetcher(exchange={self.exchange_id}, tf={self.default_timeframe})"
