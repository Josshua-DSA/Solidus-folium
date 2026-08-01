import sys
import os
import time
from datetime import datetime
import random

# App path injection
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

try:
    from data_layer.storage import StorageManager
    from data_layer.universe import LQ45, IDX_UNIVERSE
    has_backend = True
except ImportError:
    has_backend = False
    StorageManager = None
    LQ45 = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "TLKM.JK", "ASII.JK", "UNVR.JK", "ADRO.JK", "KLBF.JK", "ICBP.JK", "INDF.JK"]
    IDX_UNIVERSE = LQ45

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.align import Align

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
        self.capital = 100_000_000.0  # Initial Capital in IDR
        
        # Simulated Portfolio positions
        self.portfolio = [
            {"ticker": "BBCA.JK", "shares": 5000, "avg_price": 9850.0, "current_price": 10200.0, "sl": 9550.0, "tp": 10500.0},
            {"ticker": "TLKM.JK", "shares": 10000, "avg_price": 3620.0, "current_price": 3500.0, "sl": 3500.0, "tp": 3900.0},
            {"ticker": "BMRI.JK", "shares": 8000, "avg_price": 6100.0, "current_price": 6400.0, "sl": 5900.0, "tp": 6600.0},
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

    def draw_header(self) -> Panel:
        """Draws the Oceanic Frost header."""
        header_text = Text()
        header_text.append("▲ PAPERIUM QUANT TERMINAL ", style=f"bold {FROST_LIGHT}")
        header_text.append(" |  ", style=f"{POLAR_NIGHT_3}")
        
        mode = "SIMULATION (MOCK)" if self.db_empty else "DATABASE ACTIVE"
        mode_color = AURORA_ORANGE if self.db_empty else AURORA_GREEN
        header_text.append(f"MODE: {mode}", style=f"bold {mode_color}")
        header_text.append("  |  ", style=f"{POLAR_NIGHT_3}")
        
        header_text.append("CAPITAL: ", style=f"dim {SNOW_STORM_1}")
        header_text.append(f"Rp {self.capital:,.0f}", style=f"bold {FROST_TEAL}")
        header_text.append("  |  ", style=f"{POLAR_NIGHT_3}")
        
        header_text.append(f"TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style=f"{FROST_BLUE}")
        
        return Panel(
            Align.center(header_text),
            border_style=FROST_DARK,
            title="SYSTEM STATUS",
            title_align="left",
        )

    def draw_footer(self) -> Panel:
        """Draws the command shortcut bar."""
        footer_text = Text()
        shortcuts = [
            ("D", "Dashboard"),
            ("S", "Scanner"),
            ("P", "Portfolio"),
            ("I", "Inspect Stock"),
            ("B", "Backtest Lab"),
            ("X", "Exit")
        ]
        
        for key, name in shortcuts:
            footer_text.append(" [", style=f"{POLAR_NIGHT_3}")
            footer_text.append(key, style=f"bold {AURORA_PURPLE}")
            footer_text.append(f"] {name} ", style=f"bold {SNOW_STORM_2}")
            
        return Panel(
            Align.center(footer_text),
            border_style=FROST_DARK,
            title="NAVIGATION PANEL",
            title_align="left",
        )

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
                    # Clear screen using terminal escape codes (clean and fast)
                    sys.stdout.write("\x1b[2J\x1b[H")
                    sys.stdout.flush()
                    
                    # Reconstruct Layout
                    layout = Layout()
                    layout.split_column(
                        Layout(name="header", size=3),
                        Layout(name="body", ratio=8),
                        Layout(name="footer", size=3)
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
                    state_changed = False

                # Handle background backtest progress with direct updates
                if self.backtest_running:
                    # Reconstruct Layout
                    layout = Layout()
                    layout.split_column(
                        Layout(name="header", size=3),
                        Layout(name="body", ratio=8),
                        Layout(name="footer", size=3)
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

if __name__ == "__main__":
    app = TUIApp()
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    print("\n[dim]Paperium Terminal closed.[/dim]")
