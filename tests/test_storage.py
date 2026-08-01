"""Test StorageManager."""
import os
import tempfile
import numpy as np
import pandas as pd
import pytest

from data_layer.storage import StorageManager


@pytest.fixture
def temp_db():
    """Buat temporary database untuk testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_save_and_load(temp_db):
    """Data yang disimpan harus bisa di-load kembali."""
    sm = StorageManager(db_path=temp_db)

    dates = pd.date_range("2024-01-01", periods=5)
    df = pd.DataFrame({
        "date": dates,
        "open": [100, 101, 102, 103, 104],
        "high": [105, 106, 107, 108, 109],
        "low": [99, 100, 101, 102, 103],
        "close": [102, 103, 104, 105, 106],
        "volume": [1000, 1100, 1200, 1300, 1400],
    })

    sm.save_prices("BBCA.JK", df)

    # Load back
    loaded = sm.load_prices(tickers=["BBCA.JK"])
    assert len(loaded) == 5
    assert "BBCA.JK" in loaded["ticker"].values


def test_log_return_computation(temp_db):
    """Log return harus dihitung dengan benar."""
    sm = StorageManager(db_path=temp_db)

    dates = pd.date_range("2024-01-01", periods=3)
    df = pd.DataFrame({
        "date": dates,
        "open": [100, 110, 105],
        "high": [110, 115, 110],
        "low": [99, 108, 103],
        "close": [100, 110, 105],
        "volume": [1000, 1100, 1200],
    })

    sm.save_prices("TEST.JK", df)
    loaded = sm.load_prices(tickers=["TEST.JK"])

    # Log return baris pertama harus NaN
    assert np.isnan(loaded.iloc[0]["log_return"])
    # Log return baris kedua: ln(110/100) ≈ 0.0953
    expected_lr = np.log(110 / 100)
    assert abs(loaded.iloc[1]["log_return"] - expected_lr) < 0.001


def test_fundamentals(temp_db):
    """Data fundamental harus bisa disimpan dan di-load."""
    sm = StorageManager(db_path=temp_db)
    metrics = {
        "pe": 15.4,
        "pb": 2.1,
        "dividend_yield": 0.035,
        "roe": 0.185,
        "der": 0.45,
        "eps": 250.0,
        "market_cap": 500000000000.0,
    }
    sm.save_fundamentals("BBCA.JK", metrics)
    loaded = sm.load_fundamentals("BBCA.JK")
    assert loaded is not None
    assert loaded["pe"] == 15.4
    assert loaded["pb"] == 2.1
    assert loaded["roe"] == 0.185
    assert loaded["eps"] == 250.0
    assert loaded["ticker"] == "BBCA.JK"
    assert loaded["last_updated"] is not None

    all_funds = sm.load_all_fundamentals()
    assert len(all_funds) == 1
    assert "pe" in all_funds.columns

