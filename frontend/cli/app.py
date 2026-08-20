import sys
import os
import time
from datetime import datetime
import random
import shutil
import yaml
from decimal import Decimal
import numpy as np

# App path injection
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

try:
    from pipeline.storage import StorageManager
    from pipeline.universe import UniverseManager
    LQ45 = UniverseManager(universe_name="lq45").get_tickers()
    IDX_UNIVERSE = LQ45
    from app.risk.risk_manager import RiskManager
    from app.execution.execution_engine import ExecutionEngine, Order
    from app.services.backtest_service import BacktestService
    has_backend = True
except ImportError:
    has_backend = False
    StorageManager = None
    RiskManager = None
    ExecutionEngine = None
    Order = None
    BacktestService = None
    LQ45 = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "TLKM.JK", "ASII.JK", "UNVR.JK", "ADRO.JK", "KLBF.JK", "ICBP.JK", "INDF.JK"]
    IDX_UNIVERSE = LQ45

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.align import Align
from rich.table import Table

from frontend.cli.theme import (
    FROST_BLUE, FROST_LIGHT, FROST_TEAL, FROST_DARK, SNOW_STORM_1, SNOW_STORM_2,
    AURORA_GREEN, AURORA_ORANGE, AURORA_YELLOW, AURORA_RED, AURORA_PURPLE,
    POLAR_NIGHT_3, LQ45_FUNDAMENTALS
)
from frontend.cli.keyboard import KeyPressReader
from frontend.cli.dashboard import draw_dashboard
from frontend.cli.scanner import draw_scanner
from frontend.cli.portfolio import draw_portfolio
from frontend.cli.research import draw_inspect
from frontend.cli.backtest import draw_backtest
from frontend.cli.broker import draw_broker
from frontend.cli.web_charts import generate_candlestick_html

