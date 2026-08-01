from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from frontend.cli.theme import (
    FROST_BLUE, FROST_LIGHT, SNOW_STORM_1, SNOW_STORM_3,
    AURORA_GREEN, AURORA_YELLOW, AURORA_RED
)

def draw_scanner(signals: list, db_empty: bool) -> Panel:
    """Draws the real-time stock scanning signal screen."""
    table = Table(show_header=True, header_style=f"bold {FROST_LIGHT}", box=None)
    table.add_column("Ticker", style=f"bold {SNOW_STORM_3}")
    table.add_column("Current Price", justify="right", style=SNOW_STORM_1)
    table.add_column("LSTM Conf", justify="right")
    table.add_column("XGBoost Conf", justify="right")
    table.add_column("Combined Score", justify="right")
    table.add_column("Stop Loss (SL)", justify="right", style=AURORA_RED)
    table.add_column("Target Profit (TP)", justify="right", style=AURORA_GREEN)
    table.add_column("Alpha Signal", justify="center")

    for sig in signals:
        lstm_str = f"{sig['lstm']:.1%}"
        xgb_str = f"{sig['xgb']:.1%}" if sig['xgb'] is not None else "N/A"
        score_str = f"{sig['score']:.1%}"
        
        # Colour coding score
        if sig['score'] >= 0.70:
            score_colored = f"[{AURORA_GREEN}]{score_str}[/{AURORA_GREEN}]"
            action_colored = f"[bold white on {AURORA_GREEN}] BUY [/bold white on {AURORA_GREEN}]"
        elif sig['score'] >= 0.55:
            score_colored = f"[{AURORA_YELLOW}]{score_str}[/{AURORA_YELLOW}]"
            action_colored = f"[bold black on {AURORA_YELLOW}] HOLD [/bold black on {AURORA_YELLOW}]"
        else:
            score_colored = f"[{AURORA_RED}]{score_str}[/{AURORA_RED}]"
            action_colored = f"[bold white on {AURORA_RED}] SELL [/bold white on {AURORA_RED}]"
            
        table.add_row(
            sig['ticker'],
            f"Rp {sig['price']:,.0f}",
            lstm_str,
            xgb_str,
            score_colored,
            f"Rp {sig['sl']:,.0f}",
            f"Rp {sig['tp']:,.0f}",
            action_colored
        )
            
    return Panel(
        Align.center(table),
        title="REAL-TIME ALPHA SCANNER (LQ45)",
        border_style=FROST_BLUE,
        subtitle="Sorted by combined model confidence score",
        padding=(1, 2)
    )
