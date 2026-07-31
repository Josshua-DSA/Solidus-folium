"""
UI Renderer — Rendering tabel dan metrik estetik menggunakan Rich.
"""
from typing import Dict, List, Optional, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel


console = Console()


def render_table(
    data: List[Dict[str, Any]],
    title: str = "",
    columns: Optional[List[str]] = None,
) -> None:
    """
    Render data sebagai tabel Rich di terminal.

    Args:
        data: List of dicts (setiap dict = satu baris)
        title: Judul tabel
        columns: List kolom yang ditampilkan (None = semua)
    """
    if not data:
        console.print("[yellow]Tidak ada data untuk ditampilkan.[/yellow]")
        return

    table = Table(title=title, show_header=True, header_style="bold cyan")

    # Tentukan kolom
    if columns is None:
        columns = list(data[0].keys())

    for col in columns:
        table.add_column(col)

    for row in data:
        values = [str(row.get(col, "")) for col in columns]
        table.add_row(*values)

    console.print(table)


def render_metrics(
    metrics: Dict[str, Any],
    title: str = "Performance Metrics",
) -> None:
    """
    Render metrik performa sebagai panel Rich.

    Args:
        metrics: Dict berisi nama metrik → nilai
        title: Judul panel
    """
    lines = []
    for key, value in metrics.items():
        if isinstance(value, float):
            lines.append(f"  {key:25s} : {value:>10.4f}")
        else:
            lines.append(f"  {key:25s} : {str(value):>10s}")

    content = "\n".join(lines)
    panel = Panel(content, title=title, border_style="green")
    console.print(panel)


def render_portfolio(
    positions: List[Dict[str, Any]],
    total_capital: float,
) -> None:
    """
    Render ringkasan portofolio.

    Args:
        positions: List posisi (ticker, lot, avg_price, current_price, pnl)
        total_capital: Total modal
    """
    table = Table(title="Portfolio Summary", show_header=True, header_style="bold magenta")
    table.add_column("Ticker")
    table.add_column("Lot")
    table.add_column("Avg Price")
    table.add_column("Current")
    table.add_column("PnL")
    table.add_column("PnL %")

    total_pnl = 0
    for pos in positions:
        pnl = pos.get("pnl", 0)
        pnl_pct = pos.get("pnl_pct", 0)
        total_pnl += pnl

        color = "green" if pnl >= 0 else "red"
        table.add_row(
            pos.get("ticker", ""),
            str(pos.get("lot", 0)),
            f"{pos.get('avg_price', 0):,.0f}",
            f"{pos.get('current_price', 0):,.0f}",
            f"[{color}]{pnl:,.0f}[/{color}]",
            f"[{color}]{pnl_pct:.2f}%[/{color}]",
        )

    console.print(table)
    console.print(f"\n  Total Capital: Rp{total_capital:,.0f}")
    console.print(f"  Total PnL:     Rp{total_pnl:,.0f}\n")