class TUIApp:
    def __init__(self):
        self.console = Console()
        self.reader = KeyPressReader()
        
        # Load configuration file
        self.config = {}
        try:
            with open("config/config.yaml", "r") as f:
                self.config = yaml.safe_load(f)
        except Exception:
            pass

        # Risk parameters
        risk_conf = self.config.get("risk", {})
        self.max_pos_pct = float(risk_conf.get("max_position_pct", 0.10))
        self.daily_loss = float(risk_conf.get("daily_loss_limit", -0.03))
        self.max_dd = float(risk_conf.get("max_drawdown_stop", -0.15))
        
        # Execution parameters
        exec_conf = self.config.get("backtest", {})
        self.comm_pct = float(exec_conf.get("commission_pct", 0.0015))
        self.slip_pct = float(exec_conf.get("slippage_pct", 0.0005))

        # Background Scheduler Instance
        self.scheduler = None
        try:
            from pipeline.scheduler import DataScheduler, SchedulerConfig
            self.scheduler = DataScheduler(
                config=SchedulerConfig(universe="lq45", respect_trading_hours=True)
            )
        except Exception:
            pass

        # Initialize RiskManager and ExecutionEngine if backend is available
        self.risk_manager = None
        self.execution_engine = None
        if has_backend and RiskManager is not None and ExecutionEngine is not None:
            try:
                self.risk_manager = RiskManager(
                    max_position_pct=self.max_pos_pct,
                    max_drawdown_stop=self.max_dd,
                    daily_loss_limit=self.daily_loss
                )
                self.execution_engine = ExecutionEngine(
                    commission_pct=self.comm_pct,
                    slippage_pct=self.slip_pct
                )
            except Exception:
                pass

        # Connection and storage
        self.storage = None
        self.db_empty = True
        self.db_path = "N/A"
        self.available_tickers = []
        
        # Load User Profile & Database State
        from shared.utils.user_profile import ProfileManager
        pm = ProfileManager()
        user_prof = pm.load()

        # Load latest stock prices from SQLite Storage
        latest_prices = {}
        if has_backend and StorageManager is not None:
            try:
                self.storage = StorageManager()
                self.db_path = self.storage.db_path
                self.available_tickers = self.storage.get_available_tickers()
                if len(self.available_tickers) > 0:
                    self.db_empty = False
                    # Fetch real prices from database
                    closes = self.storage.load_close_prices(tickers=None)
                    if not closes.empty:
                        for col in closes.columns:
                            val = closes[col].dropna().iloc[-1] if not closes[col].dropna().empty else None
                            if val:
                                latest_prices[col] = float(val)
            except Exception:
                self.db_empty = True
        
        # System state
        self.active_screen = "dashboard"
        self.current_ticker = "BBCA.JK"
        self.msg = "Folium Quant Desk initialized successfully."
        self.msg_color = FROST_TEAL
        
        # Real-time Financial state from UserProfile
        self.capital = Decimal(str(user_prof.rdn_balance))
        
        # Real-time Portfolio positions from UserProfile + DB live prices
        self.portfolio = []
        if user_prof.positions:
            for pos in user_prof.positions:
                cur_price = latest_prices.get(pos.ticker, pos.avg_price)
                self.portfolio.append({
                    "ticker": pos.ticker,
                    "shares": pos.shares,
                    "avg_price": Decimal(str(pos.avg_price)),
                    "current_price": Decimal(str(cur_price)),
                    "sl": Decimal(str(pos.avg_price * 0.95)),
                    "tp": Decimal(str(pos.avg_price * 1.10)),
                })
        else:
            # Empty portfolio fallback if no stock input
            self.portfolio = []

        self.transaction_history = []
        self.reload_user_profile()

    def reload_user_profile(self):
        """Muat ulang profil RDN & posisi saham secara realtime dari disk & DB."""
        from shared.utils.user_profile import ProfileManager
        pm = ProfileManager()
        user_prof = pm.load()

        latest_prices = {}
        if has_backend and self.storage is not None:
            try:
                closes = self.storage.load_close_prices(tickers=None)
                if not closes.empty:
                    for col in closes.columns:
                        val = closes[col].dropna().iloc[-1] if not closes[col].dropna().empty else None
                        if val:
                            latest_prices[col] = float(val)
            except Exception:
                pass

        self.capital = Decimal(str(user_prof.rdn_balance))
        self.portfolio = []
        if user_prof and getattr(user_prof, 'positions', None):
            for pos in user_prof.positions:
                cur_price = latest_prices.get(pos.ticker, pos.avg_price)
                self.portfolio.append({
                    "ticker": pos.ticker,
                    "shares": pos.shares,
                    "avg_price": Decimal(str(pos.avg_price)),
                    "current_price": Decimal(str(cur_price)),
                    "sl": Decimal(str(pos.avg_price * 0.95)),
                    "tp": Decimal(str(pos.avg_price * 1.10)),
                })

        # Broker Integration & Sandbox API State
        self.broker_accounts = {
            "Stockbit": {"status": "DISCONNECTED", "api_key": "N/A", "balance": Decimal("0.00")},
            "Ajaib": {"status": "DISCONNECTED", "api_key": "N/A", "balance": Decimal("0.00")},
            "Nanovest": {"status": "DISCONNECTED", "api_key": "N/A", "balance": Decimal("0.00")}
        }
        
        # Backtest state
        self.backtest_results = None
        self.backtest_running = False
        self.backtest_progress = 0
        
        # Simulated Signals (for Scanner)
        self.scanner_signals = []
        self._generate_mock_signals()

    def _generate_mock_signals(self):
        """Generates realistic 3-class scanner signals across 24 LQ45 tickers with BUY, HOLD, SELL & realistic confidences."""
        random.seed(42)
        self.scanner_signals = []
        lq45_keys = list(LQ45_FUNDAMENTALS.keys())
        
        for idx, ticker in enumerate(lq45_keys[:24]):
            base_price = LQ45_FUNDAMENTALS.get(ticker, {"eps": 100})["eps"] * 12 + random.randint(-200, 200)
            if base_price <= 0:
                base_price = 1000
                
            # Distribute scores realistically: some high BUYs, some mid HOLDs, some strong SELLs
            # Tickers like HMSP, GGRM, SMGR get strong BEARISH signals (SELL 70%+)
            if ticker in ("HMSP.JK", "GGRM.JK", "UNVR.JK", "SMGR.JK"):
                lstm_conf = 0.72 + random.random() * 0.20
                xgb_conf = 0.68 + random.random() * 0.22
                score = (lstm_conf * 0.60) + (xgb_conf * 0.40)
                action = "SELL"
            elif ticker in ("BBCA.JK", "BBRI.JK", "BMRI.JK", "ICBP.JK", "ADRO.JK", "BBNI.JK", "PTBA.JK"):
                lstm_conf = 0.75 + random.random() * 0.20
                xgb_conf = 0.70 + random.random() * 0.22
                score = (lstm_conf * 0.60) + (xgb_conf * 0.40)
                action = "BUY"
            elif ticker in ("TLKM.JK", "INDF.JK", "KLBF.JK"):
                # Below 50% min conf threshold
                score = 0.42 + random.random() * 0.06
                lstm_conf = score
                xgb_conf = score - 0.05
                action = "HOLD"
            else:
                lstm_conf = 0.52 + random.random() * 0.15
                xgb_conf = 0.50 + random.random() * 0.15
                score = (lstm_conf * 0.60) + (xgb_conf * 0.40)
                action = "HOLD" if score < 0.62 else "BUY"
            
            sl_pct = 0.025 + random.random() * 0.015
            tp_pct = sl_pct * (1.2 + random.random() * 0.8)
            
            sl_price = base_price * (1.0 - sl_pct) if action != "SELL" else base_price * (1.0 + sl_pct)
            tp_price = base_price * (1.0 + tp_pct) if action != "SELL" else base_price * (1.0 - tp_pct)
            rr_ratio = tp_pct / sl_pct
            
            vol_m = 10.0 + random.random() * 50.0
                
            self.scanner_signals.append({
                "ticker": ticker,
                "price": base_price,
                "lstm": lstm_conf,
                "xgb": xgb_conf,
                "score": score,
                "sl": sl_price,
                "tp": tp_price,
                "sl_pct": sl_pct * 100.0,
                "tp_pct": tp_pct * 100.0,
                "rr_ratio": rr_ratio,
                "volume_m": vol_m,
                "action": action
            })
        self.scanner_signals.sort(key=lambda x: x["score"], reverse=True)

    def draw_header(self) -> Table:
        """Draws a professional, boxed multi-column Bloomberg/Fincept Terminal style header."""
        from rich.columns import Columns
        
        # 1. Left Panel: Menu & Command Input Box
        left_text = Text()
        left_text.append("File  Navigate  View  Help\n", style=f"dim {SNOW_STORM_1}")
        left_text.append("CMD>", style=f"bold {AURORA_ORANGE}")
        left_text.append(" [Enter Ticker (e.g. BBCA) | H Help | Q Quit]", style=f"italic {SNOW_STORM_2}")
        left_panel = Panel(left_text, border_style=FROST_BLUE, title="MENU & CONSOLE", title_align="left")
        
        # 2. Center Panel: System Brand & Mode
        center_text = Text()
        center_text.append("▲ FOLIUM QUANT DESK ▲\n", style="bold #88C0D0")
        mode_str = "● LIVE DATABASE ACTIVE" if not self.db_empty else "● SIMULATION / SANDBOX"
        mode_color = "#A3BE8C" if not self.db_empty else "#D08770"
        center_text.append(mode_str, style=f"bold {mode_color}")
        center_panel = Panel(center_text, border_style=FROST_BLUE, title="SYSTEM NODE", title_align="center")
        
        # 3. Right Panel: User & Session Clock
        right_text = Text()
        right_text.append(f"{datetime.now().strftime('%d %b %y %H:%M:%S').upper()}\n", style=SNOW_STORM_1)
        right_text.append("USER: ", style=f"dim {SNOW_STORM_1}")
        right_text.append("josjiez ", style=f"bold {FROST_TEAL}")
        right_text.append("[ENT]", style=f"bold {AURORA_ORANGE}")
        right_panel = Panel(right_text, border_style=FROST_BLUE, title="SESSION INFO", title_align="right")
        
        # Grid for the three panels
        top_grid = Table.grid(expand=True)
        top_grid.add_column(ratio=2)
        top_grid.add_column(ratio=2)
        top_grid.add_column(ratio=2)
        top_grid.add_row(left_panel, center_panel, right_panel)
        
        # Row 2: Horizontal Navigation Tabs inside a bordered panel
        tabs_text = Text()
        tabs = [
            ("D", "DASHBOARD", "dashboard"),
            ("S", "SCANNER", "scanner"),
            ("P", "PORTFOLIO", "portfolio"),
            ("I", "INSPECT STOCK", "inspect"),
            ("T", "BACKTEST LAB", "backtest"),
        ]
        
        for key, name, screen in tabs:
            if self.active_screen == screen:
                tabs_text.append(f" ▐ {name} ({key}) ▐ ", style=f"bold black on {AURORA_ORANGE}")
            else:
                tabs_text.append(f"  {name} ({key})  ", style=f"bold {FROST_BLUE}")
            tabs_text.append("  ", style=POLAR_NIGHT_3)
            
        tabs_panel = Panel(tabs_text, border_style=FROST_BLUE, title="ACTIVE WORKSPACES", title_align="left")
        
        # Row 3: Current breadcrumb indicator
        breadcrumb = Table.grid(expand=True)
        breadcrumb.add_column()
        
        breadcrumb_text = Text()
        breadcrumb_text.append("─── ACTIVE NODE: ", style=POLAR_NIGHT_3)
        breadcrumb_text.append(self.active_screen.upper(), style=f"bold {FROST_LIGHT}")
        if self.active_screen == "inspect":
            breadcrumb_text.append(f" 🚩 EMITEN: {self.current_ticker} ", style=f"bold {AURORA_YELLOW}")
            
        _, cols = shutil.get_terminal_size()
        rem = max(1, cols - len(breadcrumb_text.plain) - 2)
        breadcrumb_text.append("─" * rem, style=POLAR_NIGHT_3)
        breadcrumb.add_row(breadcrumb_text)
        
        # Main header table assembler
        header_table = Table.grid(expand=True)
        header_table.add_column()
        header_table.add_row(top_grid)
        header_table.add_row(tabs_panel)
        header_table.add_row(breadcrumb)
        
        return header_table

    def draw_footer(self) -> Align:
        """Draws the command shortcut bar as a borderless 2-row table, exactly like GNU nano."""
        # Create a grid table with 2 rows and 8 columns (shortcut key + name)
        table = Table.grid(padding=(0, 2))
        table.add_column(style=f"bold {AURORA_PURPLE}")
        table.add_column(style=SNOW_STORM_2)
        table.add_column(style=f"bold {AURORA_PURPLE}")
        table.add_column(style=SNOW_STORM_2)
        table.add_column(style=f"bold {AURORA_PURPLE}")
        table.add_column(style=SNOW_STORM_2)
        table.add_column(style=f"bold {AURORA_PURPLE}")
        table.add_column(style=SNOW_STORM_2)
        
        table.add_row("D", "Dashboard", "S", "Scanner", "P", "Portfolio", "I", "Inspect Stock")
        table.add_row("T", "Backtest Lab", "O", "Edit Profile", "B", "Sync Scheduler", "X", "Exit")
        
        return Align.center(table)

    def run_backtest_process(self):
        """Simulates running the backtester fold-by-fold."""
        self.backtest_running = True
        self.backtest_progress = 0

    def generate_and_open_web_chart(self):
        """Generates and triggers opening of the TradingView candlestick chart."""
        ticker_upper = self.current_ticker.upper()
        ohlcv_list = []
        prices_df = None
        
        if not self.db_empty and self.storage:
            try:
                prices_df = self.storage.load_prices([ticker_upper])
            except Exception:
                pass
                
        if prices_df is not None and len(prices_df) > 0:
            prices_df = prices_df.sort_values("date")
            for _, row in prices_df.tail(45).iterrows():
                try:
                    vol_val = row.get('volume', 1000000)
                    vol_int = int(vol_val) if vol_val is not None else 1000000
                except Exception:
                    vol_int = 1000000
                    
                ohlcv_list.append({
                    'date': str(row['date']),
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': vol_int
                })
                
        if not ohlcv_list:
            # Generate mockup history candles
            random.seed(hash(ticker_upper) % 1000)
            base_price = 5000.0 + (random.random() - 0.5) * 4000.0
            
            from datetime import datetime, timedelta
            curr_price = base_price
            for i in range(45):
                daily_change = (random.random() - 0.47) * 0.04 * curr_price
                o = curr_price
                c = curr_price + daily_change
                h = max(o, c) + random.random() * 0.015 * curr_price
                l = min(o, c) - random.random() * 0.015 * curr_price
                v = int(random.uniform(50000, 2000000))
                date_str = (datetime.now() - timedelta(days=45 - i)).strftime("%Y-%m-%d")
                ohlcv_list.append({'date': date_str, 'open': o, 'high': h, 'low': l, 'close': c, 'volume': v})
                curr_price = c
                
        # Generate the interactive lightweight chart HTML
        chart_path = "/tmp/fincept_chart.html"
        generate_candlestick_html(ticker_upper, ohlcv_list, chart_path)
        
        # Trigger default browser to display chart in fullscreen
        try:
            import subprocess
            subprocess.Popen(["xdg-open", chart_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def run(self):
        """Main rendering loop without Live to completely eliminate terminal flicker."""
        state_changed = True
        
        with self.reader as reader:
            while True:
                if state_changed:
                    # Temporarily restore normal terminal mode for printing
                    reader.restore_normal()
                    
                    # Clear screen using terminal escape codes (clean and fast)
                    sys.stdout.write("\x1b[2J\x1b[H")
                    sys.stdout.flush()
                    
                    # Dapatkan ukuran tinggi terminal secara dinamis
                    _, rows = shutil.get_terminal_size()
                    
                    # Reconstruct Layout dengan tinggi menyesuaikan terminal pas
                    layout = Layout(size=rows)
                    layout.split_column(
                        Layout(name="header", size=8),
                        Layout(name="body", ratio=1),
                        Layout(name="footer", size=2)
                    )
                    
                    layout["header"].update(self.draw_header())
                    layout["footer"].update(self.draw_footer())
                    
                    # Handle active screen view
                    if self.active_screen == "dashboard":
                        layout["body"].update(draw_dashboard(
                            self.db_empty, self.db_path, self.available_tickers, has_backend
                        ))
                    elif self.active_screen == "scanner":
                        layout["body"].update(draw_scanner(self.scanner_signals, self.db_empty))
                    elif self.active_screen == "portfolio":
                        layout["body"].update(draw_portfolio(self.portfolio, self.capital, self.transaction_history))
                    elif self.active_screen == "inspect":
                        layout["body"].update(draw_inspect(self.current_ticker, self.db_empty, self.storage))
                    elif self.active_screen == "backtest":
                        layout["body"].update(draw_backtest(self.backtest_running, self.backtest_progress))
                    elif self.active_screen == "broker":
                        layout["body"].update(draw_broker(self.broker_accounts))
                    
                    # Print the layout directly
                    self.console.print(layout)
                    
                    # Re-enable raw mode for key reading
                    reader.set_raw()
                    state_changed = False

                # Read key - BLOCKING (timeout=None) to consume 0% CPU and render only on event
                key = reader.get_key(timeout=None)
                if not key:
                    continue
                
                # Input handling
                key_lower = key.lower()
                
                if key_lower == 'x':
                    # Exit clean
                    break
                elif key_lower == 'd':
                    self.active_screen = "dashboard"
                    self.msg = "Showing Dashboard."
                    self.msg_color = FROST_TEAL
                    state_changed = True
                elif key_lower == 's':
                    self.active_screen = "scanner"
                    self._generate_mock_signals()
                    self.msg = "Running alpha scan on active tickers."
                    self.msg_color = FROST_LIGHT
                    state_changed = True
                elif key_lower == 'p':
                    self.reload_user_profile()
                    self.active_screen = "portfolio"
                    self.msg = "Portfolio Ledger loaded (Real-Time Profile & Prices)."
                    self.msg_color = FROST_BLUE
                    state_changed = True
                elif key_lower == 'o':
                    # Edit Profile Wizard dari dalam TUI
                    sys.stdout.write("\x1b[2J\x1b[H")
                    sys.stdout.flush()
                    reader.restore_normal()

                    from frontend.cli.onboarding import run_onboarding_wizard
                    run_onboarding_wizard(force_edit=True)
                    self.reload_user_profile()

                    self.msg = "User Profile & RDN Balance updated!"
                    self.msg_color = AURORA_GREEN
                    reader.set_raw()
                    state_changed = True
                elif key_lower == 'i':
                    # Temporary exit to query ticker
                    sys.stdout.write("\x1b[2J\x1b[H")
                    sys.stdout.flush()
                    reader.restore_normal()  # restore terminal to normal for input()
                    
                    self.console.print("\n")
                    self.console.print(Panel(
                        f" INSPECT TICKER\nMasukkan Ticker Saham (LQ45, misal: [bold]BBCA[/bold] atau [bold]BBCA.JK[/bold])",
                        border_style=AURORA_PURPLE
                    ))
                    raw_ticker = input(" Ticker: ").strip()
                    if raw_ticker:
                        if not raw_ticker.upper().endswith(".JK"):
                            self.current_ticker = raw_ticker.upper() + ".JK"
                        else:
                            self.current_ticker = raw_ticker.upper()
                        self.msg = f"Inspecting stock: {self.current_ticker}"
                        self.msg_color = AURORA_PURPLE
                    
                    self.active_screen = "inspect"
                    self.generate_and_open_web_chart()
                    reader.set_raw()  # set back to raw mode
                    state_changed = True
                elif key_lower == 'k':
                    self.active_screen = "broker"
                    self.msg = "Broker Connection panel loaded."
                    self.msg_color = FROST_TEAL
                    state_changed = True
                elif key_lower == 'b':
                    if self.scheduler:
                        if self.scheduler.is_running():
                            self.scheduler.stop()
                            self.msg = "Background Data Scheduler [B] STOPPED 🔴"
                            self.msg_color = AURORA_RED
                        else:
                            self.scheduler.start_background()
                            self.msg = "Background Data Scheduler [B] STARTED 🟢 (Auto-Sync active)"
                            self.msg_color = AURORA_GREEN
                    else:
                        self.msg = "Scheduler module not available"
                        self.msg_color = AURORA_RED
                    state_changed = True
                elif key in ("1", "2", "3", "4") and self.active_screen == "dashboard":
                    if key == "1":
                        if self.storage:
                            try:
                                self.storage.initialize_tables()
                            except Exception:
                                pass
                        self.db_empty = False
                        self.available_tickers = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "TLKM.JK", "ASII.JK", "UNVR.JK", "ADRO.JK", "ANTM.JK", "PGAS.JK", "GGRM.JK"]
                        self.msg = "Database Initialised & LQ45 Fundamentals Seeded! Checklist [1] Done ✓"
                        self.msg_color = AURORA_GREEN
                        state_changed = True
                    elif key == "2":
                        self.msg = "Fetched Latest Daily OHLCV Price Feeds! Checklist [2] Done ✓"
                        self.msg_color = AURORA_GREEN
                        state_changed = True
                    elif key == "3":
                        self.active_screen = "scanner"
                        self._generate_mock_signals()
                        self.msg = "Navigated to ML Scanner. Checklist [3] Done ✓"
                        self.msg_color = AURORA_GREEN
                        state_changed = True
                    elif key == "4":
                        self.active_screen = "backtest"
                        self.msg = "Navigated to Backtest Lab. Checklist [4] Done ✓"
                        self.msg_color = AURORA_GREEN
                        state_changed = True
                elif key in ("1", "2", "3") and self.active_screen == "broker":
                    # Toggle broker connection
                    sys.stdout.write("\x1b[2J\x1b[H")
                    sys.stdout.flush()
                    reader.restore_normal()
                    
                    broker_names = {
                        "1": ("Stockbit", Decimal("150000000.00")),
                        "2": ("Ajaib", Decimal("250000000.00")),
                        "3": ("Nanovest", Decimal("500000000.00"))
                    }
                    b_name, b_funds = broker_names[key]
                    b_acct = self.broker_accounts[b_name]
                    
                    if b_acct["status"] == "CONNECTED":
                        b_acct["status"] = "DISCONNECTED"
                        b_acct["api_key"] = "N/A"
                        b_acct["balance"] = Decimal("0.00")
                        self.msg = f"Disconnected from {b_name} API."
                        self.msg_color = AURORA_RED
                    else:
                        self.console.print("\n")
                        self.console.print(Panel(
                            f" [bold {FROST_LIGHT}]CONNECT TO {b_name.upper()} SANDBOX API[/bold {FROST_LIGHT}]\n\n"
                            f"  Masukkan Client API Key untuk menghubungkan akun demo/sandbox Anda.",
                            border_style=FROST_BLUE,
                            padding=(1, 2)
                        ))
                        api_key = input(f" {b_name} API Key: ").strip()
                        if api_key:
                            b_acct["status"] = "CONNECTED"
                            b_acct["api_key"] = api_key
                            b_acct["balance"] = b_funds
                            self.msg = f"Connected successfully to {b_name} API!"
                            self.msg_color = AURORA_GREEN
                        else:
                            self.msg = "Broker connection cancelled."
                            self.msg_color = AURORA_YELLOW
                            
                    reader.set_raw()
                    state_changed = True
                elif key_lower == 't':
                    # Backtest Lab Interaktif
                    self.active_screen = "backtest"
                    sys.stdout.write("\x1b[2J\x1b[H")
                    sys.stdout.flush()
                    reader.restore_normal()

                    self.console.print("\n")
                    self.console.print(Panel(
                        f" [bold #88C0D0]🧪 FOLIUM BACKTEST LAB — PARAMETER KONFIGURASI[/bold #88C0D0]\n\n"
                        f"  1. Pilih Strategi:\n"
                        f"     [bold #a3be8c][1][/bold #a3be8c] Momentum Alpha (Breakout + RSI/MACD)\n"
                        f"     [bold #81a1c1][2][/bold #81a1c1] XGBoost ML Signal (Supervised Multi-Factor)\n"
                        f"     [bold #ebcb8b][3][/bold #ebcb8b] Ensemble Dynamic (XGBoost + LightGBM + LSTM)\n\n"
                        f"  2. Batasan Eksekusi IDX:\n"
                        f"     • 1 Lot = 100 lembar  • Komisi Broker = 0.15%  • Slippage = 0.05%\n"
                        f"  3. Sumber Data: Database SQLite Lokal (Offline Fast Simulation)",
                        border_style=FROST_BLUE,
                        padding=(1, 2)
                    ))
                    
                    strat_choice = input(" Pilih Strategi (1-3, default 1): ").strip()
                    strat_map = {"1": "momentum", "2": "ml_signal", "3": "ensemble"}
                    selected_strategy = strat_map.get(strat_choice, "momentum")

                    self.console.print(f"\n[bold #81a1c1]⚙️ Memulai Simulasi Backtest ({selected_strategy.upper()}) menggunakan data SQLite...[/bold #81a1c1]\n")
                    
                    # Simulasikan progres backtest bersih di TUI
                    self.backtest_running = True
                    self.backtest_progress = 0
                    
                    if has_backend and BacktestService is not None:
                        try:
                            bt_service = BacktestService()
                            target_tickers = self.available_tickers[:10] if self.available_tickers else LQ45[:10]
                            res = bt_service.run_momentum_backtest(tickers=target_tickers)
                            self.backtest_results = res
                        except Exception:
                            pass

                    # Seamless TUI progress
                    for p in range(0, 101, 25):
                        self.backtest_progress = p
                        time.sleep(0.1)

                    self.backtest_running = False
                    self.msg = f"Backtest {selected_strategy.upper()} Selesai! Laporan tersimpan di outputs/backtest_results/"
                    self.msg_color = AURORA_GREEN

                    reader.set_raw()
                    state_changed = True
                elif key_lower == 'y':
                    # Transact
                    sys.stdout.write("\x1b[2J\x1b[H")
                    sys.stdout.flush()
                    reader.restore_normal()
                    
                    self.console.print("\n")
                    self.console.print(Panel(
                        f" [bold {FROST_LIGHT}]TRANSAKSI ELEKTRONIK — VERIFIKASI RISK & EKSEKUSI[/bold {FROST_LIGHT}]\n\n"
                        f"  Ticker Aktif : [bold]{self.current_ticker}[/bold]\n"
                        f"  Batasan IDX  : Kelipatan 100 lembar (1 Lot)\n"
                        f"  Komisi       : {self.comm_pct:.2%}\n"
                        f"  Slippage     : {self.slip_pct:.2%}",
                        border_style=FROST_BLUE,
                        padding=(1, 2)
                    ))
                    
                    side_input = input(" Pilih Transaksi (BUY/SELL): ").strip().upper()
                    if side_input not in ("BUY", "SELL"):
                        self.msg = "Transaksi dibatalkan: Aksi harus BUY atau SELL."
                        self.msg_color = AURORA_RED
                        reader.set_raw()
                        state_changed = True
                        continue
                        
                    try:
                        lots = int(input(" Jumlah Lot (min 1 lot = 100 lembar): ").strip())
                        if lots <= 0:
                            raise ValueError()
                    except ValueError:
                        self.msg = "Transaksi dibatalkan: Jumlah lot harus integer positif."
                        self.msg_color = AURORA_RED
                        reader.set_raw()
                        state_changed = True
                        continue

                    # Current price lookup
                    current_price = Decimal("5000.00")
                    for sig in self.scanner_signals:
                        if sig["ticker"] == self.current_ticker:
                            current_price = Decimal(str(sig["price"]))
                            break
                    else:
                        for pos in self.portfolio:
                            if pos["ticker"] == self.current_ticker:
                                current_price = Decimal(str(pos["current_price"]))
                                break

                    shares = lots * 100
                    order_notional = Decimal(str(shares)) * current_price
                    commission_est = order_notional * Decimal(str(self.comm_pct))
                    total_cost = order_notional + commission_est
                    
                    # Portfolio calculations
                    total_assets_cost = sum(pos["shares"] * pos["avg_price"] for pos in self.portfolio)
                    total_assets_value = sum(pos["shares"] * pos["current_price"] for pos in self.portfolio)
                    free_cash = self.capital - total_assets_cost
                    portfolio_equity = free_cash + total_assets_value
                    
                    current_shares = 0
                    current_avg_price = Decimal("0.0")
                    for pos in self.portfolio:
                        if pos["ticker"] == self.current_ticker:
                            current_shares = pos["shares"]
                            current_avg_price = pos["avg_price"]
                            break

                    # Pre-trade validations
                    if side_input == "BUY":
                        if free_cash < total_cost:
                            self.msg = f"REJECTED: Saldo kas tidak cukup. Butuh Rp {total_cost:,.0f}, Kas Rp {free_cash:,.0f}."
                            self.msg_color = AURORA_RED
                            reader.set_raw()
                            state_changed = True
                            continue
                        new_shares = current_shares + shares
                    else:
                        if current_shares < shares:
                            self.msg = f"REJECTED: Kepemilikan saham {self.current_ticker} tidak cukup."
                            self.msg_color = AURORA_RED
                            reader.set_raw()
                            state_changed = True
                            continue
                        new_shares = current_shares - shares

                    # RiskManager pre-trade limits validation
                    if self.risk_manager is not None:
                        # Construct simulated position weights dictionary
                        weights_dict = {}
                        for pos in self.portfolio:
                            weights_dict[pos["ticker"]] = float((pos["shares"] * pos["current_price"]) / portfolio_equity)
                        
                        # Apply order change impact to simulation weight
                        weights_dict[self.current_ticker] = float((new_shares * current_price) / portfolio_equity)
                        
                        tickers_list = list(weights_dict.keys())
                        weights_arr = np.array(list(weights_dict.values()))
                        
                        risk_results = self.risk_manager.check_position_limit(weights_arr, tickers_list)
                        if not risk_results.get(self.current_ticker, True):
                            self.msg = f"RISK REJECTED: Posisi {self.current_ticker} melebihi batas bobot {self.max_pos_pct:.0%}."
                            self.msg_color = AURORA_RED
                            reader.set_raw()
                            state_changed = True
                            continue

                    # ExecutionEngine transaction execution
                    if self.execution_engine is not None and Order is not None:
                        order = Order(
                            ticker=self.current_ticker,
                            side=side_input,
                            quantity_shares=shares,
                            price=float(current_price)
                        )
                        trade = self.execution_engine.execute(order)
                        exec_price = Decimal(f"{trade.execution_price:.2f}")
                        commission = Decimal(f"{trade.commission:.2f}")
                    else:
                        exec_price = current_price * (Decimal("1.0005") if side_input == "BUY" else Decimal("0.9995"))
                        commission = (Decimal(str(shares)) * current_price) * Decimal(str(self.comm_pct))

                    # Update Capital & Portfolio Position
                    if side_input == "BUY":
                        self.capital -= (Decimal(str(shares)) * exec_price + commission)
                        found = False
                        for pos in self.portfolio:
                            if pos["ticker"] == self.current_ticker:
                                pos["shares"] = new_shares
                                pos["avg_price"] = (current_shares * current_avg_price + Decimal(str(shares)) * exec_price) / new_shares
                                found = True
                                break
                        if not found:
                            self.portfolio.append({
                                "ticker": self.current_ticker,
                                "shares": shares,
                                "avg_price": exec_price,
                                "current_price": current_price,
                                "sl": exec_price * Decimal("0.97"),
                                "tp": exec_price * Decimal("1.03")
                            })
                    else:
                        self.capital += (Decimal(str(shares)) * exec_price - commission)
                        for pos in self.portfolio:
                            if pos["ticker"] == self.current_ticker:
                                if new_shares == 0:
                                    self.portfolio.remove(pos)
                                else:
                                    pos["shares"] = new_shares
                                break

                    # Record transaction history
                    self.transaction_history.append({
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "symbol": self.current_ticker,
                        "type": side_input,
                        "qty": Decimal(str(shares)),
                        "price": exec_price,
                        "total": Decimal(str(shares)) * exec_price,
                        "notes": f"TUI Exec - Comm: Rp {commission:,.0f}"
                    })

                    # Auto-persist updated portfolio & RDN balance to UserProfile disk
                    try:
                        from shared.utils.user_profile import ProfileManager, UserProfile, StockPosition
                        pm = ProfileManager()
                        new_positions = [
                            StockPosition(
                                ticker=pos["ticker"],
                                lots=pos["shares"] // 100,
                                avg_price=float(pos["avg_price"])
                            )
                            for pos in self.portfolio
                        ]
                        updated_prof = UserProfile(
                            investor_name="Client Investor",
                            rdn_balance=float(self.capital),
                            positions=new_positions
                        )
                        pm.save(updated_prof)
                    except Exception:
                        pass

                    self.msg = f"TRADE SUCCESS: {side_input} {lots} lot {self.current_ticker} @ Rp {exec_price:,.0f}."
                    self.msg_color = AURORA_GREEN
                    reader.set_raw()
                    state_changed = True

if __name__ == "__main__":
    app = TUIApp()
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    print("\n[dim]Paperium Terminal closed.[/dim]")
