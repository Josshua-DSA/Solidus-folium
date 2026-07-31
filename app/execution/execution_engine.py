"""
Execution Engine — Eksekusi order dengan VWAP simulation.

Constraint IDX:
  - Kelipatan 100 lembar (1 lot)
  - Jam bursa: 09:00-12:00 & 13:30-16:00 WIB
  - T+2 settlement
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """Representasi order trading."""
    ticker: str
    side: str  # "BUY" atau "SELL"
    quantity_shares: int  # Jumlah lembar (harus kelipatan 100)
    price: float
    order_type: str = "MARKET"  # MARKET atau LIMIT
    timestamp: Optional[pd.Timestamp] = None

    def __post_init__(self):
        """Validasi constraint IDX."""
        if self.quantity_shares % 100 != 0:
            raise ValueError(
                f"Quantity harus kelipatan 100 lembar (IDX lot). "
                f"Got: {self.quantity_shares}"
            )
        if self.side not in ("BUY", "SELL"):
            raise ValueError(f"Side harus 'BUY' atau 'SELL'. Got: {self.side}")

    @property
    def lots(self) -> int:
        """Jumlah lot."""
        return self.quantity_shares // 100

    @property
    def notional_value(self) -> float:
        """Nilai nominal order."""
        return self.quantity_shares * self.price


@dataclass
class Trade:
    """Representasi trade yang sudah tereksekusi."""
    order: Order
    execution_price: float
    commission: float
    slippage_cost: float
    timestamp: pd.Timestamp


class ExecutionEngine:
    """
    Engine eksekusi order dengan simulasi VWAP.

    Args:
        commission_pct: Komisi broker (default 0.15%)
        slippage_pct: Slippage estimate (default 0.05%)
        vbp_simulation: Gunakan Volume-Weighted Bid-Ask Price simulation
    """

    def __init__(
        self,
        commission_pct: float = 0.0015,
        slippage_pct: float = 0.0005,
        vwap_simulation: bool = True,
    ):
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct
        self.vwap_simulation = vwap_simulation
        self.trades: List[Trade] = []

    def simulate_vwap(
        self,
        order: Order,
        intraday_data: Optional[pd.DataFrame] = None,
    ) -> float:
        """
        Simulasi harga eksekusi VWAP.

        Jika intraday_data tersedia, hitung VWAP dari volume profile.
        Jika tidak, gunakan close price + slippage estimate.

        Args:
            order: Order yang akan dieksekusi
            intraday_data: DataFrame intraday (optional, Fase 6)

        Returns:
            Harga eksekusi simulasi
        """
        if intraday_data is not None and "vwap" in intraday_data.columns:
            vwap_price = intraday_data["vwap"].mean()
        else:
            # Fallback: close price + slippage
            if order.side == "BUY":
                vwap_price = order.price * (1 + self.slippage_pct)
            else:
                vwap_price = order.price * (1 - self.slippage_pct)

        return vwap_price

    def execute(self, order: Order) -> Trade:
        """
        Eksekusi satu order.

        Args:
            order: Order yang akan dieksekusi

        Returns:
            Trade object
        """
        exec_price = self.simulate_vwap(order)
        commission = order.notional_value * self.commission_pct
        slippage_cost = abs(exec_price - order.price) * order.quantity_shares

        trade = Trade(
            order=order,
            execution_price=exec_price,
            commission=commission,
            slippage_cost=slippage_cost,
            timestamp=order.timestamp or pd.Timestamp.now(),
        )

        self.trades.append(trade)
        logger.info(
            "Executed %s %s: %d lots @ %.0f (commission=%.0f, slippage=%.0f)",
            order.side, order.ticker, order.lots, exec_price,
            commission, slippage_cost,
        )

        return trade

    def execute_batch(self, orders: List[Order]) -> List[Trade]:
        """
        Eksekusi batch orders.

        Args:
            orders: List of orders

        Returns:
            List of trades
        """
        return [self.execute(order) for order in orders]

    def get_total_costs(self) -> Dict[str, float]:
        """Return total biaya transaksi."""
        total_commission = sum(t.commission for t in self.trades)
        total_slippage = sum(t.slippage_cost for t in self.trades)
        return {
            "total_commission": total_commission,
            "total_slippage": total_slippage,
            "total_cost": total_commission + total_slippage,
            "n_trades": len(self.trades),
        }

    def __repr__(self) -> str:
        return (
            f"ExecutionEngine(commission={self.commission_pct:.4f}, "
            f"slippage={self.slippage_pct:.4f}, "
            f"n_trades={len(self.trades)})"
        )
