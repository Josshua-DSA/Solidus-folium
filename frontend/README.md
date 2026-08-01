# Frontend Component - Paperium Trading Desk

Folder ini menampung seluruh implementasi antarmuka pengguna (User Interface), baik dalam bentuk **TUI CLI (Terminal-based)** maupun rencana pengembangan **GUI Web** di masa depan.

## Struktur Folder

```text
frontend/
├── cli/                 # Kode sumber Terminal User Interface (TUI)
│   ├── app.py           # Jantung aplikasi, event loop, & state manager
│   ├── keyboard.py      # Module input keyboard non-blocking
│   ├── theme.py         # Palet warna Nord Theme & Mock Data
│   └── screens/         # Komponen tampilan TUI per halaman
│       ├── __init__.py
│       ├── dashboard.py # Diagnostik sistem & ML config
│       ├── scanner.py   # Pemindai sinyal beli/jual real-time
│       ├── portfolio.py # Catatan portofolio & kalkulasi PnL
│       ├── inspect.py   # Riset rasio fundamental & grafik harga
│       └── backtest.py  # Evaluasi OOS & grafik kurva ekuitas
├── templates/           # [Masa Depan] File HTML untuk GUI Web local
├── menu.html            # [Masa Depan] Entry point menu utama GUI Web
├── tui_runner.py        # Wrapper eksekusi TUI dari root directory
└── README.md            # Dokumentasi ini
```

## Cara Menjalankan TUI

Anda dapat menjalankan TUI interaktif secara langsung dari root directory proyek dengan perintah:

```bash
# Menggunakan virtualenv Python
./venv/bin/python frontend/tui_runner.py
```

Atau melalui Unified Runner utama proyek:

```bash
python backend/run.py
# Pilih Opsi [6] "Launch TUI Dashboard (Oceanic Frost Theme)"
```

## Navigasi TUI (Keyboard-driven)

TUI ini didesain agar *keyboard-driven* (Bloomberg-like terminal) untuk efisiensi maksimal dan kompatibilitas 100% lintas terminal:
* **`[D]`** $\rightarrow$ Membuka **Dashboard** status sistem.
* **`[S]`** $\rightarrow$ Menjalankan **Alpha Scanner** sinyal LQ45.
* **`[P]`** $\rightarrow$ Memeriksa **Portfolio** & saldo kas.
* **`[I]`** $\rightarrow$ Membuka panel **Inspect Stock** (Riset Fundamental & Grafik). Anda akan diminta memasukkan ticker saham (seperti `BBCA`).
* **`[B]`** $\rightarrow$ Membuka **Backtest Lab** dan memulai simulasi pengujian baru.
* **`[X]`** $\rightarrow$ Keluar dari TUI secara bersih.
