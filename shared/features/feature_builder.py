"""
Feature Builder — Ekstraksi fitur teknikal & Triple Barrier Labeling.

Berdasarkan research papers:
  - Kang & Kim (2025): Raw OHLCV normalization, window=100
  - Malla et al.: Lagged returns (20), vol_5, vol_20, RSI_14, mean_10
  - Pabuccu & Barbu: Feature Selection Annealing (FSA)
  - Stempień & Gajda: Fractional Differentiation (De Prado)

Mode dasar (baseline backtest):
  - calculate_return(), calculate_momentum(), calculate_volatility()

Mode ML (Fase 3):
  - build_technical_features() → 10 fitur teknikal + lags
  - normalize_ohlcv_sequence() → normalisasi rolling window 100 hari
  - apply_triple_barrier() → labeling TBL dengan high/low
  - build_ml_dataset() → dataset siap training
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class FeatureBuilder:
    """
    Feature engineering engine untuk data OHLCV.

    Args:
        momentum_window: Window untuk momentum (default 20 hari)
        volatility_window: Window untuk volatilitas (default 20 hari)
        tbl_barrier_pct: Barrier +/- persentase (default 0.03 = 3%)
        tbl_horizon: Holding period maks (default 5 hari bursa)
        n_lags: Jumlah lagged returns (default 20, per Malla)
        frac_d: Parameter fractional diff (None = auto-detect)
    """

    def __init__(
        self,
        momentum_window: int = 20,
        volatility_window: int = 20,
        tbl_barrier_pct: float = 0.03,
        tbl_horizon: int = 5,
        n_lags: int = 20,
        frac_d: Optional[float] = None,
    ):
        self.momentum_window = momentum_window
        self.volatility_window = volatility_window
        self.tbl_barrier_pct = tbl_barrier_pct
        self.tbl_horizon = tbl_horizon
        self.n_lags = n_lags
        self.frac_d = frac_d

    # =========================================================================
    # Baseline features (Fase 1)
    # =========================================================================

    def calculate_return(
        self, close_prices: pd.DataFrame, periods: int = 1
    ) -> pd.DataFrame:
        """Hitung log return: ln(close_t / close_{t-periods})."""
        return np.log(close_prices / close_prices.shift(periods))

    def calculate_momentum(
        self, close_prices: pd.DataFrame
    ) -> pd.DataFrame:
        """Hitung momentum: (close_t / close_{t-window}) - 1."""
        return (close_prices / close_prices.shift(self.momentum_window)) - 1

    def calculate_volatility(
        self, close_prices: pd.DataFrame
    ) -> pd.DataFrame:
        """Hitung rolling volatility dari log return."""
        log_ret = self.calculate_return(close_prices)
        return log_ret.rolling(window=self.volatility_window).std()

    def build_features(self, close_prices: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        Build semua fitur baseline.

        Returns:
            Dict: 'return_1d', 'momentum', 'volatility'
        """
        return {
            "return_1d": self.calculate_return(close_prices),
            "momentum": self.calculate_momentum(close_prices),
            "volatility": self.calculate_volatility(close_prices),
        }

    # =========================================================================
    # Technical Features (per Malla et al.)
    # =========================================================================

    def build_technical_features(
        self,
        ohlc: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Build fitur teknikal untuk ML model.

        Berdasarkan Malla et al. (XGBoost NEPSE forecasting):
          - Lagged log-returns (1..20)
          - Short-term volatility (5 days)
          - Medium-term volatility (20 days)
          - RSI (14 periods)
          - Rolling mean log-return (10 days)
          - ATR ratio, Bollinger Band position, VWAP deviation
          - OBV slope, MFI, MACD

        Args:
            ohlc: DataFrame dengan kolom open, high, low, close, volume

        Returns:
            DataFrame dengan semua fitur teknikal
        """
        close = ohlc["close"]
        high = ohlc["high"]
        low = ohlc["low"]
        volume = ohlc["volume"] if "volume" in ohlc.columns else pd.Series(0, index=close.index)

        features = pd.DataFrame(index=close.index)

        # 1. Log returns
        log_ret = np.log(close / close.shift(1))

        # 2. Lagged log-returns (1..n_lags)
        for lag in range(1, self.n_lags + 1):
            features[f"lag_{lag}"] = log_ret.shift(lag)

        # 3. Short-term volatility (5 days)
        features["vol_5"] = log_ret.rolling(window=5).std()

        # 4. Medium-term volatility (20 days)
        features["vol_20"] = log_ret.rolling(window=20).std()

        # 5. RSI (14 periods)
        features["rsi_14"] = self._compute_rsi(close, period=14)

        # 6. Rolling mean log-return (10 days)
        features["mean_10"] = log_ret.rolling(window=10).mean()

        # 7. ATR ratio
        features["atr_ratio"] = self._compute_atr(high, low, close) / close

        # 8. Bollinger Band position
        features["bb_pos"] = self._compute_bb_position(close, window=20)

        # 9. VWAP deviation
        features["vwap_dev"] = self._compute_vwap_deviation(close, volume)

        # 10. OBV slope
        features["obv_slope"] = self._compute_obv_slope(close, volume)

        # 11. MACD
        features["macd"] = self._compute_macd(close)

        logger.info(
            "Technical features built: %d features, %d rows",
            len(features.columns), len(features),
        )

        return features

    def _compute_rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index."""
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        return 100 - (100 / (1 + rs))

    def _compute_atr(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> pd.Series:
        """Average True Range."""
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    def _compute_bb_position(
        self, close: pd.Series, window: int = 20, num_std: float = 2.0
    ) -> pd.Series:
        """Bollinger Band position (0 = lower band, 1 = upper band)."""
        sma = close.rolling(window=window).mean()
        std = close.rolling(window=window).std()
        upper = sma + num_std * std
        lower = sma - num_std * std
        return (close - lower) / (upper - lower + 1e-10)

    def _compute_vwap_deviation(
        self, close: pd.Series, volume: pd.Series, window: int = 20
    ) -> pd.Series:
        """VWAP deviation."""
        typical = (close + close.shift(1) + close.shift(2)) / 3  # Approximation
        vol = volume.rolling(window=window).sum()
        vwap = (typical * volume).rolling(window=window).sum() / (vol + 1e-10)
        return (close - vwap) / (vwap + 1e-10)

    def _compute_obv_slope(
        self, close: pd.Series, volume: pd.Series, window: int = 20
    ) -> pd.Series:
        """On-Balance Volume slope."""
        direction = np.sign(close.diff())
        obv = (direction * volume).cumsum()
        return obv.diff(window)

    def _compute_macd(
        self, close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> pd.Series:
        """MACD (Moving Average Convergence Divergence)."""
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        return macd_line - signal_line  # MACD histogram

    # =========================================================================
    # Triple Barrier Labeling (per Kang & Kim)
    # =========================================================================

    def apply_triple_barrier(
        self,
        ohlc: pd.DataFrame,
        start_idx: int,
    ) -> int:
        """
        Triple Barrier Labeling untuk satu entry point.

        Menggunakan HIGH dan LOW (bukan hanya close) untuk mengurangi
        ketidakpastian intraday. Jika keduanya menyentuh barrier pada
        hari yang sama → label sebagai NEUTRAL (Class 1).

        Args:
            ohlc: DataFrame OHLC
            start_idx: Index baris entry

        Returns:
            0 = LOSS, 1 = NEUTRAL, 2 = PROFIT
        """
        from shared.features.triple_barrier import TripleBarrierLabeler

        lbl = TripleBarrierLabeler(
            barrier_pct=self.tbl_barrier_pct,
            horizon=self.tbl_horizon,
            use_high_low=True,
        )
        return lbl.label(ohlc, start_idx)

    def label_all(
        self,
        ohlc: pd.DataFrame,
        ticker: str = "",
    ) -> np.ndarray:
        """
        Label semua entry point.

        Args:
            ohlc: DataFrame OHLC
            ticker: Nama ticker

        Returns:
            np.ndarray labels (0, 1, 2)
        """
        from shared.features.triple_barrier import TripleBarrierLabeler

        lbl = TripleBarrierLabeler(
            barrier_pct=self.tbl_barrier_pct,
            horizon=self.tbl_horizon,
            use_high_low=True,
        )
        return lbl.label_all(ohlc, ticker)

    # =========================================================================
    # OHLCV Normalization (per Kang & Kim: window=100)
    # =========================================================================

    def normalize_ohlcv_sequence(
        self,
        ohlcv_chunk: pd.DataFrame,
    ) -> np.ndarray:
        """
        Normalisasi rolling window 100 hari (Kang & Kim).

        Harga relatif terhadap close hari ke-0, volume log1p.

        Args:
            ohlcv_chunk: DataFrame OHLCV (window_size baris)

        Returns:
            np.ndarray shape (window_size, 5) — [open, high, low, close, volume]
        """
        if len(ohlcv_chunk) == 0:
            raise ValueError("ohlcv_chunk kosong")

        base_price = ohlcv_chunk["close"].iloc[0]
        if base_price <= 0:
            base_price = 1.0

        normalized = np.zeros((len(ohlcv_chunk), 5))
        normalized[:, 0] = ohlcv_chunk["open"].values / base_price
        normalized[:, 1] = ohlcv_chunk["high"].values / base_price
        normalized[:, 2] = ohlcv_chunk["low"].values / base_price
        normalized[:, 3] = ohlcv_chunk["close"].values / base_price

        # Volume: log1p normalization relatif terhadap volume hari ke-0
        base_vol = ohlcv_chunk["volume"].iloc[0]
        if "volume" in ohlcv_chunk.columns and base_vol > 0:
            normalized[:, 4] = np.log1p(ohlcv_chunk["volume"].values) / np.log1p(base_vol)

        return normalized

    def create_sequences(
        self,
        ohlcv: pd.DataFrame,
        window_size: int = 100,
        step: int = 1,
    ) -> Tuple[np.ndarray, List[int]]:
        """
        Buat sequences dari OHLCV data untuk model sequence-based.

        Args:
            ohlcv: DataFrame OHLCV lengkap
            window_size: Ukuran window (default 100)
            step: Step size antar sequence

        Returns:
            (sequences, indices) — sequences shape (n_seq, window_size, 5)
        """
        sequences = []
        indices = []

        for i in range(0, len(ohlcv) - window_size + 1, step):
            chunk = ohlcv.iloc[i: i + window_size]
            seq = self.normalize_ohlcv_sequence(chunk)
            sequences.append(seq)
            indices.append(i + window_size - 1)  # Index target

        return np.array(sequences), indices

    # =========================================================================
    # Build ML Dataset (pipeline lengkap)
    # =========================================================================

    def build_ml_dataset(
        self,
        ohlcv: pd.DataFrame,
        ticker: str = "",
        window_size: int = 100,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Build dataset ML: setiap baris = satu window rolling + label TBL.

        Pipeline:
          1. Buat sequences OHLCV ternormalisasi (window_size=100)
          2. Label setiap sequence menggunakan TBL
          3. Return (X, y) untuk training

        Args:
            ohlcv: DataFrame OHLCV lengkap
            ticker: Nama ticker
            window_size: Ukuran window

        Returns:
            (X, y) di mana:
              X: np.ndarray shape (n_samples, window_size, 5)
              y: np.ndarray shape (n_samples,) — labels 0, 1, 2
        """
        sequences, indices = self.create_sequences(ohlcv, window_size)

        # Label setiap sequence
        labels = np.full(len(sequences), np.nan, dtype=float)
        for i, idx in enumerate(indices):
            # Label berdasarkan entry di akhir sequence
            entry_idx = idx - window_size + 1
            if entry_idx >= 0:
                labels[i] = self.apply_triple_barrier(ohlcv, entry_idx)

        # Hapus baris tanpa label
        valid_mask = ~np.isnan(labels)
        X = sequences[valid_mask]
        y = labels[valid_mask].astype(int)

        logger.info(
            "ML dataset built for %s: X=%s, y=%s, class dist=%s",
            ticker,
            X.shape,
            y.shape,
            pd.Series(y).value_counts().to_dict(),
        )

        return X, y

    # =========================================================================
    # Fractional Differentiation integration
    # =========================================================================

    def build_fracdiff_features(
        self,
        close_prices: pd.Series,
        d: Optional[float] = None,
    ) -> pd.Series:
        """
        Build fractional differentiated features.

        Args:
            close_prices: Series harga close
            d: Parameter differencing (None = auto-detect via ADF)

        Returns:
            Series terdifferensiasi secara fraksional
        """
        from shared.features.fractional_diff import FractionalDifferencer

        fd = FractionalDifferencer(method="ffd", d=d)
        return fd.transform(close_prices)

    def __repr__(self) -> str:
        return (
            f"FeatureBuilder(momentum={self.momentum_window}, "
            f"volatility={self.volatility_window}, "
            f"tbl_barrier={self.tbl_barrier_pct}, "
            f"tbl_horizon={self.tbl_horizon}, "
            f"n_lags={self.n_lags})"
        )
