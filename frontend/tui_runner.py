#!/usr/bin/env python3
"""
PAPERIUM QUANT DESK — TUI Runner Wrapper
Redirects to the modular TUI application under frontend/cli/.
"""
import sys
import os

# Ensure root path is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from frontend.cli.app import TUIApp

if __name__ == "__main__":
    app = TUIApp()
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    print("\n[dim]Paperium Terminal closed.[/dim]")
