from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.align import Align
from frontend.cli.theme import (
    FROST_BLUE, FROST_LIGHT, SNOW_STORM_1, SNOW_STORM_2, SNOW_STORM_3,
    AURORA_GREEN, AURORA_RED, AURORA_YELLOW, POLAR_NIGHT_3
)

def draw_broker(broker_accounts: dict) -> Panel:
    """Draws the Broker Connection and External API management screen."""
    
    # Table of Active Integrations
    table = Table(show_header=True, header_style=f"bold {FROST_LIGHT}", box=None)
    table.add_column("Broker Name", style=f"bold {SNOW_STORM_3}")
    table.add_column("Status", justify="center")
    table.add_column("API Credentials Key", justify="center")
    table.add_column("Linked Sandbox Balance", justify="right", style=SNOW_STORM_2)
    table.add_column("Supported Markets", justify="center", style=FROST_BLUE)

    for name, acct in broker_accounts.items():
        status_colored = f"[bold white on {AURORA_GREEN}] CONNECTED [/bold white on {AURORA_GREEN}]" if acct["status"] == "CONNECTED" else f"[bold white on {AURORA_RED}] DISCONNECTED [/bold white on {AURORA_RED}]"
        
        balance_str = f"Rp {acct['balance']:,.2f}" if acct["status"] == "CONNECTED" else "N/A"
        key_str = acct["api_key"] if acct["status"] == "DISCONNECTED" or acct["api_key"] == "N/A" else f"{acct['api_key'][:8]}********"
        
        table.add_row(
            name,
            status_colored,
            key_str,
            balance_str,
            "IDX Equity & Derivatives" if name != "Nanovest" else "IDX & US Equities / Crypto"
        )

    # API Configuration Notes & How-To Connect
    notes_text = Text()
    notes_text.append("\nINSTRUCTIONS FOR BROKER CONNECT INTEGRATION:\n\n", style=f"bold {FROST_LIGHT}")
    notes_text.append("  [1] Toggle Stockbit API  ", style=f"bold {AURORA_YELLOW}")
    notes_text.append(" Connect your Stockbit virtual / live account for execution routing.\n")
    notes_text.append("  [2] Toggle Ajaib API     ", style=f"bold {AURORA_YELLOW}")
    notes_text.append(" Link Ajaib accounts via client-id and secret token authentication.\n")
    notes_text.append("  [3] Toggle Nanovest API  ", style=f"bold {AURORA_YELLOW}")
    notes_text.append(" Route orders to US fractionals and IDX stocks simultaneously.\n\n")
    notes_text.append("  * Note: Direct broker trading uses secure local keyrings to persist API secrets locally.\n", style=f"italic {SNOW_STORM_1}")
    notes_text.append("    Make sure you have configured proxy bypass in config.yaml if needed.", style=f"italic {SNOW_STORM_1}")

    outer_layout = Table(show_header=False, box=None)
    outer_layout.add_column("col")
    outer_layout.add_row(table)
    outer_layout.add_row(Text("--------------------------------------------------------------------------------", style=POLAR_NIGHT_3))
    outer_layout.add_row(notes_text)

    return Panel(
        outer_layout,
        title="BROKER GATEWAY & SANDBOX API CONNECTIONS",
        border_style=FROST_BLUE,
        padding=(1, 2)
    )
