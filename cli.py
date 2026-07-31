"""
QUANT TRADING IDX v7 — CLI Entry Point
Menggunakan Typer untuk command-line interface.

Usage:
    python cli.py fetch          — Download & simpan data ke SQLite
    python cli.py clean          — Jalankan pipeline DataCleaner
    python cli.py features       — Build fitur teknikal
    python cli.py backtest       — Jalankan backtest baseline
    python cli.py status         — Cek status database & pipeline
"""
import typer
from rich.console import Console

console = Console()
app = typer.Typer(
    name="quant-trading-idx",
    help="QUANT TRADING IDX v7 — Sistem Trading Kuantitatif Bursa Indonesia",
    add_completion=False,
)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command()
def fetch(
    universe: str = typer.Option("lq45", help="Universe: idx_all, lq45, kompas100, custom"),
    start: str = typer.Option("2015-01-01", help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option("2025-12-31", help="End date (YYYY-MM-DD)"),
    cache_days: int = typer.Option(7, help="Cache validity (days)"),
):
    """Download data saham dari yfinance dan simpan ke SQLite."""
    from data_layer.universe import UniverseManager
    from data_layer.fetcher import DataFetcher
    from data_layer.storage import StorageManager

    console.print(f"[bold cyan]Fetching data: universe={universe}, {start} → {end}[/bold cyan]")

    um = UniverseManager(universe_name=universe)
    tickers = um.get_tickers()
    console.print(f"  → {len(tickers)} tickers loaded")

    fetcher = DataFetcher(cache_days=cache_days)
    storage = StorageManager()

    success, failed = 0, 0
    for i, ticker in enumerate(tickers, 1):
        try:
            df = fetcher.fetch_single(ticker, start=start, end=end)
            if df is not None and not df.empty:
                storage.save_prices(ticker, df)
                success += 1
            else:
                failed += 1
        except Exception as e:
            console.print(f"  [red]✗ {ticker}: {e}[/red]")
            failed += 1

        if i % 50 == 0:
            console.print(f"  Progress: {i}/{len(tickers)}")

    console.print(f"\n[green]✓ Done: {success} success, {failed} failed[/green]")


@app.command()
def clean():
    """Jalankan pipeline DataCleaner pada data di database."""
    from data_layer.storage import StorageManager
    from data_layer.data_cleaner import DataCleaner

    console.print("[bold cyan]Running DataCleaner pipeline...[/bold cyan]")

    storage = StorageManager()
    cleaner = DataCleaner()

    close_prices = storage.load_close_prices()
    if close_prices.empty:
        console.print("[yellow]Database kosong. Jalankan 'fetch' terlebih dahulu.[/yellow]")
        raise typer.Exit(1)

    console.print(f"  → Raw data shape: {close_prices.shape}")
    cleaned = cleaner.clean(close_prices)
    console.print(f"  → Cleaned shape:  {cleaned.shape}")
    console.print("[green]✓ DataCleaner selesai[/green]")


@app.command()
def features():
    """Build fitur teknikal dari data bersih."""
    from data_layer.storage import StorageManager
    from data_layer.data_cleaner import DataCleaner
    from shared.features.feature_builder import FeatureBuilder

    console.print("[bold cyan]Building features...[/bold cyan]")

    storage = StorageManager()
    cleaner = DataCleaner()
    fb = FeatureBuilder()

    close_prices = storage.load_close_prices()
    if close_prices.empty:
        console.print("[yellow]Database kosong.[/yellow]")
        raise typer.Exit(1)

    cleaned = cleaner.clean(close_prices)
    feature_dict = fb.build_features(cleaned)

    for name, df in feature_dict.items():
        console.print(f"  → {name}: shape={df.shape}, NaN={df.isna().sum().sum()}")

    console.print("[green]✓ Feature building selesai[/green]")


@app.command()
def backtest(
    capital: float = typer.Option(100_000_000, help="Initial capital (Rp)"),
):
    """Jalankan backtest baseline (equal-weight momentum)."""
    console.print("[bold cyan]Running baseline backtest...[/bold cyan]")
    console.print(f"  Initial capital: Rp{capital:,.0f}")
    console.print("[yellow]⚠ Backtest engine akan diimplementasi penuh di Fase 2[/yellow]")


@app.command()
def status():
    """Cek status database dan pipeline."""
    from data_layer.storage import StorageManager

    console.print("[bold cyan]System Status[/bold cyan]")
    console.print("=" * 50)

    try:
        storage = StorageManager()
        tickers = storage.get_available_tickers()
        date_range = storage.get_date_range()

        console.print(f"  Database:     {storage.db_path}")
        console.print(f"  Tickers:      {len(tickers)}")
        console.print(f"  Date range:   {date_range[0]} → {date_range[1]}")
        console.print(f"  [green]✓ Database OK[/green]")
    except Exception as e:
        console.print(f"  [red]✗ Database error: {e}[/red]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
