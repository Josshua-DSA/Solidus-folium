"""
Extended Performance Metrics — Kalkulasi metrik performa trading.

Metrik yang tersedia:
  - Sharpe Ratio (annualized)
  - Sortino Ratio (downside deviation only)
  - CAGR (Compound Annual Growth Rate)
  - Max Drawdown + Drawdown Duration
  - Calmar Ratio (CAGR / |Max DD|)
  - Win Rate (% trades profitable)
  - Profit Factor (gross profit / gross loss)
  - J-value Score (custom: Sharpe × CAGR / |MDD|)
  - Total Return
  - Annualized Volatility

Layer 6: app/backtest/ — Risk & Validation.
"""
import numpy as np
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# IDX trading days per year
TRADING_DAYS_PER_YEAR = 252


def calculate_total_return(equity_curve: pd.Series) -> float:
    """
    Total return dari equity curve.

    Returns:
        float: Total return sebagai fraksi (0.10 = 10%)
    """
    if equity_curve.empty or len(equity_curve) < 2:
        return 0.0
    return float((equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1)


def calculate_cagr(
    equity_curve: pd.Series,
    trading_days_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """
    Compound Annual Growth Rate.

    Args:
        equity_curve: Series nilai portofolio per tanggal
        trading_days_per_year: Jumlah hari bursa per tahun

    Returns:
        CAGR sebagai fraksi (0.10 = 10%)
    """
    if equity_curve.empty or len(equity_curve) < 2:
        return 0.0

    total_return = equity_curve.iloc[-1] / equity_curve.iloc[0]
    n_days = len(equity_curve)
    n_years = n_days / trading_days_per_year

    if n_years <= 0 or total_return <= 0:
        return 0.0

    return float(total_return ** (1 / n_years) - 1)


def calculate_sharpe_ratio(
    equity_curve: pd.Series,
    risk_free_rate: float = 0.0,
    trading_days_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """
    Annualized Sharpe Ratio.

    Args:
        equity_curve: Series nilai portofolio per tanggal
        risk_free_rate: Risk-free rate tahunan (default 0)
        trading_days_per_year: Hari bursa per tahun

    Returns:
        Sharpe ratio annualized
    """
    if equity_curve.empty or len(equity_curve) < 2:
        return 0.0

    returns = equity_curve.pct_change().dropna()
    if returns.std() == 0:
        return 0.0

    daily_rf = risk_free_rate / trading_days_per_year
    excess = returns - daily_rf
    return float((excess.mean() / excess.std()) * np.sqrt(trading_days_per_year))


def calculate_sortino_ratio(
    equity_curve: pd.Series,
    risk_free_rate: float = 0.0,
    trading_days_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """
    Annualized Sortino Ratio — hanya downside deviation.

    Args:
        equity_curve: Series nilai portofolio per tanggal
        risk_free_rate: Risk-free rate tahunan
        trading_days_per_year: Hari bursa per tahun

    Returns:
        Sortino ratio annualized
    """
    if equity_curve.empty or len(equity_curve) < 2:
        return 0.0

    returns = equity_curve.pct_change().dropna()
    daily_rf = risk_free_rate / trading_days_per_year
    excess = returns - daily_rf

    downside = excess[excess < 0]
    if downside.empty or downside.std() == 0:
        return 0.0 if excess.mean() <= 0 else float("inf")

    downside_std = np.sqrt(np.mean(downside**2))
    return float((excess.mean() / downside_std) * np.sqrt(trading_days_per_year))


def calculate_max_drawdown(equity_curve: pd.Series) -> Dict[str, float]:
    """
    Max drawdown + durasi recovery.

    Returns:
        Dict dengan:
            max_drawdown: MDD sebagai fraksi negatif (e.g. -0.15 = -15%)
            max_drawdown_duration: Durasi (hari bursa) dari peak ke trough
            recovery_days: Hari dari trough ke recovery (0 jika belum recover)
    """
    if equity_curve.empty or len(equity_curve) < 2:
        return {"max_drawdown": 0.0, "max_drawdown_duration": 0, "recovery_days": 0}

    cum_max = equity_curve.cummax()
    drawdown = (equity_curve - cum_max) / cum_max
    max_dd = float(drawdown.min())

    # Cari durasi drawdown terdalam
    trough_idx = drawdown.idxmin()
    peak_idx = equity_curve.loc[:trough_idx].idxmax()

    # Peak to trough duration (dalam jumlah bar)
    peak_pos = equity_curve.index.get_loc(peak_idx)
    trough_pos = equity_curve.index.get_loc(trough_idx)
    dd_duration = int(trough_pos - peak_pos)

    # Recovery: dari trough sampai equity >= peak value
    peak_value = equity_curve.loc[peak_idx]
    post_trough = equity_curve.loc[trough_idx:]
    recovered = post_trough[post_trough >= peak_value]

    if len(recovered) > 0:
        recovery_idx = recovered.index[0]
        recovery_pos = equity_curve.index.get_loc(recovery_idx)
        recovery_days = int(recovery_pos - trough_pos)
    else:
        recovery_days = 0  # Belum recover

    return {
        "max_drawdown": max_dd,
        "max_drawdown_duration": dd_duration,
        "recovery_days": recovery_days,
    }


def calculate_calmar_ratio(
    equity_curve: pd.Series,
    trading_days_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """
    Calmar Ratio = CAGR / |Max Drawdown|.

    Returns:
        Calmar ratio (0 jika MDD = 0)
    """
    cagr = calculate_cagr(equity_curve, trading_days_per_year)
    dd_info = calculate_max_drawdown(equity_curve)
    mdd = abs(dd_info["max_drawdown"])

    if mdd == 0:
        return 0.0
    return float(cagr / mdd)


def calculate_annualized_volatility(
    equity_curve: pd.Series,
    trading_days_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """
    Annualized volatility dari equity curve.

    Returns:
        Volatility tahunan sebagai fraksi
    """
    if equity_curve.empty or len(equity_curve) < 2:
        return 0.0

    returns = equity_curve.pct_change().dropna()
    return float(returns.std() * np.sqrt(trading_days_per_year))


def calculate_trade_metrics(trades: List[Dict]) -> Dict[str, float]:
    """
    Hitung metrik level trade: win rate, profit factor, avg win/loss.

    Args:
        trades: List of trade dicts, masing-masing harus punya key 'pnl'

    Returns:
        Dict metrik trade-level
    """
    if not trades:
        return {
            "n_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "total_commission": 0.0,
        }

    pnls = [float(t.get("pnl", 0)) for t in trades]
    commissions = [float(t.get("commission", 0)) for t in trades]

    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p < 0]

    n_trades = len(pnls)
    win_rate = len(winners) / n_trades if n_trades > 0 else 0.0

    gross_profit = sum(winners) if winners else 0.0
    gross_loss = abs(sum(losers)) if losers else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    avg_win = np.mean(winners) if winners else 0.0
    avg_loss = np.mean(losers) if losers else 0.0

    return {
        "n_trades": n_trades,
        "win_rate": float(win_rate),
        "profit_factor": float(profit_factor),
        "avg_win": float(avg_win),
        "avg_loss": float(avg_loss),
        "best_trade": float(max(pnls)) if pnls else 0.0,
        "worst_trade": float(min(pnls)) if pnls else 0.0,
        "total_commission": float(sum(commissions)),
    }


def calculate_j_value(
    equity_curve: pd.Series,
    trading_days_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """
    J-value Score (custom risk-adjusted metric).

    Formula: J = (Sharpe × CAGR) / |Max Drawdown|

    Semakin tinggi, semakin baik risk-adjusted performance.

    Returns:
        J-value score
    """
    sharpe = calculate_sharpe_ratio(equity_curve, trading_days_per_year=trading_days_per_year)
    cagr = calculate_cagr(equity_curve, trading_days_per_year)
    dd_info = calculate_max_drawdown(equity_curve)
    mdd = abs(dd_info["max_drawdown"])

    if mdd == 0:
        return 0.0
    return float((sharpe * cagr) / mdd)


def calculate_all_metrics(
    equity_curve: pd.Series,
    trades: Optional[List[Dict]] = None,
    risk_free_rate: float = 0.0,
    trading_days_per_year: int = TRADING_DAYS_PER_YEAR,
) -> Dict[str, float]:
    """
    Hitung semua metrik performa sekaligus.

    Args:
        equity_curve: Series nilai portofolio per tanggal
        trades: List trade dicts (optional, untuk trade-level metrics)
        risk_free_rate: Risk-free rate tahunan
        trading_days_per_year: Hari bursa per tahun

    Returns:
        Dict lengkap semua metrik
    """
    metrics = {}

    # Equity curve metrics
    metrics["total_return"] = calculate_total_return(equity_curve)
    metrics["cagr"] = calculate_cagr(equity_curve, trading_days_per_year)
    metrics["sharpe_ratio"] = calculate_sharpe_ratio(
        equity_curve, risk_free_rate, trading_days_per_year
    )
    metrics["sortino_ratio"] = calculate_sortino_ratio(
        equity_curve, risk_free_rate, trading_days_per_year
    )
    metrics["annualized_volatility"] = calculate_annualized_volatility(
        equity_curve, trading_days_per_year
    )
    metrics["calmar_ratio"] = calculate_calmar_ratio(
        equity_curve, trading_days_per_year
    )
    metrics["j_value"] = calculate_j_value(equity_curve, trading_days_per_year)

    # Drawdown metrics
    dd_info = calculate_max_drawdown(equity_curve)
    metrics["max_drawdown"] = dd_info["max_drawdown"]
    metrics["max_drawdown_duration"] = dd_info["max_drawdown_duration"]
    metrics["recovery_days"] = dd_info["recovery_days"]

    # Periode
    metrics["n_days"] = len(equity_curve)

    # Trade-level metrics
    if trades is not None:
        trade_metrics = calculate_trade_metrics(trades)
        metrics.update(trade_metrics)

    return metrics
