"""
Portfolio Service — Manage posisi, NAV, P&L tracking.

Menyediakan API untuk TUI portfolio panel:
  - Open/close positions (paper trading)
  - Hitung NAV, unrealized P&L
  - Track transaction history
  - Sector exposure analysis

Menggunakan Decimal precision untuk semua nilai uang.
"""
import pandas as pd
import numpy as np
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import logging

from app.execution.execution_engine import ExecutionEngine, Order, Trade
from app.execution.position_manager import PositionManager
from app.risk.risk_manager import RiskManager
from app.backtest.transaction_cost import TransactionCostModel
from shared.utils.user_profile import ProfileManager

logger = logging.getLogger(__name__)


class PortfolioService:
    """
    Service layer untuk portfolio management (paper trading).
    Otomatis menyinkronkan modal RDN dan holding awal dari UserProfile jika ada.
    """

    def __init__(
        self,
        initial_capital: Optional[float] = None,
        commission_pct: float = 0.0015,
        slippage_pct: float = 0.0005,
        max_position_pct: float = 1.0,
        daily_loss_limit: float = 0.03,
        max_drawdown_stop: float = 0.15,
        seed_profile: bool = True,
    ):
        # Auto-sync dengan UserProfile jika disetujui & ada profile
        profile = None
        if seed_profile:
            pm = ProfileManager()
            profile = pm.load() if pm.exists() else None

        if initial_capital is None:
            if profile and profile.rdn_balance > 0:
                initial_capital = profile.rdn_balance
            else:
                initial_capital = 10_000_000.0

        self.initial_capital = Decimal(str(initial_capital))
        self.risk_manager = RiskManager(
            max_position_pct=max_position_pct,
            daily_loss_limit=daily_loss_limit,
            max_drawdown_stop=max_drawdown_stop,
        )
        self.cost_model = TransactionCostModel(
            commission_buy_pct=commission_pct,
            commission_sell_pct=commission_pct,
            slippage_pct=slippage_pct,
        )
        self.engine = ExecutionEngine(
            commission_pct=commission_pct,
            slippage_pct=slippage_pct,
        )
        self.position_manager = PositionManager(initial_capital=float(self.initial_capital))

        # Seed posisi awal dari UserProfile jika seed_profile=True
        if seed_profile and profile and profile.positions:
            for p in profile.positions:
                try:
                    self.position_manager.open_position(
                        ticker=p.ticker,
                        quantity_shares=p.shares,
                        price=float(p.avg_price),
                    )
                except Exception as e:
                    logger.warning("Gagal seed posisi awal %s: %s", p.ticker, e)

        # Transaction cost model
        self.tc_model = TransactionCostModel(
            commission_buy_pct=commission_pct,
            commission_sell_pct=commission_pct,
            slippage_pct=slippage_pct,
        )

        # NAV history
        self.nav_history: List[Dict] = []
        self.transaction_log: List[Dict] = []

    def execute_order(
        self,
        ticker: str,
        side: str,
        lots: int,
        current_price: float,
        current_prices: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Eksekusi order paper trading dengan full risk validation.

        Args:
            ticker: Ticker saham
            side: 'BUY' atau 'SELL'
            lots: Jumlah lot (1 lot = 100 lembar)
            current_price: Harga saat ini
            current_prices: Dict harga semua posisi (untuk NAV calc)

        Returns:
            Dict: {"success": bool, "message": str, "trade": Trade|None}
        """
        shares = lots * 100

        # Validate side
        if side not in ("BUY", "SELL"):
            return {"success": False, "message": "Side harus BUY atau SELL", "trade": None}

        if lots <= 0:
            return {"success": False, "message": "Lot harus > 0", "trade": None}

        # Pre-trade risk checks
        if side == "BUY":
            risk_result = self._check_buy_risk(ticker, shares, current_price, current_prices)
            if not risk_result["passed"]:
                return {"success": False, "message": risk_result["reason"], "trade": None}

        elif side == "SELL":
            # Check position exists
            if ticker not in self.position_manager.positions:
                return {"success": False, "message": f"Tidak punya posisi {ticker}", "trade": None}
            pos = self.position_manager.positions[ticker]
            if shares > pos.quantity_shares:
                return {
                    "success": False,
                    "message": f"Shares tidak cukup: mau {shares}, punya {pos.quantity_shares}",
                    "trade": None,
                }

        # Execute via engine
        try:
            order = Order(
                ticker=ticker,
                side=side,
                quantity_shares=shares,
                price=current_price,
                timestamp=pd.Timestamp.now(),
            )
            trade = self.engine.execute(order)
        except ValueError as e:
            return {"success": False, "message": str(e), "trade": None}

        # Update position manager
        cost = trade.commission + trade.slippage_cost
        if side == "BUY":
            success = self.position_manager.open_position(
                ticker=ticker,
                quantity_shares=shares,
                price=trade.execution_price,
                cost=cost,
                timestamp=trade.timestamp,
            )
        else:
            success = self.position_manager.close_position(
                ticker=ticker,
                quantity_shares=shares,
                price=trade.execution_price,
                cost=cost,
                timestamp=trade.timestamp,
            )

        if success:
            self.transaction_log.append({
                "timestamp": trade.timestamp,
                "ticker": ticker,
                "side": side,
                "lots": lots,
                "shares": shares,
                "price": trade.execution_price,
                "commission": trade.commission,
                "slippage": trade.slippage_cost,
            })

            return {
                "success": True,
                "message": f"{side} {lots} lot {ticker} @ Rp {trade.execution_price:,.0f}",
                "trade": trade,
            }

        return {"success": False, "message": "Position manager rejected order", "trade": None}

    def _check_buy_risk(
        self,
        ticker: str,
        shares: int,
        price: float,
        current_prices: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Pre-trade risk check untuk BUY order."""
        price_dec = Decimal(str(price))
        notional = price_dec * Decimal(str(shares))

        # Cash check
        if notional > self.position_manager.cash:
            return {
                "passed": False,
                "reason": f"Cash tidak cukup: butuh Rp {notional:,.0f}, punya Rp {self.position_manager.cash:,.0f}",
            }

        # Position concentration check
        if current_prices:
            portfolio_val = self.position_manager.get_portfolio_value(current_prices)
            if portfolio_val > 0:
                new_weight = float(notional / portfolio_val)
                if new_weight > self.risk_manager.max_position_pct:
                    return {
                        "passed": False,
                        "reason": f"Position weight {new_weight:.1%} > limit {self.risk_manager.max_position_pct:.0%}",
                    }

        return {"passed": True, "reason": ""}

    def get_portfolio_summary(
        self,
        current_prices: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        Return ringkasan portofolio lengkap untuk TUI.

        Args:
            current_prices: Dict {ticker: current_price}

        Returns:
            Dict summary lengkap
        """
        summary = self.position_manager.get_portfolio_summary(current_prices)

        # Enrich with position details
        positions = []
        for ticker, pos in self.position_manager.positions.items():
            cur_price = current_prices.get(ticker, pos.avg_price)
            pnl = pos.unrealized_pnl(cur_price)
            pnl_pct = pos.unrealized_pnl_pct(cur_price)

            positions.append({
                "ticker": ticker,
                "shares": pos.quantity_shares,
                "lots": pos.lots,
                "avg_price": pos.avg_price,
                "current_price": cur_price,
                "market_value": float(Decimal(str(cur_price)) * Decimal(str(pos.quantity_shares))),
                "cost_basis": float(pos.notional),
                "unrealized_pnl": float(pnl),
                "unrealized_pnl_pct": pnl_pct,
                "entry_date": pos.entry_date,
            })

        summary["positions"] = positions
        summary["transaction_count"] = len(self.transaction_log)

        return summary

    def get_transaction_history(self, last_n: int = 20) -> List[Dict]:
        """Return N transaksi terakhir."""
        return self.transaction_log[-last_n:]

    def __repr__(self) -> str:
        return (
            f"PortfolioService(capital={self.initial_capital:,}, "
            f"positions={len(self.position_manager.positions)})"
        )
