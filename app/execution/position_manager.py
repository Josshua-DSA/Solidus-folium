"""
Position Manager — Tracking posisi portofolio dan P/L.

Layer 5: app/execution/ — Execution Engine.
"""
import pandas as pd
import numpy as np
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Representasi satu posisi terbuka."""
    ticker: str
    quantity_shares: int  # Kelipatan 100 (IDX lot)
    avg_price: float
    side: str = "LONG"
    entry_date: Optional[pd.Timestamp] = None

    @property
    def lots(self) -> int:
        return self.quantity_shares // 100

    @property
    def notional(self) -> Decimal:
        return Decimal(str(self.avg_price)) * Decimal(str(self.quantity_shares))

    def unrealized_pnl(self, current_price: float) -> Decimal:
        """Hitung unrealized P/L."""
        current_value = Decimal(str(current_price)) * Decimal(str(self.quantity_shares))
        cost_basis = self.notional
        return current_value - cost_basis

    def unrealized_pnl_pct(self, current_price: float) -> float:
        """Unrealized P/L dalam persentase."""
        if self.avg_price <= 0:
            return 0.0
        return (current_price - self.avg_price) / self.avg_price


class PositionManager:
    """
    Mengelola posisi portofolio paper trading.

    Constraint IDX:
    - Lot minimum: 100 lembar
    - Long-only (no short selling)

    Args:
        initial_capital: Modal awal (Rp)
    """

    def __init__(self, initial_capital: float = 100_000_000):
        self.initial_capital = Decimal(str(initial_capital))
        self.cash = Decimal(str(initial_capital))
        self.positions: Dict[str, Position] = {}
        self.closed_trades: List[Dict] = []

    def open_position(
        self,
        ticker: str,
        quantity_shares: int,
        price: float,
        cost: float = 0.0,
        timestamp: Optional[pd.Timestamp] = None,
    ) -> bool:
        """
        Buka posisi baru atau tambah posisi existing.

        Args:
            ticker: Ticker saham
            quantity_shares: Jumlah lembar (harus kelipatan 100)
            price: Harga per lembar
            cost: Total transaction cost
            timestamp: Waktu transaksi

        Returns:
            True jika berhasil, False jika gagal (modal tidak cukup)
        """
        if quantity_shares % 100 != 0:
            logger.error("Quantity harus kelipatan 100 (IDX lot). Got: %d", quantity_shares)
            return False

        total_cost = Decimal(str(price)) * Decimal(str(quantity_shares)) + Decimal(str(cost))

        if total_cost > self.cash:
            logger.warning("Insufficient cash: need %s, have %s", total_cost, self.cash)
            return False

        self.cash -= total_cost

        if ticker in self.positions:
            # Average up/down
            pos = self.positions[ticker]
            old_value = Decimal(str(pos.avg_price)) * Decimal(str(pos.quantity_shares))
            new_value = Decimal(str(price)) * Decimal(str(quantity_shares))
            total_shares = pos.quantity_shares + quantity_shares
            new_avg = float((old_value + new_value) / Decimal(str(total_shares)))
            pos.quantity_shares = total_shares
            pos.avg_price = new_avg
        else:
            self.positions[ticker] = Position(
                ticker=ticker,
                quantity_shares=quantity_shares,
                avg_price=price,
                entry_date=timestamp,
            )

        logger.info(
            "OPEN %s: %d shares @ %.0f (cost=%.0f, cash=%.0f)",
            ticker, quantity_shares, price, float(cost), float(self.cash),
        )
        return True

    def close_position(
        self,
        ticker: str,
        quantity_shares: Optional[int] = None,
        price: float = 0.0,
        cost: float = 0.0,
        timestamp: Optional[pd.Timestamp] = None,
    ) -> bool:
        """
        Tutup posisi (sebagian atau seluruhnya).

        Args:
            ticker: Ticker saham
            quantity_shares: Jumlah lembar ditutup (None = seluruhnya)
            price: Harga jual
            cost: Transaction cost
            timestamp: Waktu transaksi

        Returns:
            True jika berhasil
        """
        if ticker not in self.positions:
            logger.warning("No position for %s", ticker)
            return False

        pos = self.positions[ticker]
        close_qty = quantity_shares or pos.quantity_shares

        if close_qty > pos.quantity_shares:
            logger.error("Cannot close %d shares, only have %d", close_qty, pos.quantity_shares)
            return False

        proceeds = Decimal(str(price)) * Decimal(str(close_qty)) - Decimal(str(cost))
        self.cash += proceeds

        # Record closed trade
        pnl = float(proceeds - Decimal(str(pos.avg_price)) * Decimal(str(close_qty)))
        self.closed_trades.append({
            "ticker": ticker,
            "quantity": close_qty,
            "entry_price": pos.avg_price,
            "exit_price": price,
            "pnl": pnl,
            "cost": cost,
            "entry_date": pos.entry_date,
            "exit_date": timestamp,
        })

        # Update or remove position
        if close_qty >= pos.quantity_shares:
            del self.positions[ticker]
        else:
            pos.quantity_shares -= close_qty

        logger.info(
            "CLOSE %s: %d shares @ %.0f (P/L=%.0f, cash=%.0f)",
            ticker, close_qty, price, pnl, float(self.cash),
        )
        return True

    def get_portfolio_value(self, current_prices: Dict[str, float]) -> Decimal:
        """Hitung total portfolio value (cash + positions)."""
        positions_value = Decimal("0")
        for ticker, pos in self.positions.items():
            price = current_prices.get(ticker, pos.avg_price)
            positions_value += Decimal(str(price)) * Decimal(str(pos.quantity_shares))
        return self.cash + positions_value

    def get_portfolio_summary(self, current_prices: Dict[str, float]) -> Dict:
        """Return summary portofolio."""
        total_value = self.get_portfolio_value(current_prices)
        total_return = float((total_value - self.initial_capital) / self.initial_capital)
        return {
            "cash": float(self.cash),
            "positions_count": len(self.positions),
            "total_value": float(total_value),
            "total_return_pct": total_return * 100,
            "closed_trades": len(self.closed_trades),
        }

    def __repr__(self) -> str:
        return (
            f"PositionManager(cash={float(self.cash):,.0f}, "
            f"positions={len(self.positions)})"
        )
