#!/usr/bin/env python3
"""
Build script for Windows Health Checker Pro v1.0.0
Creates a production executable using PyInstaller
"""

import subprocess
import sys
import os
from pathlib import Path

# Configuration
APP_NAME = "WindowsHealthCheckerPro"
VERSION = "1.0.0"
MAIN_SCRIPT = "driver_updater_qt_mk5.py"
ICON_FILE = None  # Set to "icon.ico" if you have one

def build():
    print(f"Building {APP_NAME} v{VERSION}...")
    print("=" * 50)
    
    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onefile",  # Single executable
        "--windowed",  # No console window
        "--clean",  # Clean cache
        "--noconfirm",  # Overwrite without asking
        
        # Hidden imports that PyInstaller might miss
        "--hidden-import", "PyQt6.QtCore",
        "--hidden-import", "PyQt6.QtWidgets", 
        "--hidden-import", "PyQt6.QtGui",
        "--hidden-import", "wmi",
        "--hidden-import", "win32com.client",
        "--hidden-import", "pythoncom",
        "--hidden-import", "pywintypes",
        "--hidden-import", "multiprocessing",
        
        # Add data files (Python modules that are part of the app)
        "--add-data", "hardware_scanner.py;.",
        "--add-data", "startup_scanner.py;.",
        "--add-data", "perf_utils.py;.",
        
        # Exclude unnecessary modules to reduce size
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",
        "--exclude-module", "numpy",
        "--exclude-module", "pandas",
        "--exclude-module", "scipy",
        "--exclude-module", "PIL",
        "--exclude-module", "pytest",
        "--exclude-module", "unittest",
        
        # UAC admin manifest for Windows
        "--uac-admin",
        
        MAIN_SCRIPT
    ]
    
    # Add icon if available
    if ICON_FILE and Path(ICON_FILE).exists():
        cmd.extend(["--icon", ICON_FILE])
    
    print("Running PyInstaller...")
    print(f"Command: {' '.join(cmd)}")
    print()
    
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    
    if result.returncode == 0:
        exe_path = Path(__file__).parent / "dist" / f"{APP_NAME}.exe"
        print()
        print("=" * 50)
        print(f"✅ BUILD SUCCESSFUL!")
        print(f"   Executable: {exe_path}")
        print(f"   Size: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
        print()
        print("To distribute:")
        print(f"   1. Copy {APP_NAME}.exe to target machine")
        print("   2. Run as Administrator for full functionality")
        print("=" * 50)
    else:
        print()
        print("❌ BUILD FAILED!")
        print("   Check the output above for errors.")
        sys.exit(1)


if __name__ == "__main__":
    build()
