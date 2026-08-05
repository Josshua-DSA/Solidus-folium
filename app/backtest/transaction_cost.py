"""
Transaction Cost Model — Simulasi biaya transaksi IDX.

Layer 6: app/backtest/ — Risk & Validation.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class TransactionCostModel:
    """
    Model biaya transaksi untuk pasar IDX.

    Biaya transaksi terdiri dari:
    - Komisi broker (buy & sell)
    - Pajak penjualan (PPh final 0.1%)
    - Slippage estimate
    - Levy BEI & KPEI

    Args:
        commission_buy_pct: Komisi beli (default 0.15%)
        commission_sell_pct: Komisi jual (default 0.15%)
        tax_sell_pct: Pajak jual / PPh final (default 0.10%)
        slippage_pct: Slippage estimate (default 0.05%)
        levy_pct: Levy BEI + KPEI (default 0.043%)
    """

    def __init__(
        self,
        commission_buy_pct: float = 0.0015,
        commission_sell_pct: float = 0.0015,
        tax_sell_pct: float = 0.001,
        slippage_pct: float = 0.0005,
        levy_pct: float = 0.00043,
    ):
        self.commission_buy_pct = Decimal(str(commission_buy_pct))
        self.commission_sell_pct = Decimal(str(commission_sell_pct))
        self.tax_sell_pct = Decimal(str(tax_sell_pct))
        self.slippage_pct = Decimal(str(slippage_pct))
        self.levy_pct = Decimal(str(levy_pct))

    def calculate_buy_cost(
        self,
        price: float,
        quantity_shares: int,
    ) -> Dict[str, Decimal]:
        """
        Hitung total biaya untuk transaksi beli.

        Args:
            price: Harga per lembar
            quantity_shares: Jumlah lembar

        Returns:
            Dict dengan breakdown biaya
        """
        notional = Decimal(str(price)) * Decimal(str(quantity_shares))
        commission = notional * self.commission_buy_pct
        levy = notional * self.levy_pct
        slippage = notional * self.slippage_pct
        total = commission + levy + slippage

        return {
            "notional": notional.quantize(Decimal("0.01"), ROUND_HALF_UP),
            "commission": commission.quantize(Decimal("0.01"), ROUND_HALF_UP),
            "levy": levy.quantize(Decimal("0.01"), ROUND_HALF_UP),
            "slippage": slippage.quantize(Decimal("0.01"), ROUND_HALF_UP),
            "tax": Decimal("0"),
            "total_cost": total.quantize(Decimal("0.01"), ROUND_HALF_UP),
            "effective_price": (notional + total).quantize(Decimal("0.01"), ROUND_HALF_UP),
        }

    def calculate_sell_cost(
        self,
        price: float,
        quantity_shares: int,
    ) -> Dict[str, Decimal]:
        """
        Hitung total biaya untuk transaksi jual.

        Args:
            price: Harga per lembar
            quantity_shares: Jumlah lembar

        Returns:
            Dict dengan breakdown biaya
        """
        notional = Decimal(str(price)) * Decimal(str(quantity_shares))
        commission = notional * self.commission_sell_pct
        tax = notional * self.tax_sell_pct
        levy = notional * self.levy_pct
        slippage = notional * self.slippage_pct
        total = commission + tax + levy + slippage

        return {
            "notional": notional.quantize(Decimal("0.01"), ROUND_HALF_UP),
            "commission": commission.quantize(Decimal("0.01"), ROUND_HALF_UP),
            "tax": tax.quantize(Decimal("0.01"), ROUND_HALF_UP),
            "levy": levy.quantize(Decimal("0.01"), ROUND_HALF_UP),
            "slippage": slippage.quantize(Decimal("0.01"), ROUND_HALF_UP),
            "total_cost": total.quantize(Decimal("0.01"), ROUND_HALF_UP),
            "effective_proceeds": (notional - total).quantize(Decimal("0.01"), ROUND_HALF_UP),
        }

    def round_trip_cost_pct(self) -> float:
        """Total cost percentage untuk round-trip (buy + sell)."""
        total = (
            self.commission_buy_pct
            + self.commission_sell_pct
            + self.tax_sell_pct
            + self.levy_pct * 2
            + self.slippage_pct * 2
        )
        return float(total)

    def __repr__(self) -> str:
        return (
            f"TransactionCostModel("
            f"buy={float(self.commission_buy_pct):.4f}, "
            f"sell={float(self.commission_sell_pct):.4f}, "
            f"tax={float(self.tax_sell_pct):.4f})"
        )
