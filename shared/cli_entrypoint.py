#!/usr/bin/env python3
"""
Folium Terminal Standalone Entrypoint Launcher.
Ensures project root directory is prioritized in sys.path before execution.
"""
import sys
import os
from pathlib import Path

# Force current project root to front of sys.path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from cli import app

def main():
    app()

if __name__ == "__main__":
    main()
