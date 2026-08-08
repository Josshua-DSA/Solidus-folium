"""
Tests for pipeline/ — StorageManager, DataFetcher, DataCleaner,
UniverseManager, BlacklistFilter, IntradayFetcher, CryptoFetcher.
"""
import numpy as np
import pandas as pd
import pytest
import os
import tempfile
from decimal import Decimal
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from pipeline.storage import StorageManager
from pipeline.fetcher import DataFetcher, get_sector_mapping
from pipeline.data_cleaner import DataCleaner
from pipeline.universe import UniverseManager, LQ45, KOMPAS100, IDX_UNIVERSE
from pipeline.blacklist import BlacklistFilter, BLACKLIST_UNIVERSE
from pipeline.intraday_fetcher import IntradayFetcher
from pipeline.crypto_fetcher import CryptoFetcher


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path):
    """Temporary SQLite database."""
    db_path = str(tmp_path / "test.db")
    return db_path


@pytest.fixture
def storage(tmp_db):
    """StorageManager with temp database."""
    return StorageManager(db_path=tmp_db)


@pytest.fixture
def sample_ohlcv():
    """Sample OHLCV DataFrame for one ticker."""
    dates = pd.date_range("2023-01-02", periods=60, freq="B")
    np.random.seed(42)
    base = 10000
    close = base * np.cumprod(1 + np.random.normal(0.001, 0.015, 60))
    return pd.DataFrame({
        "date": dates,
        "open": close * 0.998,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": np.random.randint(1_000_000, 10_000_000, 60),
    })


@pytest.fixture
def wide_prices():
    """Wide-format close prices for 5 tickers."""
    dates = pd.date_range("2023-01-02", periods=60, freq="B")
    np.random.seed(42)
    data = {}
    for ticker in ["BBCA.JK", "BBRI.JK", "TLKM.JK", "ADRO.JK", "GGRM.JK"]:
        base = 5000 + np.random.randint(0, 10000)
        data[ticker] = base * np.cumprod(1 + np.random.normal(0.001, 0.015, 60))
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def wide_volume():
    """Wide-format volume for 5 tickers."""
    dates = pd.date_range("2023-01-02", periods=60, freq="B")
    np.random.seed(99)
    data = {}
    for ticker in ["BBCA.JK", "BBRI.JK", "TLKM.JK", "ADRO.JK", "GGRM.JK"]:
        data[ticker] = np.random.randint(500_000, 20_000_000, 60)
    return pd.DataFrame(data, index=dates)


# ---------------------------------------------------------------------------
# Tests: StorageManager
# ---------------------------------------------------------------------------

