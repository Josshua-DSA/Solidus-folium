"""
Blacklist Filter — Menyaring emiten tidak likuid / saham gocap.
"""
import pandas as pd
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Konstanta: Daftar saham yang di-blacklist (delisted, gocap, tidak likuid)
# ---------------------------------------------------------------------------

BLACKLIST_UNIVERSE = [
    "ALMI.JK",
    "ARMY.JK",
    "ARTI.JK",
    "BEBS.JK",
    "BIKA.JK",
    "BOSS.JK",
    "BTEL.JK",
    "CBMF.JK",
    "COWL.JK",
    "CPRI.JK",
    "DEAL.JK",
    "DUCK.JK",
    "ENVY.JK",
    "ETWA.JK",
    "FASW.JK",
    "GAMA.JK",
    "GOLL.JK",
    "HKMU.JK",
    "HOME.JK",
    "HOTL.JK",
    "IIKP.JK",
    "INAF.JK",
    "IPPE.JK",
    "JSKY.JK",
    "KAYU.JK",
    "KBRI.JK",
    "LCGP.JK",
    "LMAS.JK",
    "LMSH.JK",
    "MABA.JK",
    "MAGP.JK",
    "MFMI.JK",
    "MKNT.JK",
    "MTRA.JK",
    "MTSM.JK",
    "MYTX.JK",
    "NUSA.JK",
    "PLAS.JK",
    "PLIN.JK",
    "POLL.JK",
    "POOL.JK",
    "POSA.JK",
    "PPRO.JK",
    "PTMR.JK",
    "PURE.JK",
    "RIMO.JK",
    "RSGK.JK",
    "SBAT.JK",
    "SIMA.JK",
    "SKYB.JK",
    "SMCB.JK",
    "SMRU.JK",
    "SRIL.JK",
    "SUGI.JK",
    "SUPR.JK",
    "TDPM.JK",
    "TECH.JK",
    "TELE.JK",
    "TGRA.JK",
    "TGUK.JK",
    "TOPS.JK",
    "TOYS.JK",
    "TRAM.JK",
    "TRIL.JK",
    "TRIO.JK",
    "UNIT.JK",
    "WICO.JK",
    "WIKA.JK",
    "WMPP.JK",
    "WSKT.JK"
]


class BlacklistFilter:
    """
    Menyaring saham yang tidak memenuhi kriteria likuiditas dan harga minimum.

    Args:
        min_price: Harga minimum (default Rp200 — filter saham gocap IDX)
        min_avg_volume: Rata-rata volume harian minimum
        manual_blacklist: List ticker tambahan yang di-blacklist manual
    """

    def __init__(
        self,
        min_price: float = 200.0,
        min_avg_volume: float = 1_000_000,
        manual_blacklist: Optional[List[str]] = None,
    ):
        self.min_price = min_price
        self.min_avg_volume = min_avg_volume
        self.manual_blacklist: set = set(manual_blacklist or [])
        self.static_blacklist: set = set(BLACKLIST_UNIVERSE)

    def filter(
        self,
        close_prices: pd.DataFrame,
        volume: Optional[pd.DataFrame] = None,
    ) -> List[str]:
        """
        Return list ticker yang LOLOS semua filter.

        Args:
            close_prices: DataFrame wide (index=date, columns=ticker)
            volume: DataFrame wide (index=date, columns=ticker), optional

        Returns:
            List ticker yang lolos filter
        """
        all_tickers = set(close_prices.columns)

        # 1. Filter harga minimum (rata-rata 20 hari terakhir)
        price_ok = set()
        for ticker in all_tickers:
            avg_price = close_prices[ticker].tail(20).mean()
            if pd.notna(avg_price) and avg_price >= self.min_price:
                price_ok.add(ticker)

        # 2. Filter volume minimum (rata-rata 20 hari terakhir)
        volume_ok = all_tickers
        if volume is not None:
            volume_ok = set()
            for ticker in all_tickers:
                if ticker in volume.columns:
                    avg_vol = volume[ticker].tail(20).mean()
                    if pd.notna(avg_vol) and avg_vol >= self.min_avg_volume:
                        volume_ok.add(ticker)

        # 3. Gabungkan semua filter
        blocked = self.static_blacklist | self.manual_blacklist
        passed = (price_ok & volume_ok) - blocked

        removed = all_tickers - passed
        if removed:
            logger.info("BlacklistFilter: %d ticker diblokir: %s", len(removed), sorted(removed))

        return sorted(passed)

    def __repr__(self) -> str:
        return (
            f"BlacklistFilter(min_price={self.min_price}, "
            f"min_avg_volume={self.min_avg_volume}, "
            f"static_blocked={len(self.static_blacklist)})"
        )