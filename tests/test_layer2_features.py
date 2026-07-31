"""
Test Layer 2: Feature Engineering — TBL, Fractional Diff, Feature Builder, FSA.
"""
import numpy as np
import pandas as pd
import pytest

from shared.features.triple_barrier import TripleBarrierLabeler
from shared.features.fractional_diff import FractionalDifferencer, frac_diff_ffd, get_weights_ffd
from shared.features.feature_builder import FeatureBuilder
from shared.features.feature_selection import FeatureSelectionAnnealing, LassoFeatureSelector


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def sample_ohlc():
    """Generate sample OHLC data for testing."""
    np.random.seed(42)
    n = 200
    base_price = 5000
    returns = np.random.normal(0.0005, 0.02, n)
    prices = base_price * np.cumprod(1 + returns)

    # Generate OHLC from close prices
    close = prices
    high = close * (1 + np.abs(np.random.normal(0, 0.01, n)))
    low = close * (1 - np.abs(np.random.normal(0, 0.01, n)))
    open_price = np.roll(close, 1)
    open_price[0] = close[0]
    volume = np.random.randint(1_000_000, 100_000_000, n)

    return pd.DataFrame({
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


# ===========================================================================
# Triple Barrier Labeling Tests
# ===========================================================================

class TestTripleBarrierLabeler:
    def test_label_profit(self, sample_ohlc):
        """Entry dengan close naik > barrier → PROFIT."""
        lbl = TripleBarrierLabeler(barrier_pct=0.03, horizon=5, use_high_low=True)

        # Create artificial scenario: price goes up 5% on day 1
        ohlc = sample_ohlc.copy()
        ohlc.iloc[0, ohlc.columns.get_loc("close")] = 5000
        ohlc.iloc[1, ohlc.columns.get_loc("high")] = 5000 * 1.05  # 5% up
        ohlc.iloc[1, ohlc.columns.get_loc("low")] = 5000 * 0.98

        result = lbl.label(ohlc, 0)
        assert result == 2, "Should be PROFIT when high hits upper barrier"

    def test_label_loss(self, sample_ohlc):
        """Entry dengan close turun > barrier → LOSS."""
        lbl = TripleBarrierLabeler(barrier_pct=0.03, horizon=5, use_high_low=True)

        ohlc = sample_ohlc.copy()
        ohlc.iloc[0, ohlc.columns.get_loc("close")] = 5000
        ohlc.iloc[1, ohlc.columns.get_loc("high")] = 5000 * 1.02
        ohlc.iloc[1, ohlc.columns.get_loc("low")] = 5000 * 0.95  # 5% down

        result = lbl.label(ohlc, 0)
        assert result == 0, "Should be LOSS when low hits lower barrier"

    def test_label_neutral_both_hit(self, sample_ohlc):
        """Jika HIGH dan LOW keduanya hit barrier → NEUTRAL (Kang & Kim rule)."""
        lbl = TripleBarrierLabeler(barrier_pct=0.03, horizon=5, use_high_low=True)

        ohlc = sample_ohlc.copy()
        ohlc.iloc[0, ohlc.columns.get_loc("close")] = 5000
        ohlc.iloc[1, ohlc.columns.get_loc("high")] = 5000 * 1.05  # Above upper
        ohlc.iloc[1, ohlc.columns.get_loc("low")] = 5000 * 0.95   # Below lower

        result = lbl.label(ohlc, 0)
        assert result == 1, "Should be NEUTRAL when both barriers hit on same day"

    def test_label_neutral_horizon(self, sample_ohlc):
        """Jika tidak ada barrier yang tersentuh → NEUTRAL."""
        lbl = TripleBarrierLabeler(barrier_pct=0.03, horizon=2, use_high_low=True)

        ohlc = sample_ohlc.copy()
        ohlc.iloc[0, ohlc.columns.get_loc("close")] = 5000
        # Price stays within barrier
        ohlc.iloc[1, ohlc.columns.get_loc("high")] = 5000 * 1.01
        ohlc.iloc[1, ohlc.columns.get_loc("low")] = 5000 * 0.99

        result = lbl.label(ohlc, 0)
        assert result == 1, "Should be NEUTRAL when no barrier hit within horizon"

    def test_label_all_returns_array(self, sample_ohlc):
        """label_all harus return array dengan panjang sama dengan data."""
        lbl = TripleBarrierLabeler(barrier_pct=0.03, horizon=5)
        labels = lbl.label_all(sample_ohlc)
        assert len(labels) == len(sample_ohlc)
        assert not np.all(np.isnan(labels))

    def test_repr(self):
        """Repr harus informatif."""
        lbl = TripleBarrierLabeler(barrier_pct=0.03, horizon=5)
        repr_str = repr(lbl)
        assert "barrier" in repr_str
        assert "horizon" in repr_str


# ===========================================================================
# Fractional Differentiation Tests
# ===========================================================================

class TestFractionalDiff:
    def test_weights_positive_first(self):
        """Bobot pertama harus 1.0."""
        weights = get_weights_ffd(0.5)
        assert weights[0] == 1.0

    def test_weights_decay(self):
        """Bobot harus menurun."""
        weights = get_weights_ffd(0.5)
        assert np.abs(weights[-1]) < np.abs(weights[0])

    def test_frac_diff_output_length(self, sample_ohlc):
        """Output harus sama panjang dengan input."""
        result = frac_diff_ffd(sample_ohlc["close"], d=0.5)
        assert len(result) == len(sample_ohlc["close"])

    def test_frac_diff_valid_output(self, sample_ohlc):
        """Fractional diff harus menghasilkan output valid."""
        log_prices = np.log(sample_ohlc["close"])
        result = frac_diff_ffd(log_prices, d=0.5)
        # Should have some non-NaN values
        assert result.dropna().shape[0] > 0
        # Should have fewer valid values than original (due to width truncation)
        assert result.dropna().shape[0] < len(log_prices)

    def test_differencer_class(self, sample_ohlc):
        """FractionalDifferencer class harus bisa transform."""
        fd = FractionalDifferencer(method="ffd", d=0.5)
        result = fd.transform(sample_ohlc["close"])
        assert len(result) == len(sample_ohlc["close"])
        assert not result.dropna().empty


# ===========================================================================
# Feature Builder Tests
# ===========================================================================

class TestFeatureBuilder:
    def test_calculate_return(self, sample_ohlc):
        """Log return harus benar."""
        fb = FeatureBuilder()
        returns = fb.calculate_return(sample_ohlc["close"])
        # First value should be NaN
        assert np.isnan(returns.iloc[0])
        # Second value should be ln(close_1 / close_0)
        expected = np.log(sample_ohlc["close"].iloc[1] / sample_ohlc["close"].iloc[0])
        assert abs(returns.iloc[1] - expected) < 1e-10

    def test_calculate_momentum(self, sample_ohlc):
        """Momentum harus benar."""
        fb = FeatureBuilder(momentum_window=5)
        mom = fb.calculate_momentum(sample_ohlc["close"])
        assert mom.iloc[5] == (sample_ohlc["close"].iloc[5] / sample_ohlc["close"].iloc[0]) - 1

    def test_build_features_dict(self, sample_ohlc):
        """build_features harus return dict dengan 3 keys."""
        fb = FeatureBuilder()
        features = fb.build_features(sample_ohlc["close"])
        assert "return_1d" in features
        assert "momentum" in features
        assert "volatility" in features

    def test_build_technical_features(self, sample_ohlc):
        """Technical features harus ada semua."""
        fb = FeatureBuilder(n_lags=20)
        tech = fb.build_technical_features(sample_ohlc)

        # Should have lag_1..lag_20 + 6 technical indicators
        assert "lag_1" in tech.columns
        assert "lag_20" in tech.columns
        assert "vol_5" in tech.columns
        assert "vol_20" in tech.columns
        assert "rsi_14" in tech.columns
        assert "mean_10" in tech.columns
        assert "atr_ratio" in tech.columns
        assert "bb_pos" in tech.columns

    def test_normalize_ohlcv_sequence(self, sample_ohlc):
        """Normalisasi harus relatif terhadap close hari ke-0."""
        fb = FeatureBuilder()
        chunk = sample_ohlc.iloc[:100]
        normalized = fb.normalize_ohlcv_sequence(chunk)

        assert normalized.shape == (100, 5)
        # Close pada hari ke-0 harus = 1.0
        assert abs(normalized[0, 3] - 1.0) < 1e-10

    def test_create_sequences(self, sample_ohlc):
        """Create sequences harus return array 3D."""
        fb = FeatureBuilder()
        sequences, indices = fb.create_sequences(sample_ohlc, window_size=100)
        assert sequences.ndim == 3
        assert sequences.shape[1] == 100
        assert sequences.shape[2] == 5
        assert len(indices) == len(sequences)

    def test_apply_triple_barrier(self, sample_ohlc):
        """TBL harus return label 0, 1, atau 2."""
        fb = FeatureBuilder(tbl_barrier_pct=0.05, tbl_horizon=5)
        label = fb.apply_triple_barrier(sample_ohlc, 0)
        assert label in [0, 1, 2]

    def test_repr(self):
        """Repr harus informatif."""
        fb = FeatureBuilder(tbl_barrier_pct=0.03, tbl_horizon=5)
        repr_str = repr(fb)
        assert "tbl_barrier" in repr_str
        assert "tbl_horizon" in repr_str


# ===========================================================================
# Feature Selection Tests
# ===========================================================================

class TestFeatureSelectionAnnealing:
    def test_fit_selects_features(self):
        """FSA harus bisa fit dan select features."""
        np.random.seed(42)
        X = np.random.randn(200, 50)
        # Make features 0 and 1 truly predictive
        y = X[:, 0] * 2 + X[:, 1] * 3 + np.random.randn(200) * 0.1

        fsa = FeatureSelectionAnnealing(n_features=5, epochs=100)
        fsa.fit(X, y)

        selected = fsa.get_selected_features()
        assert len(selected) == 5

    def test_transform_reduces_dimensions(self):
        """Transform harus reduce ke n_features."""
        np.random.seed(42)
        X = np.random.randn(200, 30)
        y = np.random.randn(200)

        fsa = FeatureSelectionAnnealing(n_features=10, epochs=50)
        X_reduced = fsa.fit_transform(X, y)
        assert X_reduced.shape[1] == 10


class TestLassoFeatureSelector:
    def test_lasso_selects_features(self):
        """Lasso harus bisa select features."""
        np.random.seed(42)
        X = np.random.randn(200, 20)
        y = X[:, 0] * 5 + np.random.randn(200) * 0.1

        lfs = LassoFeatureSelector(alpha=0.1, n_features=5)
        lfs.fit(X, y)

        selected = lfs.get_selected_features()
        assert len(selected) == 5
