"""
FOLIUM TERMINAL — CLI Entry Point & DI Orchestrator
Menggunakan Typer untuk command-line interface.

Usage:
    folium fetch          — Download & simpan data ke SQLite
    folium clean          — Jalankan pipeline DataCleaner
    folium features       — Build fitur teknikal
    folium backtest       — Jalankan backtest (momentum / ml_signal)
    folium status         — Cek status database & pipeline
    folium health         — Cek konektivitas API eksternal
    folium train          — Latih model ML di background
    folium models         — Kelola Model Registry (list/compare/promote)
    folium scheduler      — Sinkronisasi data otomatis jam bursa
"""
import typer
from typing import Optional
from rich.console import Console

console = Console()
app = typer.Typer(
    name="folium",
    help="🍃 Folium Quantitative Terminal — Bloomberg-style Trading Platform for IDX",
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
def train(
    model_type: str = typer.Option("xgboost", help="Model type: xgboost, lightgbm, ensemble, autoencoder"),
    use_optuna: bool = typer.Option(False, help="Gunakan Optuna untuk hyperparameter tuning"),
    n_trials: int = typer.Option(20, help="Jumlah trial Optuna jika use_optuna=True"),
):
    """Latih model Machine Learning (Fase 3) dari data di database."""
    from pipeline.storage import StorageManager
    from pipeline.data_cleaner import DataCleaner
    from shared.features.feature_builder import FeatureBuilder
    from model.trainer import ModelTrainer, TrainingConfig
    import numpy as np
    import pandas as pd

    console.print(f"[bold cyan]Running Model Training: model_type={model_type}...[/bold cyan]")

    storage = StorageManager()
    if not storage.get_available_tickers():
        console.print("[yellow]Database kosong. Jalankan 'fetch' terlebih dahulu.[/yellow]")
        raise typer.Exit(1)

    cleaner = DataCleaner()
    fb = FeatureBuilder()

    close_prices = storage.load_close_prices()
    cleaned = cleaner.clean(close_prices)

    console.print("  → Building technical features & labels...")
    features_dict = fb.build_features(cleaned)

    # Combined dataset setup (multi-feature matrix per ticker)
    feature_matrices = []
    labels_list = []
    
    ret = cleaned.pct_change().shift(-1)
    
    for ticker in cleaned.columns:
        ohlc = pd.DataFrame({
            "open": cleaned[ticker],
            "high": cleaned[ticker] * 1.002,
            "low": cleaned[ticker] * 0.998,
            "close": cleaned[ticker],
            "volume": 1000000
        })
        tf = fb.build_technical_features(ohlc).dropna()
        lbl = np.where(ret[ticker].loc[tf.index] > 0.005, 1, np.where(ret[ticker].loc[tf.index] < -0.005, -1, 0))
        
        feature_matrices.append(tf.values)
        labels_list.append(lbl)
        
    X = np.vstack(feature_matrices)
    y = np.concatenate(labels_list)
    
    # Alignment map for labels (-1, 0, 1) -> (0, 1, 2)
    if -1 in y:
        y = y + 1
        
    feat_names = list(fb.build_technical_features(pd.DataFrame({
        "open": cleaned.iloc[:, 0], "high": cleaned.iloc[:, 0], "low": cleaned.iloc[:, 0], "close": cleaned.iloc[:, 0], "volume": 1000000
    })).dropna().columns)

    console.print(f"  → Prepared dataset: X={X.shape}, y={y.shape}")

    # Sample last 10,000 rows for fast training
    X = X[-10000:]
    y = y[-10000:]

    config = TrainingConfig(
        model_type=model_type,
        use_optuna=use_optuna,
        optuna_n_trials=n_trials,
        train_size=3000,
        test_size=1000,
        step=3000,
        max_folds=2,
    )
    trainer = ModelTrainer(config=config)

    console.print("  → Starting Walk-Forward Validation & Training...")
    results = trainer.train(X, y, feature_names=feat_names)

    console.print("\n[bold green]═══ Training Completed ═══[/bold green]")
    metrics = results.get("aggregate_metrics", {})
    for k, v in metrics.items():
        if isinstance(v, float):
            console.print(f"  {k:<20}: {v:.4f}")
        else:
            console.print(f"  {k:<20}: {v}")

    console.print(f"  Artifacts saved to: {config.artifact_dir}")
    console.print("[green]✓ Training model selesai[/green]")
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


@app.command()
def models(
    action: str = typer.Argument("list", help="Action: list, compare, promote, archive"),
    version_id: Optional[str] = typer.Argument(None, help="Version ID (untuk promote/archive)"),
    model_type: Optional[str] = typer.Option(None, help="Filter berdasarkan tipe model"),
):
    """Kelola Model Registry: list, compare, promote, archive model ML."""
    from model.registry import ModelRegistry

    registry = ModelRegistry()

    if action == "list":
        versions = registry.list_versions(model_type=model_type)
        if not versions:
            console.print("[yellow]Belum ada model terdaftar di registry.[/yellow]")
            return

        from rich.table import Table
        table = Table(title="📦 Model Registry", border_style="#88C0D0", show_lines=True)
        table.add_column("Version ID", style="bold #88C0D0")
        table.add_column("Type", style="#81A1C1")
        table.add_column("Stage", style="bold")
        table.add_column("Accuracy", justify="right")
        table.add_column("F1 Macro", justify="right")
        table.add_column("AUC OVR", justify="right")
        table.add_column("Created At", style="dim")

        for mv in versions:
            stage_style = {"production": "[bold green]🟢 PRODUCTION[/bold green]",
                           "staging": "[yellow]🟡 STAGING[/yellow]",
                           "archived": "[dim]⚪ ARCHIVED[/dim]"}.get(mv.stage, mv.stage)
            table.add_row(
                mv.version_id,
                mv.model_type,
                stage_style,
                f"{mv.metrics.get('accuracy', 0):.4f}",
                f"{mv.metrics.get('f1_macro', 0):.4f}",
                f"{mv.metrics.get('auc_ovr', 0):.4f}",
                mv.created_at,
            )
        console.print(table)

    elif action == "compare":
        rows = registry.compare(model_type=model_type)
        if not rows:
            console.print("[yellow]Belum ada model untuk dibandingkan.[/yellow]")
            return

        from rich.table import Table
        table = Table(title="📊 Model Comparison (Sorted by F1-Macro)", border_style="#88C0D0", show_lines=True)
        table.add_column("#", style="bold", justify="right")
        table.add_column("Version ID", style="bold #88C0D0")
        table.add_column("Stage")
        table.add_column("Accuracy", justify="right")
        table.add_column("F1 Macro", justify="right", style="bold #A3BE8C")
        table.add_column("AUC OVR", justify="right")
        table.add_column("Log Loss", justify="right")

        for i, r in enumerate(rows, 1):
            stage_icon = {"production": "🟢", "staging": "🟡", "archived": "⚪"}.get(r["stage"], "")
            table.add_row(
                str(i),
                r["version_id"],
                f"{stage_icon} {r['stage']}",
                f"{r['accuracy']:.4f}",
                f"{r['f1_macro']:.4f}",
                f"{r['auc_ovr']:.4f}",
                f"{r['log_loss']:.4f}",
            )
        console.print(table)

    elif action == "promote":
        if not version_id:
            console.print("[red]Berikan version_id untuk di-promote. Contoh: python main.py models promote xgboost_v001[/red]")
            raise typer.Exit(1)
        mv = registry.promote(version_id)
        console.print(f"[bold green]✓ {mv.version_id} dipromosikan ke PRODUCTION[/bold green]")

    elif action == "archive":
        if not version_id:
            console.print("[red]Berikan version_id untuk di-archive.[/red]")
            raise typer.Exit(1)
        registry.archive(version_id)
        console.print(f"[bold yellow]✓ {version_id} di-archive[/bold yellow]")

    else:
        console.print(f"[red]Unknown action: {action}. Gunakan: list, compare, promote, archive[/red]")


@app.command()
def scheduler(
    action: str = typer.Argument("status", help="Action: start, stop, status, once"),
    universe: str = typer.Option("lq45", help="Universe ticker"),
    daily_interval: int = typer.Option(60, help="Daily fetch interval (menit)"),
    intraday_interval: int = typer.Option(15, help="Intraday fetch interval (menit)"),
    force: bool = typer.Option(False, help="Paksa eksekusi (abaikan jam bursa)"),
):
    """
    Background Data Scheduler — sinkronisasi data otomatis saat jam bursa IDX.

    Actions:
        status  — Tampilkan status scheduler & jam bursa.
        start   — Jalankan scheduler di background thread.
        once    — Jalankan satu siklus fetch + clean (sinkron).
    """
    from pipeline.scheduler import DataScheduler, SchedulerConfig
    from rich.table import Table
    from datetime import datetime
    from zoneinfo import ZoneInfo

    WIB = ZoneInfo("Asia/Jakarta")
    now = datetime.now(WIB)

    config = SchedulerConfig(
        universe=universe,
        daily_fetch_interval_minutes=daily_interval,
        intraday_interval_minutes=intraday_interval,
    )

    def on_event(event):
        icon = "✓" if event.status == "completed" else "⚠" if event.status == "failed" else "→"
        console.print(f"  [{event.timestamp}] {icon} {event.task}: {event.message}")

    sched = DataScheduler(config=config, on_event=on_event)

    if action == "status":
        is_trading = sched._is_trading_hours(now)
        next_open = sched.next_trading_window(now)

        table = Table(title="📡 Data Scheduler Status", border_style="cyan")
        table.add_column("Parameter", style="bold")
        table.add_column("Value", style="green")

        table.add_row("Waktu Sekarang (WIB)", now.strftime("%A, %d %B %Y %H:%M:%S"))
        table.add_row("Jam Bursa IDX", "🟢 AKTIF (09:00-16:00)" if is_trading else "🔴 TUTUP")
        table.add_row("Sesi Bursa Berikutnya", next_open.strftime("%A %d %b %H:%M WIB") if not is_trading else "Sedang berjalan")
        table.add_row("Universe", config.universe.upper())
        table.add_row("Daily Fetch Interval", f"{config.daily_fetch_interval_minutes} menit")
        table.add_row("Intraday Fetch Interval", f"{config.intraday_interval_minutes} menit")
        table.add_row("Auto-Clean", "✓ Enabled" if config.auto_clean else "✗ Disabled")

        console.print(table)

    elif action == "once":
        console.print("[bold cyan]🔄 Menjalankan satu siklus fetch + clean...[/bold cyan]")
        results = sched.run_once(force=force)

        if results.get("skipped"):
            console.print(f"[yellow]⏸ Skipped: {results['reason']}[/yellow]")
            console.print("[dim]Gunakan --force untuk paksa eksekusi di luar jam bursa.[/dim]")
        else:
            for task_result in results.get("tasks", []):
                status_icon = "✓" if task_result["status"] == "completed" else "✗"
                console.print(f"  {status_icon} {task_result['task']}: {task_result['status']}")
            console.print("[green]✓ Siklus scheduler selesai.[/green]")

    elif action == "start":
        console.print("[bold cyan]🚀 Starting Background Data Scheduler...[/bold cyan]")
        console.print(f"  Universe     : {config.universe.upper()}")
        console.print(f"  Daily Fetch  : setiap {config.daily_fetch_interval_minutes} menit")
        console.print(f"  Intraday     : setiap {config.intraday_interval_minutes} menit")
        console.print(f"  Auto-Clean   : {'✓' if config.auto_clean else '✗'}")
        console.print("\n[dim]Tekan Ctrl+C untuk menghentikan scheduler.[/dim]\n")

        sched.start_background()

        try:
            while sched.is_running():
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            sched.stop()
            console.print("\n[yellow]Scheduler dihentikan oleh user.[/yellow]")

    else:
        console.print(f"[red]Unknown action: {action}. Gunakan: status, start, once[/red]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