class TestStorageManager:
    def test_init_creates_db(self, tmp_db):
        sm = StorageManager(db_path=tmp_db)
        assert os.path.exists(tmp_db)

    def test_save_and_load_prices(self, storage, sample_ohlcv):
        storage.save_prices("BBCA.JK", sample_ohlcv)
        loaded = storage.load_prices(["BBCA.JK"])
        assert not loaded.empty
        assert "BBCA.JK" in loaded["ticker"].values
        assert len(loaded) == 60

    def test_log_return_computed(self, storage, sample_ohlcv):
        storage.save_prices("BBCA.JK", sample_ohlcv)
        loaded = storage.load_prices(["BBCA.JK"])
        # First row log_return is NaN, rest should be computed
        assert pd.isna(loaded["log_return"].iloc[0])
        assert loaded["log_return"].iloc[1:].notna().all()

    def test_load_close_prices_wide(self, storage, sample_ohlcv):
        storage.save_prices("BBCA.JK", sample_ohlcv)
        wide = storage.load_close_prices(["BBCA.JK"])
        assert "BBCA.JK" in wide.columns
        assert len(wide) == 60

    def test_load_volume_wide(self, storage, sample_ohlcv):
        storage.save_prices("BBCA.JK", sample_ohlcv)
        vol = storage.load_volume(["BBCA.JK"])
        assert "BBCA.JK" in vol.columns

    def test_get_available_tickers(self, storage, sample_ohlcv):
        storage.save_prices("BBCA.JK", sample_ohlcv)
        storage.save_prices("BBRI.JK", sample_ohlcv)
        tickers = storage.get_available_tickers()
        assert "BBCA.JK" in tickers
        assert "BBRI.JK" in tickers

    def test_get_date_range(self, storage, sample_ohlcv):
        storage.save_prices("BBCA.JK", sample_ohlcv)
        dr = storage.get_date_range()
        assert dr[0] is not None
        assert dr[1] is not None

    def test_empty_db(self, storage):
        tickers = storage.get_available_tickers()
        assert tickers == []
        prices = storage.load_prices()
        assert prices.empty

    def test_save_and_load_fundamentals(self, storage):
        metrics = {
            "pe": 15.5, "pb": 2.3, "dividend_yield": 0.03,
            "roe": 0.21, "der": 0.85, "eps": 850.0,
            "market_cap": 900_000_000_000.0,
        }
        storage.save_fundamentals("BBCA.JK", metrics)
        loaded = storage.load_fundamentals("BBCA.JK")
        assert loaded is not None
        assert loaded["pe"] == 15.5
        assert loaded["roe"] == 0.21

    def test_load_fundamentals_not_found(self, storage):
        result = storage.load_fundamentals("NONEXISTENT.JK")
        assert result is None

    def test_load_all_fundamentals(self, storage):
        storage.save_fundamentals("BBCA.JK", {"pe": 15.0})
        storage.save_fundamentals("BBRI.JK", {"pe": 12.0})
        df = storage.load_all_fundamentals()
        assert len(df) == 2

    def test_upsert_prices(self, storage, sample_ohlcv):
        """Save same ticker twice — should upsert, not duplicate."""
        storage.save_prices("BBCA.JK", sample_ohlcv)
        storage.save_prices("BBCA.JK", sample_ohlcv)
        loaded = storage.load_prices(["BBCA.JK"])
        assert len(loaded) == 60  # No duplicates

    def test_repr(self, storage):
        r = repr(storage)
        assert "StorageManager" in r


# ---------------------------------------------------------------------------
# Tests: DataFetcher
# ---------------------------------------------------------------------------

class TestDataFetcher:
    def test_init_default(self):
        f = DataFetcher()
        assert f.tickers == []
        assert f.cache_days == 7

    def test_init_with_tickers(self):
        f = DataFetcher(tickers=["BBCA.JK", "BBRI.JK"])
        assert len(f.tickers) == 2

    def test_init_with_cache_days(self):
        f = DataFetcher(cache_days=14)
        assert f.cache_days == 14

    @patch("pipeline.fetcher.yf.Ticker")
    def test_fetch_single_success(self, mock_ticker):
        """Mock yfinance untuk test tanpa network."""
        dates = pd.date_range("2023-01-02", periods=5, freq="B")
        mock_hist = pd.DataFrame({
            "Open": [100, 101, 102, 103, 104],
            "High": [105, 106, 107, 108, 109],
            "Low": [95, 96, 97, 98, 99],
            "Close": [102, 103, 104, 105, 106],
            "Volume": [1000, 2000, 3000, 4000, 5000],
        }, index=dates)

        mock_instance = MagicMock()
        mock_instance.history.return_value = mock_hist
        mock_ticker.return_value = mock_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            f = DataFetcher(cache_dir=tmpdir)
            df = f.fetch_single("BBCA.JK", start="2023-01-01", end="2023-01-10")

        assert df is not None
        assert len(df) == 5
        assert "ticker" in df.columns
        assert "date" in df.columns
        assert df["ticker"].iloc[0] == "BBCA.JK"

    @patch("pipeline.fetcher.yf.Ticker")
    def test_fetch_single_empty(self, mock_ticker):
        """Empty result dari yfinance."""
        mock_instance = MagicMock()
        mock_instance.history.return_value = pd.DataFrame()
        mock_ticker.return_value = mock_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            f = DataFetcher(cache_dir=tmpdir)
            df = f.fetch_single("NONEXISTENT.JK")

        assert df is None

    def test_get_sector_mapping(self):
        mapping = get_sector_mapping()
        assert isinstance(mapping, dict)
        assert "BBCA.JK" in mapping
        assert mapping["BBCA.JK"] == "Banking"
        assert mapping["TLKM.JK"] == "Telecom"

    def test_repr(self):
        f = DataFetcher(tickers=["BBCA.JK"], cache_days=3)
        r = repr(f)
        assert "DataFetcher" in r
        assert "1" in r  # 1 ticker


