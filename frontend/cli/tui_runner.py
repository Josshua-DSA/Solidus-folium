#!/usr/bin/env python3
"""
FOLIUM QUANT DESK — TUI Runner Wrapper
Redirects to the modular TUI application under frontend/cli/.
"""
import sys
import os

# Ensure root path is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from frontend.cli.app import TUIApp

if __name__ == "__main__":
    app = TUIApp()
    try:
        app.run()
    except KeyboardInterrupt:
        sys.stdout.write("\x1b[2J\x1b[H")
        print("\n🍃 Folium Quantitative Terminal session ended.")
    except Exception as e:
        sys.stdout.write("\x1b[2J\x1b[H")
        print(f"\n[!] Folium Terminal Error: {e}")
        import traceback
        traceback.print_exc()
