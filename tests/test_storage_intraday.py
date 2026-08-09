"""
Tests for StorageManager intraday operations.
"""
import pandas as pd
import pytest
import tempfile
import os

from pipeline.storage import StorageManager


class TestStorageIntraday:
    @pytest.fixture
    def temp_storage(self):
        """Create a temp DB StorageManager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            yield StorageManager(db_path=db_path)

    @pytest.fixture
    def sample_intraday_df(self):
        """Sample hourly OHLCV data for 3 days."""
        rows = []
        for day in range(3):
            for hour in range(9, 16):
                rows.append({
                    "timestamp": f"2026-01-{15+day:02d} {hour:02d}:00:00",
                    "open": 9000.0 + day * 10 + hour,
                    "high": 9050.0 + day * 10 + hour,
                    "low": 8950.0 + day * 10 + hour,
                    "close": 9020.0 + day * 10 + hour,
                    "volume": 100000 + hour * 1000,
                })
        return pd.DataFrame(rows)

    def test_save_intraday_basic(self, temp_storage, sample_intraday_df):
        """save_intraday harus menyimpan tanpa error."""
        temp_storage.save_intraday("BBCA.JK", sample_intraday_df)
        # Verify tersimpan
        tickers = temp_storage.get_intraday_tickers()
        assert "BBCA.JK" in tickers

    def test_load_intraday_basic(self, temp_storage, sample_intraday_df):
        """load_intraday harus return data yang tersimpan."""
        temp_storage.save_intraday("BBCA.JK", sample_intraday_df)
        df = temp_storage.load_intraday("BBCA.JK", days=9999)
        assert not df.empty
        assert len(df) == len(sample_intraday_df)
        assert "timestamp" in df.columns
        assert "ticker" in df.columns
        assert "close" in df.columns

    def test_load_intraday_empty(self, temp_storage):
        """load_intraday harus return empty jika tidak ada data."""
        df = temp_storage.load_intraday("FAKE.JK", days=5)
        assert df.empty

    def test_save_intraday_upsert(self, temp_storage, sample_intraday_df):
        """save_intraday harus upsert (not duplicate)."""
        temp_storage.save_intraday("BBCA.JK", sample_intraday_df)
        # Save again -> should upsert, not duplicate
        temp_storage.save_intraday("BBCA.JK", sample_intraday_df)
        df = temp_storage.load_intraday("BBCA.JK", days=9999)
        assert len(df) == len(sample_intraday_df)

    def test_save_intraday_multiple_tickers(self, temp_storage, sample_intraday_df):
        """Multiple tickers harus tersimpan terpisah."""
        temp_storage.save_intraday("BBCA.JK", sample_intraday_df)
        temp_storage.save_intraday("BBRI.JK", sample_intraday_df)
        tickers = temp_storage.get_intraday_tickers()
        assert set(tickers) == {"BBCA.JK", "BBRI.JK"}

    def test_load_intraday_all_tickers(self, temp_storage, sample_intraday_df):
        """load_intraday_all_tickers harus return semua ticker."""
        temp_storage.save_intraday("BBCA.JK", sample_intraday_df)
        temp_storage.save_intraday("BBRI.JK", sample_intraday_df)
        df = temp_storage.load_intraday_all_tickers(days=9999)
        assert not df.empty
        assert set(df["ticker"].unique()) == {"BBCA.JK", "BBRI.JK"}

    def test_save_intraday_with_date_column(self, temp_storage):
        """save_intraday harus handle kolom 'date' sebagai alias timestamp."""
        df = pd.DataFrame({
            "date": ["2026-01-15 09:00:00", "2026-01-15 10:00:00"],
            "open": [9000.0, 9010.0],
            "high": [9050.0, 9060.0],
            "low": [8950.0, 8960.0],
            "close": [9020.0, 9030.0],
            "volume": [100000, 110000],
        })
        temp_storage.save_intraday("BBCA.JK", df)
        loaded = temp_storage.load_intraday("BBCA.JK", days=9999)
        assert len(loaded) == 2

    def test_save_intraday_missing_column(self, temp_storage):
        """save_intraday harus raise ValueError jika kolom wajib tidak ada."""
        df = pd.DataFrame({
            "timestamp": ["2026-01-15 09:00:00"],
            "open": [9000.0],
            # missing high, low, close, volume
        })
        with pytest.raises(ValueError, match="Kolom wajib"):
            temp_storage.save_intraday("BBCA.JK", df)

    def test_get_intraday_tickers_empty(self, temp_storage):
        """get_intraday_tickers harus return empty jika tidak ada data."""
        assert temp_storage.get_intraday_tickers() == []

    def test_intraday_does_not_affect_daily(self, temp_storage, sample_intraday_df):
        """Intraday operations harus tidak mempengaruhi tabel daily prices."""
        temp_storage.save_intraday("BBCA.JK", sample_intraday_df)
        # Daily prices harus tetap kosong
        daily = temp_storage.load_prices(["BBCA.JK"])
        assert daily.empty

    def test_intraday_timestamp_parsed(self, temp_storage, sample_intraday_df):
        """Loaded intraday timestamp harus bertype datetime."""
        temp_storage.save_intraday("BBCA.JK", sample_intraday_df)
        df = temp_storage.load_intraday("BBCA.JK", days=9999)
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