# ---------------------------------------------------------------------------
# Tests: DataCleaner
# ---------------------------------------------------------------------------

class TestDataCleaner:
    def test_init(self):
        dc = DataCleaner()
        assert dc.max_return_threshold == 0.25
        assert dc.max_forward_fill == 5

    def test_remove_anomaly_clean_data(self, wide_prices):
        dc = DataCleaner()
        cleaned = dc.remove_anomaly(wide_prices)
        # No extreme anomalies in random walk → same shape
        assert cleaned.shape == wide_prices.shape

    def test_remove_anomaly_with_spike(self, wide_prices):
        """Inject artificial anomaly → should be removed."""
        dc = DataCleaner(max_return_threshold=0.25, max_anomaly_ratio=0.50)
        # Make >50% of tickers spike >25% on one day
        spiked = wide_prices.copy()
        for col in spiked.columns:
            spiked.iloc[30, spiked.columns.get_loc(col)] *= 2.0  # 100% spike
        cleaned = dc.remove_anomaly(spiked)
        assert len(cleaned) < len(spiked)

    def test_fill_missing(self, wide_prices):
        dc = DataCleaner()
        # Inject NaN
        with_nan = wide_prices.copy()
        with_nan.iloc[10, 0] = np.nan
        with_nan.iloc[11, 0] = np.nan
        filled = dc.fill_missing(with_nan)
        assert filled.iloc[10, 0] == wide_prices.iloc[9, 0]  # Forward filled

    def test_clean_pipeline(self, wide_prices):
        dc = DataCleaner()
        cleaned = dc.clean(wide_prices)
        assert not cleaned.empty
        assert cleaned.shape[1] == wide_prices.shape[1]

    def test_repr(self):
        dc = DataCleaner()
        assert "DataCleaner" in repr(dc)


# ---------------------------------------------------------------------------
# Tests: UniverseManager
# ---------------------------------------------------------------------------

class TestUniverseManager:
    def test_lq45(self):
        um = UniverseManager(universe_name="lq45")
        tickers = um.get_tickers()
        assert len(tickers) == len(LQ45)
        assert "BBCA.JK" in tickers

    def test_kompas100(self):
        um = UniverseManager(universe_name="kompas100")
        tickers = um.get_tickers()
        assert len(tickers) > 0
        assert len(tickers) == len(set(KOMPAS100))  # No duplicates

    def test_idx_all(self):
        um = UniverseManager(universe_name="idx_all")
        tickers = um.get_tickers()
        assert len(tickers) > 100

    def test_custom(self):
        custom = ["BBCA.JK", "BBRI.JK"]
        um = UniverseManager(universe_name="custom", custom_tickers=custom)
        assert um.get_tickers() == sorted(custom)

    def test_custom_no_tickers_raises(self):
        with pytest.raises(ValueError):
            UniverseManager(universe_name="custom")

    def test_unknown_universe_raises(self):
        with pytest.raises(ValueError):
            UniverseManager(universe_name="nonexistent")

    def test_repr(self):
        um = UniverseManager(universe_name="lq45")
        assert "lq45" in repr(um)


