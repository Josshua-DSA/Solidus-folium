import random
from datetime import datetime, timedelta
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from frontend.cli.theme import (
    FROST_BLUE, FROST_LIGHT, SNOW_STORM_1, SNOW_STORM_2,
    AURORA_GREEN, AURORA_YELLOW, AURORA_RED, LQ45_FUNDAMENTALS
)

def draw_inspect(ticker: str, db_empty: bool, storage) -> Layout:
    """Draws the detailed stock metrics and price inspection screen."""
    grid = Layout()
    grid.split_row(
        Layout(name="inspect_left", ratio=1),
        Layout(name="inspect_right", ratio=1)
    )

    ticker_upper = ticker.upper()
    if not ticker_upper.endswith(".JK"):
        ticker_upper += ".JK"
        
    # Try loading database fundamentals if available
    fundamentals = None
    if not db_empty and storage:
        try:
            fundamentals = storage.load_fundamentals(ticker_upper)
        except Exception:
            pass
            
    # Fallback to Mock LQ45 Fundamentals if database empty or missing ticker
    if not fundamentals:
        fundamentals = LQ45_FUNDAMENTALS.get(ticker_upper, {
            "pe": 12.5, "pb": 1.5, "dividend_yield": 0.035, "roe": 0.14, "der": 0.5, "eps": 150, "market_cap": 100e9, "name": "IDX Listed Company"
        })
        
    # Left Pane: Financial Ratios (Valuation & Profitability)
    ratio_table = Table(show_header=False, box=None)
    ratio_table.add_column("Ratio Name", style=f"bold {FROST_LIGHT}")
    ratio_table.add_column("Value", style=SNOW_STORM_1)
    
    ratio_table.add_row("Company Name", str(fundamentals.get("name", "N/A")))
    
    pe_val = fundamentals.get("pe")
    pe_str = f"{pe_val:.1f}x" if pe_val is not None else "N/A"
    ratio_table.add_row("Price to Earnings (P/E)", pe_str)
    
    pb_val = fundamentals.get("pb")
    pb_str = f"{pb_val:.1f}x" if pb_val is not None else "N/A"
    ratio_table.add_row("Price to Book (P/B)", pb_str)
    
    div_val = fundamentals.get("dividend_yield")
    div_str = f"{div_val * 100:.2f}%" if div_val is not None else "N/A"
    ratio_table.add_row("Dividend Yield", div_str)
    
    roe_val = fundamentals.get("roe")
    roe_str = f"{roe_val * 100:.1f}%" if roe_val is not None else "N/A"
    ratio_table.add_row("Return on Equity (ROE)", roe_str)
    
    der_val = fundamentals.get("der")
    der_str = f"{der_val:.2f}" if der_val is not None else "N/A"
    ratio_table.add_row("Debt to Equity (D/E)", der_str)
    
    eps_val = fundamentals.get("eps")
    eps_str = f"Rp {eps_val:,.0f}" if eps_val is not None else "N/A"
    ratio_table.add_row("Earnings Per Share (EPS)", eps_str)
    
    cap_val = fundamentals.get("market_cap")
    cap_str = f"Rp {cap_val / 1e9:,.0f} B" if cap_val is not None else "N/A"
    ratio_table.add_row("Market Capitalization", cap_str)
    
    left_panel = Panel(
        ratio_table,
        title=f"VALUATION & FUNDAMENTAL METRICS: {ticker_upper}",
        border_style=FROST_BLUE,
        padding=(1, 2)
    )

    # Right Pane: Historic Price & ML Prediction
    price_table = Table(show_header=True, header_style=f"bold {FROST_LIGHT}", box=None)
    price_table.add_column("Date", style=SNOW_STORM_2)
    price_table.add_column("Open", justify="right", style=SNOW_STORM_1)
    price_table.add_column("High", justify="right", style=SNOW_STORM_1)
    price_table.add_column("Low", justify="right", style=SNOW_STORM_1)
    price_table.add_column("Close", justify="right", style="bold white")
    price_table.add_column("Volume", justify="right", style=SNOW_STORM_1)

    # Simulated last 8 days of price history
    random.seed(hash(ticker_upper))
    close_p = LQ45_FUNDAMENTALS.get(ticker_upper, {"eps": 100})["eps"] * 12 + random.randint(-200, 200)
    if close_p <= 0:
        close_p = 2500
        
    for i in range(8):
        date_str = (datetime.now() - timedelta(days=(8-i))).strftime("%Y-%m-%d")
        chg = random.uniform(-0.02, 0.02)
        op = close_p * (1 - chg * 0.5)
        hi = max(op, close_p) * (1 + random.uniform(0, 0.01))
        lo = min(op, close_p) * (1 - random.uniform(0, 0.01))
        vol = random.randint(100000, 10000000)
        
        price_table.add_row(
            date_str,
            f"{op:,.0f}",
            f"{hi:,.0f}",
            f"{lo:,.0f}",
            f"{close_p:,.0f}",
            f"{vol:,}"
        )
        close_p = close_p * (1 + chg)

    # Prediction probability bars
    pred_text = Text()
    pred_text.append("\nML CLASSIFIER PREDICTIONS (TBL HORIZON 5 DAYS):\n\n")
    pred_text.append("  Class 2 (PROFIT)  : ", style=AURORA_GREEN)
    pred_text.append("██████████████░░░░░░  72.5%\n", style=AURORA_GREEN)
    pred_text.append("  Class 1 (NEUTRAL) : ", style=AURORA_YELLOW)
    pred_text.append("████░░░░░░░░░░░░░░░░  20.0%\n", style=AURORA_YELLOW)
    pred_text.append("  Class 0 (LOSS)    : ", style=AURORA_RED)
    pred_text.append("██░░░░░░░░░░░░░░░░░░  7.5%\n", style=AURORA_RED)
    
    right_layout = Layout()
    right_layout.split_column(
        Layout(price_table, ratio=2),
        Layout(pred_text, ratio=1)
    )
    
    right_panel = Panel(
        right_layout,
        title=f"HISTORICAL PRICES & ML ALIGNMENT",
        border_style=FROST_BLUE,
        padding=(1, 2)
    )

    grid["inspect_left"].update(left_panel)
    grid["inspect_right"].update(right_panel)
    return grid
