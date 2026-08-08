"""
QUANT TRADING IDX v7 — CLI Entry Point & DI Orchestrator
Menggunakan Typer untuk command-line interface.

Satu-satunya tempat yang boleh import dari semua package.
Bertindak sebagai Dependency Injection orchestrator.

Usage:
    python cli.py fetch          — Download & simpan data ke SQLite
    python cli.py clean          — Jalankan pipeline DataCleaner
    python cli.py features       — Build fitur teknikal
    python cli.py backtest       — Jalankan backtest (momentum / ml_signal)
    python cli.py status         — Cek status database & pipeline
    python cli.py health         — Cek konektivitas API eksternal
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
    from pipeline.universe import UniverseManager
    from pipeline.fetcher import DataFetcher
    from pipeline.storage import StorageManager

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
    from pipeline.storage import StorageManager
    from pipeline.data_cleaner import DataCleaner

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
    from pipeline.storage import StorageManager
    from pipeline.data_cleaner import DataCleaner
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
    strategy: str = typer.Option("momentum", help="Strategy: momentum, ml_signal"),
    fast_window: int = typer.Option(5, help="Momentum fast window"),
    slow_window: int = typer.Option(20, help="Momentum slow window"),
):
    """Jalankan backtest menggunakan BacktestService."""
    from app.services.backtest_service import BacktestService
    from app.services.data_service import DataService

    console.print(f"[bold cyan]Running backtest: strategy={strategy}[/bold cyan]")
    console.print(f"  Initial capital: Rp{capital:,.0f}")

    data_service = DataService()
    if not data_service.is_db_populated():
        console.print("[yellow]Database kosong. Jalankan 'fetch' terlebih dahulu.[/yellow]")
        raise typer.Exit(1)

    bs = BacktestService(
        data_service=data_service,
        initial_capital=capital,
    )

    if strategy == "momentum":
        console.print(f"  Strategy: Momentum (fast={fast_window}, slow={slow_window})")
        result = bs.run_momentum_backtest(
            fast_window=fast_window,
            slow_window=slow_window,
        )
    elif strategy == "ml_signal":
        console.print("  Strategy: ML Signal (requires trained model predictions)")
        console.print("[yellow]⚠ ML predictions belum tersedia. Gunakan 'momentum'.[/yellow]")
        raise typer.Exit(1)
    else:
        console.print(f"[red]Unknown strategy: {strategy}[/red]")
        raise typer.Exit(1)

    if "error" in result:
        console.print(f"[red]✗ {result['error']}[/red]")
        raise typer.Exit(1)

    # Print results
    metrics = result.get("metrics", {})
    console.print("\n[bold green]═══ Backtest Results ═══[/bold green]")
    console.print(f"  Total Return:    {metrics.get('total_return', 0):.2%}")
    console.print(f"  CAGR:            {metrics.get('cagr', 0):.2%}")
    console.print(f"  Sharpe Ratio:    {metrics.get('sharpe_ratio', 0):.2f}")
    console.print(f"  Sortino Ratio:   {metrics.get('sortino_ratio', 0):.2f}")
    console.print(f"  Max Drawdown:    {metrics.get('max_drawdown', 0):.2%}")
    console.print(f"  Calmar Ratio:    {metrics.get('calmar_ratio', 0):.2f}")
    console.print(f"  J-value:         {metrics.get('j_value', 0):.4f}")
    console.print(f"  Win Rate:        {metrics.get('win_rate', 0):.2%}")
    console.print(f"  Profit Factor:   {metrics.get('profit_factor', 0):.2f}")
    console.print(f"  Total Trades:    {metrics.get('n_trades', 0)}")
    console.print(f"  Final NAV:       Rp{metrics.get('final_nav', 0):,.0f}")
    console.print("[green]✓ Backtest selesai[/green]")


@app.command()
def status():
    """Cek status database dan pipeline."""
    from app.services.data_service import DataService

    console.print("[bold cyan]System Status[/bold cyan]")
    console.print("=" * 50)

    try:
        ds = DataService()
        info = ds.get_db_status()

        console.print(f"  Database:     {info['db_path']}")
        console.print(f"  Tickers:      {info['n_tickers']}")
        console.print(f"  Date range:   {info['date_start']} → {info['date_end']}")
        console.print(f"  Populated:    {info['is_populated']}")
        console.print("[green]✓ Database OK[/green]")
    except Exception as e:
        console.print(f"  [red]✗ Database error: {e}[/red]")


@app.command()
def health():
    """Cek konektivitas API eksternal (yfinance, ccxt)."""
    import importlib

    console.print("[bold cyan]Running health checks...[/bold cyan]")
    console.print("=" * 50)

    # 1. yfinance
    try:
        import yfinance as yf
        test = yf.Ticker("BBCA.JK")
        info = test.fast_info
        console.print(f"  [green]✓ yfinance: OK (BBCA.JK accessible)[/green]")
    except Exception as e:
        console.print(f"  [red]✗ yfinance: {e}[/red]")

    # 2. SQLite database
    try:
        from pipeline.storage import StorageManager
        sm = StorageManager()
        tickers = sm.get_available_tickers()
        console.print(f"  [green]✓ SQLite: OK ({len(tickers)} tickers)[/green]")
    except Exception as e:
        console.print(f"  [red]✗ SQLite: {e}[/red]")

    # 3. ccxt (optional)
    try:
        importlib.import_module("ccxt")
        console.print("  [green]✓ ccxt: installed[/green]")
    except ImportError:
        console.print("  [yellow]⚠ ccxt: not installed (crypto features disabled)[/yellow]")

    # 4. Key dependencies
    for pkg in ["numpy", "pandas", "sklearn", "xgboost", "lightgbm"]:
        try:
            importlib.import_module(pkg)
            console.print(f"  [green]✓ {pkg}: OK[/green]")
        except ImportError:
            console.print(f"  [red]✗ {pkg}: not installed[/red]")

    console.print("\n[green]✓ Health check selesai[/green]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