# ---------------------------------------------------------------------------
# Tests: BlacklistFilter
# ---------------------------------------------------------------------------

class TestBlacklistFilter:
    def test_init(self):
        bf = BlacklistFilter()
        assert bf.min_price == 200.0
        assert bf.min_avg_volume == 1_000_000

    def test_filter_removes_low_price(self, wide_prices):
        """Stocks below min_price should be filtered out."""
        bf = BlacklistFilter(min_price=200.0)
        # All our test prices are >5000, so all should pass price filter
        passed = bf.filter(wide_prices)
        assert len(passed) == len(wide_prices.columns)

    def test_filter_removes_blacklisted(self, wide_prices):
        """Manually blacklisted ticker should be removed."""
        bf = BlacklistFilter(manual_blacklist=["BBCA.JK"])
        passed = bf.filter(wide_prices)
        assert "BBCA.JK" not in passed

    def test_filter_with_volume(self, wide_prices, wide_volume):
        bf = BlacklistFilter(min_avg_volume=1_000_000)
        passed = bf.filter(wide_prices, volume=wide_volume)
        assert isinstance(passed, list)

    def test_static_blacklist_loaded(self):
        bf = BlacklistFilter()
        assert len(bf.static_blacklist) == len(BLACKLIST_UNIVERSE)
        assert "SRIL.JK" in bf.static_blacklist  # Known blacklisted

    def test_repr(self):
        bf = BlacklistFilter()
        assert "BlacklistFilter" in repr(bf)


# ---------------------------------------------------------------------------
# Tests: IntradayFetcher
# ---------------------------------------------------------------------------

class TestIntradayFetcher:
    def test_init(self):
        f = IntradayFetcher()
        assert f.batch_size == 10
        assert f.delay_seconds == 3

    def test_calculate_hour0_metrics_empty(self):
        f = IntradayFetcher()
        result = f.calculate_hour0_metrics(pd.DataFrame())
        assert result.empty

    def test_calculate_hour0_metrics(self):
        """Test Hour-0 metrics calculation with synthetic hourly data."""
        f = IntradayFetcher()
        dates = []
        for day in pd.date_range("2023-06-01", periods=3, freq="B"):
            for hour in [9, 10, 11, 13, 14, 15]:
                dates.append(day.replace(hour=hour))

        np.random.seed(42)
        n = len(dates)
        hourly_df = pd.DataFrame({
            "date": dates,
            "ticker": ["BBCA.JK"] * n,
            "open": np.random.uniform(9800, 10200, n),
            "high": np.random.uniform(10000, 10400, n),
            "low": np.random.uniform(9600, 10000, n),
            "close": np.random.uniform(9800, 10200, n),
            "volume": np.random.randint(100000, 500000, n),
        })

        result = f.calculate_hour0_metrics(hourly_df)
        assert not result.empty
        assert "h0_spike_pct" in result.columns
        assert "h0_fade_pct" in result.columns
        assert "h0_net_pct" in result.columns


# ---------------------------------------------------------------------------
# Tests: CryptoFetcher
# ---------------------------------------------------------------------------

class TestCryptoFetcher:
    def test_init(self):
        cf = CryptoFetcher()
        assert cf.exchange_id == "binanceusdm"
        assert cf.default_timeframe == "1d"

    def test_repr(self):
        cf = CryptoFetcher()
        assert "CryptoFetcher" in repr(cf)
        assert "binanceusdm" in repr(cf)

    def test_get_exchange_requires_ccxt(self):
        """Should raise ImportError if ccxt not installed."""
        cf = CryptoFetcher()
        try:
            import ccxt  # noqa: F401
            # If ccxt is installed, _get_exchange should work
            exchange = cf._get_exchange()
            assert exchange is not None
        except ImportError:
            with pytest.raises(ImportError, match="ccxt"):
                cf._get_exchange()
