"""
Qt Compatibility Shim — Abstraksi PySide6 / PyQt6.

Mencoba import PySide6 terlebih dahulu, fallback ke PyQt6.
Seluruh modul GUI menggunakan `from frontend.gui.qt_compat import ...`
sehingga bisa berjalan di kedua binding tanpa perubahan kode.
"""
try:
    from PySide6.QtWidgets import *  # noqa: F401,F403
    from PySide6.QtCore import *     # noqa: F401,F403
    from PySide6.QtGui import *      # noqa: F401,F403
    QT_BINDING = "PySide6"
except ImportError:
    from PyQt6.QtWidgets import *  # noqa: F401,F403
    from PyQt6.QtCore import *     # noqa: F401,F403
    from PyQt6.QtGui import *      # noqa: F401,F403
    QT_BINDING = "PyQt6"
