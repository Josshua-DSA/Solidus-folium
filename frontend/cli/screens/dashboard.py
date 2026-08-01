import sys
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from frontend.cli.theme import FROST_BLUE, FROST_LIGHT, SNOW_STORM_1

def draw_dashboard(db_empty: bool, db_path: str, available_tickers: list, has_backend: bool) -> Layout:
    """Draws the system dashboard screen."""
    grid = Layout()
    grid.split_row(
        Layout(name="left_panel", ratio=1),
        Layout(name="right_panel", ratio=1)
    )
    
    # Left Panel: System Diagnostics
    diag_table = Table(show_header=False, box=None)
    diag_table.add_column("Key", style=f"bold {FROST_LIGHT}")
    diag_table.add_column("Value", style=SNOW_STORM_1)
    
    diag_table.add_row("Database Engine", "SQLite3 (Local Storage)")
    diag_table.add_row("Database Path", db_path)
    diag_table.add_row("DB Price Records", "0 records" if db_empty else f"{len(available_tickers)} tickers sync'd")
    diag_table.add_row("Active Universe", "LQ45 (Indo Blue-chips)")
    diag_table.add_row("Cache Directory", ".cache/")
    diag_table.add_row("Python Version", sys.version.split()[0])
    diag_table.add_row("Backend Integr.", "[green]CONNECTED[/green]" if has_backend else "[yellow]STUB (MOCK)[/yellow]")
    
    left_panel = Panel(
        diag_table,
        title="SYSTEM DIAGNOSTICS & HARDWARE",
        border_style=FROST_BLUE,
        padding=(1, 2)
    )
    
    # Right Panel: ML Ensemble Architecture
    ml_table = Table(show_header=False, box=None)
    ml_table.add_column("Key", style=f"bold {FROST_LIGHT}")
    ml_table.add_column("Value", style=SNOW_STORM_1)
    
    ml_table.add_row("Primary Model", "LSTM Sequence Classifier")
    ml_table.add_row("Secondary Model", "XGBoost Log-Returns Classifier")
    ml_table.add_row("Ensemble Method", "Weighted Confidence Score")
    ml_table.add_row("LSTM Checkpoint", "outputs/models/best_lstm.pt")
    ml_table.add_row("XGBoost Champion", "outputs/models/global_xgb_champion.json")
    ml_table.add_row("Walk-Forward Train Size", "504 days (2 Years)")
    ml_table.add_row("Walk-Forward Test Size", "126 days (6 Months)")
    ml_table.add_row("TBL Horizon Barrier", "5 Days / ±3.0% (Profit/Loss)")
    
    right_panel = Panel(
        ml_table,
        title="QUANT ARCHITECTURE & STRATEGY PARAMS",
        border_style=FROST_BLUE,
        padding=(1, 2)
    )
    
    grid["left_panel"].update(left_panel)
    grid["right_panel"].update(right_panel)
    return grid
