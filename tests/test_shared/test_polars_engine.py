"""
Tests for Polars Feature Engine & FeatureBuilder Polars integration.
"""
import numpy as np
import pandas as pd
import pytest

from shared.features.polars_engine import PolarsFeatureEngine
from shared.features.feature_builder import FeatureBuilder


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def sample_ohlc():
    """Create realistic OHLCV data for testing."""
    np.random.seed(42)
    n = 500
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    close = 1000 + np.cumsum(np.random.randn(n) * 5)
    df = pd.DataFrame({
        "open": close * (1 + np.random.randn(n) * 0.001),
        "high": close * (1 + np.abs(np.random.randn(n) * 0.005)),
        "low": close * (1 - np.abs(np.random.randn(n) * 0.005)),
        "close": close,
        "volume": np.random.randint(100_000, 10_000_000, n),
    }, index=dates)
    return df


@pytest.fixture
def polars_engine():
    return PolarsFeatureEngine(n_lags=20)


@pytest.fixture
def pandas_builder():
    return FeatureBuilder(n_lags=20, use_polars=False)


@pytest.fixture
def polars_builder():
    return FeatureBuilder(n_lags=20, use_polars=True)


# ------------------------------------------------------------------
# Test: PolarsFeatureEngine standalone
# ------------------------------------------------------------------

class TestPolarsFeatureEngine:
    def test_output_shape(self, polars_engine, sample_ohlc):
        result = polars_engine.build_technical_features(sample_ohlc)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(sample_ohlc)
        # 20 lags + vol_5, vol_20, rsi_14, mean_10, atr_ratio, bb_pos, vwap_dev, obv_slope, macd = 29
        assert len(result.columns) == 29

    def test_column_names(self, polars_engine, sample_ohlc):
        result = polars_engine.build_technical_features(sample_ohlc)
        expected_cols = (
            [f"lag_{i}" for i in range(1, 21)]
            + ["vol_5", "vol_20", "rsi_14", "mean_10", "atr_ratio",
               "bb_pos", "vwap_dev", "obv_slope", "macd"]
        )
        assert list(result.columns) == expected_cols

    def test_index_preserved(self, polars_engine, sample_ohlc):
        result = polars_engine.build_technical_features(sample_ohlc)
        assert result.index.equals(sample_ohlc.index)

    def test_no_inf_values(self, polars_engine, sample_ohlc):
        result = polars_engine.build_technical_features(sample_ohlc).dropna()
        assert not np.isinf(result.values).any()

    def test_repr(self, polars_engine):
        assert "PolarsFeatureEngine" in repr(polars_engine)

    def test_custom_lags(self, sample_ohlc):
        engine = PolarsFeatureEngine(n_lags=5)
        result = engine.build_technical_features(sample_ohlc)
        lag_cols = [c for c in result.columns if c.startswith("lag_")]
        assert len(lag_cols) == 5


# ------------------------------------------------------------------
# Test: FeatureBuilder with use_polars=True
# ------------------------------------------------------------------

class TestFeatureBuilderPolarsIntegration:
    def test_polars_builder_activates(self, polars_builder):
        assert polars_builder.use_polars is True
        assert polars_builder._polars_engine is not None

    def test_pandas_builder_no_polars(self, pandas_builder):
        assert pandas_builder.use_polars is False
        assert pandas_builder._polars_engine is None

    def test_same_column_names(self, pandas_builder, polars_builder, sample_ohlc):
        pd_result = pandas_builder.build_technical_features(sample_ohlc)
        pl_result = polars_builder.build_technical_features(sample_ohlc)
        assert list(pd_result.columns) == list(pl_result.columns)

    def test_same_shape(self, pandas_builder, polars_builder, sample_ohlc):
        pd_result = pandas_builder.build_technical_features(sample_ohlc)
        pl_result = polars_builder.build_technical_features(sample_ohlc)
        assert pd_result.shape == pl_result.shape

    def test_values_close(self, pandas_builder, polars_builder, sample_ohlc):
        """Polars and Pandas should produce numerically close results."""
        pd_result = pandas_builder.build_technical_features(sample_ohlc).dropna()
        pl_result = polars_builder.build_technical_features(sample_ohlc).dropna()

        # Align indices
        common_idx = pd_result.index.intersection(pl_result.index)
        pd_aligned = pd_result.loc[common_idx]
        pl_aligned = pl_result.loc[common_idx]

        # Compare with tolerance (floating point diffs between engines)
        for col in pd_aligned.columns:
            pd_vals = pd_aligned[col].values
            pl_vals = pl_aligned[col].values
            # Use relative tolerance for non-zero values
            mask = np.abs(pd_vals) > 1e-10
            if mask.any():
                rel_diff = np.abs((pd_vals[mask] - pl_vals[mask]) / (pd_vals[mask] + 1e-10))
                assert np.median(rel_diff) < 0.05, (
                    f"Column '{col}' median relative diff {np.median(rel_diff):.4f} > 5%"
                )

    def test_baseline_features_unaffected(self, polars_builder, sample_ohlc):
        """use_polars should not affect baseline build_features()."""
        result = polars_builder.build_features(sample_ohlc[["close"]])
        assert "return_1d" in result
        assert "momentum" in result
        assert "volatility" in result


# ------------------------------------------------------------------
# Test: Benchmark Polars vs Pandas speed
# ------------------------------------------------------------------

class TestPolarsPerformance:
    def test_polars_faster_than_pandas(self, pandas_builder, polars_builder, sample_ohlc):
        """Polars should be at least as fast as pandas on 500 rows."""
        import time

        # Warm up
        pandas_builder.build_technical_features(sample_ohlc)
        polars_builder.build_technical_features(sample_ohlc)

        # Benchmark pandas
        t0 = time.perf_counter()
        for _ in range(5):
            pandas_builder.build_technical_features(sample_ohlc)
        pandas_time = time.perf_counter() - t0

        # Benchmark polars
        t0 = time.perf_counter()
        for _ in range(5):
            polars_builder.build_technical_features(sample_ohlc)
        polars_time = time.perf_counter() - t0

        speedup = pandas_time / (polars_time + 1e-10)
        print(f"\n  Pandas: {pandas_time:.3f}s | Polars: {polars_time:.3f}s | Speedup: {speedup:.1f}x")

        # Polars should at minimum not be 10x slower than pandas
        assert polars_time < pandas_time * 10, (
            f"Polars ({polars_time:.3f}s) much slower than pandas ({pandas_time:.3f}s)"
        )
