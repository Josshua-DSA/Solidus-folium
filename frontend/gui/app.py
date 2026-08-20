#!/usr/bin/env python3
"""
Folium Quant Desk — PySide6/PyQt6 Desktop GUI Application Entrypoint.

Launch with:
    python -m frontend.gui.app
    folium gui
    python main.py --gui
"""
import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

from frontend.gui.main_window import FoliumMainWindow


def run_gui():
    """Launch the Folium Quant Desk Desktop GUI."""
    app = QApplication(sys.argv)
    app.setApplicationName("Folium Quant Desk")
    app.setOrganizationName("Folium")
    app.setApplicationVersion("7.0.0")

    # Set default monospace font
    font = QFont("JetBrains Mono", 11)
    font.setStyleHint(QFont.StyleHint.Monospace)
    app.setFont(font)

    window = FoliumMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_gui()
