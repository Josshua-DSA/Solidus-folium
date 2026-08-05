"""Test DataCleaner."""
import numpy as np
import pandas as pd
import pytest

from pipeline.data_cleaner import DataCleaner


def test_remove_anomaly():
    """Tanggal dengan >50% aset return ekstrem harus dihapus."""
    dates = pd.date_range("2024-01-01", periods=10)
    tickers = ["A", "B", "C", "D"]
    data = np.ones((10, 4))
    # Buat anomali di tanggal ke-5: 3 dari 4 aset return ekstrem
    data[5] = [2.0, 0.3, 3.0, 0.01]
    df = pd.DataFrame(data, index=dates, columns=tickers)

    cleaner = DataCleaner(max_return_threshold=0.25, max_anomaly_ratio=0.50)
    result = cleaner.remove_anomaly(df)
    assert len(result) < len(df)


def test_fill_missing():
    """Forward fill harus mengisi NaN maksimum N hari."""
    dates = pd.date_range("2024-01-01", periods=10)
    df = pd.DataFrame(
        {"A": [1, 2, np.nan, np.nan, 5, 6, 7, 8, 9, 10]},
        index=dates,
    )

    cleaner = DataCleaner(max_forward_fill=3)
    result = cleaner.fill_missing(df)
    # NaN di index 2 dan 3 harus terisi (limit=3 > 2 NaN berturut)
    assert result["A"].iloc[2] == 2.0
    assert result["A"].iloc[3] == 2.0


def test_fill_missing_exceeds_limit():
    """NaN yang melebihi limit tidak boleh diisi."""
    dates = pd.date_range("2024-01-01", periods=10)
    df = pd.DataFrame(
        {"A": [1, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, 8, 9, 10]},
        index=dates,
    )

    cleaner = DataCleaner(max_forward_fill=2)
    result = cleaner.fill_missing(df)
    # Hanya 2 NaN pertama yang terisi
    assert not np.isnan(result["A"].iloc[2])
    assert np.isnan(result["A"].iloc[5])
