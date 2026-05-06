"""
OS Assistant — Native Desktop App Launcher
Run this to start the PyQt6 desktop application.
No browser, no Flask, no web server needed.
"""
import sys
import os

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "0")

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from native.app import main

if __name__ == "__main__":
    main()
