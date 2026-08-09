"""
Paper Executor — Paper trading execution engine.
Wraps ExecutionEngine + PositionManager untuk simulasi trading.
Includes DriftMonitor for real-time risk anomaly detection.

Layer 5: app/execution/ — Execution Engine.
"""
import pandas as pd
from typing import Dict, List, Optional
from app.execution.execution_engine import ExecutionEngine, Order, Trade
from app.execution.position_manager import PositionManager
from app.execution.drift_monitor import DriftMonitor, DriftEvent
import logging

logger = logging.getLogger(__name__)


class PaperExecutor:
    """
    Paper trading executor — menggabungkan ExecutionEngine dan PositionManager.

    Mensimulasikan eksekusi order tanpa koneksi ke broker nyata.
    Semua transaksi di-log dan dilacak via PositionManager.
    DriftMonitor memantau equity curve setelah setiap trade.

    Args:
        initial_capital: Modal awal (Rp)
        commission_pct: Komisi broker (default 0.15%)
        slippage_pct: Slippage estimate (default 0.05%)
        max_drawdown_stop: Batas drawdown untuk drift alert (default -15%)
        daily_loss_limit: Batas daily loss untuk drift alert (default -3%)
    """

    def __init__(
        self,
        initial_capital: float = 100_000_000,
        commission_pct: float = 0.0015,
        slippage_pct: float = 0.0005,
        max_drawdown_stop: float = -0.15,
        daily_loss_limit: float = -0.03,
    ):
        self.engine = ExecutionEngine(
            commission_pct=commission_pct,
            slippage_pct=slippage_pct,
        )
        self.position_manager = PositionManager(initial_capital=initial_capital)
        self.execution_log: List[Dict] = []

        # Drift monitor — tracks equity after every trade
        self.drift_monitor = DriftMonitor(
            max_drawdown_stop=max_drawdown_stop,
            daily_loss_limit=daily_loss_limit,
        )
        # Seed initial equity point
        self.drift_monitor.update(
            equity=initial_capital,
            timestamp=pd.Timestamp.now(),
        )

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

            # --- Post-trade drift monitoring ---
            # Hitung NAV terkini dan update drift monitor
            current_prices_snapshot = {
                t: p.avg_price for t, p in self.position_manager.positions.items()
            }
            # Override with actual execution price for this ticker
            current_prices_snapshot[ticker] = trade.execution_price
            nav = float(self.position_manager.get_portfolio_value(current_prices_snapshot))

            # Hitung position weights untuk concentration check
            weights: Dict[str, float] = {}
            if nav > 0:
                for t, pos in self.position_manager.positions.items():
                    pos_price = current_prices_snapshot.get(t, pos.avg_price)
                    pos_value = pos.quantity_shares * pos_price
                    weights[t] = pos_value / nav

            new_drift_events = self.drift_monitor.update(
                equity=nav,
                timestamp=trade.timestamp,
                positions_weights=weights,
            )

            # Log any new drift events
            for event in new_drift_events:
                logger.warning(
                    "DRIFT ALERT [%s] %s: %s",
                    event.severity, event.event_type, event.message,
                )

        return trade if success else None

    def get_portfolio_status(self, current_prices: Dict[str, float]) -> Dict:
        """Return current portfolio status with drift info."""
        summary = self.position_manager.get_portfolio_summary(current_prices)
        summary["drift_summary"] = self.drift_monitor.get_summary()
        return summary

    def get_drift_events(self, n: int = 10) -> List[DriftEvent]:
        """Return recent drift events."""
        return self.drift_monitor.recent_events(n)

    def get_drift_summary(self) -> Dict:
        """Return drift monitor summary."""
        return self.drift_monitor.get_summary()

    def __repr__(self) -> str:
        return (
            f"PaperExecutor("
            f"positions={len(self.position_manager.positions)}, "
            f"trades={len(self.execution_log)}, "
            f"drift_events={self.drift_monitor.total_events})"
        )
