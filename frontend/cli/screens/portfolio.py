from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from frontend.cli.theme import (
    FROST_BLUE, FROST_LIGHT, SNOW_STORM_1, SNOW_STORM_2, SNOW_STORM_3,
    AURORA_GREEN, AURORA_RED, POLAR_NIGHT_3
)

def draw_portfolio(portfolio: list, capital: float) -> Panel:
    """Draws the current active positions and capital allocation."""
    table = Table(show_header=True, header_style=f"bold {FROST_LIGHT}", box=None)
    table.add_column("Ticker", style=f"bold {SNOW_STORM_3}")
    table.add_column("Shares", justify="right", style=SNOW_STORM_1)
    table.add_column("Avg Entry Price", justify="right", style=SNOW_STORM_1)
    table.add_column("Current Price", justify="right", style=SNOW_STORM_1)
    table.add_column("Total Cost", justify="right", style=SNOW_STORM_2)
    table.add_column("Market Value", justify="right", style=SNOW_STORM_2)
    table.add_column("Unrealized PnL (IDR)", justify="right")
    table.add_column("PnL %", justify="right")
    table.add_column("SL / TP", justify="center", style=FROST_BLUE)

    total_cost = 0.0
    total_value = 0.0
    total_pnl = 0.0

    for pos in portfolio:
        cost = pos["shares"] * pos["avg_price"]
        value = pos["shares"] * pos["current_price"]
        pnl = value - cost
        pnl_pct = (pnl / cost) * 100
        
        total_cost += cost
        total_value += value
        total_pnl += pnl
        
        pnl_color = AURORA_GREEN if pnl >= 0 else AURORA_RED
        pnl_str = f"Rp {pnl:+,.0f}"
        pnl_pct_str = f"{pnl_pct:+.2f}%"
        
        table.add_row(
            pos["ticker"],
            f"{pos['shares']:,}",
            f"Rp {pos['avg_price']:,.0f}",
            f"Rp {pos['current_price']:,.0f}",
            f"Rp {cost:,.0f}",
            f"Rp {value:,.0f}",
            f"[{pnl_color}]{pnl_str}[/{pnl_color}]",
            f"[{pnl_color}]{pnl_pct_str}[/{pnl_color}]",
            f"{pos['sl']:,.0f} / {pos['tp']:,.0f}"
        )
        
    free_cash = capital - total_cost
    portfolio_equity = free_cash + total_value
    net_return = ((portfolio_equity - capital) / capital) * 100
    net_return_color = AURORA_GREEN if net_return >= 0 else AURORA_RED

    summary_table = Table(show_header=False, box=None)
    summary_table.add_column("Metric", style=FROST_LIGHT)
    summary_table.add_column("Val", style="bold")
    summary_table.add_row("Initial Deposit:", f"Rp {capital:,.0f}")
    summary_table.add_row("Cash Balance:", f"Rp {free_cash:,.0f}")
    summary_table.add_row("Total Assets Cost:", f"Rp {total_cost:,.0f}")
    summary_table.add_row("Current Assets Value:", f"Rp {total_value:,.0f}")
    summary_table.add_row("Portfolio Net Equity:", f"Rp {portfolio_equity:,.0f}")
    summary_table.add_row("Net Return:", f"[{net_return_color}]{net_return:+.2f}% (Rp {portfolio_equity-capital:+,.0f})[/{net_return_color}]")

    outer_table = Table(show_header=False, box=None)
    outer_table.add_column("col1")
    outer_table.add_row(table)
    outer_table.add_row(Text("----------------------------------------------------------------------------------------------------------------", style=POLAR_NIGHT_3))
    outer_table.add_row(summary_table)

    return Panel(
        outer_table,
        title="ACTIVE PORTFOLIO & LEDGER BALANCE",
        border_style=FROST_BLUE,
        padding=(1, 2)
    )
