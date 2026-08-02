import random
from datetime import datetime, timedelta
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from frontend.cli.theme import (
    FROST_BLUE, FROST_LIGHT, FROST_TEAL, SNOW_STORM_1, SNOW_STORM_2, SNOW_STORM_3,
    AURORA_GREEN, AURORA_YELLOW, AURORA_RED, AURORA_ORANGE, POLAR_NIGHT_3, LQ45_FUNDAMENTALS
)

def draw_inspect(ticker: str, db_empty: bool, storage) -> Layout:
    """Draws a professional 3-column Equity Research screen matching the Fincept style."""
    grid = Layout()
    grid.split_column(
        Layout(name="inspect_top", ratio=1),
        Layout(name="inspect_bottom", size=5)
    )
    
    inspect_top = grid["inspect_top"]
    inspect_top.split_row(
        Layout(name="inspect_left", ratio=1),
        Layout(name="inspect_center", ratio=2),
        Layout(name="inspect_right", ratio=1)
    )

    ticker_upper = ticker.upper()
    if not ticker_upper.endswith(".JK"):
        ticker_upper += ".JK"
        
    # Load database fundamentals if available
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
        
    # 1. Left Panel: Valuation & Share Stats
    left_table = Table(show_header=False, box=None)
    left_table.add_column("Key", style=f"bold {FROST_LIGHT}")
    left_table.add_column("Val", style=SNOW_STORM_1, justify="right")
    
    # Valuation
    pe_val = fundamentals.get("pe")
    pe_str = f"{pe_val:.1f}x" if pe_val is not None else "N/A"
    left_table.add_row("P/E Ratio", pe_str)
    
    pb_val = fundamentals.get("pb")
    pb_str = f"{pb_val:.1f}x" if pb_val is not None else "N/A"
    left_table.add_row("P/B Ratio", pb_str)
    
    left_table.add_row("PEG Ratio", "1.45x")
    
    div_val = fundamentals.get("dividend_yield")
    div_str = f"{div_val * 100:.2f}%" if div_val is not None else "N/A"
    left_table.add_row("Div Yield", div_str)
    
    roe_val = fundamentals.get("roe")
    roe_str = f"{roe_val * 100:.1f}%" if roe_val is not None else "N/A"
    left_table.add_row("ROE", roe_str)
    
    der_val = fundamentals.get("der")
    der_str = f"{der_val:.2f}" if der_val is not None else "N/A"
    left_table.add_row("D/E Ratio", der_str)
    
    eps_val = fundamentals.get("eps")
    eps_str = f"Rp {eps_val:,.0f}" if eps_val is not None else "N/A"
    left_table.add_row("EPS", eps_str)
    
    cap_val = fundamentals.get("market_cap")
    cap_str = f"Rp {cap_val / 1e9:,.0f} B" if cap_val is not None else "N/A"
    left_table.add_row("Market Cap", cap_str)
    
    left_panel = Panel(
        left_table,
        title="VALUATION & STATS",
        border_style=FROST_BLUE,
        padding=(0, 1)
    )
    
    # 2. Center Panel: Candlestick Chart (Simulated 1Y)
    chart_text = Text()
    chart_text.append("\n  1Y CANDLESTICK CHART & VOLUME (Rp):\n\n", style=f"bold {FROST_LIGHT}")
    chart_text.append("  12,000 |                 ▲   ▲\n")
    chart_text.append("  11,000 |             ▲ █ █ █ █   ▲\n")
    chart_text.append("  10,000 |         ▲ █ █ █ █ █ █ █ █   ▲\n")
    chart_text.append("   9,000 |   ▲ █ █ █ █ █ █ █ █ █ █ █ █ █\n")
    chart_text.append("   8,000 | █ █ █ █ █ █ █ █ █ █ █ █ █ █ █ █\n")
    chart_text.append("         +───────────────────────────────────\n")
    chart_text.append("           Jun   Aug   Oct   Dec   Feb   Apr\n\n", style=POLAR_NIGHT_3)
    
    # ML Prediction bars combined
    chart_text.append("  ML SIGNAL DIRECTION (5D HORIZON):\n", style=f"bold {FROST_BLUE}")
    chart_text.append("    [PROFIT/BUY] : ██████████████░░░░░░  72.5%\n", style=AURORA_GREEN)
    chart_text.append("    [LOSS/SELL]  : ██░░░░░░░░░░░░░░░░░░  7.5%", style=AURORA_RED)
    
    center_panel = Panel(
        chart_text,
        title=f"PRICE ACTION & PREDICTIONS: {ticker_upper}",
        border_style=FROST_BLUE,
        padding=(0, 1)
    )

    # 3. Right Panel: Analyst Targets & Financial Health
    right_table = Table(show_header=False, box=None)
    right_table.add_column("Key", style=f"bold {FROST_LIGHT}")
    right_table.add_column("Val", style=SNOW_STORM_1, justify="right")
    
    # Analyst Targets
    right_table.add_row("Consensus Target", "Rp 11,500")
    right_table.add_row("High Target", "Rp 12,800")
    right_table.add_row("Low Target", "Rp 9,100")
    right_table.add_row("Consensus Rating", "[green]STRONG BUY[/green]")
    
    # Margins
    right_table.add_row("Gross Margin", "48.20%")
    right_table.add_row("Operating Margin", "34.50%")
    right_table.add_row("Net Profit Margin", "26.10%")
    right_table.add_row("Beta (3Y Vol)", "0.95")
    
    right_panel = Panel(
        right_table,
        title="ANALYST VIEW & MARGINS",
        border_style=FROST_BLUE,
        padding=(0, 1)
    )
    
    # 4. Bottom Panel: Company Overview & Info
    overview_text = Text()
    overview_text.append(f"COMPANY INFO & PROFILES ({ticker_upper}):\n", style=f"bold {FROST_LIGHT}")
    
    desc_map = {
        "BBCA.JK": "Bank Central Asia Tbk menyediakan jasa perbankan komersial dan ritel di Indonesia. Merupakan bank swasta terbesar dengan kapitalisasi pasar tertinggi di Indonesia.",
        "BBRI.JK": "Bank Rakyat Indonesia Tbk berfokus pada jasa perbankan mikro, kecil, dan menengah (UMKM) untuk pembangunan ekonomi rakyat di Indonesia.",
        "BMRI.JK": "Bank Mandiri (Persero) Tbk adalah salah satu bank BUMN terbesar di Indonesia yang melayani segmen korporasi, komersial, dan konsumer secara terintegrasi.",
        "TLKM.JK": "Telkom Indonesia Tbk adalah perusahaan BUMN jasa telekomunikasi terbesar yang menyediakan konektivitas seluler (Telkomsel) dan broadband (IndiHome)."
    }
    desc = desc_map.get(ticker_upper, f"{fundamentals.get('name', 'Perusahaan Tercatat IDX')} adalah emiten anggota konstituen indeks LQ45 yang memiliki likuiditas transaksi tinggi dan kinerja keuangan solid.")
    
    overview_text.append(f"  Deskripsi : {desc}\n", style=SNOW_STORM_1)
    overview_text.append(f"  Situs Web : ", style=f"bold {FROST_BLUE}")
    overview_text.append(f"https://www.{ticker_upper.replace('.JK','').lower()}.co.id", style=f"underline {FROST_LIGHT}")
    
    overview_panel = Panel(
        overview_text,
        title="COMPANY OVERVIEW",
        border_style=FROST_BLUE,
        padding=(0, 1)
    )
    
    inspect_left = inspect_top["inspect_left"]
    inspect_center = inspect_top["inspect_center"]
    inspect_right = inspect_top["inspect_right"]
    
    inspect_left.update(left_panel)
    inspect_center.update(center_panel)
    inspect_right.update(right_panel)
    grid["inspect_bottom"].update(overview_panel)
    
    return grid
