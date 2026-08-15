"""
Polars Feature Engine — High-performance vectorized technical indicator computation.

Drop-in accelerator for FeatureBuilder.build_technical_features().
Uses Polars lazy evaluation and SIMD-vectorized operations for 10x-50x
speedup over pandas on large datasets.

Implements the same 29+ Malla et al. indicators as FeatureBuilder:
  - Lagged log-returns (1..n_lags)
  - Short-term volatility (5d), Medium-term volatility (20d)
  - RSI (14), Rolling mean log-return (10d)
  - ATR ratio, Bollinger Band position, VWAP deviation
  - OBV slope, MACD histogram
"""
import polars as pl
import numpy as np
import pandas as pd
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class PolarsFeatureEngine:
    """
    High-performance feature engine using Polars lazy evaluation.

    Produces identical output to FeatureBuilder.build_technical_features()
    but leverages Polars' columnar engine for significantly faster computation.

    Args:
        n_lags: Number of lagged returns (default 20, per Malla et al.)
    """

    def __init__(self, n_lags: int = 20):
        self.n_lags = n_lags

    def build_technical_features(
        self,
        ohlc: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Build all Malla et al. technical features using Polars engine.

        Args:
            ohlc: pandas DataFrame with columns: open, high, low, close, volume

        Returns:
            pandas DataFrame with all technical features (same schema as FeatureBuilder)
        """
        # Convert pandas → Polars LazyFrame
        lf = pl.LazyFrame(ohlc.reset_index(drop=True))

        close_col = pl.col("close")
        high_col = pl.col("high")
        low_col = pl.col("low")
        volume_col = pl.col("volume")

        # 1. Log returns
        log_ret = (close_col / close_col.shift(1)).log().alias("_log_ret")
        lf = lf.with_columns(log_ret)

        # 2. Lagged log-returns (1..n_lags)
        lag_exprs = [
            pl.col("_log_ret").shift(lag).alias(f"lag_{lag}")
            for lag in range(1, self.n_lags + 1)
        ]
        lf = lf.with_columns(lag_exprs)

        # 3. Short-term volatility (5d)
        lf = lf.with_columns(
            pl.col("_log_ret").rolling_std(window_size=5).alias("vol_5")
        )

        # 4. Medium-term volatility (20d)
        lf = lf.with_columns(
            pl.col("_log_ret").rolling_std(window_size=20).alias("vol_20")
        )

        # 5. RSI (14 periods)
        delta = close_col - close_col.shift(1)
        gain = pl.when(delta > 0).then(delta).otherwise(0.0).alias("_gain")
        loss = pl.when(delta < 0).then(-delta).otherwise(0.0).alias("_loss")
        lf = lf.with_columns([gain, loss])
        lf = lf.with_columns([
            pl.col("_gain").rolling_mean(window_size=14).alias("_avg_gain"),
            pl.col("_loss").rolling_mean(window_size=14).alias("_avg_loss"),
        ])
        rsi = (
            100.0 - (100.0 / (1.0 + pl.col("_avg_gain") / (pl.col("_avg_loss") + 1e-10)))
        ).alias("rsi_14")
        lf = lf.with_columns(rsi)

        # 6. Rolling mean log-return (10d)
        lf = lf.with_columns(
            pl.col("_log_ret").rolling_mean(window_size=10).alias("mean_10")
        )

        # 7. ATR ratio (14 periods)
        tr1 = (high_col - low_col).alias("_tr1")
        tr2 = (high_col - close_col.shift(1)).abs().alias("_tr2")
        tr3 = (low_col - close_col.shift(1)).abs().alias("_tr3")
        lf = lf.with_columns([tr1, tr2, tr3])
        lf = lf.with_columns(
            pl.max_horizontal("_tr1", "_tr2", "_tr3").alias("_tr")
        )
        lf = lf.with_columns(
            (pl.col("_tr").rolling_mean(window_size=14) / (close_col + 1e-10))
            .alias("atr_ratio")
        )

        # 8. Bollinger Band position
        sma_20 = close_col.rolling_mean(window_size=20).alias("_sma_20")
        std_20 = close_col.rolling_std(window_size=20).alias("_std_20")
        lf = lf.with_columns([sma_20, std_20])
        upper_bb = (pl.col("_sma_20") + 2.0 * pl.col("_std_20")).alias("_upper_bb")
        lower_bb = (pl.col("_sma_20") - 2.0 * pl.col("_std_20")).alias("_lower_bb")
        lf = lf.with_columns([upper_bb, lower_bb])
        lf = lf.with_columns(
            ((close_col - pl.col("_lower_bb")) /
             (pl.col("_upper_bb") - pl.col("_lower_bb") + 1e-10))
            .alias("bb_pos")
        )

        # 9. VWAP deviation
        typical = ((close_col + close_col.shift(1) + close_col.shift(2)) / 3.0).alias("_typical")
        lf = lf.with_columns(typical)
        lf = lf.with_columns([
            (pl.col("_typical") * volume_col).rolling_sum(window_size=20).alias("_tp_vol"),
            volume_col.rolling_sum(window_size=20).alias("_vol_sum"),
        ])
        lf = lf.with_columns(
            (pl.col("_tp_vol") / (pl.col("_vol_sum") + 1e-10)).alias("_vwap")
        )
        lf = lf.with_columns(
            ((close_col - pl.col("_vwap")) / (pl.col("_vwap") + 1e-10))
            .alias("vwap_dev")
        )

        # 10. OBV slope (20d)
        direction = (close_col - close_col.shift(1)).sign().alias("_direction")
        lf = lf.with_columns(direction)
        lf = lf.with_columns(
            (pl.col("_direction") * volume_col).cum_sum().alias("_obv")
        )
        lf = lf.with_columns(
            (pl.col("_obv") - pl.col("_obv").shift(20)).alias("obv_slope")
        )

        # 11. MACD histogram
        ema_fast = close_col.ewm_mean(span=12, adjust=False).alias("_ema_12")
        ema_slow = close_col.ewm_mean(span=26, adjust=False).alias("_ema_26")
        lf = lf.with_columns([ema_fast, ema_slow])
        lf = lf.with_columns(
            (pl.col("_ema_12") - pl.col("_ema_26")).alias("_macd_line")
        )
        lf = lf.with_columns(
            pl.col("_macd_line").ewm_mean(span=9, adjust=False).alias("_signal_line")
        )
        lf = lf.with_columns(
            (pl.col("_macd_line") - pl.col("_signal_line")).alias("macd")
        )

        # Collect and select only feature columns
        feature_cols = (
            [f"lag_{i}" for i in range(1, self.n_lags + 1)]
            + ["vol_5", "vol_20", "rsi_14", "mean_10", "atr_ratio",
               "bb_pos", "vwap_dev", "obv_slope", "macd"]
        )

        result_df = lf.select(feature_cols).collect()

        # Convert back to pandas with original index
        pdf = result_df.to_pandas()
        pdf.index = ohlc.index

        logger.info(
            "Polars features built: %d features, %d rows",
            len(feature_cols), len(pdf),
        )

        return pdf

    def __repr__(self) -> str:
        return f"PolarsFeatureEngine(n_lags={self.n_lags})"
