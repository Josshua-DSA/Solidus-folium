"""
Backtest Engine — Simulasi trading historis end-to-end.
Layer 6: app/backtest/ — Risk & Validation.

Menjalankan simulasi trading berdasarkan sinyal (BUY/SELL/HOLD)
pada data harga historis, dengan:
  - IDX lot constraint (kelipatan 100 lembar)
  - Transaction cost model (komisi + pajak + levy + slippage)
  - Position tracking via Decimal precision
  - Pre-trade risk checks via RiskManager
  - Extended performance metrics
"""
import numpy as np
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Any
import logging

from app.backtest.transaction_cost import TransactionCostModel
from app.backtest.metrics import calculate_all_metrics
from app.risk.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class Backtester:
    """
    Engine backtesting simulasi trading historis.

    Args:
        initial_capital: Modal awal (default Rp100 juta)
        commission_pct: Komisi broker per transaksi (default 0.15%)
        slippage_pct: Slippage estimate (default 0.05%)
        lot_size: IDX lot size (default 100 lembar)
        max_position_pct: Bobot maksimum per posisi (untuk RiskManager)
        risk_free_rate: Risk-free rate tahunan untuk Sharpe/Sortino
    """

    def __init__(
        self,
        initial_capital: float = 100_000_000,
        commission_pct: float = 0.0015,
        slippage_pct: float = 0.0005,
        lot_size: int = 100,
        max_position_pct: float = 0.10,
        risk_free_rate: float = 0.0,
    ):
        self.initial_capital = Decimal(str(initial_capital))
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct
        self.lot_size = lot_size
        self.max_position_pct = max_position_pct
        self.risk_free_rate = risk_free_rate

        # Transaction cost model
        self.tc_model = TransactionCostModel(
            commission_buy_pct=commission_pct,
            commission_sell_pct=commission_pct,
            slippage_pct=slippage_pct,
        )

        # Risk manager
        self.risk_manager = RiskManager(max_position_pct=max_position_pct)

    def run(
        self,
        close_prices: pd.DataFrame,
        signals: pd.DataFrame,
        position_size_pct: float = 0.10,
    ) -> Dict[str, Any]:
        """
        Jalankan backtest end-to-end.

        Args:
            close_prices: DataFrame wide (index=date, columns=ticker)
            signals: DataFrame sinyal trading (same shape as close_prices)
                     1 = BUY, -1 = SELL, 0 = HOLD
            position_size_pct: Target bobot per posisi (default 10%)

        Returns:
            Dict berisi:
                equity_curve: pd.Series NAV per tanggal
                trades: List[Dict] semua closed trades
                metrics: Dict semua performance metrics
                positions_history: List[Dict] snapshot posisi per tanggal
        """
        # Validasi input
        if close_prices.empty or signals.empty:
            logger.warning("Empty data — cannot run backtest")
            return self._empty_result()

        # Align index dan columns
        common_dates = close_prices.index.intersection(signals.index)
        common_tickers = close_prices.columns.intersection(signals.columns)

        if len(common_dates) < 2 or len(common_tickers) == 0:
            logger.warning("Insufficient overlapping data for backtest")
            return self._empty_result()

        prices = close_prices.loc[common_dates, common_tickers].sort_index()
        sigs = signals.loc[common_dates, common_tickers].sort_index()

        # State tracking (Decimal precision untuk semua nilai uang)
        cash = self.initial_capital
        # positions: {ticker: {"shares": int, "avg_price": Decimal, "entry_date": date}}
        positions: Dict[str, Dict] = {}
        trades: List[Dict] = []
        equity_values: List[float] = []
        equity_dates: List = []

        logger.info(
            "Backtest start: %d dates, %d tickers, capital=%s",
            len(prices), len(common_tickers), self.initial_capital,
        )

        for date_idx, date in enumerate(prices.index):
            row_prices = prices.loc[date]
            row_signals = sigs.loc[date]

            # ---------- Process signals ----------
            for ticker in common_tickers:
                price = row_prices[ticker]
                signal = row_signals[ticker]

                # Skip NaN
                if pd.isna(price) or pd.isna(signal):
                    continue

                price_dec = Decimal(str(float(price)))
                signal_int = int(signal)

                if signal_int == 1 and ticker not in positions:
                    # ----- BUY -----
                    # Hitung jumlah shares berdasarkan target position size
                    portfolio_value = self._portfolio_value(cash, positions, row_prices)
                    target_value = portfolio_value * Decimal(str(position_size_pct))

                    if price_dec <= 0:
                        continue

                    # Hitung jumlah lot (bulatkan ke bawah)
                    raw_shares = target_value / price_dec
                    lots = int(raw_shares) // self.lot_size
                    if lots <= 0:
                        continue
                    shares = lots * self.lot_size

                    # Transaction cost
                    buy_costs = self.tc_model.calculate_buy_cost(
                        float(price_dec), shares
                    )
                    total_cost = buy_costs["effective_price"]

                    # Cash check
                    if total_cost > cash:
                        # Kurangi lot sampai cukup
                        while lots > 0 and total_cost > cash:
                            lots -= 1
                            shares = lots * self.lot_size
                            if shares <= 0:
                                break
                            buy_costs = self.tc_model.calculate_buy_cost(
                                float(price_dec), shares
                            )
                            total_cost = buy_costs["effective_price"]

                        if lots <= 0:
                            continue

                    # Pre-trade risk check: position limit
                    new_pv = self._portfolio_value(cash, positions, row_prices)
                    if new_pv > 0:
                        new_weight = (Decimal(str(shares)) * price_dec) / new_pv
                        if float(new_weight) > self.max_position_pct:
                            logger.debug(
                                "Position limit skip: %s weight=%.2f%%",
                                ticker, float(new_weight) * 100,
                            )
                            continue

                    # Execute buy
                    cash -= total_cost
                    positions[ticker] = {
                        "shares": shares,
                        "avg_price": price_dec,
                        "entry_date": date,
                    }

                    logger.debug(
                        "BUY %s: %d shares @ %s (cost=%s)",
                        ticker, shares, price_dec, buy_costs["total_cost"],
                    )

                elif signal_int == -1 and ticker in positions:
                    # ----- SELL -----
                    pos = positions[ticker]
                    shares = pos["shares"]

                    # Transaction cost (sell)
                    sell_costs = self.tc_model.calculate_sell_cost(
                        float(price_dec), shares
                    )
                    proceeds = sell_costs["effective_proceeds"]

                    # P&L
                    cost_basis = pos["avg_price"] * Decimal(str(shares))
                    pnl = proceeds - cost_basis

                    cash += proceeds

                    # Record trade
                    trades.append({
                        "ticker": ticker,
                        "entry_date": pos["entry_date"],
                        "exit_date": date,
                        "entry_price": float(pos["avg_price"]),
                        "exit_price": float(price_dec),
                        "shares": shares,
                        "pnl": float(pnl),
                        "pnl_pct": float(pnl / cost_basis) if cost_basis > 0 else 0.0,
                        "commission": float(
                            sell_costs["commission"] + sell_costs["levy"]
                        ),
                        "holding_days": (date - pos["entry_date"]).days
                        if hasattr(date, "__sub__") and hasattr(pos["entry_date"], "__sub__")
                        else 0,
                    })

                    del positions[ticker]

                    logger.debug(
                        "SELL %s: %d shares @ %s (pnl=%s)",
                        ticker, shares, price_dec, pnl,
                    )

            # ---------- End-of-day NAV ----------
            nav = self._portfolio_value(cash, positions, row_prices)
            equity_values.append(float(nav))
            equity_dates.append(date)

        # Equity curve
        equity_curve = pd.Series(
            equity_values, index=equity_dates, name="equity"
        )

        # Calculate metrics
        metrics = calculate_all_metrics(
            equity_curve=equity_curve,
            trades=trades,
            risk_free_rate=self.risk_free_rate,
        )
        metrics["initial_capital"] = float(self.initial_capital)
        metrics["final_nav"] = equity_values[-1] if equity_values else float(self.initial_capital)

        logger.info(
            "Backtest complete: %d trades, total_return=%.2f%%, sharpe=%.2f",
            len(trades),
            metrics.get("total_return", 0) * 100,
            metrics.get("sharpe_ratio", 0),
        )

        return {
            "equity_curve": equity_curve,
            "trades": trades,
            "metrics": metrics,
            "open_positions": {
                ticker: {
                    "shares": pos["shares"],
                    "avg_price": float(pos["avg_price"]),
                    "entry_date": pos["entry_date"],
                }
                for ticker, pos in positions.items()
            },
        }

    def calculate_metrics(
        self, equity_curve: pd.Series
    ) -> Dict[str, float]:
        """
        Hitung metrik performa dari equity curve.
        Wrapper untuk backward compatibility.

        Args:
            equity_curve: Series nilai portofolio per tanggal

        Returns:
            Dict metrik
        """
        return calculate_all_metrics(
            equity_curve=equity_curve,
            risk_free_rate=self.risk_free_rate,
        )

    def _portfolio_value(
        self,
        cash: Decimal,
        positions: Dict[str, Dict],
        current_prices: pd.Series,
    ) -> Decimal:
        """Hitung total portfolio value (cash + positions)."""
        positions_value = Decimal("0")
        for ticker, pos in positions.items():
            price = current_prices.get(ticker)
            if price is not None and not pd.isna(price):
                positions_value += Decimal(str(float(price))) * Decimal(str(pos["shares"]))
            else:
                # Fallback ke avg_price jika harga hari ini tidak ada
                positions_value += pos["avg_price"] * Decimal(str(pos["shares"]))
        return cash + positions_value

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure."""
        return {
            "equity_curve": pd.Series(dtype=float),
            "trades": [],
            "metrics": {},
            "open_positions": {},
        }

    def __repr__(self) -> str:
        return (
            f"Backtester(capital={self.initial_capital:,}, "
            f"commission={self.commission_pct:.4f}, "
            f"lot_size={self.lot_size})"
        )
