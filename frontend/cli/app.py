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
    from data_layer.storage import StorageManager
    from data_layer.universe import LQ45, IDX_UNIVERSE
    from app.risk.risk_manager import RiskManager
    from app.execution.execution_engine import ExecutionEngine, Order
    has_backend = True
except ImportError:
    has_backend = False
    StorageManager = None
    RiskManager = None
    ExecutionEngine = None
    Order = None
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
from frontend.cli.screens import (
    draw_dashboard, draw_scanner, draw_portfolio, draw_inspect, draw_backtest
)

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
        
        # Load database status
        if has_backend and StorageManager is not None:
            try:
                self.storage = StorageManager()
                self.db_path = self.storage.db_path
                self.available_tickers = self.storage.get_available_tickers()
                if len(self.available_tickers) > 0:
                    self.db_empty = False
            except Exception:
                self.db_empty = True
        
        # System state
        self.active_screen = "dashboard"
        self.current_ticker = "BBCA.JK"
        self.msg = "Paperium Desk initialized successfully."
        self.msg_color = FROST_TEAL
        
        # Financial state using Decimals for precision
        self.capital = Decimal("100000000.00")  # Initial Capital in IDR
        
        # Simulated Portfolio positions using Decimals
        self.portfolio = [
            {"ticker": "BBCA.JK", "shares": 5000, "avg_price": Decimal("9850.00"), "current_price": Decimal("10200.00"), "sl": Decimal("9550.00"), "tp": Decimal("10500.00")},
            {"ticker": "TLKM.JK", "shares": 10000, "avg_price": Decimal("3620.00"), "current_price": Decimal("3500.00"), "sl": Decimal("3500.00"), "tp": Decimal("3900.00")},
            {"ticker": "BMRI.JK", "shares": 8000, "avg_price": Decimal("6100.00"), "current_price": Decimal("6400.00"), "sl": Decimal("5900.00"), "tp": Decimal("6600.00")},
        ]
        
        # Backtest state
        self.backtest_results = None
        self.backtest_running = False
        self.backtest_progress = 0
        
        # Simulated Signals (for Scanner)
        self.scanner_signals = []
        self._generate_mock_signals()

    def _generate_mock_signals(self):
        """Generates realistic scanner signals."""
        random.seed(42)
        self.scanner_signals = []
        for ticker in LQ45[:12]:
            base_price = LQ45_FUNDAMENTALS.get(ticker, {"eps": 100})["eps"] * 12 + random.randint(-500, 500)
            if base_price <= 0:
                base_price = 1000
            lstm_conf = 0.5 + random.random() * 0.45
            xgb_conf = 0.5 + random.random() * 0.42
            score = (lstm_conf + xgb_conf) / 2.0
            
            self.scanner_signals.append({
                "ticker": ticker,
                "price": base_price,
                "lstm": lstm_conf,
                "xgb": xgb_conf,
                "score": score,
                "sl": base_price * 0.97,
                "tp": base_price * 1.03,
                "action": "BUY" if score > 0.65 else "HOLD"
            })
        self.scanner_signals.sort(key=lambda x: x["score"], reverse=True)

    def draw_header(self) -> Text:
        """Draws the Oceanic Frost header as a single borderless reversed-color bar."""
        header_text = Text()
        header_text.append(" ▲ PAPERIUM QUANT TERMINAL ", style=f"bold {FROST_LIGHT}")
        header_text.append(" | ", style=POLAR_NIGHT_3)
        
        mode = "SIMULATION (MOCK)" if self.db_empty else "DATABASE ACTIVE"
        mode_color = AURORA_ORANGE if self.db_empty else AURORA_GREEN
        header_text.append(f"MODE: {mode}", style=f"bold {mode_color}")
        header_text.append(" | ", style=POLAR_NIGHT_3)
        
        header_text.append("CAPITAL: ", style=f"dim {SNOW_STORM_1}")
        header_text.append(f"Rp {self.capital:,.0f}", style=f"bold {FROST_TEAL}")
        header_text.append(" | ", style=POLAR_NIGHT_3)
        
        header_text.append(f"TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style=FROST_BLUE)
        return header_text

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
        table.add_row("T", "Transact (Buy/Sell)", "B", "Backtest Lab", "X", "Exit", "", "")
        
        return Align.center(table)

    def run_backtest_process(self):
        """Simulates running the backtester fold-by-fold."""
        self.backtest_running = True
        self.backtest_progress = 0

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
                        Layout(name="header", size=1),
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
                        layout["body"].update(draw_portfolio(self.portfolio, self.capital))
                    elif self.active_screen == "inspect":
                        layout["body"].update(draw_inspect(self.current_ticker, self.db_empty, self.storage))
                    elif self.active_screen == "backtest":
                        layout["body"].update(draw_backtest(self.backtest_running, self.backtest_progress))
                    
                    # Print the layout directly
                    self.console.print(layout)
                    
                    # Re-enable raw mode for key reading
                    reader.set_raw()
                    state_changed = False

                # Handle background backtest progress with direct updates
                if self.backtest_running:
                    # Temporarily restore normal terminal mode for printing
                    reader.restore_normal()
                    
                    # Dapatkan ukuran tinggi terminal
                    _, rows = shutil.get_terminal_size()
                    
                    # Reconstruct Layout
                    layout = Layout(size=rows)
                    layout.split_column(
                        Layout(name="header", size=1),
                        Layout(name="body", ratio=1),
                        Layout(name="footer", size=2)
                    )
                    layout["header"].update(self.draw_header())
                    layout["footer"].update(self.draw_footer())
                    
                    for p in range(0, 101, 10):
                        self.backtest_progress = p
                        sys.stdout.write("\x1b[2J\x1b[H")
                        sys.stdout.flush()
                        layout["body"].update(draw_backtest(True, self.backtest_progress))
                        self.console.print(layout)
                        time.sleep(0.15)
                        
                    self.backtest_running = False
                    self.msg = "Backtest run complete."
                    self.msg_color = AURORA_GREEN
                    
                    # Re-enable raw mode for key reading
                    reader.set_raw()
                    state_changed = True
                    continue

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
                    self.active_screen = "portfolio"
                    self.msg = "Portfolio Ledger loaded."
                    self.msg_color = FROST_BLUE
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
                    reader.set_raw()  # set back to raw mode
                    state_changed = True
                elif key_lower == 'b':
                    self.active_screen = "backtest"
                    if not self.backtest_running:
                        self.msg = "Starting backtest..."
                        self.msg_color = AURORA_PURPLE
                        self.run_backtest_process()
                        state_changed = True
                elif key_lower == 't':
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
