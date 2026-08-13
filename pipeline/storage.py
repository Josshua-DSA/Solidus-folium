"""
Storage Manager — SQLite3 sebagai satu sumber kebenaran data.
Layer 1: pipeline/ — Data Pipeline.

Schema: date TEXT | ticker TEXT | open REAL | high REAL | low REAL |
        close REAL | volume INTEGER | log_return REAL
PRIMARY KEY (date, ticker)
"""
import sqlite3
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Default DB path (relative to project root)
_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ihsg_trading.db"


class StorageManager:
    """
    Engine SQLite3 untuk menyimpan dan memuat data OHLCV + log return.

    Args:
        db_path: Path ke file SQLite3 database.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path) if db_path else str(_DEFAULT_DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Buat tabel prices, fundamentals, dan intraday_ohlcv jika belum ada."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS prices (
                    date       TEXT    NOT NULL,
                    ticker     TEXT    NOT NULL,
                    open       REAL,
                    high       REAL,
                    low        REAL,
                    close      REAL,
                    volume     INTEGER,
                    log_return REAL,
                    PRIMARY KEY (date, ticker)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fundamentals (
                    ticker         TEXT    PRIMARY KEY,
                    pe             REAL,
                    pb             REAL,
                    dividend_yield REAL,
                    roe            REAL,
                    der            REAL,
                    eps            REAL,
                    market_cap     REAL,
                    last_updated   TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS intraday_ohlcv (
                    timestamp  TEXT    NOT NULL,
                    ticker     TEXT    NOT NULL,
                    open       REAL,
                    high       REAL,
                    low        REAL,
                    close      REAL,
                    volume     INTEGER,
                    PRIMARY KEY (timestamp, ticker)
                )
            """)
            # Index untuk query intraday cepat per-ticker
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_intraday_ticker
                ON intraday_ohlcv (ticker, timestamp)
            """)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    @staticmethod
    def _compute_log_returns(close_values: np.ndarray) -> np.ndarray:
        """Hitung log return: ln(close_t / close_{t-1})."""
        log_returns = np.full(len(close_values), np.nan)
        for i in range(1, len(close_values)):
            prev = close_values[i - 1]
            curr = close_values[i]
            if prev > 0 and curr > 0:
                log_returns[i] = np.log(curr / prev)
        return log_returns

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def save_prices(self, ticker: str, df: pd.DataFrame) -> None:
        """
        Simpan DataFrame OHLCV ke database (upsert).

        Args:
            ticker: Ticker saham (e.g. 'BBCA.JK')
            df: DataFrame dengan kolom date, open, high, low, close, volume
        """
        data = df.copy()

        # Pastikan kolom date ada dan string
        if "date" not in data.columns:
            if data.index.name == "date" or hasattr(data.index, "date"):
                data = data.reset_index()
            else:
                raise ValueError("DataFrame harus memiliki kolom 'date'")

        data["date"] = pd.to_datetime(data["date"]).dt.strftime("%Y-%m-%d")
        data["ticker"] = ticker

        # Hitung log return
        data = data.sort_values("date")
        close_values = data["close"].values.astype(float)
        data["log_return"] = self._compute_log_returns(close_values)

        # Upsert ke database
        with self._connect() as conn:
            for _, row in data.iterrows():
                conn.execute("""
                    INSERT OR REPLACE INTO prices
                    (date, ticker, open, high, low, close, volume, log_return)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row["date"], row["ticker"],
                    float(row["open"]), float(row["high"]),
                    float(row["low"]), float(row["close"]),
                    int(row["volume"]), 
                    float(row["log_return"]) if pd.notna(row["log_return"]) else None,
                ))
            conn.commit()

        logger.info("Saved %d rows for %s", len(data), ticker)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def load_prices(
        self, tickers: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Load semua data harga (long format).

        Args:
            tickers: Filter ticker tertentu. None = semua.

        Returns:
            DataFrame long format: date, ticker, open, high, low, close, volume, log_return
        """
        with self._connect() as conn:
            if tickers:
                placeholders = ",".join("?" * len(tickers))
                query = f"SELECT * FROM prices WHERE ticker IN ({placeholders}) ORDER BY date"
                df = pd.read_sql_query(query, conn, params=tickers)
            else:
                df = pd.read_sql_query("SELECT * FROM prices ORDER BY date", conn)

        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
        return df

    def load_close_prices(
        self, tickers: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Load close prices dalam format wide (index=date, columns=ticker).

        Returns:
            DataFrame wide format
        """
        df = self.load_prices(tickers)
        if df.empty:
            return pd.DataFrame()
        return df.pivot_table(index="date", columns="ticker", values="close")

    def load_volume(
        self, tickers: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Load volume dalam format wide (index=date, columns=ticker).

        Returns:
            DataFrame wide format
        """
        df = self.load_prices(tickers)
        if df.empty:
            return pd.DataFrame()
        return df.pivot_table(index="date", columns="ticker", values="volume")

    def get_available_tickers(self) -> List[str]:
        """Return list ticker yang tersedia di database."""
        with self._connect() as conn:
            result = conn.execute(
                "SELECT DISTINCT ticker FROM prices ORDER BY ticker"
            ).fetchall()
        return [row[0] for row in result]

    def get_date_range(self) -> Tuple[Optional[str], Optional[str]]:
        """Return (min_date, max_date) dari database."""
        with self._connect() as conn:
            result = conn.execute(
                "SELECT MIN(date), MAX(date) FROM prices"
            ).fetchone()
        return result if result else (None, None)

    def save_fundamentals(self, ticker: str, metrics: dict) -> None:
        """
        Simpan data fundamental saham ke database.
        """
        import datetime
        last_updated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO fundamentals
                (ticker, pe, pb, dividend_yield, roe, der, eps, market_cap, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker,
                metrics.get("pe"),
                metrics.get("pb"),
                metrics.get("dividend_yield"),
                metrics.get("roe"),
                metrics.get("der"),
                metrics.get("eps"),
                metrics.get("market_cap"),
                last_updated
            ))
            conn.commit()

    def load_fundamentals(self, ticker: str) -> Optional[dict]:
        """
        Muat data fundamental saham tertentu.
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM fundamentals WHERE ticker = ?", (ticker,)
            ).fetchone()
        if row:
            return dict(row)
        return None

    def load_all_fundamentals(self) -> pd.DataFrame:
        """
        Muat semua data fundamental ke DataFrame.
        """
        with self._connect() as conn:
            df = pd.read_sql_query("SELECT * FROM fundamentals", conn)
        return df

    # ------------------------------------------------------------------
    # Intraday operations
    # ------------------------------------------------------------------

    def save_intraday(self, ticker: str, df: pd.DataFrame) -> None:
        """
        Simpan DataFrame intraday OHLCV ke database (upsert).

        Args:
            ticker: Ticker saham (e.g. 'BBCA.JK')
            df: DataFrame dengan kolom timestamp/date, open, high, low, close, volume
        """
        data = df.copy()

        # Normalise timestamp column
        if "timestamp" not in data.columns:
            if "date" in data.columns:
                data = data.rename(columns={"date": "timestamp"})
            elif data.index.name in ("timestamp", "date", "Datetime"):
                data = data.reset_index()
                if "Datetime" in data.columns:
                    data = data.rename(columns={"Datetime": "timestamp"})
                elif "date" in data.columns:
                    data = data.rename(columns={"date": "timestamp"})
            else:
                raise ValueError(
                    "DataFrame harus memiliki kolom 'timestamp' atau 'date'"
                )

        data["timestamp"] = pd.to_datetime(data["timestamp"]).dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        data["ticker"] = ticker

        required_cols = ["open", "high", "low", "close", "volume"]
        for col in required_cols:
            if col not in data.columns:
                raise ValueError(f"Kolom wajib '{col}' tidak ditemukan")

        with self._connect() as conn:
            rows = [
                (
                    row["timestamp"],
                    row["ticker"],
                    float(row["open"]),
                    float(row["high"]),
                    float(row["low"]),
                    float(row["close"]),
                    int(row["volume"]),
                )
                for _, row in data.iterrows()
            ]
            conn.executemany(
                """
                INSERT OR REPLACE INTO intraday_ohlcv
                (timestamp, ticker, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()

        logger.info("Saved %d intraday rows for %s", len(rows), ticker)

    def load_intraday(
        self,
        ticker: str,
        days: int = 5,
    ) -> pd.DataFrame:
        """
        Load data intraday untuk satu ticker (N hari terakhir).

        Args:
            ticker: Ticker saham
            days: Jumlah hari terakhir (default 5)

        Returns:
            DataFrame dengan kolom timestamp, ticker, open, high, low, close, volume
        """
        import datetime as _dt

        cutoff = (_dt.datetime.now() - _dt.timedelta(days=days)).strftime(
            "%Y-%m-%d 00:00:00"
        )
        with self._connect() as conn:
            df = pd.read_sql_query(
                """
                SELECT * FROM intraday_ohlcv
                WHERE ticker = ? AND timestamp >= ?
                ORDER BY timestamp
                """,
                conn,
                params=[ticker, cutoff],
            )

        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df

    def load_intraday_all_tickers(
        self,
        days: int = 5,
    ) -> pd.DataFrame:
        """
        Load data intraday untuk semua ticker (N hari terakhir).

        Args:
            days: Jumlah hari terakhir (default 5)

        Returns:
            DataFrame long format
        """
        import datetime as _dt

        cutoff = (_dt.datetime.now() - _dt.timedelta(days=days)).strftime(
            "%Y-%m-%d 00:00:00"
        )
        with self._connect() as conn:
            df = pd.read_sql_query(
                """
                SELECT * FROM intraday_ohlcv
                WHERE timestamp >= ?
                ORDER BY ticker, timestamp
                """,
                conn,
                params=[cutoff],
            )

        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df

    def get_intraday_tickers(self) -> List[str]:
        """Return list ticker yang memiliki data intraday."""
        with self._connect() as conn:
            result = conn.execute(
                "SELECT DISTINCT ticker FROM intraday_ohlcv ORDER BY ticker"
            ).fetchall()
        return [row[0] for row in result]

    def __repr__(self) -> str:
        tickers = self.get_available_tickers()
        date_range = self.get_date_range()
        return (
            f"StorageManager(db='{self.db_path}', "
            f"tickers={len(tickers)}, range={date_range})"
        )
