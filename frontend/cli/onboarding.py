"""
Client Onboarding Wizard — Inisialisasi profil investor RDN & saham pegangan.

Menyediakan antarmuka interaktif Nord-theme untuk mengumpulkan:
  1. Saldo RDN Aktif (Rp)
  2. Daftar Saham yang sedang dipegang (Ticker, Lot, Avg Price)
  3. Menyimpannya ke user_profile.json
"""
import sys
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from shared.utils.user_profile import ProfileManager, UserProfile, StockPosition

console = Console()

# Nord Theme Colors
FROST_TEAL = "#88C0D0"
FROST_BLUE = "#81A1C1"
AURORA_GREEN = "#A3BE8C"
AURORA_YELLOW = "#EBCB8B"
AURORA_RED = "#BF616A"
POLAR_DARK = "#2E3440"


def run_onboarding_wizard(force_edit: bool = False) -> UserProfile:
    """
    Jalankan Wizard Onboarding Interaktif.
    Jika profil sudah ada dan force_edit=False, langsung kembalikan profil yang ada.
    """
    pm = ProfileManager()
    if pm.exists() and not force_edit:
        return pm.load()

    console.print("\n")
    console.print(Panel(
        f"[bold {FROST_TEAL}]🍃 FOLIUM TERMINAL — ONBOARDING PROFIL INVESTOR[/bold {FROST_TEAL}]\n\n"
        f"Selamat datang di [bold]Folium Terminal[/bold]! Sebelum masuk ke Dashboard Command Center,\n"
        f"silakan atur saldo kas RDN dan portofolio awal Anda.",
        border_style=FROST_BLUE,
        padding=(1, 2)
    ))

    # Prompt 1: Saldo RDN
    existing = pm.load()
    default_rdn = f"{int(existing.rdn_balance):,}" if existing else "10000000"

    rdn_input = questionary.text(
        "💰 Berapa Saldo Kas RDN Aktif Anda saat ini (Rp)?",
        default=str(int(existing.rdn_balance)) if existing else "10000000",
        validate=lambda val: val.isdigit() and int(val) >= 0 or "Masukkan angka positif tanpa titik/koma!"
    ).ask()

    if rdn_input is None:
        console.print("[yellow]Onboarding dibatalkan. Menggunakan profil default.[/yellow]")
        return existing

    rdn_balance = float(rdn_input)

    # Prompt 2: Pegang saham apa dan berapa lot
    positions: list[StockPosition] = []

    has_stocks = questionary.confirm(
        "📈 Apakah Anda saat ini sedang memegang saham di portofolio?",
        default=len(existing.positions) > 0 if existing else False
    ).ask()

    if has_stocks:
        console.print(f"\n[bold {FROST_TEAL}]--- INPUT PORTOFOLIO SAHAM ---[/bold {FROST_TEAL}]")
        while True:
            ticker = questionary.text(
                "Kode Ticker Saham (contoh: BBCA.JK atau BBRI):",
                validate=lambda val: len(val.strip()) >= 3 or "Ticker minimal 3 karakter!"
            ).ask()

            if not ticker:
                break

            ticker = ticker.strip().upper()
            if not ticker.endswith(".JK") and not ticker.startswith("^"):
                ticker = f"{ticker}.JK"

            lots_input = questionary.text(
                f"Berapa Lot {ticker} yang Anda pegang (1 Lot = 100 lembar)?",
                default="10",
                validate=lambda val: val.isdigit() and int(val) > 0 or "Lot harus integer positif!"
            ).ask()

            if not lots_input:
                break

            lots = int(lots_input)

            avg_price_input = questionary.text(
                f"Harga Beli Rata-Rata (Avg Price) {ticker} per lembar (Rp)?",
                default="9000",
                validate=lambda val: val.replace(".", "").isdigit() or "Masukkan harga angka valid!"
            ).ask()

            if not avg_price_input:
                break

            avg_price = float(avg_price_input)
            positions.append(StockPosition(ticker=ticker, lots=lots, avg_price=avg_price))

            add_more = questionary.confirm("Tambah saham lainnya?", default=False).ask()
            if not add_more:
                break

    # Simpan profil
    new_profile = UserProfile(
        investor_name=existing.investor_name if existing else "Client Folium",
        rdn_balance=rdn_balance,
        positions=positions,
    )
    pm.save(new_profile)

    # Tampilkan Ringkasan
    table = Table(title="📋 RINGKASAN PROFIL INVESTOR FOLIUM", border_style=FROST_BLUE)
    table.add_column("Komponen", style="bold cyan")
    table.add_column("Nilai", style="bold white")

    table.add_row("Saldo Kas RDN", f"Rp {rdn_balance:,.0f}")
    table.add_row("Jumlah Saham Pegangan", f"{len(positions)} Ticker")

    total_portfolio_val = rdn_balance
    for pos in positions:
        pos_val = pos.total_value
        total_portfolio_val += pos_val
        table.add_row(f"  • {pos.ticker}", f"{pos.lots} Lot ({pos.shares:,} lembar) @ Rp {pos.avg_price:,.0f} = Rp {pos_val:,.0f}")

    table.add_row("TOTAL EKUITAS MODAL", f"Rp {total_portfolio_val:,.0f}", style=f"bold {AURORA_GREEN}")

    console.print("\n")
    console.print(table)
    console.print(f"[bold {AURORA_GREEN}]✓ Profil berhasil disimpan ke ~/.folium/user_profile.json[/bold {AURORA_GREEN}]\n")

    return new_profile
