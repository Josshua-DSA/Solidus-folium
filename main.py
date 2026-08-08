"""
Finance-Pro Quant & Execution Platform — Root Entry Point.

Interactive Interface Selector (9router / sol-fol style):
  1. Web UI (Launch FastAPI Server & Open Browser)
  2. Terminal UI (Launch Interactive Rich TUI)
  3. Exit
"""
import os
import sys
import webbrowser
import subprocess
import time
from typing import NoReturn

import questionary
from questionary import Choice, Style
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

# Custom Nord-Theme Questionary Style
NORD_STYLE = Style([
    ("qmark", "fg:#88c0d0 bold"),        # Frost Teal
    ("question", "fg:#eceff4 bold"),     # Snow Storm White
    ("answer", "fg:#a3be8c bold"),       # Aurora Green
    ("pointer", "fg:#88c0d0 bold"),      # Pointer arrow
    ("highlighted", "fg:#88c0d0 bold"),  # Selected option
    ("selected", "fg:#a3be8c bold"),     # Checked option
    ("separator", "fg:#4c566a"),         # Polar Night Gray
    ("instruction", "fg:#d8dee9"),       # Instruction text
])

BANNER = """[bold #88c0d0]========================================[/bold #88c0d0]
[bold #eceff4]  Finance-Pro Quant Platform (v1.0.0)[/bold #eceff4]
[bold #81a1c1]  🚀 Server API: http://localhost:8000[/bold #81a1c1]
[bold #88c0d0]========================================[/bold #88c0d0]"""


def print_banner():
    """Tampilkan banner header platform."""
    console.print(BANNER)
    console.print()


def launch_web_ui():
    """Jalankan FastAPI Server & Buka Web Browser."""
    console.print("\n[bold #a3be8c]🚀 Memulai FastAPI Server di http://localhost:8000 ...[/bold #a3be8c]")
    console.print("[dim #d8dee9]Buka browser ke http://localhost:8000/docs untuk OpenAPI Documentation.[/dim #d8dee9]\n")

    # Open browser after 1.5 seconds delay
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://localhost:8000/docs")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    # Run Uvicorn server (blocking)
    import uvicorn
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=8000, reload=True)


def launch_terminal_ui():
    """Jalankan Terminal UI (Interactive CLI TUI)."""
    console.print("\n[bold #88c0d0]🖥️  Membuka Terminal UI (TUI)...[/bold #88c0d0]\n")
    
    tui_script = os.path.join("frontend", "cli", "tui_runner.py")
    if os.path.exists(tui_script):
        subprocess.run([sys.executable, tui_script])
    else:
        # Fallback run cli.py status if tui_runner standalone is not present
        cli_script = os.path.join("cli.py")
        subprocess.run([sys.executable, cli_script, "status"])


def main():
    """Main Interactive Selector Loop."""
    os.system("clear" if os.name != "nt" else "cls")
    print_banner()

    choices = [
        Choice(title="★ Web UI (Open in Browser & Run API)", value="web"),
        Choice(title="☆ Terminal UI (Interactive CLI)", value="tui"),
        Choice(title="☆ Exit", value="exit"),
    ]

    answer = questionary.select(
        "Choose Interface:",
        choices=choices,
        style=NORD_STYLE,
        use_pointer=True,
    ).ask()

    if answer == "web":
        launch_web_ui()
    elif answer == "tui":
        launch_terminal_ui()
    elif answer == "exit":
        console.print("[bold #d8dee9]Sampai jumpa! 👋[/bold #d8dee9]")
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[dim #d8dee9]Dibatalkan oleh pengguna.[/dim #d8dee9]")
        sys.exit(0)
