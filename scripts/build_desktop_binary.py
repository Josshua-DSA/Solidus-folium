#!/usr/bin/env python3
"""
Folium Desktop GUI — Standalone Binary Packaging Build Script.

Builds a standalone, zero-dependency executable for Linux / macOS / Windows
using PyInstaller. Bundles:
- All core engine modules (app, model, pipeline, shared, frontend)
- Nord Theme QSS stylesheets (frontend/gui/styles/nord_theme.qss)
- Application configuration (config/config.yaml)
- SQLite WAL runtime dependencies & PyQt6/PySide6 assets

Usage:
    python scripts/build_desktop_binary.py [--onefile] [--onedir] [--clean]
"""
import sys
import os
import shutil
import subprocess
import argparse
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def build_binary(onefile: bool = False, clean: bool = True):
    """Run PyInstaller with optimal flags for Folium Quant Desk."""
    print("=" * 65)
    print("▲ FOLIUM QUANT DESK — DESKTOP BINARY PACKAGING")
    print("=" * 65)

    dist_dir = PROJECT_ROOT / "dist"
    build_dir = PROJECT_ROOT / "build"

    if clean:
        print("[1/4] Cleaning previous build artifacts...")
        if dist_dir.exists():
            shutil.rmtree(dist_dir)
        if build_dir.exists():
            shutil.rmtree(build_dir)

    entrypoint = PROJECT_ROOT / "frontend" / "gui" / "app.py"
    if not entrypoint.exists():
        print(f"❌ Entrypoint not found: {entrypoint}")
        sys.exit(1)

    print(f"[2/4] Entrypoint verified: {entrypoint}")

    # Build PyInstaller command
    pyinstaller_bin = PROJECT_ROOT / "venv" / "bin" / "pyinstaller"
    if not pyinstaller_bin.exists():
        pyinstaller_bin = "pyinstaller"

    cmd = [
        str(pyinstaller_bin),
        "--name=folium-workstation",
        "--noconfirm",
        "--windowed",  # No console window on launch
        # Data Files (source:dest)
        f"--add-data={PROJECT_ROOT / 'frontend' / 'gui' / 'styles' / 'nord_theme.qss'}:frontend/gui/styles",
        f"--add-data={PROJECT_ROOT / 'config' / 'config.yaml'}:config",
        # Hidden imports for dynamic modules & Qt plugins
        "--hidden-import=PyQt6",
        "--hidden-import=PyQt6.QtCore",
        "--hidden-import=PyQt6.QtGui",
        "--hidden-import=PyQt6.QtWidgets",
        "--hidden-import=pyqtgraph",
        "--hidden-import=pipeline",
        "--hidden-import=pipeline.storage",
        "--hidden-import=pipeline.universe",
        "--hidden-import=model",
        "--hidden-import=model.registry",
        "--hidden-import=app",
        "--hidden-import=app.risk",
        "--hidden-import=app.risk.risk_manager",
        "--hidden-import=app.execution",
        "--hidden-import=app.execution.execution_engine",
        "--hidden-import=app.services",
        "--hidden-import=app.services.backtest_service",
        "--hidden-import=app.services.scanner_service",
        "--hidden-import=app.services.portfolio_service",
        "--hidden-import=shared",
        "--hidden-import=shared.utils.user_profile",
        "--hidden-import=frontend.gui.workers.signal_bus",
        "--hidden-import=frontend.gui.workers.async_workers",
        "--hidden-import=frontend.gui.workers.inference_worker",
        "--hidden-import=frontend.gui.components.chart_canvas",
        "--hidden-import=frontend.gui.components.market_table",
        "--hidden-import=frontend.gui.components.risk_meter",
        "--hidden-import=frontend.gui.components.backtest_lab",
        "--hidden-import=frontend.gui.components.portfolio_panel",
        "--hidden-import=frontend.gui.components.order_dialog",
        f"--paths={PROJECT_ROOT}",
    ]

    if onefile:
        cmd.append("--onefile")
        print("[3/4] Packaging mode: Single Executable Binary (--onefile)...")
    else:
        cmd.append("--onedir")
        print("[3/4] Packaging mode: Standalone Application Directory (--onedir)...")

    cmd.append(str(entrypoint))

    print(f"Running command:\n{' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    if result.returncode != 0:
        print("❌ PyInstaller packaging failed!")
        sys.exit(result.returncode)

    print("\n[4/4] ✅ Build completed successfully!")
    out_path = dist_dir / "folium-workstation"
    print(f"Executable output: {out_path}")
    print("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Folium Desktop Standalone Executable")
    parser.add_argument("--onefile", action="store_true", help="Build as a single-file executable")
    parser.add_argument("--onedir", action="store_true", default=True, help="Build as an application folder (default)")
    parser.add_argument("--no-clean", action="store_false", dest="clean", help="Keep previous build files")

    args = parser.parse_args()
    build_binary(onefile=args.onefile, clean=args.clean)
