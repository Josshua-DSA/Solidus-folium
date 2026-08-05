"""
Fundamental Features — Feature engineering dari data fundamental.
Refactored dari backend/fundamental_component/.

Stateless, zero external layer dependency.
Dipakai oleh model/ dan app/ untuk fitur fundamental ML.
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class FundamentalFeatureBuilder:
    """
    Membangun fitur fundamental dari data keuangan perusahaan.

    Output: DataFrame dengan kolom fitur fundamental per ticker per tanggal,
    siap digabungkan dengan fitur teknikal dari FeatureBuilder.
    """

    # Kolom fundamental standar
    FUNDAMENTAL_COLUMNS = [
        "pe_ratio",
        "pb_ratio",
        "peg_ratio",
        "roe",
        "der",
        "eps",
        "dividend_yield",
        "market_cap_log",
    ]

    def build_features(
        self,
        fundamentals: pd.DataFrame,
        prices: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Bangun fitur fundamental dari raw data.

        Args:
            fundamentals: DataFrame dengan kolom:
                ticker, pe, pb, dividend_yield, roe, der, eps, market_cap
            prices: Optional close prices (wide format) untuk dynamic P/E

        Returns:
            DataFrame dengan fitur fundamental yang sudah dinormalisasi
        """
        if fundamentals.empty:
            logger.warning("Empty fundamentals DataFrame")
            return pd.DataFrame(columns=["ticker"] + self.FUNDAMENTAL_COLUMNS)

        df = fundamentals.copy()

        # Rename untuk konsistensi
        rename_map = {
            "pe": "pe_ratio",
            "pb": "pb_ratio",
        }
        df = df.rename(columns=rename_map)

        # Hitung fitur turunan
        if "pe_ratio" in df.columns and "roe" in df.columns:
            # PEG proxy: P/E dibagi ROE (jika ROE > 0)
            df["peg_ratio"] = df.apply(
                lambda row: row["pe_ratio"] / (row["roe"] * 100)
                if pd.notna(row["roe"]) and row["roe"] > 0 and pd.notna(row["pe_ratio"])
                else None,
                axis=1,
            )

        # Log market cap (untuk normalisasi)
        if "market_cap" in df.columns:
            df["market_cap_log"] = df["market_cap"].apply(
                lambda x: np.log(x) if pd.notna(x) and x > 0 else None
            )

        # Select dan return
        available = [c for c in ["ticker"] + self.FUNDAMENTAL_COLUMNS if c in df.columns]
        return df[available]

    @staticmethod
    def compute_fundamental_score(row: Dict) -> float:
        """
        Hitung composite fundamental score (0-100) dari rasio keuangan.

        Scoring sederhana berbasis ranking relatif:
        - P/E rendah = bagus (growth stock exception)
        - ROE tinggi = bagus
        - DER rendah = bagus
        - Dividend yield tinggi = bagus (investment mode)

        Args:
            row: Dict dengan kunci fundamental

        Returns:
            Score 0-100
        """
        score = 50.0  # Baseline

        pe = row.get("pe_ratio")
        roe = row.get("roe")
        der = row.get("der")
        div_yield = row.get("dividend_yield")

        # P/E scoring (lower is better, cap at 0-50)
        if pe is not None and pe > 0:
            if pe < 10:
                score += 15
            elif pe < 20:
                score += 5
            elif pe > 40:
                score -= 10

        # ROE scoring (higher is better)
        if roe is not None:
            if roe > 0.20:
                score += 15
            elif roe > 0.10:
                score += 5
            elif roe < 0:
                score -= 15

        # DER scoring (lower is better)
        if der is not None:
            if der < 0.5:
                score += 10
            elif der > 2.0:
                score -= 10

        # Dividend yield scoring
        if div_yield is not None:
            if div_yield > 0.05:
                score += 10
            elif div_yield > 0.02:
                score += 5

        return max(0.0, min(100.0, score))

    def __repr__(self) -> str:
        return "FundamentalFeatureBuilder()"
