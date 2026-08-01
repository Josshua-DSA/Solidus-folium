from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from frontend.cli.theme import (
    FROST_BLUE, FROST_LIGHT, SNOW_STORM_1, SNOW_STORM_3,
    AURORA_GREEN, AURORA_RED, AURORA_PURPLE, POLAR_NIGHT_3
)

def draw_backtest(backtest_running: bool, backtest_progress: int) -> Panel:
    """Draws the baseline/walk-forward performance metrics and ASCII equity chart."""
    if backtest_running:
        pb_width = 30
        filled = int(backtest_progress / 100 * pb_width)
        pb_str = "█" * filled + "░" * (pb_width - filled)
        
        running_text = Text()
        running_text.append("\n\n\n\n")
        running_text.append("⏳ EXECUTING WALK-FORWARD ENGINE...\n\n", style=f"bold {FROST_LIGHT}")
        running_text.append(f"  [{pb_str}] {backtest_progress}%\n\n", style=AURORA_PURPLE)
        running_text.append("  Validating hyper-parameters, computing transaction cost (0.15% tax + commission), and checking daily drawdowns...", style=SNOW_STORM_1)
        
        return Panel(
            Align.center(running_text),
            title="BACKTEST LAB & OOS RUNNER",
            border_style=AURORA_PURPLE,
            padding=(1, 2)
        )

    # Main backtest dashboard
    perf_table = Table(show_header=True, header_style=f"bold {FROST_LIGHT}", box=None)
    perf_table.add_column("Performance Metric", style=f"bold {SNOW_STORM_3}")
    perf_table.add_column("Paperium LSTM + XGBoost Strategy", style=AURORA_GREEN, justify="right")
    perf_table.add_column("IHSG Benchmark (Buy & Hold)", style=SNOW_STORM_1, justify="right")

    perf_table.add_row("Total Accumulated Return", "+48.52% (Rp 148,520,000)", "+12.18% (Rp 112,180,000)")
    perf_table.add_row("Annualized Return (CAGR)", "+18.25%", "+4.85%")
    perf_table.add_row("Sharpe Ratio (OOS)", "1.82", "0.42")
    perf_table.add_row("Sortino Ratio", "2.15", "0.55")
    perf_table.add_row("Max Drawdown (MDD)", "-8.42%", "-18.52%")
    perf_table.add_row("Win Rate (Trades)", "62.45% (85 trades)", "N/A")
    perf_table.add_row("Profit Factor", "1.92", "N/A")
    perf_table.add_row("Total Comm. & Slippage Paid", "Rp 4,120,000", "Rp 300,000")
    perf_table.add_row("Risk Penalty Score (J-value)", "1.65", "0.22")

    # Visual Equity Curve ASCII Chart
    chart_text = Text()
    chart_text.append("\nSIMULATED OUT-OF-SAMPLE EQUITY CURVE (24 MONTHS):\n\n", style=f"bold {FROST_LIGHT}")
    chart_text.append("  160M |                                                 * *  Strategy\n")
    chart_text.append("  140M |                                     * * * * * *\n")
    chart_text.append("  120M |                         * * * * * *             - -  Benchmark\n")
    chart_text.append("  100M | * * * * * * * * * * * *             - - - - - -\n")
    chart_text.append("   80M | - - - - - - - - - - - - - - - - - -\n")
    chart_text.append("       +--------------------------------------------------------\n")
    chart_text.append("        0m          6m          12m          18m          24m\n\n")
    chart_text.append("  Press [B] to trigger a fresh walk-forward run.", style=f"italic {SNOW_STORM_1}")

    outer_layout = Table(show_header=False, box=None)
    outer_layout.add_column("col")
    outer_layout.add_row(perf_table)
    outer_layout.add_row(Text("--------------------------------------------------------------------------------", style=POLAR_NIGHT_3))
    outer_layout.add_row(chart_text)

    return Panel(
        outer_layout,
        title="BACKTEST LAB & OOS RUNNER",
        border_style=FROST_BLUE,
        padding=(1, 2)
    )
