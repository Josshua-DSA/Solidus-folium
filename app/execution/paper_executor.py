"""
Paper Executor — Paper trading execution engine.
Wraps ExecutionEngine + PositionManager untuk simulasi trading.

Layer 5: app/execution/ — Execution Engine.
"""
import pandas as pd
from typing import Dict, List, Optional
from app.execution.execution_engine import ExecutionEngine, Order, Trade
from app.execution.position_manager import PositionManager
import logging

logger = logging.getLogger(__name__)


class PaperExecutor:
    """
    Paper trading executor — menggabungkan ExecutionEngine dan PositionManager.

    Mensimulasikan eksekusi order tanpa koneksi ke broker nyata.
    Semua transaksi di-log dan dilacak via PositionManager.

    Args:
        initial_capital: Modal awal (Rp)
        commission_pct: Komisi broker (default 0.15%)
        slippage_pct: Slippage estimate (default 0.05%)
    """

    def __init__(
        self,
        initial_capital: float = 100_000_000,
        commission_pct: float = 0.0015,
        slippage_pct: float = 0.0005,
    ):
        self.engine = ExecutionEngine(
            commission_pct=commission_pct,
            slippage_pct=slippage_pct,
        )
        self.position_manager = PositionManager(initial_capital=initial_capital)
        self.execution_log: List[Dict] = []

    def execute_signal(
        self,
        ticker: str,
        signal: str,
        price: float,
        quantity_shares: int = 100,
        timestamp: Optional[pd.Timestamp] = None,
    ) -> Optional[Trade]:
        """
        Eksekusi sinyal trading.

        Args:
            ticker: Ticker saham
            signal: 'BUY' atau 'SELL'
            price: Harga saat ini
            quantity_shares: Jumlah lembar (kelipatan 100)
            timestamp: Waktu eksekusi

        Returns:
            Trade object atau None jika gagal
        """
        if signal not in ("BUY", "SELL"):
            logger.warning("Unknown signal: %s", signal)
            return None

        try:
            order = Order(
                ticker=ticker,
                side=signal,
                quantity_shares=quantity_shares,
                price=price,
                timestamp=timestamp,
            )
        except ValueError as e:
            logger.error("Invalid order: %s", e)
            return None

        # Execute via engine
        trade = self.engine.execute(order)

        # Update position manager
        cost = trade.commission + trade.slippage_cost
        if signal == "BUY":
            success = self.position_manager.open_position(
                ticker=ticker,
                quantity_shares=quantity_shares,
                price=trade.execution_price,
                cost=cost,
                timestamp=trade.timestamp,
            )
        else:  # SELL
            success = self.position_manager.close_position(
                ticker=ticker,
                quantity_shares=quantity_shares,
                price=trade.execution_price,
                cost=cost,
                timestamp=trade.timestamp,
            )

        if success:
            self.execution_log.append({
                "ticker": ticker,
                "signal": signal,
                "price": trade.execution_price,
                "quantity": quantity_shares,
                "cost": cost,
                "timestamp": trade.timestamp,
            })

        return trade if success else None

    def get_portfolio_status(self, current_prices: Dict[str, float]) -> Dict:
        """Return current portfolio status."""
        return self.position_manager.get_portfolio_summary(current_prices)

    def __repr__(self) -> str:
        return (
            f"PaperExecutor("
            f"positions={len(self.position_manager.positions)}, "
            f"trades={len(self.execution_log)})"
        )
