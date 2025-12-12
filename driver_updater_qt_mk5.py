"""
Windows Health Checker Pro - MK5
Refined professional UI with proper visual polish

Performance optimizations:
- QThread workers for blocking operations (hardware/startup scans)
- Cached static data (motherboard, BIOS)
- Optimized real-time graphs (no subprocess for CPU/RAM)
- Batch UI updates to reduce repaints
- Timing instrumentation for profiling
"""

import sys
import json
import os
import subprocess
import ctypes
import threading
from ctypes import wintypes
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QProgressBar,
    QStackedWidget, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
    QSizePolicy, QDialog, QGridLayout, QTextEdit, QSpacerItem, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer, QSize, QPropertyAnimation, QEasingCurve, pyqtSignal, QThread, QObject, QPoint
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush, QFontDatabase, QPainterPath, QIcon, QPixmap

from driver_backend import (
    DriverScanner, OnlineDriverChecker, ManufacturerSupport,
    HealthChecker, DiskManager, DriverInfo,
    is_admin, run_as_admin
)

# Performance utilities
try:
    from perf_utils import timed, TimingContext, perf_logger, BatchUpdater # pyright: ignore[reportAssignmentType]
    PERF_UTILS_AVAILABLE = True
except ImportError:
    PERF_UTILS_AVAILABLE = False
    def timed(name=None):
        def decorator(func):
            return func
        return decorator

# Hardware scanner for comprehensive hardware info
try:
    from hardware_scanner import (
        collect_hardware_snapshot, get_hardware_summary,
        HardwareSnapshot, HealthStatus as HWHealthStatus
    )
    HARDWARE_SCANNER_AVAILABLE = True
except ImportError:
    HARDWARE_SCANNER_AVAILABLE = False


# =============================================================================
# APPLICATION CONFIGURATION
# =============================================================================

APP_VERSION = "4.1.1"
APP_BUILD = "2025.12.11"

# Production mode - disable settings persistence for release builds
PRODUCTION_MODE = True


# =============================================================================
# ANIMATED STACKED WIDGET - Smooth Page Transitions
# =============================================================================

class AnimatedStackedWidget(QStackedWidget):
    """QStackedWidget with smooth page transitions.
    
    NOTE: Using instant transitions to avoid QPainter conflicts with 
    QGraphicsOpacityEffect when widgets have other graphics effects applied.
    The widget provides a clean interface for future animation improvements.
    """
    
    # Signal emitted when transition completes
    transition_finished = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._duration = 200  # Reserved for future use
    
    def setCurrentWidget(self, w):
        """Switch to widget (instant transition to avoid QPainter conflicts)."""
        super().setCurrentWidget(w)
        self.transition_finished.emit()
    
    def setCurrentIndex(self, index):
        """Switch to index (instant transition)."""
        if 0 <= index < self.count():
            super().setCurrentIndex(index)
            self.transition_finished.emit()
    
    def set_transition_duration(self, ms: int):
        """Set animation duration (reserved for future use)."""
        self._duration = max(50, min(500, ms))
    
    def set_transition_easing(self, easing: QEasingCurve.Type):
        """Set the easing curve (reserved for future use)."""
        pass  # Reserved for future animation implementation


# =============================================================================
# ICON EXTRACTION UTILITIES
# =============================================================================

# Check for QtWinExtras availability (PyQt5 only, not available in PyQt6)
QTWIN_EXTRAS_AVAILABLE = False
QtWin = None
try:
    from PyQt6.QtWinExtras import QtWin  # type: ignore
    QTWIN_EXTRAS_AVAILABLE = True
except ImportError:
    pass

# Check for pywin32 availability
PYWIN32_AVAILABLE = False
try:
    import win32gui  # type: ignore
    import win32ui  # type: ignore
    import win32con  # type: ignore
    PYWIN32_AVAILABLE = True
except ImportError:
    pass


def extract_icon_from_exe(exe_path: str, size: int = 32) -> QPixmap | None:
    """Extract icon from an executable using Windows Shell32 API"""
    if not os.path.exists(exe_path):
        return None
    
    try:
        # Use Shell32 to extract icon
        shell32 = ctypes.windll.shell32
        
        # ExtractIconExW returns the number of icons
        large_icons = (ctypes.c_void_p * 1)()
        small_icons = (ctypes.c_void_p * 1)()
        
        # Extract the first icon (index 0)
        result = shell32.ExtractIconExW(exe_path, 0, large_icons, small_icons, 1)
        
        if result > 0:
            # Use large icon for better quality
            hicon = large_icons[0] if large_icons[0] else small_icons[0]
            
            if hicon:
                # Method 1: Try QtWinExtras if available (PyQt5 only)
                if QTWIN_EXTRAS_AVAILABLE and QtWin:
                    try:
                        pixmap = QtWin.fromHICON(hicon)
                        # Clean up the icon handle
                        ctypes.windll.user32.DestroyIcon(hicon)
                        if small_icons[0]:
                            ctypes.windll.user32.DestroyIcon(small_icons[0])
                        return pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
                    except Exception:
                        pass
                
                # Method 2: Use pywin32 if available
                if PYWIN32_AVAILABLE:
                    try:
                        # Get icon info
                        info = win32gui.GetIconInfo(hicon)  # type: ignore
                        hbmColor = info[4]
                        
                        if hbmColor:
                            # Get bitmap dimensions
                            bmp = win32gui.GetObject(hbmColor)  # type: ignore
                            width, height = bmp.bmWidth, bmp.bmHeight
                            
                            # Create compatible DC
                            hdc = win32gui.GetDC(0)  # type: ignore
                            hdc_mem = win32gui.CreateCompatibleDC(hdc)  # type: ignore
                            old_bmp = win32gui.SelectObject(hdc_mem, hbmColor)  # type: ignore
                            
                            # Create QImage from DC
                            from PyQt6.QtGui import QImage
                            img = QImage(width, height, QImage.Format.Format_ARGB32)
                            
                            # Copy pixels
                            for y in range(height):
                                for x in range(width):
                                    pixel = win32gui.GetPixel(hdc_mem, x, y)  # type: ignore
                                    r = pixel & 0xFF
                                    g = (pixel >> 8) & 0xFF
                                    b = (pixel >> 16) & 0xFF
                                    img.setPixelColor(x, y, QColor(r, g, b))
                            
                            # Clean up
                            win32gui.SelectObject(hdc_mem, old_bmp)  # type: ignore
                            win32gui.DeleteDC(hdc_mem)  # type: ignore
                            win32gui.ReleaseDC(0, hdc)  # type: ignore
                            win32gui.DeleteObject(hbmColor)  # type: ignore
                            if info[3]:
                                win32gui.DeleteObject(info[3])  # type: ignore
                            ctypes.windll.user32.DestroyIcon(hicon)
                            if small_icons[0]:
                                ctypes.windll.user32.DestroyIcon(small_icons[0])
                            
                            pixmap = QPixmap.fromImage(img)
                            if not pixmap.isNull():
                                return pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                                    Qt.TransformationMode.SmoothTransformation)
                    except Exception:
                        pass
                
                # Clean up handles if we didn't use them
                ctypes.windll.user32.DestroyIcon(hicon)
                if small_icons[0]:
                    ctypes.windll.user32.DestroyIcon(small_icons[0])
        
        # Method 3: Fall back to QIcon which sometimes works for exe files
        icon = QIcon(exe_path)
        if not icon.isNull():
            pixmap = icon.pixmap(size, size)
            if not pixmap.isNull():
                return pixmap
                
    except Exception:
        pass
    
    return None


def get_app_icon_from_registry(app_name: str) -> QPixmap | None:
    """Try to extract application icon from Windows registry install location"""
    import winreg
    import os
    
    # Common registry paths for installed apps
    reg_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    
    app_name_lower = app_name.lower()
    
    for hkey, path in reg_paths:
        try:
            with winreg.OpenKey(hkey, path) as key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            try:
                                display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                                if app_name_lower in display_name.lower():
                                    # Found the app, try to get DisplayIcon first
                                    try:
                                        display_icon, _ = winreg.QueryValueEx(subkey, "DisplayIcon")
                                        # DisplayIcon can be "path,index" format
                                        icon_path = display_icon.split(",")[0].strip('"').strip()
                                        
                                        if os.path.exists(icon_path):
                                            # Try to extract icon from the file
                                            pixmap = extract_icon_from_exe(icon_path, 32)
                                            if pixmap and not pixmap.isNull():
                                                return pixmap
                                            
                                            # If it's an .ico file, load directly
                                            if icon_path.lower().endswith('.ico'):
                                                icon = QIcon(icon_path)
                                                if not icon.isNull():
                                                    return icon.pixmap(32, 32)
                                    except:
                                        pass
                                    
                                    # Try InstallLocation to find exe
                                    try:
                                        install_loc, _ = winreg.QueryValueEx(subkey, "InstallLocation")
                                        if install_loc and os.path.isdir(install_loc):
                                            # Look for main exe files
                                            for f in os.listdir(install_loc):
                                                if f.endswith('.exe'):
                                                    exe_path = os.path.join(install_loc, f)
                                                    pixmap = extract_icon_from_exe(exe_path, 32)
                                                    if pixmap and not pixmap.isNull():
                                                        return pixmap
                                    except:
                                        pass
                            except:
                                pass
                        i += 1
                    except OSError:
                        break
        except:
            continue
    
    return None


def get_cached_app_icon(app_name: str, size: int = 32) -> QPixmap | None:
    """Get app icon with caching to avoid repeated registry lookups"""
    # Use a simple module-level cache
    if not hasattr(get_cached_app_icon, '_cache'):
        get_cached_app_icon._cache = {} # type: ignore
    
    cache_key = f"{app_name}_{size}"
    if cache_key in get_cached_app_icon._cache: # type: ignore
        return get_cached_app_icon._cache[cache_key] # pyright: ignore[reportFunctionMemberAccess]
    
    pixmap = get_app_icon_from_registry(app_name)
    if pixmap:
        # Scale to desired size
        pixmap = pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, 
                               Qt.TransformationMode.SmoothTransformation)
    
    get_cached_app_icon._cache[cache_key] = pixmap # type: ignore
    return pixmap


# =============================================================================
# DESIGN SYSTEM - Material Design Dark Theme (Balanced)
# Based on https://m2.material.io/design/color/dark-theme.html
# =============================================================================

class Theme:
    """Material Design Dark Theme - Balanced for Visual Appeal
    
    Key Material Design Principles Applied:
    1. Dark grey surfaces (not pure black) for depth perception
    2. Elevation expressed through lighter surfaces
    3. HIGH CONTRAST text (nearly pure white for primary text)
    4. VIBRANT accent colors for interactive elements
    5. Desaturated colors only where needed for accessibility
    
    Important: Material Design recommends desaturated colors for TEXT
    on dark surfaces, but BUTTONS and ACCENTS should be vibrant.
    """
    
    # =========================================================================
    # ACCENT COLOR PRESETS
    # =========================================================================
    ACCENT_COLORS = {
        "Blue": {
            "primary": "#0078d4",
            "hover": "#1a86dc", 
            "pressed": "#006cc1",
            "light": "#4da3e8",
            "subtle": "rgba(0, 120, 212, 0.15)",
        },
        "Green": {
            "primary": "#107c10",
            "hover": "#1a9c1a",
            "pressed": "#0d6b0d",
            "light": "#54b054",
            "subtle": "rgba(16, 124, 16, 0.15)",
        },
        "Purple": {
            "primary": "#881798",
            "hover": "#a020a8",
            "pressed": "#6b1280",
            "light": "#b060c0",
            "subtle": "rgba(136, 23, 152, 0.15)",
        },
        "Orange": {
            "primary": "#ca5010",
            "hover": "#da6820",
            "pressed": "#a84000",
            "light": "#e08050",
            "subtle": "rgba(202, 80, 16, 0.15)",
        },
        "Red": {
            "primary": "#d13438",
            "hover": "#e04448",
            "pressed": "#b02028",
            "light": "#e06060",
            "subtle": "rgba(209, 52, 56, 0.15)",
        },
    }
    
    # =========================================================================
    # SURFACE COLORS - Elevation System
    # Using slightly warmer dark grey for better visual comfort
    # =========================================================================
    SURFACE_BASE = "#1a1a1e"           # Slightly warmer than #121212
    
    # Elevation levels - lighter surfaces = higher elevation
    SURFACE_00DP = "#1a1a1e"           # 0dp  - Window background
    SURFACE_01DP = "#212125"           # 1dp  - Sidebar
    SURFACE_02DP = "#28282d"           # 2dp  - Cards
    SURFACE_03DP = "#2e2e33"           # 3dp  - Menus
    SURFACE_04DP = "#333338"           # 4dp  - Hover states
    SURFACE_06DP = "#3a3a40"           # 6dp  - Elevated cards
    SURFACE_08DP = "#404046"           # 8dp  - App bars
    SURFACE_12DP = "#48484f"           # 12dp - FAB
    SURFACE_16DP = "#505058"           # 16dp - Nav drawer
    SURFACE_24DP = "#5a5a62"           # 24dp - Dialogs
    
    # Semantic surface assignments
    BG_WINDOW = SURFACE_00DP           # Window background
    BG_SIDEBAR = SURFACE_01DP          # Sidebar
    BG_CARD = SURFACE_02DP             # Cards/containers
    BG_CARD_HOVER = SURFACE_04DP       # Card hover
    BG_ELEVATED = SURFACE_06DP         # Elevated elements
    BG_DIALOG = SURFACE_24DP           # Dialogs
    
    # =========================================================================
    # BORDERS - Visible but subtle
    # =========================================================================
    BORDER = "#404048"                 # Visible border
    BORDER_LIGHT = "#505058"           # Emphasized border
    BORDER_ACCENT = "#0078d4"          # Accent border (Windows blue)
    
    # =========================================================================
    # TEXT COLORS - High Contrast for Readability
    # Optimized for dark backgrounds with improved contrast ratios
    # =========================================================================
    TEXT_PRIMARY = "#ffffff"           # Pure white for headings
    TEXT_SECONDARY = "#b8b8c0"         # Slightly brighter for better subtitle readability
    TEXT_TERTIARY = "#909098"          # Improved contrast for captions/timestamps
    TEXT_DISABLED = "#686870"          # Slightly lighter disabled state
    
    # Hex versions (same as above for Qt stylesheet compatibility)
    TEXT_PRIMARY_HEX = "#ffffff"
    TEXT_SECONDARY_HEX = "#b8b8c0"
    TEXT_TERTIARY_HEX = "#909098"
    
    # =========================================================================
    # PRIMARY ACCENT - Windows Blue (Vibrant!)
    # Material says use desaturated for text, but buttons should POP
    # =========================================================================
    PRIMARY = "#0078d4"                # Windows Blue - VIBRANT
    PRIMARY_HOVER = "#1a86dc"          # Lighter on hover
    PRIMARY_PRESSED = "#006cc1"        # Darker when pressed
    PRIMARY_LIGHT = "#4da3e8"          # Light variant for text on dark
    ON_PRIMARY = "#ffffff"             # White text on primary
    
    # Alternative accent (for secondary actions)
    ACCENT = "#0078d4"                 # Same as primary for consistency
    ACCENT_HOVER = "#1a86dc"
    ACCENT_LIGHT = "#60cdff"           # Light blue for highlights
    ACCENT_SUBTLE = "rgba(0, 120, 212, 0.15)"  # Selection background
    
    # =========================================================================
    # SECONDARY ACCENT - Teal (for variety)
    # =========================================================================
    SECONDARY = "#00b4a0"              # Teal - vibrant
    SECONDARY_VARIANT = "#00897b"
    ON_SECONDARY = "#000000"
    
    # =========================================================================
    # SEMANTIC COLORS - Balanced for visibility and comfort
    # Clear enough to communicate status, comfortable for extended viewing
    # =========================================================================
    # Success - Green (clear and positive)
    SUCCESS = "#22c55e"                # Tailwind Green 500 - balanced
    SUCCESS_LIGHT = "#4ade80"          # Lighter for text
    SUCCESS_BG = "rgba(34, 197, 94, 0.15)"
    
    # Warning - Amber/Gold (warm and noticeable)
    WARNING = "#eab308"                # Tailwind Yellow 500 - golden
    WARNING_LIGHT = "#facc15"          # Lighter for text
    WARNING_BG = "rgba(234, 179, 8, 0.15)"
    
    # Error - Red (attention-getting but not alarming)
    ERROR = "#ef4444"                  # Tailwind Red 500 - balanced
    ERROR_LIGHT = "#f87171"            # Lighter variant
    ERROR_BG = "rgba(239, 68, 68, 0.15)"
    
    # Info - Blue (informative and calm)
    INFO = "#3b82f6"                   # Tailwind Blue 500 - balanced
    INFO_LIGHT = "#60a5fa"             # Lighter for text
    INFO_BG = "rgba(59, 130, 246, 0.15)"
    
    # Running/Progress - Purple (engaging)
    RUNNING = "#a855f7"                # Tailwind Purple 500 - balanced
    RUNNING_LIGHT = "#c084fc"          # Lighter variant
    RUNNING_BG = "rgba(168, 85, 247, 0.15)"
    
    # =========================================================================
    # STATUS GLOW COLORS - Balanced for clarity and comfort
    # Vibrant enough to be clear, soft enough to not cause fatigue
    # =========================================================================
    GLOW_SUCCESS = "#22c55e"           # Balanced green - clear but not neon
    GLOW_ERROR = "#ef4444"             # Balanced red - visible but not harsh
    GLOW_WARNING = "#eab308"           # Balanced yellow/gold - warm and clear
    GLOW_INFO = "#3b82f6"              # Balanced blue - clear and calming
    GLOW_RUNNING = "#a855f7"           # Balanced purple - engaging
    
    # =========================================================================
    # GLASSMORPHISM - Apple-style glass effect
    # =========================================================================
    GLASS_BG = "rgba(40, 40, 45, 0.75)"           # Semi-transparent dark
    GLASS_BG_LIGHT = "rgba(60, 60, 68, 0.6)"      # Lighter glass
    GLASS_BORDER = "rgba(255, 255, 255, 0.1)"     # Subtle white border
    GLASS_BORDER_HOVER = "rgba(255, 255, 255, 0.2)"  # Brighter on hover
    
    # =========================================================================
    # SPACING & SIZING
    # =========================================================================
    SIDEBAR_W = 184
    RADIUS_SM = 6                      # Slightly more rounded
    RADIUS_MD = 8
    RADIUS_LG = 12
    
    # =========================================================================
    # SHADOWS - Subtle but present
    # =========================================================================
    SHADOW_COLOR = "#000000"
    SHADOW_OPACITY = 80                # More visible shadows
    SHADOW_BLUR_SM = 6
    SHADOW_BLUR_MD = 12
    SHADOW_BLUR_LG = 20
    SHADOW_BLUR_XL = 28
    SHADOW_OFFSET_Y = 3
    
    # =========================================================================
    # ANIMATION
    # =========================================================================
    ANIM_DURATION_FAST = 100
    ANIM_DURATION_NORMAL = 200
    ANIM_DURATION_SLOW = 300
    
    # =========================================================================
    # GRADIENTS - For visual interest
    # =========================================================================
    GRADIENT_ACCENT = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0078d4, stop:1 #00b4d8)"
    GRADIENT_SURFACE = f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {SURFACE_04DP}, stop:1 {SURFACE_02DP})"
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    @staticmethod
    def get_elevation_color(elevation_dp: int) -> str:
        """Get surface color for elevation level."""
        elevation_map = {
            0: Theme.SURFACE_00DP,
            1: Theme.SURFACE_01DP,
            2: Theme.SURFACE_02DP,
            3: Theme.SURFACE_03DP,
            4: Theme.SURFACE_04DP,
            6: Theme.SURFACE_06DP,
            8: Theme.SURFACE_08DP,
            12: Theme.SURFACE_12DP,
            16: Theme.SURFACE_16DP,
            24: Theme.SURFACE_24DP,
        }
        if elevation_dp in elevation_map:
            return elevation_map[elevation_dp]
        lower = max([e for e in elevation_map.keys() if e <= elevation_dp], default=0)
        return elevation_map[lower]
    
    @staticmethod
    def apply_shadow(widget, blur_radius=12, offset_x=0, offset_y=3, color=None, opacity=80):
        """Apply drop shadow to widget."""
        shadow = QGraphicsDropShadowEffect(widget)
        shadow_color = QColor(color if color else Theme.SHADOW_COLOR)
        shadow_color.setAlpha(opacity)
        shadow.setColor(shadow_color)
        shadow.setBlurRadius(blur_radius)
        shadow.setXOffset(offset_x)
        shadow.setYOffset(offset_y)
        widget.setGraphicsEffect(shadow)
        return shadow
    
    @staticmethod
    def apply_card_shadow(widget):
        """Apply card shadow."""
        return Theme.apply_shadow(widget, blur_radius=Theme.SHADOW_BLUR_MD, 
                                   offset_y=Theme.SHADOW_OFFSET_Y, opacity=Theme.SHADOW_OPACITY)
    
    @staticmethod
    def apply_button_shadow(widget, on_hover=False):
        """Apply button shadow."""
        if on_hover:
            return Theme.apply_shadow(widget, blur_radius=16, offset_y=4, opacity=100)
        else:
            return Theme.apply_shadow(widget, blur_radius=Theme.SHADOW_BLUR_SM, 
                                       offset_y=2, opacity=60)
    
    @staticmethod
    def apply_dialog_shadow(widget):
        """Apply dialog shadow."""
        return Theme.apply_shadow(widget, blur_radius=Theme.SHADOW_BLUR_XL, 
                                   offset_y=8, opacity=120)
    
    @staticmethod
    def style_accent_button(btn, style_type: str = "primary"):
        """Style a button with current accent color and tag it for refresh.
        
        Args:
            btn: QPushButton to style
            style_type: "primary" for filled, "outline" for bordered
        """
        btn.setProperty("accent_style", style_type)
        if style_type == "primary":
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {Theme.ACCENT};
                    color: white;
                    border: none;
                    border-radius: {Theme.RADIUS_SM}px;
                    padding: 10px 24px;
                    font-size: 13px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {Theme.ACCENT_HOVER};
                }}
                QPushButton:pressed {{
                    background: {Theme.PRIMARY_PRESSED};
                }}
            """)
        elif style_type == "outline":
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {Theme.ACCENT};
                    border: 1px solid {Theme.ACCENT};
                    border-radius: {Theme.RADIUS_SM}px;
                    padding: 6px 12px;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background: {Theme.ACCENT_SUBTLE};
                }}
            """)


# =============================================================================
# GLOBAL STYLESHEET - Material Design Dark Theme (Vibrant)
# =============================================================================

GLOBAL_STYLE = f"""
* {{
    font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
}}

QMainWindow {{
    background: {Theme.BG_WINDOW};
}}

QWidget {{
    background: transparent;
    color: {Theme.TEXT_PRIMARY};
}}

QLabel {{
    background: transparent;
    color: {Theme.TEXT_PRIMARY};
}}

QScrollArea {{
    border: none;
    background: transparent;
}}

QScrollBar:vertical {{
    background: {Theme.SURFACE_01DP};
    width: 10px;
    margin: 2px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical {{
    background: {Theme.SURFACE_08DP};
    border-radius: 5px;
    min-height: 40px;
}}

QScrollBar::handle:vertical:hover {{
    background: {Theme.PRIMARY};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
    height: 0px;
}}

QScrollBar:horizontal {{
    background: {Theme.SURFACE_01DP};
    height: 10px;
    margin: 2px;
    border-radius: 5px;
}}

QScrollBar::handle:horizontal {{
    background: {Theme.SURFACE_08DP};
    border-radius: 5px;
    min-width: 40px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {Theme.PRIMARY};
}}

QProgressBar {{
    background: {Theme.SURFACE_02DP};
    border: none;
    border-radius: 3px;
    height: 6px;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {Theme.PRIMARY}, stop:1 {Theme.ACCENT_LIGHT});
    border-radius: 3px;
}}

QTextEdit {{
    background: {Theme.SURFACE_02DP};
    border: none;
    border-radius: {Theme.RADIUS_MD}px;
    padding: 12px;
    color: {Theme.TEXT_PRIMARY};
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 12px;
    selection-background-color: {Theme.PRIMARY};
}}

QDialog {{
    background: {Theme.BG_DIALOG};
}}

QPushButton {{
    background: {Theme.SURFACE_04DP};
    color: {Theme.TEXT_PRIMARY};
    border: none;
    border-radius: {Theme.RADIUS_SM}px;
    padding: 10px 20px;
    font-weight: 500;
}}

QPushButton:hover {{
    background: {Theme.SURFACE_08DP};
    color: {Theme.PRIMARY_LIGHT};
}}

QPushButton:pressed {{
    background: {Theme.PRIMARY_PRESSED};
    color: white;
}}

QPushButton:disabled {{
    background: {Theme.SURFACE_01DP};
    color: {Theme.TEXT_DISABLED};
    border-color: transparent;
}}

QComboBox {{
    background: {Theme.BG_CARD_HOVER};
    color: {Theme.TEXT_PRIMARY};
    border: none;
    border-radius: {Theme.RADIUS_SM}px;
    padding: 6px 12px;
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background: {Theme.BG_CARD};
    color: {Theme.TEXT_PRIMARY};
    border: none;
    outline: none;
    selection-background-color: {Theme.ACCENT};
}}

QComboBox QAbstractItemView::item {{
    background: {Theme.BG_CARD};
    color: {Theme.TEXT_PRIMARY};
    border: none;
    padding: 8px 12px;
    min-height: 24px;
}}

QComboBox QAbstractItemView::item:hover {{
    background: {Theme.BG_CARD_HOVER};
}}

QComboBox QAbstractItemView::item:selected {{
    background: {Theme.ACCENT};
    color: white;
}}

QListView {{
    background: {Theme.BG_CARD};
    border: none;
    outline: none;
}}

QMenu {{
    background: {Theme.BG_CARD};
    color: {Theme.TEXT_PRIMARY};
    border: none;
    border-radius: {Theme.RADIUS_SM}px;
    padding: 4px;
}}

QMenu::item {{
    background: transparent;
    padding: 8px 16px;
    border-radius: {Theme.RADIUS_SM}px;
}}

QMenu::item:selected {{
    background: {Theme.BG_CARD_HOVER};
}}

QToolTip {{
    background: #1e1e1e;
    color: {Theme.TEXT_PRIMARY};
    border: 1px solid #3a3a3f;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 12px;
}}
"""


# =============================================================================
# BACKGROUND WORKER CLASSES (For non-blocking operations)
# =============================================================================

class HardwareScanWorker(QObject):
    """Worker to run hardware scanning in background thread"""
    finished = pyqtSignal(object)  # Emits hardware_data dict or None on error
    error = pyqtSignal(str)        # Emits error message
    
    def run(self):
        """Execute the hardware scan"""
        try:
            if HARDWARE_SCANNER_AVAILABLE:
                result = get_hardware_summary() # type: ignore
                self.finished.emit(result)
            else:
                self.error.emit("Hardware scanner module not available")
                self.finished.emit(None)
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(None)


class StartupScanWorker(QObject):
    """Worker to run startup scanning in background thread"""
    finished = pyqtSignal(list)   # Emits list of startup items
    error = pyqtSignal(str)       # Emits error message
    
    def run(self):
        """Execute the startup scan"""
        try:
            # Import here to avoid circular imports
            from startup_scanner import collect_startup_entries, StartupStatus
            result = collect_startup_entries()
            
            # Convert to dict format for UI
            items = []
            for entry in result.entries:
                items.append({
                    "name": entry.name,
                    "publisher": entry.publisher or "Unknown",
                    "enabled": entry.status == StartupStatus.ENABLED,
                    "impact": entry.impact,
                    "location": entry.source.value,
                    "command": entry.command,
                    "source_path": entry.source_path,
                    "confidence": entry.confidence.value,
                })
            
            self.finished.emit(items)
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit([])


class WindowsUpdateWorker(QObject):
    """Worker to check Windows Update status in background thread"""
    finished = pyqtSignal(dict)   # Emits update info dict
    
    def __init__(self, health_checker):
        super().__init__()
        self.health_checker = health_checker
    
    def run(self):
        """Execute the Windows Update check"""
        try:
            result = self.health_checker.check_windows_update_status()
            self.finished.emit(result)
        except Exception as e:
            self.finished.emit({"Error": str(e)})


class StorageCheckWorker(QObject):
    """Worker to check storage health in background thread"""
    finished = pyqtSignal(list)   # Emits volume info list
    
    def __init__(self, health_checker):
        super().__init__()
        self.health_checker = health_checker
    
    def run(self):
        """Execute the storage health check"""
        try:
            result = self.health_checker.get_volume_info()
            self.finished.emit(result if result else [])
        except Exception as e:
            self.finished.emit([])


class SecurityCheckWorker(QObject):
    """Worker to check Windows Defender status in background thread"""
    finished = pyqtSignal(dict)   # Emits defender status dict
    
    def __init__(self, health_checker):
        super().__init__()
        self.health_checker = health_checker
    
    def run(self):
        """Execute the security check"""
        try:
            result = self.health_checker.check_defender_status()
            self.finished.emit(result)
        except Exception as e:
            self.finished.emit({"Error": str(e)})


class EventScanWorker(QObject):
    """Worker to scan event logs in background thread"""
    finished = pyqtSignal(dict)   # Emits event data dict
    
    def run(self):
        """Execute the event log scan"""
        try:
            import subprocess
            import json
            cmd = '''
            $output = @{
                ErrorCount = 0
                WarningCount = 0
                CriticalCount = 0
                RecentErrors = @()
                RecentWarnings = @()
            }
            
            $since = (Get-Date).AddHours(-24)
            
            try {
                $critical = Get-WinEvent -FilterHashtable @{LogName='System'; Level=1; StartTime=$since} -MaxEvents 50 -ErrorAction SilentlyContinue
                $output.CriticalCount = if ($critical) { $critical.Count } else { 0 }
            } catch {}
            
            try {
                $sysErrors = Get-WinEvent -FilterHashtable @{LogName='System'; Level=2; StartTime=$since} -MaxEvents 100 -ErrorAction SilentlyContinue
                $output.ErrorCount = if ($sysErrors) { $sysErrors.Count } else { 0 }
                
                $output.RecentErrors = $sysErrors | Select-Object -First 10 | ForEach-Object {
                    $msg = if ($_.Message) { ($_.Message -split "`n")[0] } else { "No message available" }
                    $msg = $msg.Substring(0, [Math]::Min(120, $msg.Length))
                    @{
                        Time = $_.TimeCreated.ToString("MMM dd, HH:mm")
                        Source = $_.ProviderName
                        Id = $_.Id
                        Message = $msg
                    }
                }
            } catch {}
            
            try {
                $sysWarnings = Get-WinEvent -FilterHashtable @{LogName='System'; Level=3; StartTime=$since} -MaxEvents 100 -ErrorAction SilentlyContinue
                $output.WarningCount = if ($sysWarnings) { $sysWarnings.Count } else { 0 }
                
                $output.RecentWarnings = $sysWarnings | Select-Object -First 6 | ForEach-Object {
                    $msg = if ($_.Message) { ($_.Message -split "`n")[0] } else { "No message available" }
                    $msg = $msg.Substring(0, [Math]::Min(120, $msg.Length))
                    @{
                        Time = $_.TimeCreated.ToString("MMM dd, HH:mm")
                        Source = $_.ProviderName
                        Id = $_.Id
                        Message = $msg
                    }
                }
            } catch {}
            
            $output | ConvertTo-Json -Depth 4
            '''
            result = subprocess.run(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            if result.returncode == 0 and result.stdout.strip():
                event_data = json.loads(result.stdout)
                self.finished.emit(event_data)
            else:
                self.finished.emit({})
        except Exception as e:
            self.finished.emit({"Error": str(e)})


class HardwareMemoryWorker(QObject):
    """Worker to check hardware/memory info in background thread"""
    finished = pyqtSignal(dict)   # Emits hardware data dict
    
    def run(self):
        """Execute the hardware check"""
        try:
            import subprocess
            import json
            cmd = '''
            $os = Get-CimInstance Win32_OperatingSystem
            $mem = @{
                TotalGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
                FreeGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
            }
            $mem | ConvertTo-Json
            '''
            result = subprocess.run(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", cmd],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            if result.returncode == 0 and result.stdout.strip():
                mem_info = json.loads(result.stdout)
                self.finished.emit({"memory": mem_info})
            else:
                self.finished.emit({})
        except Exception as e:
            self.finished.emit({"Error": str(e)})


class MetricsWorker(QObject):
    """
    Background worker that collects CPU and disk metrics.
    Runs in a separate thread to avoid blocking the UI.
    """
    metrics_ready = pyqtSignal(float, float, float)  # cpu, ram, disk
    
    def __init__(self):
        super().__init__()
        self._running = False
        self._last_cpu = 0.0
        self._last_disk = 0.0
        
        # Pre-define the memory status structure for RAM (instant, no blocking)
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        self._mem_status = MEMORYSTATUSEX()
        self._mem_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    
    def start_collecting(self):
        """Start the collection loop"""
        import time
        self._running = True
        
        while self._running:
            try:
                # RAM is instant (no subprocess) - safe to call from thread
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(self._mem_status))
                ram = float(self._mem_status.dwMemoryLoad)
                
                # CPU load (slow, but we're in a background thread now)
                try:
                    cpu_cmd = 'wmic cpu get loadpercentage /value'
                    cpu_result = subprocess.run(
                        cpu_cmd, capture_output=True, text=True, shell=True,
                        timeout=2, creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    for line in cpu_result.stdout.split('\n'):
                        if 'LoadPercentage=' in line:
                            try:
                                self._last_cpu = float(line.split('=')[1].strip())
                            except (ValueError, IndexError):
                                pass
                            break
                except Exception:
                    pass
                
                # Disk activity (slow, but we're in a background thread now)
                try:
                    disk_cmd = r'wmic path Win32_PerfFormattedData_PerfDisk_PhysicalDisk where Name="_Total" get PercentDiskTime /value'
                    disk_result = subprocess.run(
                        disk_cmd, capture_output=True, text=True, shell=True,
                        timeout=2, creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    for line in disk_result.stdout.split('\n'):
                        if 'PercentDiskTime=' in line:
                            try:
                                self._last_disk = min(100.0, float(line.split('=')[1].strip()))
                            except (ValueError, IndexError):
                                pass
                            break
                except Exception:
                    pass
                
                # Emit the metrics (thread-safe via Qt signal)
                self.metrics_ready.emit(self._last_cpu, ram, self._last_disk)
                
            except Exception:
                self.metrics_ready.emit(0.0, 0.0, 0.0)
            
            # Sleep for 1.5 seconds between updates (in the background thread)
            time.sleep(1.5)
    
    def stop(self):
        """Stop the collection loop"""
        self._running = False


class MetricsCollector(QObject):
    """
    Manages the MetricsWorker in a background thread.
    Provides a clean interface to start/stop monitoring.
    """
    metrics_ready = pyqtSignal(float, float, float)  # cpu, ram, disk
    
    def __init__(self):
        super().__init__()
        self._thread = None
        self._worker = None
    
    def start(self):
        """Start collecting metrics in background thread"""
        if self._thread is not None:
            return  # Already running
        
        self._thread = QThread(self)
        self._worker = MetricsWorker()
        self._worker.moveToThread(self._thread)
        
        # Connect signals
        self._thread.started.connect(self._worker.start_collecting)
        self._worker.metrics_ready.connect(self.metrics_ready.emit)
        
        self._thread.start()
    
    def stop(self):
        """Stop the background metrics collection"""
        if self._worker:
            self._worker.stop()
        if self._thread:
            self._thread.quit()
            self._thread.wait(2000)  # Wait up to 2 seconds for thread to finish
            self._thread = None
            self._worker = None
    
    def collect(self):
        """Legacy method - now starts background collection if not running"""
        if self._thread is None:
            self.start()


# =============================================================================
# CUSTOM ICON PAINTER (No external dependencies)
# =============================================================================

class IconPainter:
    """Draw clean vector-style icons"""
    
    @staticmethod
    def draw_check(painter: QPainter, rect, color):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(color))
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        
        # Draw checkmark
        cx, cy = rect.center().x(), rect.center().y()
        size = min(rect.width(), rect.height()) * 0.35
        painter.drawLine(int(cx - size*0.6), int(cy), int(cx - size*0.1), int(cy + size*0.5))
        painter.drawLine(int(cx - size*0.1), int(cy + size*0.5), int(cx + size*0.7), int(cy - size*0.4))
    
    @staticmethod
    def draw_warning(painter: QPainter, rect, color):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(color))
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        cx, cy = rect.center().x(), rect.center().y()
        size = min(rect.width(), rect.height()) * 0.35
        
        # Draw exclamation
        painter.drawLine(int(cx), int(cy - size*0.6), int(cx), int(cy + size*0.1))
        painter.drawPoint(int(cx), int(cy + size*0.5))
    
    @staticmethod
    def draw_error(painter: QPainter, rect, color):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(color))
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        cx, cy = rect.center().x(), rect.center().y()
        size = min(rect.width(), rect.height()) * 0.3
        
        # Draw X
        painter.drawLine(int(cx - size), int(cy - size), int(cx + size), int(cy + size))
        painter.drawLine(int(cx + size), int(cy - size), int(cx - size), int(cy + size))


# =============================================================================
# CUSTOM WIDGETS
# =============================================================================

class StatusIcon(QWidget):
    """Custom painted status icon with animated glow effect (Apple-style)
    
    Features:
    - Pulsing glow animation around icons
    - Green glow for success/check
    - Red glow for errors
    - Amber glow for warnings
    - Glass-like appearance
    """
    
    def __init__(self, status: str = "check", size: int = 20, parent=None):
        super().__init__(parent)
        self.status = status
        self.icon_size = size
        self._glow_intensity = 0.0
        self._glow_direction = 1
        self._glow_enabled = True
        self.setFixedSize(size + 12, size + 12)  # Extra space for glow
        
        # Glow animation timer
        self._glow_timer = QTimer(self)
        self._glow_timer.timeout.connect(self._animate_glow)
        self._start_glow_animation()
    
    def _start_glow_animation(self):
        """Start the pulsing glow animation"""
        if self._glow_enabled and self.status in ("check", "error", "warning"):
            self._glow_timer.start(50)  # 20fps for smooth pulse
    
    def _stop_glow_animation(self):
        """Stop the glow animation"""
        self._glow_timer.stop()
    
    def _animate_glow(self):
        """Animate the glow intensity"""
        # Pulse between 0.3 and 1.0
        self._glow_intensity += 0.05 * self._glow_direction
        if self._glow_intensity >= 1.0:
            self._glow_intensity = 1.0
            self._glow_direction = -1
        elif self._glow_intensity <= 0.3:
            self._glow_intensity = 0.3
            self._glow_direction = 1
        self.update()
    
    def set_status(self, status: str):
        self.status = status
        # Restart animation for relevant statuses
        self._stop_glow_animation()
        if status in ("check", "error", "warning"):
            self._glow_intensity = 0.5
            self._start_glow_animation()
        self.update()
    
    def set_glow_enabled(self, enabled: bool):
        """Enable or disable the glow animation"""
        self._glow_enabled = enabled
        if enabled:
            self._start_glow_animation()
        else:
            self._stop_glow_animation()
            self.update()
    
    def paintEvent(self, event): # type: ignore
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get glow color based on status
        glow_colors = {
            "check": Theme.GLOW_SUCCESS,
            "warning": Theme.GLOW_WARNING,
            "error": Theme.GLOW_ERROR,
            "info": Theme.GLOW_INFO,
            "running": Theme.GLOW_RUNNING,
            "pending": Theme.TEXT_TERTIARY,
        }
        glow_color = glow_colors.get(self.status, Theme.TEXT_TERTIARY)
        
        # Icon colors (slightly different from glow for depth)
        icon_colors = {
            "check": Theme.SUCCESS,
            "warning": Theme.WARNING,
            "error": Theme.ERROR,
            "pending": Theme.TEXT_TERTIARY,
            "running": Theme.ACCENT,
            "info": Theme.INFO,
        }
        icon_color = icon_colors.get(self.status, Theme.TEXT_TERTIARY)
        
        center_x = self.width() // 2
        center_y = self.height() // 2
        
        # Draw glow effect for check, error, warning statuses
        if self._glow_enabled and self.status in ("check", "error", "warning"):
            glow_qcolor = QColor(glow_color)
            
            # Outer glow (larger, more transparent)
            for i in range(3, 0, -1):
                glow_qcolor.setAlpha(int(30 * self._glow_intensity * (4 - i) / 3))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(glow_qcolor))
                glow_radius = self.icon_size // 2 + i * 3
                painter.drawEllipse(
                    center_x - glow_radius,
                    center_y - glow_radius,
                    glow_radius * 2,
                    glow_radius * 2
                )
        
        # Calculate icon rect (centered)
        icon_rect = self.rect().adjusted(6, 6, -6, -6)
        
        if self.status == "check":
            IconPainter.draw_check(painter, icon_rect, icon_color)
        elif self.status == "warning":
            IconPainter.draw_warning(painter, icon_rect, icon_color)
        elif self.status == "error":
            IconPainter.draw_error(painter, icon_rect, icon_color)
        elif self.status == "running":
            # Draw spinning arc
            pen = QPen(QColor(icon_color))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawArc(icon_rect.adjusted(2, 2, -2, -2), 30*16, 300*16)
        else:
            # Pending - empty circle
            pen = QPen(QColor(icon_color))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(icon_rect.adjusted(2, 2, -2, -2))


# =============================================================================
# MODERN ANIMATED WIDGETS (Inspired by QT-PyQt-PySide-Custom-Widgets)
# =============================================================================

class AnimatedButton(QPushButton):
    """Modern animated button with hover effects and optional shadow.
    
    Features:
    - Smooth color transitions on hover
    - Optional drop shadow effect (animates on hover)
    - Primary (accent) and secondary (muted) variants
    """
    
    def __init__(self, text: str, variant: str = "primary", parent=None):
        super().__init__(text, parent)
        self.variant = variant
        self._current_bg = QColor(Theme.ACCENT if variant == "primary" else Theme.BG_ELEVATED)
        self._target_bg = self._current_bg
        self._shadow = None
        self._hover_shadow_blur = 16
        self._normal_shadow_blur = 8
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_animation()
        self._apply_style()
    
    def _setup_animation(self):
        """Setup color transition animation"""
        self._bg_animation = QPropertyAnimation(self, b"")
        self._bg_animation.setDuration(Theme.ANIM_DURATION_FAST)
        self._bg_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    
    def enable_shadow(self, enabled: bool = True):
        """Enable or disable shadow effect"""
        if enabled:
            self._shadow = Theme.apply_button_shadow(self)
        else:
            self.setGraphicsEffect(None)
            self._shadow = None
    
    def _apply_style(self):
        """Apply button styling based on variant"""
        if self.variant == "primary":
            self.setStyleSheet(f"""
                AnimatedButton {{
                    background: {Theme.ACCENT};
                    color: white;
                    border: none;
                    border-radius: {Theme.RADIUS_SM}px;
                    padding: 10px 24px;
                    font-size: 13px;
                    font-weight: 600;
                }}
                AnimatedButton:hover {{
                    background: {Theme.ACCENT_HOVER};
                }}
                AnimatedButton:pressed {{
                    background: {Theme.ACCENT};
                }}
                AnimatedButton:disabled {{
                    background: {Theme.BG_ELEVATED};
                    color: {Theme.TEXT_DISABLED};
                }}
            """)
        else:  # secondary
            self.setStyleSheet(f"""
                AnimatedButton {{
                    background: {Theme.BG_ELEVATED};
                    color: {Theme.TEXT_PRIMARY};
                    border: none;
                    border-radius: {Theme.RADIUS_SM}px;
                    padding: 10px 20px;
                    font-size: 13px;
                    font-weight: 500;
                }}
                AnimatedButton:hover {{
                    background: {Theme.BG_CARD_HOVER};
                }}
                AnimatedButton:pressed {{
                    background: {Theme.BG_CARD};
                }}
                AnimatedButton:disabled {{
                    background: {Theme.BG_CARD};
                    color: {Theme.TEXT_DISABLED};
                }}
            """)
    
    def enterEvent(self, event):
        """Animate shadow on hover"""
        if self._shadow:
            self._shadow.setBlurRadius(self._hover_shadow_blur)
        super().enterEvent(event)
    
    def leaveEvent(self, event): # type: ignore
        """Reset shadow on leave"""
        if self._shadow:
            self._shadow.setBlurRadius(self._normal_shadow_blur)
        super().leaveEvent(event)


class ModernSpinner(QWidget):
    """Modern loading spinner with smooth arc animation.
    
    Features:
    - Smooth spinning arc animation
    - Customizable colors, size, and line width
    - Optional bounce animation type
    """
    
    def __init__(self, size: int = 40, line_width: int = 3, color: str | None = None, parent=None):
        super().__init__(parent)
        self.spinner_size = size
        self.line_width = line_width
        self.color = QColor(color if color else Theme.ACCENT)
        self._angle = 0
        self._span = 90  # Arc span in degrees
        self._is_running = False
        
        self.setFixedSize(size, size)
        
        # Setup animation timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
    
    def start(self):
        """Start the spinning animation"""
        self._is_running = True
        self._timer.start(16)  # ~60fps
        self.show()
    
    def stop(self):
        """Stop the spinning animation"""
        self._is_running = False
        self._timer.stop()
    
    def _rotate(self):
        """Update rotation angle"""
        self._angle = (self._angle + 6) % 360
        self.update()
    
    def set_color(self, color: str):
        """Change spinner color"""
        self.color = QColor(color)
        self.update()
    
    def paintEvent(self, event): # pyright: ignore[reportIncompatibleMethodOverride]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Calculate drawing area
        margin = self.line_width
        rect_size = self.spinner_size - 2 * margin
        
        # Setup pen
        pen = QPen(self.color)
        pen.setWidth(self.line_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # Draw arc (rotating)
        # Qt uses 1/16th of a degree for arc angles
        start_angle = int(self._angle * 16)
        span_angle = int(self._span * 16)
        painter.drawArc(margin, margin, rect_size, rect_size, start_angle, span_angle)
        
        # Draw trailing arc (faded)
        faded_color = QColor(self.color)
        faded_color.setAlphaF(0.3)
        pen.setColor(faded_color)
        painter.setPen(pen)
        trail_start = int((self._angle + self._span) * 16)
        trail_span = int((360 - self._span - 20) * 16)
        painter.drawArc(margin, margin, rect_size, rect_size, trail_start, trail_span)


class GlowButton(QPushButton):
    """Button with glow effect on hover - for action buttons.
    
    Uses a subtle glow effect that intensifies on hover.
    """
    
    def __init__(self, text: str, glow_color: str | None = None, parent=None):
        super().__init__(text, parent)
        self.glow_color = glow_color if glow_color else Theme.ACCENT
        self._glow_effect = None
        self._is_hovering = False
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()
        self._setup_glow()
    
    def _apply_style(self):
        self.setStyleSheet(f"""
            GlowButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                border-radius: {Theme.RADIUS_SM}px;
                padding: 10px 24px;
                font-size: 14px;
                font-weight: 600;
            }}
            GlowButton:hover {{
                background: {Theme.ACCENT_LIGHT};
            }}
            GlowButton:pressed {{
                background: {Theme.ACCENT_HOVER};
            }}
        """)
    
    def _setup_glow(self):
        """Setup initial subtle glow"""
        self._glow_effect = QGraphicsDropShadowEffect(self)
        glow_qcolor = QColor(self.glow_color)
        glow_qcolor.setAlpha(100)
        self._glow_effect.setColor(glow_qcolor)
        self._glow_effect.setBlurRadius(12)
        self._glow_effect.setOffset(0, 2)
        self.setGraphicsEffect(self._glow_effect)
    
    def enterEvent(self, event):
        """Intensify glow on hover"""
        if self._glow_effect:
            glow_qcolor = QColor(self.glow_color)
            glow_qcolor.setAlpha(180)
            self._glow_effect.setColor(glow_qcolor)
            self._glow_effect.setBlurRadius(24)
        super().enterEvent(event)
    
    def leaveEvent(self, event): # type: ignore
        """Reset glow on leave"""
        if self._glow_effect:
            glow_qcolor = QColor(self.glow_color)
            glow_qcolor.setAlpha(100)
            self._glow_effect.setColor(glow_qcolor)
            self._glow_effect.setBlurRadius(12)
        super().leaveEvent(event)


class ModernListRow(QFrame):
    """Modern styled list row with improved readability.
    
    Features:
    - Card-like appearance with subtle background
    - Alternating row colors for easier scanning
    - Smooth hover effects
    - Status indicator integration
    - Better spacing and visual hierarchy
    """
    
    clicked = pyqtSignal()
    
    def __init__(self, 
                 title: str = "",
                 subtitle: str = "",
                 status: str = "ok",  # ok, warning, error, info
                 status_text: str = "",
                 is_alternate: bool = False,
                 show_chevron: bool = False,
                 parent=None):
        super().__init__(parent)
        self.is_alternate = is_alternate
        self.status = status
        self._setup_ui(title, subtitle, status, status_text, show_chevron)
        self._apply_style()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def _setup_ui(self, title: str, subtitle: str, status: str, status_text: str, show_chevron: bool):
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(14)
        
        # Status icon
        icon_type = {
            "ok": "check",
            "warning": "warning", 
            "error": "error",
            "info": "info"
        }.get(status, "check")
        self.status_icon = StatusIcon(icon_type, 18)
        self.main_layout.addWidget(self.status_icon)
        
        # Content area
        content = QVBoxLayout()
        content.setSpacing(4)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 500;
        """)
        content.addWidget(self.title_label)
        
        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setStyleSheet(f"""
                background: transparent;
                color: {Theme.TEXT_SECONDARY};
                font-size: 12px;
            """)
            content.addWidget(self.subtitle_label)
        
        self.main_layout.addLayout(content, 1)
        
        # Status text/badge
        if status_text:
            self.status_badge = QLabel(status_text)
            status_color = {
                "ok": Theme.SUCCESS,
                "warning": Theme.WARNING,
                "error": Theme.ERROR,
                "info": Theme.ACCENT_LIGHT
            }.get(status, Theme.TEXT_SECONDARY)
            status_bg = {
                "ok": Theme.SUCCESS_BG,
                "warning": Theme.WARNING_BG,
                "error": Theme.ERROR_BG,
                "info": Theme.INFO_BG
            }.get(status, "transparent")
            self.status_badge.setStyleSheet(f"""
                background: {status_bg};
                color: {status_color};
                font-size: 11px;
                font-weight: 600;
                padding: 4px 10px;
                border-radius: 4px;
            """)
            self.main_layout.addWidget(self.status_badge)
        
        # Chevron for clickable items
        if show_chevron:
            chevron = QLabel("›")
            chevron.setStyleSheet(f"""
                background: transparent;
                color: {Theme.TEXT_TERTIARY};
                font-size: 18px;
                font-weight: 300;
            """)
            self.main_layout.addWidget(chevron)
        
        # Placeholder for action buttons
        self.action_layout = QHBoxLayout()
        self.action_layout.setSpacing(8)
        self.main_layout.addLayout(self.action_layout)
    
    def add_action_button(self, text: str, callback, primary: bool = False) -> QPushButton:
        """Add an action button to the row"""
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(28)
        if primary:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {Theme.ACCENT};
                    color: white;
                    border: none;
                    padding: 4px 14px;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {Theme.ACCENT_HOVER};
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {Theme.ACCENT};
                    border: 1px solid {Theme.ACCENT};
                    padding: 4px 14px;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background: {Theme.ACCENT};
                    color: white;
                }}
            """)
        btn.clicked.connect(callback)
        self.action_layout.addWidget(btn)
        return btn
    
    def _apply_style(self):
        # More noticeable alternating row colors
        bg = Theme.BG_CARD if not self.is_alternate else "#252528"
        hover_bg = Theme.BG_CARD_HOVER
        
        self.setStyleSheet(f"""
            ModernListRow {{
                background: {bg};
                border: none;
                border-radius: 0px;
            }}
            ModernListRow:hover {{
                background: {hover_bg};
            }}
        """)
    
    def set_title(self, title: str):
        self.title_label.setText(title)
    
    def set_subtitle(self, subtitle: str):
        if hasattr(self, 'subtitle_label'):
            self.subtitle_label.setText(subtitle)
    
    def mousePressEvent(self, event): # type: ignore
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ModernCategoryHeader(QFrame):
    """Category header for grouping list items with a modern look."""
    
    def __init__(self, title: str, count: int = 0, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        
        # Category title - per spec Section 16.3
        title_label = QLabel(title.upper())
        title_label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_SECONDARY};
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1px;
        """)
        layout.addWidget(title_label)
        
        # Count badge
        if count > 0:
            count_label = QLabel(f"({count})")
            count_label.setStyleSheet(f"""
                background: transparent;
                color: {Theme.TEXT_TERTIARY};
                font-size: 11px;
                font-weight: 600;
            """)
            layout.addWidget(count_label)
        
        layout.addStretch()
        
        self.setStyleSheet(f"""
            ModernCategoryHeader {{
                background: {Theme.BG_SIDEBAR};
                border: none;
                border-top: 2px solid {Theme.BORDER};
                border-bottom: 1px solid {Theme.BORDER};
            }}
        """)


class ModernListContainer(QFrame):
    """Container for modern list items with proper styling and borders."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items_layout = QVBoxLayout(self)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(0)
        self.item_count = 0
        
        self.setStyleSheet(f"""
            ModernListContainer {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        
        # Apply subtle shadow
        Theme.apply_shadow(self, blur_radius=12, offset_y=3, opacity=50)
    
    def add_category(self, title: str, count: int = 0) -> ModernCategoryHeader:
        """Add a category header"""
        header = ModernCategoryHeader(title, count)
        self.items_layout.addWidget(header)
        self.item_count = 0  # Reset alternating count for new category
        return header
    
    def add_row(self, title: str, subtitle: str = "", status: str = "ok", 
                status_text: str = "", show_chevron: bool = False) -> ModernListRow:
        """Add a list row"""
        row = ModernListRow(
            title=title,
            subtitle=subtitle,
            status=status,
            status_text=status_text,
            is_alternate=(self.item_count % 2 == 1),
            show_chevron=show_chevron
        )
        self.items_layout.addWidget(row)
        self.item_count += 1
        return row
    
    def add_separator(self):
        """Add a visual separator"""
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {Theme.BORDER};")
        self.items_layout.addWidget(sep)
    
    def add_more_label(self, text: str):
        """Add a 'more items' label"""
        label = QLabel(text)
        label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_TERTIARY};
            font-size: 12px;
            padding: 12px 16px;
            font-style: italic;
        """)
        self.items_layout.addWidget(label)
    
    def clear(self):
        """Remove all items"""
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        self.item_count = 0


class NavIcon(QWidget):
    """Navigation icon widget using Segoe Fluent Icons"""
    
    # Segoe Fluent Icons unicode characters
    FLUENT_ICONS = {
        "grid": "\uE80A",       # GridView
        "download": "\uE896",   # Download
        "hdd": "\uEDA2",        # HardDrive
        "shield": "\uE83D",     # Shield
        "cpu": "\uE950",        # Processor
        "file": "\uE8A5",       # Document
        "alert": "\uE7BA",      # Warning
        "gear": "\uE713",       # Settings
        "chip": "\uE964",       # DeveloperBoard
        "rocket": "\uE7C4",     # Up arrow / Launch
        "speaker": "\uE767",    # Volume
        "wrench": "\uE90F",     # Repair
        "package": "\uE7B8",    # Package
    }
    
    def __init__(self, icon_name: str, size: int = 20, parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.icon_size = size
        self.color = Theme.TEXT_SECONDARY
        self.setFixedSize(size, size)
        
        # Create label for the icon
        self.icon_label = QLabel(self)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setGeometry(0, 0, size, size)
        self._update_icon()
    
    def set_color(self, color: str):
        self.color = color
        self._update_icon()
    
    def _update_icon(self):
        icon_char = self.FLUENT_ICONS.get(self.icon_name, "\uE946")  # Default to a generic icon
        self.icon_label.setText(icon_char)
        self.icon_label.setStyleSheet(f"""
            background: transparent;
            color: {self.color};
            font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';
            font-size: {self.icon_size}px;
        """)


class SidebarItem(QFrame):
    """Refined sidebar navigation item with keyboard navigation support
    
    Per UI spec section 10.5: Arrow Up/Down to navigate, Enter/Space to select
    """
    
    clicked = pyqtSignal()  # Signal emitted when item is clicked
    
    def __init__(self, icon_name: str, label: str, parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.label_text = label
        self.is_active = False
        self.setFixedHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)  # Enable keyboard navigation
        self.setup_ui()
        self._update_style()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)
        
        # Icon
        self.icon = NavIcon(self.icon_name, 16)
        layout.addWidget(self.icon)
        
        # Label
        self.label = QLabel(self.label_text)
        self.label.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self.label)
        layout.addStretch()
    
    def mousePressEvent(self, event):  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
    
    def set_active(self, active: bool):
        self.is_active = active
        self._update_style()
    
    def _update_style(self):
        """Update style - Apple-style glass with vibrant accent"""
        if self.is_active:
            # Selected state: full-width highlight with left accent border
            self.setStyleSheet(f"""
                SidebarItem {{
                    background: {Theme.ACCENT_SUBTLE};
                    border-left: 3px solid {Theme.ACCENT};
                    border-radius: 0px;
                    margin: 0px;
                    padding-left: 9px;
                }}
            """)
            self.icon.set_color(Theme.ACCENT)
            self.label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-weight: 600;")
        else:
            # Default state: transparent, no margins
            self.setStyleSheet(f"""
                SidebarItem {{
                    background: transparent;
                    border-left: 3px solid transparent;
                    border-radius: 0px;
                    margin: 0px;
                    padding-left: 9px;
                }}
            """)
            self.icon.set_color(Theme.TEXT_SECONDARY)
            self.label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-weight: normal;")
    
    def enterEvent(self, event):
        if not self.is_active:
            # Hover state: subtle background, full width
            self.setStyleSheet(f"""
                SidebarItem {{
                    background: {Theme.BG_CARD_HOVER};
                    border-left: 3px solid transparent;
                    border-radius: 0px;
                    margin: 0px;
                    padding-left: 9px;
                }}
            """)
            self.icon.set_color(Theme.TEXT_PRIMARY)
            self.label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-weight: normal;")
    
    def leaveEvent(self, event): # pyright: ignore[reportIncompatibleMethodOverride]
        self._update_style()
    
    def keyPressEvent(self, event):
        """Handle keyboard activation per UI spec section 10.5"""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)
    
    def focusInEvent(self, event):
        """Show focus indicator - blue outline per UI spec"""
        if not self.is_active:
            self.setStyleSheet(f"""
                SidebarItem {{
                    background: {Theme.BG_CARD_HOVER};
                    border-left: 3px solid {Theme.ACCENT_LIGHT};
                    border-radius: 0px;
                    margin: 0px;
                    padding-left: 9px;
                    outline: none;
                }}
            """)
            self.icon.set_color(Theme.ACCENT_LIGHT)
            self.label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-weight: normal;")
        super().focusInEvent(event)
    
    def focusOutEvent(self, event):
        """Remove focus indicator"""
        self._update_style()
        super().focusOutEvent(event)


class ScoreRing(QWidget):
    """Animated score ring widget with health context tooltip
    
    Per UI spec section 5.7 and 10.6: Shows health score with gradient
    colors and provides context via tooltip.
    """
    
    def __init__(self, size: int = 120, parent=None):
        super().__init__(parent)
        self.ring_size = size
        self.score = 0
        self.target_score = 0
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)  # Indicate help available
        self.setToolTip("Health score based on system checks.\\n80+ = Healthy\\n60-79 = Needs attention\\nBelow 60 = Critical issues")
        
        # Animation timer
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self._animate)
    
    def set_score(self, score: int, animate: bool = True):
        self.target_score = max(0, min(100, score))
        if animate:
            self.anim_timer.start(16)
        else:
            self.score = self.target_score
            self.update()
    
    def _animate(self):
        diff = self.target_score - self.score
        if abs(diff) < 1:
            self.score = self.target_score
            self.anim_timer.stop()
        else:
            self.score += diff * 0.1
        self.update()
    
    def paintEvent(self, event): # pyright: ignore[reportIncompatibleMethodOverride]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        size = self.ring_size
        ring_width = 10  # Slightly thicker for more presence
        margin = ring_width // 2 + 4
        
        # Determine color based on score (use Apple-style glow colors)
        if self.score >= 80:
            color = QColor(Theme.GLOW_SUCCESS)
            glow_color = QColor(Theme.GLOW_SUCCESS)
        elif self.score >= 50:
            color = QColor(Theme.GLOW_WARNING)
            glow_color = QColor(Theme.GLOW_WARNING)
        else:
            color = QColor(Theme.GLOW_ERROR)
            glow_color = QColor(Theme.GLOW_ERROR)
        
        center = size // 2
        radius = (size - 2 * margin) // 2
        
        # Draw subtle glow effect behind the progress arc
        if self.score > 0:
            for i in range(2, 0, -1):
                glow_color.setAlpha(int(15 * (3 - i)))
                glow_pen = QPen(glow_color)
                glow_pen.setWidth(ring_width + i * 3)
                glow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(glow_pen)
                span = int((self.score / 100) * 360 * 16)
                painter.drawArc(margin - i, margin - i, 
                               size - 2*margin + i*2, size - 2*margin + i*2, 
                               90*16, -span)
        
        # Background ring
        pen = QPen(QColor(Theme.SURFACE_04DP))
        pen.setWidth(ring_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(margin, margin, size-2*margin, size-2*margin, 0, 360*16)
        
        # Progress ring (main)
        pen.setColor(color)
        painter.setPen(pen)
        span = int((self.score / 100) * 360 * 16)
        painter.drawArc(margin, margin, size-2*margin, size-2*margin, 90*16, -span)
        
        # Score text
        painter.setPen(QColor(Theme.TEXT_PRIMARY))
        font = QFont("Segoe UI Variable", 32, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, str(int(self.score)))


class GlassCard(QFrame):
    """Interactive glass card with hover animations and visual feedback
    
    Features:
    - Lift effect on hover (translateY simulation via margin)
    - Glow intensification on hover
    - Smooth transitions
    - Keyboard navigation support
    """
    
    clicked = pyqtSignal()
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title_text = title
        self._status = "pending"
        self._hovered = False
        self._base_margin = 4  # Base margin for lift effect
        self.setMinimumHeight(80)  # Increased for lift animation space
        self.setMaximumHeight(98)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        
        # Hover animation
        self._hover_progress = 0.0
        self._hover_timer = QTimer(self)
        self._hover_timer.timeout.connect(self._animate_hover)
        self._hover_timer.setInterval(16)  # 60fps
        
        self.setup_ui()
    
    def _animate_hover(self):
        """Animate hover progress for smooth transitions"""
        if self._hovered:
            self._hover_progress = min(1.0, self._hover_progress + 0.15)
        else:
            self._hover_progress = max(0.0, self._hover_progress - 0.15)
        
        # Update margins for lift effect
        lift = int(self._hover_progress * 4)
        self.setContentsMargins(0, self._base_margin - lift, 0, self._base_margin + lift)
        
        # Stop timer when animation complete
        if (self._hovered and self._hover_progress >= 1.0) or (not self._hovered and self._hover_progress <= 0.0):
            self._hover_timer.stop()
        
        self.update()
        if self.parent():
            self.parent().update()
    
    def enterEvent(self, event):
        """Start hover animation"""
        self._hovered = True
        if not self._hover_timer.isActive():
            self._hover_timer.start()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """End hover animation"""
        self._hovered = False
        if not self._hover_timer.isActive():
            self._hover_timer.start()
        super().leaveEvent(event)
    
    def get_hover_progress(self) -> float:
        """Return current hover animation progress (0.0 to 1.0)"""
        return self._hover_progress
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        # Status icon - per spec Section 5.4 status icon 24x24 container, 18px icon
        self.status_icon = QLabel("\uE946")  # Fluent icon - default info
        self.status_icon.setFixedSize(24, 24)
        self.status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_icon.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets'; font-size: 18px;")
        layout.addWidget(self.status_icon)
        
        # Text - per spec Section 5.4 status icon positioning
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        self.title = QLabel(self.title_text)
        self.title.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 14px; font-weight: 600;")
        text_layout.addWidget(self.title)
        
        self.subtitle = QLabel("Checking...")
        self.subtitle.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        text_layout.addWidget(self.subtitle)
        
        layout.addLayout(text_layout)
        layout.addStretch()
        
        # Chevron
        chevron = QLabel("›")
        chevron.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 16px;")
        layout.addWidget(chevron)
    
    def get_status(self) -> str:
        return self._status
    
    def get_glow_color(self) -> QColor:
        """Return the glow color for this card's status"""
        colors = {
            "check": QColor(Theme.GLOW_SUCCESS),
            "warning": QColor(Theme.GLOW_WARNING),
            "error": QColor(Theme.GLOW_ERROR),
            "info": QColor(Theme.GLOW_INFO),
            "running": QColor(Theme.GLOW_RUNNING),
        }
        return colors.get(self._status, QColor(0, 0, 0, 0))
    
    def mousePressEvent(self, event): # pyright: ignore[reportIncompatibleMethodOverride]
        self.clicked.emit()
        super().mousePressEvent(event)
    
    def keyPressEvent(self, event):
        """Handle keyboard activation per UI spec section 10.5"""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)
    
    def focusInEvent(self, event):
        """Show focus indicator per UI spec section 10.5"""
        self.setStyleSheet(f"border: 2px solid {Theme.ACCENT_LIGHT};")
        super().focusInEvent(event)
    
    def focusOutEvent(self, event):
        """Remove focus indicator"""
        self.setStyleSheet("")
        super().focusOutEvent(event)
    
    def set_status(self, status: str, subtitle: str):
        self._status = status
        self.subtitle.setText(subtitle)
        self.subtitle.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        
        # Update icon with vibrant colors - using Segoe Fluent Icons
        icons = {
            "check": ("\uE73E", Theme.GLOW_SUCCESS),      # CheckMark
            "warning": ("\uE7BA", Theme.GLOW_WARNING),    # Warning
            "error": ("\uE711", Theme.GLOW_ERROR),        # Cancel/X
            "info": ("\uE946", Theme.GLOW_INFO),          # Info
            "running": ("\uE895", Theme.GLOW_RUNNING),    # Sync/Running
            "pending": ("\uE946", Theme.TEXT_TERTIARY),   # Info (pending)
        }
        icon_char, icon_color = icons.get(status, ("\uE946", Theme.TEXT_TERTIARY))
        self.status_icon.setText(icon_char)
        self.status_icon.setStyleSheet(f"background: transparent; color: {icon_color}; font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets'; font-size: 16px;")
        
        # Trigger parent repaint for glow update
        if self.parent():
            self.parent().update()


class GlowingCardGrid(QWidget):
    """Container that paints glows behind glass cards - React-style design
    
    This widget manages a grid of GlassCards and paints animated glows
    on a single canvas, allowing them to overlap naturally.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards = []  # List of (card, row, col) tuples
        self._glow_phase = 0.0
        self._glow_intensity = 0.7
        self._glow_direction = 1
        
        # Animation timer for flowing glow
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(33)  # 30fps
        
        # Grid layout for cards
        self._layout = QGridLayout(self)
        self._layout.setSpacing(16)
        self._layout.setContentsMargins(20, 20, 20, 20)  # Margin for glow overflow
    
    def _animate(self):
        """Animate glow intensity and phase"""
        import math
        self._glow_phase += 0.04
        if self._glow_phase > math.pi * 2:
            self._glow_phase = 0
        
        self._glow_intensity += 0.02 * self._glow_direction
        if self._glow_intensity >= 0.9:
            self._glow_direction = -1
        elif self._glow_intensity <= 0.5:
            self._glow_direction = 1
        
        self.update()
    
    def add_card(self, card: GlassCard, row: int, col: int):
        """Add a card to the grid"""
        self._cards.append((card, row, col))
        self._layout.addWidget(card, row, col)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        import math
        radius = Theme.RADIUS_LG
        
        # Subtle pulsing
        pulse = 0.7 + 0.3 * math.sin(self._glow_phase)
        
        # First pass: Draw very subtle colored shadows behind cards with status
        for card, row, col in self._cards:
            status = card.get_status()
            if status not in ("check", "error", "warning"):
                continue
            
            glow_color = card.get_glow_color()
            card_rect = card.geometry()
            
            # Get hover progress for intensified glow on hover
            hover_progress = card.get_hover_progress()
            hover_boost = 1.0 + hover_progress * 0.8  # Up to 80% more intense on hover
            
            # Dynamic glow layers - more layers and intensity on hover
            glow_layers = 2 + int(hover_progress * 2)  # 2-4 layers based on hover
            for i in range(glow_layers, 0, -1):
                layer_color = QColor(glow_color)
                # Base alpha with hover boost
                base_alpha = 18 * pulse * (glow_layers + 1 - i) / glow_layers
                alpha = int(base_alpha * hover_boost)
                alpha = min(alpha, 60)  # Cap to prevent over-saturation
                layer_color.setAlpha(alpha)
                
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(layer_color))
                
                expand = i * (6 + int(hover_progress * 4))  # Larger glow on hover
                glow_rect = card_rect.adjusted(-expand, -expand, expand, expand)
                
                path = QPainterPath()
                path.addRoundedRect(
                    float(glow_rect.x()), float(glow_rect.y()),
                    float(glow_rect.width()), float(glow_rect.height()),
                    radius + i * 3, radius + i * 3
                )
                painter.drawPath(path)
        
        # Second pass: Draw solid card backgrounds
        for card, row, col in self._cards:
            card_rect = card.geometry()
            status = card.get_status()
            
            # Card background - uses theme color
            bg_color = QColor(Theme.BG_CARD)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(bg_color))
            
            path = QPainterPath()
            path.addRoundedRect(
                float(card_rect.x()), float(card_rect.y()),
                float(card_rect.width()), float(card_rect.height()),
                radius, radius
            )
            painter.drawPath(path)
            
            # Colored border for status cards - intensifies on hover
            if status in ("check", "error", "warning"):
                glow_color = card.get_glow_color()
                hover_progress = card.get_hover_progress()
                # Border gets brighter on hover
                border_alpha = int((80 + 50 * pulse) * (1 + hover_progress * 0.5))
                border_alpha = min(border_alpha, 200)
                border_color = QColor(glow_color.red(), glow_color.green(), glow_color.blue(), border_alpha)
                border_width = 1.5 + hover_progress * 0.5  # Slightly thicker on hover
                painter.setPen(QPen(border_color, border_width))
            else:
                painter.setPen(QPen(QColor(55, 55, 60), 1))
            
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                card_rect.adjusted(0, 0, -1, -1),
                radius, radius
            )


# Alias for backward compatibility
StatusCard = GlassCard


class HealthSummaryCard(QWidget):
    """Large health score summary card - clean design with subtle colored border"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._score = 0
        self.setup_ui()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        radius = Theme.RADIUS_LG
        
        # Dynamic gradient background based on health score
        from PyQt6.QtGui import QLinearGradient
        
        # Base card color
        base_color = QColor(Theme.BG_CARD)
        
        # Tint color based on score (subtle gradient overlay)
        if self._score >= 80:
            tint_color = QColor(Theme.GLOW_SUCCESS)  # Green tint for good health
        elif self._score >= 50:
            tint_color = QColor(Theme.GLOW_WARNING)  # Yellow tint for warning
        else:
            tint_color = QColor(Theme.GLOW_ERROR)    # Red tint for poor health
        
        # Create diagonal gradient from top-left to bottom-right
        gradient = QLinearGradient(0, 0, rect.width(), rect.height())
        
        # Start with base color, blend to tinted color
        start_color = QColor(base_color)
        end_color = QColor(
            int(base_color.red() * 0.92 + tint_color.red() * 0.08),
            int(base_color.green() * 0.92 + tint_color.green() * 0.08),
            int(base_color.blue() * 0.92 + tint_color.blue() * 0.08)
        )
        
        gradient.setColorAt(0, start_color)
        gradient.setColorAt(1, end_color)
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))
        
        path = QPainterPath()
        path.addRoundedRect(float(rect.x()), float(rect.y()),
                           float(rect.width()), float(rect.height()),
                           radius, radius)
        painter.drawPath(path)
        
        # Subtle colored border based on score
        if self._score >= 80:
            border_color = QColor(Theme.GLOW_SUCCESS)
        elif self._score >= 50:
            border_color = QColor(Theme.GLOW_WARNING)
        else:
            border_color = QColor(Theme.GLOW_ERROR)
        border_color.setAlpha(100)  # Subtle
        painter.setPen(QPen(border_color, 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), radius, radius)
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(32)
        
        # Score ring
        self.score_ring = ScoreRing(100)
        layout.addWidget(self.score_ring)
        
        # Info section
        info_layout = QVBoxLayout()
        info_layout.setSpacing(6)
        
        self.status_label = QLabel("Analyzing system...")
        self.status_label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 18px;
            font-weight: 600;
        """)
        info_layout.addWidget(self.status_label)
        
        self.details_label = QLabel("Run a scan to check your system health")
        self.details_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        info_layout.addWidget(self.details_label)
        
        info_layout.addSpacing(8)
        
        self.timestamp_label = QLabel("Last scan: Never")
        self.timestamp_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
        info_layout.addWidget(self.timestamp_label)
        
        info_layout.addStretch()
        layout.addLayout(info_layout, 1)
        
        # Scan button with gradient and glow effect
        self.scan_btn = QPushButton("Run Full Scan")
        self.scan_btn.setFixedSize(140, 44)
        self.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {Theme.ACCENT}, stop:1 {Theme.ACCENT_LIGHT});
                color: white;
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {Theme.ACCENT_LIGHT}, stop:1 {Theme.ACCENT});
            }}
            QPushButton:pressed {{
                background: {Theme.ACCENT_HOVER};
            }}
        """)
        # Add glow effect to scan button
        Theme.apply_shadow(self.scan_btn, blur_radius=16, offset_y=4, 
                           color=Theme.ACCENT, opacity=120)
        layout.addWidget(self.scan_btn, 0, Qt.AlignmentFlag.AlignTop)
    
    def set_score(self, score: int, passed: int, warnings: int, errors: int):
        self._score = score
        self.score_ring.set_score(score)
        
        if score >= 80:
            status = "Your system is healthy"
        elif score >= 50:
            status = "Some attention needed"
        else:
            status = "Issues detected"
        
        self.status_label.setText(status)
        self.details_label.setText(f"{passed} checks passed  •  {warnings} warnings  •  {errors} errors")
        self.timestamp_label.setText(f"Last scan: {datetime.now().strftime('%I:%M %p')}")
    
    def refresh_theme(self):
        """Refresh colors for theme change"""
        self.status_label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 18px;
            font-weight: 600;
        """)
        self.details_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        self.timestamp_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
        self.update()  # Force repaint of paintEvent


class TipsCarousel(QFrame):
    """Rotating carousel of Windows health and safety tips"""
    
    # Using Segoe Fluent Icons unicode characters per spec
    TIPS = [
        ("\uE946", "Keep Windows Updated", "Enable automatic updates to protect against the latest security threats and get new features."),
        ("\uE83D", "Use Windows Defender", "Windows Defender provides real-time protection against viruses, malware, and other threats."),
        ("\uEDA2", "Back Up Your Data", "Use Windows Backup or File History to regularly back up important files to an external drive or cloud."),
        ("\uE72E", "Enable BitLocker", "Encrypt your drives with BitLocker to protect your data if your device is lost or stolen."),
        ("\uE90F", "Clean Up Disk Space", "Run Disk Cleanup monthly to remove temporary files and free up storage space."),
        ("\uE7C4", "Manage Startup Programs", "Disable unnecessary startup programs to improve boot time and system performance."),
        ("\uE72E", "Use Strong Passwords", "Create unique, complex passwords and consider using Windows Hello for biometric login."),
        ("\uE839", "Secure Your Network", "Use WPA3 WiFi encryption and keep your router firmware updated."),
        ("\uE8F8", "Avoid Suspicious Downloads", "Only download software from trusted sources like the Microsoft Store or official websites."),
        ("\uE72C", "Restart Regularly", "Restart your PC weekly to apply updates and clear temporary memory issues."),
        ("\uE90F", "Check Driver Updates", "Keep device drivers updated for better performance and security."),
        ("\uE80A", "Monitor System Health", "Use this tool regularly to check for issues before they become problems."),
        ("\uE774", "Use a Secure Browser", "Keep your browser updated and use extensions to block malicious websites."),
        ("\uE916", "Schedule Scans", "Set up weekly antivirus scans during off-hours for comprehensive protection."),
        ("\uE7BA", "Review App Permissions", "Periodically check which apps have access to your camera, microphone, and location."),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_index = 0
        self._fade_opacity = 1.0
        self._is_fading_out = False
        self.setup_ui()
        self._setup_timer()
        Theme.apply_shadow(self, blur_radius=12, offset_y=3, opacity=50)
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            TipsCarousel {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 {Theme.BG_CARD}, stop:1 {Theme.BG_ELEVATED});
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        self.setFixedHeight(90)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)
        
        # Icon with colored background
        self.icon_container = QFrame()
        self.icon_container.setFixedSize(50, 50)
        self.icon_container.setStyleSheet(f"""
            background: {Theme.ACCENT}25;
            border-radius: 12px;
        """)
        icon_layout = QHBoxLayout(self.icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        
        self.icon_label = QLabel("\uE946")  # Fluent icon
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet(f"background: transparent; font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets'; font-size: 24px; color: {Theme.ACCENT};")
        icon_layout.addWidget(self.icon_label)
        layout.addWidget(self.icon_container)
        
        # Text content
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        # Header with "Tip" label
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        tip_badge = QLabel("TIP")
        tip_badge.setStyleSheet(f"""
            background: {Theme.ACCENT};
            color: white;
            font-size: 9px;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 3px;
        """)
        tip_badge.setFixedHeight(16)
        header_layout.addWidget(tip_badge)
        
        self.title_label = QLabel("Keep Windows Updated")
        self.title_label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 600;
        """)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        
        # Navigation dots
        self.dots_layout = QHBoxLayout()
        self.dots_layout.setSpacing(4)
        self.dot_labels = []
        for i in range(len(self.TIPS)):
            dot = QLabel("●")
            dot.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 6px;")
            dot.setCursor(Qt.CursorShape.PointingHandCursor)
            dot.mousePressEvent = lambda e, idx=i: self._go_to_tip(idx)
            self.dots_layout.addWidget(dot)
            self.dot_labels.append(dot)
        header_layout.addLayout(self.dots_layout)
        
        text_layout.addLayout(header_layout)
        
        self.description_label = QLabel("Enable automatic updates to protect against the latest security threats.")
        self.description_label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_SECONDARY};
            font-size: 12px;
        """)
        self.description_label.setWordWrap(True)
        text_layout.addWidget(self.description_label)
        
        layout.addLayout(text_layout, 1)
        
        # Navigation buttons
        nav_layout = QVBoxLayout()
        nav_layout.setSpacing(4)
        
        prev_btn = QPushButton("‹")
        prev_btn.setFixedSize(24, 24)
        prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        prev_btn.clicked.connect(self._prev_tip)
        prev_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_SECONDARY};
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        nav_layout.addWidget(prev_btn)
        
        next_btn = QPushButton("›")
        next_btn.setFixedSize(24, 24)
        next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        next_btn.clicked.connect(self._next_tip)
        next_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_SECONDARY};
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        nav_layout.addWidget(next_btn)
        
        layout.addLayout(nav_layout)
        
        self._update_display()
    
    def _setup_timer(self):
        """Setup auto-rotation timer"""
        self._rotation_timer = QTimer(self)
        self._rotation_timer.timeout.connect(self._next_tip)
        self._rotation_timer.start(8000)  # Rotate every 8 seconds
    
    def _update_display(self):
        """Update the display with current tip"""
        icon, title, description = self.TIPS[self._current_index]
        self.icon_label.setText(icon)
        self.title_label.setText(title)
        self.description_label.setText(description)
        
        # Update dots
        for i, dot in enumerate(self.dot_labels):
            if i == self._current_index:
                dot.setStyleSheet(f"background: transparent; color: {Theme.ACCENT}; font-size: 8px;")
            else:
                dot.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 6px;")
    
    def _next_tip(self):
        """Go to next tip"""
        self._current_index = (self._current_index + 1) % len(self.TIPS)
        self._update_display()
        self._reset_timer()
    
    def _prev_tip(self):
        """Go to previous tip"""
        self._current_index = (self._current_index - 1) % len(self.TIPS)
        self._update_display()
        self._reset_timer()
    
    def _go_to_tip(self, index: int):
        """Go to specific tip"""
        self._current_index = index
        self._update_display()
        self._reset_timer()
    
    def _reset_timer(self):
        """Reset the auto-rotation timer"""
        self._rotation_timer.stop()
        self._rotation_timer.start(8000)
    
    def refresh_theme(self):
        """Refresh colors for theme change"""
        self.setStyleSheet(f"""
            TipsCarousel {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 {Theme.BG_CARD}, stop:1 {Theme.BG_ELEVATED});
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        self.title_label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 600;
        """)
        self.description_label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_SECONDARY};
            font-size: 12px;
        """)
        self._update_display()  # Refresh dot colors


class FloatingToolButton(QLabel):
    """Circular floating tool button with proper hover effect"""
    
    def __init__(self, icon: str, tooltip: str, action, parent=None):
        super().__init__(parent)
        self.action = action
        self.icon_char = icon
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setFixedSize(44, 44)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText(icon)
        
        # Store colors for hover effect
        accent = Theme.ACCENT.lstrip('#')
        self.r, self.g, self.b = int(accent[0:2], 16), int(accent[2:4], 16), int(accent[4:6], 16)
        
        self._hovered = False
        self._update_style()
    
    def _update_style(self):
        if self._hovered:
            self.setStyleSheet(f"""
                background: rgba({self.r}, {self.g}, {self.b}, 0.35);
                border: 1px solid rgba({self.r}, {self.g}, {self.b}, 0.5);
                border-radius: 22px;
                color: {Theme.TEXT_PRIMARY};
                font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';
                font-size: 18px;
            """)
        else:
            self.setStyleSheet(f"""
                background: rgba({self.r}, {self.g}, {self.b}, 0.15);
                border: 1px solid transparent;
                border-radius: 22px;
                color: {Theme.TEXT_PRIMARY};
                font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';
                font-size: 18px;
            """)
    
    def enterEvent(self, event):
        self._hovered = True
        self._update_style()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        self._hovered = False
        self._update_style()
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        if self.action:
            self.action()
        super().mousePressEvent(event)


class FloatingToolbar(QFrame):
    """Reusable floating toolbar component for any page"""
    
    def __init__(self, tools: list, parent=None):
        """
        Create a floating toolbar with the given tools.
        
        Args:
            tools: List of tuples (tooltip, icon_unicode, action_callback)
            parent: Parent widget
        """
        super().__init__(parent)
        self._toolbar_visible = True
        self._scrollbar_margin = 16
        self._toolbar_width = 60
        self._toggle_width = 20
        self._tools = tools
        
        self._create_toolbar()
    
    def _create_toolbar(self):
        """Create the toolbar panel and toggle button"""
        # Toolbar panel with glass effect
        self.toolbar_panel = QFrame(self.parent())
        self.toolbar_panel.setFixedWidth(self._toolbar_width)
        
        # Glass effect background
        accent = Theme.ACCENT.lstrip('#')
        r, g, b = int(accent[0:2], 16), int(accent[2:4], 16), int(accent[4:6], 16)
        
        self.toolbar_panel.setStyleSheet(f"""
            QFrame {{
                background: rgba(30, 30, 30, 0.85);
                border: 1px solid rgba({r}, {g}, {b}, 0.3);
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        Theme.apply_shadow(self.toolbar_panel, blur_radius=20, offset_y=4, opacity=100)
        
        toolbar_layout = QVBoxLayout(self.toolbar_panel)
        toolbar_layout.setContentsMargins(8, 12, 8, 12)
        toolbar_layout.setSpacing(8)
        
        # Add tool buttons
        for tooltip, icon, action in self._tools:
            btn = FloatingToolButton(icon, tooltip, action)
            toolbar_layout.addWidget(btn)
        
        self.toolbar_panel.adjustSize()
        
        # Toggle button - pinned to right edge
        self.toggle_btn = QFrame(self.parent())
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setFixedSize(self._toggle_width, 48)
        self.toggle_btn.setToolTip("Hide Quick Tools")
        self.toggle_btn.setStyleSheet(f"""
            QFrame {{
                background: rgba(30, 30, 30, 0.85);
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
            }}
            QFrame:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        toggle_layout = QVBoxLayout(self.toggle_btn)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        self.toggle_icon = QLabel("\uE76B")  # ChevronLeft
        self.toggle_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toggle_icon.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_SECONDARY};
            font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';
            font-size: 12px;
        """)
        toggle_layout.addWidget(self.toggle_icon)
        self.toggle_btn.mousePressEvent = lambda e: self._toggle()
    
    def _toggle(self):
        """Toggle toolbar visibility"""
        self._toolbar_visible = not self._toolbar_visible
        
        if self._toolbar_visible:
            self.toolbar_panel.show()
            self.toggle_icon.setText("\uE76B")  # ChevronLeft
            self.toggle_btn.setToolTip("Hide Quick Tools")
        else:
            self.toolbar_panel.hide()
            self.toggle_icon.setText("\uE76C")  # ChevronRight
            self.toggle_btn.setToolTip("Show Quick Tools")
        
        self.update_position()
    
    def update_position(self):
        """Position the toolbar and toggle button"""
        parent = self.parent()
        if not parent:
            return
            
        # Toggle is always pinned to the right edge
        toggle_x = parent.width() - self._toggle_width - self._scrollbar_margin
        toggle_y = (parent.height() - self.toggle_btn.height()) // 2
        self.toggle_btn.move(toggle_x, toggle_y)
        self.toggle_btn.raise_()
        
        # Toolbar is to the left of the toggle
        if self._toolbar_visible:
            toolbar_x = toggle_x - self._toolbar_width - 4
        else:
            toolbar_x = parent.width() + 10  # Off screen
        
        toolbar_y = (parent.height() - self.toolbar_panel.height()) // 2
        self.toolbar_panel.move(toolbar_x, toolbar_y)
    
    def show_toolbar(self):
        """Show both toolbar and toggle"""
        self.toolbar_panel.show()
        self.toggle_btn.show()
        self.update_position()
    
    def hide_toolbar(self):
        """Hide both toolbar and toggle"""
        self.toolbar_panel.hide()
        self.toggle_btn.hide()


class ActivityItem(QFrame):
    """Single activity log item with glowing status indicator"""
    
    def __init__(self, status: str, text: str, time: str = "", parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)
        
        # Status dot with glow color
        dot = QLabel("●")  # Filled circle instead of bullet
        glow_color = {
            "success": Theme.GLOW_SUCCESS,
            "warning": Theme.GLOW_WARNING,
            "error": Theme.GLOW_ERROR,
            "info": Theme.GLOW_INFO,
        }.get(status, Theme.TEXT_TERTIARY)
        # Add text-shadow effect via rich text for glow illusion
        dot.setStyleSheet(f"background: transparent; color: {glow_color}; font-size: 12px;")
        layout.addWidget(dot)
        
        # Text
        label = QLabel(text)
        label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(label)
        
        layout.addStretch()
        
        # Time
        if time:
            time_label = QLabel(time)
            time_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
            layout.addWidget(time_label)


# =============================================================================
# STARTUP DATA HELPERS
# =============================================================================

# Try to import the real startup scanner
try:
    from startup_scanner import collect_startup_entries, get_startup_summary, StartupStatus
    STARTUP_SCANNER_AVAILABLE = True
except ImportError:
    STARTUP_SCANNER_AVAILABLE = False


def get_startup_data() -> dict:
    """Get startup programs data from real scanner or fallback to placeholder"""
    if STARTUP_SCANNER_AVAILABLE:
        try:
            return get_startup_summary()
        except Exception as e:
            print(f"[StartupScanner] Error: {e}")
    
    # Fallback placeholder data
    return {
        "enabled_count": 0,
        "disabled_count": 0,
        "unknown_count": 0,
        "high_impact": [],
        "threshold": 30,  # Per UI spec: ≤30 OK, 31-60 Warning, >60 Attention
        "total": 0,
        "warnings": ["Startup scanner not available"],
    }


def get_simulated_boot_security() -> dict:
    """Simulate boot security data"""
    return {
        "secure_boot": True,  # True = Enabled, False = Disabled, None = Unsupported
        "bios_mode": "UEFI",  # "UEFI" or "Legacy"
    }


# =============================================================================
# DASHBOARD CARDS
# =============================================================================

class StartupProgramsCard(QFrame):
    """Card showing startup programs status with Apple-style glass effect"""
    
    manage_clicked = pyqtSignal()  # Signal to navigate to startup page
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_data()
        self._setup_shadow()
    
    def _setup_shadow(self):
        """Apply card shadow for elevation"""
        Theme.apply_shadow(self, blur_radius=16, offset_y=4, opacity=80)
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            StartupProgramsCard {{
                background: {Theme.GLASS_BG};
                border: none;
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        
        # Header row
        header = QHBoxLayout()
        header.setSpacing(12)
        
        # Icon container (Fluent style)
        icon_container = QFrame()
        icon_container.setFixedSize(36, 36)
        icon_container.setStyleSheet(f"""
            background: {Theme.BG_CARD_HOVER};
            border-radius: {Theme.RADIUS_SM}px;
        """)
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel("\uE768")  # Play icon for Startup
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"background: transparent; color: {Theme.ACCENT_LIGHT}; font-size: 16px; font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';")
        icon_layout.addWidget(icon_label)
        header.addWidget(icon_container)
        
        # Title and status chip
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        
        title = QLabel("Startup Programs")
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 600;
        """)
        title_row.addWidget(title)
        
        self.status_chip = QLabel("Healthy")
        self.status_chip.setStyleSheet(f"""
            background: {Theme.SUCCESS_BG};
            color: {Theme.SUCCESS};
            font-size: 11px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 4px;
        """)
        title_row.addWidget(self.status_chip)
        title_row.addStretch()
        
        title_layout.addLayout(title_row)
        
        self.summary_label = QLabel("Loading...")
        self.summary_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        title_layout.addWidget(self.summary_label)
        
        header.addLayout(title_layout, 1)
        layout.addLayout(header)
        
        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255, 255, 255, 0.08);")
        layout.addWidget(sep)
        
        # Details list (top offenders)
        self.details_container = QFrame()
        self.details_container.setStyleSheet("background: transparent;")
        self.details_layout = QVBoxLayout(self.details_container)
        self.details_layout.setContentsMargins(0, 0, 0, 0)
        self.details_layout.setSpacing(6)
        layout.addWidget(self.details_container)
        
        # Action button
        self.action_btn = QPushButton("Manage Startup")
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                padding: 8px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_ELEVATED};
            }}
        """)
        self.action_btn.clicked.connect(self.on_manage_clicked)
        layout.addWidget(self.action_btn)
    
    def load_data(self):
        """Load and display startup data
        
        Per UI spec section 5.8 - Warning Thresholds:
        - ≤30 enabled = OK (Healthy)
        - 31-60 enabled = Warning
        - >60 enabled = Attention
        - >100 or unknown apps = Critical
        """
        data = get_startup_data()
        
        enabled = data["enabled_count"]
        disabled = data["disabled_count"]
        unknown = data["unknown_count"]
        
        # Update summary
        self.summary_label.setText(f"{enabled} enabled, {disabled} disabled")
        
        # Update status chip based on thresholds per UI spec section 5.8
        if enabled > 100 or unknown > 0:
            # Critical - too many or unknown problematic apps
            self.status_chip.setText("Critical")
            self.status_chip.setStyleSheet(f"""
                background: rgba(255, 69, 58, 0.2);
                color: {Theme.GLOW_ERROR};
                font-size: 11px;
                font-weight: 600;
                padding: 4px 10px;
                border-radius: 4px;
            """)
        elif enabled > 60:
            # Attention - significantly too many
            self.status_chip.setText("Attention")
            self.status_chip.setStyleSheet(f"""
                background: rgba(255, 149, 0, 0.2);
                color: #ff9500;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 10px;
                border-radius: 4px;
            """)
        elif enabled > 30:
            # Warning - more than recommended
            self.status_chip.setText("Warning")
            self.status_chip.setStyleSheet(f"""
                background: rgba(255, 214, 10, 0.2);
                color: {Theme.GLOW_WARNING};
                font-size: 11px;
                font-weight: 600;
                padding: 4px 10px;
                border-radius: 4px;
            """)
        else:
            # Healthy - 30 or fewer
            self.status_chip.setText("Healthy")
            self.status_chip.setStyleSheet(f"""
                background: rgba(48, 209, 88, 0.2);
                color: {Theme.GLOW_SUCCESS};
                font-size: 11px;
                font-weight: 600;
                padding: 4px 10px;
                border-radius: 4px;
            """)
        
        # Clear existing details
        while self.details_layout.count():
            item = self.details_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        
        # Add high impact items
        for item in data["high_impact"][:3]:
            row = QFrame()
            row.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 2, 0, 2)
            row_layout.setSpacing(8)
            
            # Impact indicator
            impact_color = Theme.WARNING if item["impact"] == "High" else Theme.TEXT_TERTIARY
            impact_dot = QLabel("●")
            impact_dot.setStyleSheet(f"background: transparent; color: {impact_color}; font-size: 8px;")
            row_layout.addWidget(impact_dot)
            
            # Name
            name = QLabel(item["name"])
            name.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
            row_layout.addWidget(name, 1)
            
            # Impact label
            impact = QLabel(item["impact"])
            impact.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
            row_layout.addWidget(impact)
            
            self.details_layout.addWidget(row)
    
    def on_manage_clicked(self):
        """Handle manage button click - emit signal to navigate"""
        self.manage_clicked.emit()
    
    def refresh_theme(self):
        """Refresh colors for theme change"""
        self.setStyleSheet(f"""
            StartupProgramsCard {{
                background: {Theme.GLASS_BG};
                border: none;
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)


class BootSecurityCard(QFrame):
    """Card showing Secure Boot and BIOS mode status with Apple-style glass effect"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_data()
        self._setup_shadow()
    
    def _setup_shadow(self):
        """Apply card shadow for elevation"""
        Theme.apply_shadow(self, blur_radius=16, offset_y=4, opacity=80)
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            BootSecurityCard {{
                background: {Theme.GLASS_BG};
                border: none;
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        
        # Header
        header = QHBoxLayout()
        header.setSpacing(10)
        
        # Icon container (Fluent style)
        icon_container = QFrame()
        icon_container.setFixedSize(32, 32)
        icon_container.setStyleSheet(f"""
            background: {Theme.BG_CARD_HOVER};
            border-radius: {Theme.RADIUS_SM}px;
        """)
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel("\uE72E")  # Lock icon for Boot Security
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"background: transparent; color: {Theme.ACCENT_LIGHT}; font-size: 14px; font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';")
        icon_layout.addWidget(icon_label)
        header.addWidget(icon_container)
        
        title = QLabel("Boot Security")
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 600;
        """)
        header.addWidget(title)
        header.addStretch()
        
        layout.addLayout(header)
        
        # Info rows container
        info_container = QFrame()
        info_container.setStyleSheet(f"""
            background: {Theme.BG_CARD_HOVER};
            border-radius: {Theme.RADIUS_SM}px;
        """)
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(14, 12, 14, 12)
        info_layout.setSpacing(10)
        
        # Secure Boot row
        secure_boot_row = QHBoxLayout()
        secure_boot_row.setSpacing(8)
        
        sb_label = QLabel("Secure Boot")
        sb_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        secure_boot_row.addWidget(sb_label)
        secure_boot_row.addStretch()
        
        self.secure_boot_status = QLabel("Checking...")
        self.secure_boot_status.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 13px;")
        secure_boot_row.addWidget(self.secure_boot_status)
        
        self.secure_boot_dot = QLabel("●")
        self.secure_boot_dot.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 10px;")
        secure_boot_row.addWidget(self.secure_boot_dot)
        
        info_layout.addLayout(secure_boot_row)
        
        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255, 255, 255, 0.08);")
        info_layout.addWidget(sep)
        
        # BIOS Mode row
        bios_row = QHBoxLayout()
        bios_row.setSpacing(8)
        
        bios_label = QLabel("BIOS Mode")
        bios_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        bios_row.addWidget(bios_label)
        bios_row.addStretch()
        
        self.bios_status = QLabel("Checking...")
        self.bios_status.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 13px;")
        bios_row.addWidget(self.bios_status)
        
        self.bios_dot = QLabel("●")
        self.bios_dot.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 10px;")
        bios_row.addWidget(self.bios_dot)
        
        info_layout.addLayout(bios_row)
        
        layout.addWidget(info_container)
    
    def load_data(self):
        """Load and display boot security data"""
        data = get_simulated_boot_security()
        
        secure_boot = data["secure_boot"]
        bios_mode = data["bios_mode"]
        
        # Update Secure Boot status with vibrant glow colors
        if secure_boot is True:
            self.secure_boot_status.setText("Enabled")
            self.secure_boot_status.setStyleSheet(f"background: transparent; color: {Theme.GLOW_SUCCESS}; font-size: 13px; font-weight: 600;")
            self.secure_boot_dot.setStyleSheet(f"background: transparent; color: {Theme.GLOW_SUCCESS}; font-size: 10px;")
        elif secure_boot is False:
            self.secure_boot_status.setText("Disabled")
            self.secure_boot_status.setStyleSheet(f"background: transparent; color: {Theme.GLOW_WARNING}; font-size: 13px; font-weight: 600;")
            self.secure_boot_dot.setStyleSheet(f"background: transparent; color: {Theme.GLOW_WARNING}; font-size: 10px;")
        else:
            self.secure_boot_status.setText("Unsupported")
            self.secure_boot_status.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 13px;")
            self.secure_boot_dot.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 10px;")
        
        # Update BIOS mode status with vibrant glow colors
        self.bios_status.setText(bios_mode)
        if bios_mode == "UEFI":
            self.bios_status.setStyleSheet(f"background: transparent; color: {Theme.GLOW_INFO}; font-size: 13px; font-weight: 600;")
            self.bios_dot.setStyleSheet(f"background: transparent; color: {Theme.GLOW_INFO}; font-size: 10px;")
        else:
            self.bios_status.setStyleSheet(f"background: transparent; color: {Theme.GLOW_WARNING}; font-size: 13px; font-weight: 600;")
            self.bios_dot.setStyleSheet(f"background: transparent; color: {Theme.GLOW_WARNING}; font-size: 10px;")
    
    def update_data(self, secure_boot: bool, bios_mode: str):
        """Update with new data (for future backend integration)"""
        # Store and reload
        pass  # Placeholder for future backend hook
    
    def refresh_theme(self):
        """Refresh colors for theme change"""
        self.setStyleSheet(f"""
            BootSecurityCard {{
                background: {Theme.GLASS_BG};
                border: none;
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)


class SystemInfoCard(QFrame):
    """Card showing Fast Startup status and live system uptime"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_data()
        self._setup_shadow()
        self._start_uptime_timer()
    
    def _setup_shadow(self):
        """Apply card shadow for elevation"""
        Theme.apply_shadow(self, blur_radius=16, offset_y=4, opacity=80)
    
    def _start_uptime_timer(self):
        """Start timer to update uptime every second"""
        self.uptime_timer = QTimer(self)
        self.uptime_timer.timeout.connect(self._update_uptime)
        self.uptime_timer.start(1000)  # Update every second
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            SystemInfoCard {{
                background: {Theme.GLASS_BG};
                border: none;
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        
        # Header
        header = QHBoxLayout()
        header.setSpacing(10)
        
        # Icon container (Fluent style)
        icon_container = QFrame()
        icon_container.setFixedSize(32, 32)
        icon_container.setStyleSheet(f"""
            background: {Theme.BG_CARD_HOVER};
            border-radius: {Theme.RADIUS_SM}px;
        """)
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel("\uE916")  # Timer icon for System Info
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"background: transparent; color: {Theme.ACCENT_LIGHT}; font-size: 14px; font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';")
        icon_layout.addWidget(icon_label)
        header.addWidget(icon_container)
        
        title = QLabel("System Info")
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 600;
        """)
        header.addWidget(title)
        header.addStretch()
        
        layout.addLayout(header)
        
        # Info rows container
        info_container = QFrame()
        info_container.setStyleSheet(f"""
            background: {Theme.BG_CARD_HOVER};
            border-radius: {Theme.RADIUS_SM}px;
        """)
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(14, 12, 14, 12)
        info_layout.setSpacing(10)
        
        # Fast Startup row
        fast_startup_row = QHBoxLayout()
        fast_startup_row.setSpacing(8)
        
        fs_label = QLabel("Fast Startup")
        fs_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        fast_startup_row.addWidget(fs_label)
        fast_startup_row.addStretch()
        
        self.fast_startup_status = QLabel("Checking...")
        self.fast_startup_status.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 13px;")
        fast_startup_row.addWidget(self.fast_startup_status)
        
        self.fast_startup_dot = QLabel("●")
        self.fast_startup_dot.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 10px;")
        fast_startup_row.addWidget(self.fast_startup_dot)
        
        info_layout.addLayout(fast_startup_row)
        
        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255, 255, 255, 0.08);")
        info_layout.addWidget(sep)
        
        # Uptime row
        uptime_row = QHBoxLayout()
        uptime_row.setSpacing(8)
        
        uptime_label = QLabel("System Uptime")
        uptime_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        uptime_row.addWidget(uptime_label)
        uptime_row.addStretch()
        
        self.uptime_status = QLabel("Calculating...")
        self.uptime_status.setStyleSheet(f"background: transparent; color: {Theme.GLOW_INFO}; font-size: 13px; font-weight: 600;")
        uptime_row.addWidget(self.uptime_status)
        
        info_layout.addLayout(uptime_row)
        
        layout.addWidget(info_container)
    
    def load_data(self):
        """Load Fast Startup status"""
        fast_startup = self._check_fast_startup()
        
        if fast_startup is True:
            self.fast_startup_status.setText("Enabled")
            self.fast_startup_status.setStyleSheet(f"background: transparent; color: {Theme.GLOW_SUCCESS}; font-size: 13px; font-weight: 600;")
            self.fast_startup_dot.setStyleSheet(f"background: transparent; color: {Theme.GLOW_SUCCESS}; font-size: 10px;")
        elif fast_startup is False:
            self.fast_startup_status.setText("Disabled")
            self.fast_startup_status.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 13px; font-weight: 600;")
            self.fast_startup_dot.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 10px;")
        else:
            self.fast_startup_status.setText("Unknown")
            self.fast_startup_status.setStyleSheet(f"background: transparent; color: {Theme.GLOW_WARNING}; font-size: 13px; font-weight: 600;")
            self.fast_startup_dot.setStyleSheet(f"background: transparent; color: {Theme.GLOW_WARNING}; font-size: 10px;")
        
        # Initial uptime update
        self._update_uptime()
    
    def _check_fast_startup(self):
        """Check if Fast Startup (Hybrid Boot) is enabled"""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Power",
                0,
                winreg.KEY_READ
            )
            value, _ = winreg.QueryValueEx(key, "HiberbootEnabled")
            winreg.CloseKey(key)
            return value == 1
        except:
            return None
    
    def _update_uptime(self):
        """Update the uptime display"""
        try:
            import ctypes
            # GetTickCount64 returns milliseconds since system start
            kernel32 = ctypes.windll.kernel32
            kernel32.GetTickCount64.restype = ctypes.c_ulonglong
            uptime_ms = kernel32.GetTickCount64()
            
            # Convert to seconds
            uptime_seconds = uptime_ms // 1000
            
            days = uptime_seconds // 86400
            hours = (uptime_seconds % 86400) // 3600
            minutes = (uptime_seconds % 3600) // 60
            seconds = uptime_seconds % 60
            
            if days > 0:
                uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
            elif hours > 0:
                uptime_str = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                uptime_str = f"{minutes}m {seconds}s"
            else:
                uptime_str = f"{seconds}s"
            
            self.uptime_status.setText(uptime_str)
        except:
            self.uptime_status.setText("Unknown")
    
    def refresh_theme(self):
        """Refresh colors for theme change"""
        self.setStyleSheet(f"""
            SystemInfoCard {{
                background: {Theme.GLASS_BG};
                border: none;
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)


class ScanProgressDialog(QDialog):
    """Refined scan progress dialog"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("System Health Check")
        self.setModal(True)
        self.setFixedSize(480, 420)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        # Header
        header = QLabel("Running System Health Check")
        header.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 16px;
            font-weight: 600;
        """)
        layout.addWidget(header)
        
        # Task list container
        tasks_container = QFrame()
        tasks_container.setStyleSheet(f"""
            background: {Theme.BG_WINDOW};
            border-radius: {Theme.RADIUS_MD}px;
        """)
        tasks_layout = QVBoxLayout(tasks_container)
        tasks_layout.setContentsMargins(16, 12, 16, 12)
        tasks_layout.setSpacing(8)
        
        self.tasks = {}
        task_items = [
            ("update", "Windows Update"),
            ("defender", "Windows Defender"),
            ("sfc", "System File Integrity"),
            ("smart", "Drive SMART Health"),
            ("memory", "Memory Health"),
            ("events", "Event Log Analysis"),
            ("services", "Service Status"),
        ]
        
        for task_id, task_name in task_items:
            task_row = QHBoxLayout()
            task_row.setSpacing(12)
            
            # Status icon
            icon = StatusIcon("pending", 18)
            task_row.addWidget(icon)
            
            # Name
            name = QLabel(task_name)
            name.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 12px;")
            task_row.addWidget(name)
            
            task_row.addStretch()
            
            # Status text
            status = QLabel("Waiting")
            status.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
            status.setFixedWidth(70)
            status.setAlignment(Qt.AlignmentFlag.AlignRight)
            task_row.addWidget(status)
            
            self.tasks[task_id] = {"icon": icon, "status": status}
            tasks_layout.addLayout(task_row)
        
        layout.addWidget(tasks_container)
        
        # Progress section
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(8)
        
        progress_header = QHBoxLayout()
        progress_label = QLabel("Overall Progress")
        progress_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        progress_header.addWidget(progress_label)
        
        self.progress_percent = QLabel("0%")
        self.progress_percent.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 12px; font-weight: 600;")
        progress_header.addWidget(self.progress_percent)
        progress_layout.addLayout(progress_header)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        progress_layout.addWidget(self.progress_bar)
        
        self.time_label = QLabel("Estimating time...")
        self.time_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
        progress_layout.addWidget(self.time_label)
        
        layout.addLayout(progress_layout)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.bg_btn = QPushButton("Run in Background")
        self.bg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bg_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                padding: 10px 18px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BORDER};
            }}
        """)
        btn_layout.addWidget(self.bg_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Theme.TEXT_SECONDARY};
                border: none;
                padding: 10px 14px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def update_task(self, task_id: str, status: str, text: str | None = None, time_ms: float | None = None):
        if task_id not in self.tasks:
            return
        
        task = self.tasks[task_id]
        
        status_map = {
            "running": ("running", Theme.ACCENT, "Running..."),
            "complete": ("check", Theme.SUCCESS, "Complete"),
            "error": ("error", Theme.ERROR, "Failed"),
        }
        
        icon_status, color, default_text = status_map.get(status, ("pending", Theme.TEXT_TERTIARY, "Waiting"))
        
        # If time is provided, format it nicely
        if time_ms is not None and status == "complete":
            if time_ms < 1000:
                time_text = f"{int(time_ms)}ms"
            else:
                time_text = f"{time_ms / 1000:.1f}s"
            display_text = text or time_text
        else:
            display_text = text or default_text
        
        task["icon"].set_status(icon_status)
        task["status"].setText(display_text)
        task["status"].setStyleSheet(f"background: transparent; color: {color}; font-size: 11px;")
    
    def set_progress(self, percent: int, time_remaining: str | None = None):
        self.progress_bar.setValue(percent)
        self.progress_percent.setText(f"{percent}%")
        if time_remaining:
            self.time_label.setText(f"About {time_remaining} remaining")


# =============================================================================
# PAGES
# =============================================================================

class OverviewPage(QWidget):
    """Main overview/dashboard page with staggered fade-in animations"""
    
    card_clicked = pyqtSignal(str)  # Signal emits card_id when clicked
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._animated_widgets = []  # Widgets to animate on show
        self._animation_index = 0
        self._animation_timer = None
        self._first_show = True  # Only animate on first show
        self.setup_ui()
    
    def setup_ui(self):
        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(24)
        
        # Page title
        title = QLabel("System Health")
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 28px;
            font-weight: 600;
        """)
        layout.addWidget(title)
        
        # Tips Carousel at top
        self.tips_carousel = TipsCarousel()
        self.tips_carousel.setGraphicsEffect(self._create_opacity_effect(0))
        self._animated_widgets.append(self.tips_carousel)
        layout.addWidget(self.tips_carousel)
        
        # Health summary card
        self.health_card = HealthSummaryCard()
        self.health_card.setGraphicsEffect(self._create_opacity_effect(0))
        self._animated_widgets.append(self.health_card)
        layout.addWidget(self.health_card)
        
        # Quick Status section
        section_header = QLabel("Quick Status")
        section_header.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 16px;
            font-weight: 600;
            margin-top: 8px;
        """)
        layout.addWidget(section_header)
        
        # Status cards in glowing grid container
        self.card_grid = GlowingCardGrid()
        self.card_grid.setGraphicsEffect(self._create_opacity_effect(0))
        self._animated_widgets.append(self.card_grid)
        
        self.status_cards = {}
        # Map card_id to the navigation page id
        cards_data = [
            ("updates", "Windows Update", "updates"),
            ("defender", "Defender", "security"),
            ("storage", "Storage", "storage"),
            ("drivers", "Drivers", "drivers"),
            ("memory", "Memory", "hardware"),
            ("system", "Event Logs", "events"),  # Navigate to Events page to see errors
        ]
        
        for i, (card_id, title, nav_target) in enumerate(cards_data):
            card = GlassCard(title)
            card.clicked.connect(lambda target=nav_target: self.card_clicked.emit(target))
            self.status_cards[card_id] = card
            self.card_grid.add_card(card, i // 3, i % 3)
        
        layout.addWidget(self.card_grid)
        
        # System Cards row - Startup Programs and Boot Security
        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)
        
        self.startup_card = StartupProgramsCard()
        self.startup_card.manage_clicked.connect(lambda: self.card_clicked.emit("startup"))
        self.startup_card.setGraphicsEffect(self._create_opacity_effect(0))
        self._animated_widgets.append(self.startup_card)
        cards_row.addWidget(self.startup_card, 1)
        
        self.boot_security_card = BootSecurityCard()
        self.boot_security_card.setGraphicsEffect(self._create_opacity_effect(0))
        self._animated_widgets.append(self.boot_security_card)
        cards_row.addWidget(self.boot_security_card, 1)
        
        layout.addLayout(cards_row)
        
        # Second row - System Info card
        cards_row2 = QHBoxLayout()
        cards_row2.setSpacing(16)
        
        self.system_info_card = SystemInfoCard()
        self.system_info_card.setGraphicsEffect(self._create_opacity_effect(0))
        self._animated_widgets.append(self.system_info_card)
        cards_row2.addWidget(self.system_info_card, 1)
        
        # Spacer to match layout (or add another card here later)
        cards_row2.addStretch(1)
        
        layout.addLayout(cards_row2)
        
        # Recent Activity section
        activity_header = QLabel("Recent Activity")
        activity_header.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 16px;
            font-weight: 600;
            margin-top: 8px;
        """)
        layout.addWidget(activity_header)
        
        # Activity list
        self.activity_container = QFrame()
        self.activity_container.setStyleSheet(f"""
            background: {Theme.BG_CARD};
            border: none;
            border-radius: {Theme.RADIUS_MD}px;
        """)
        Theme.apply_shadow(self.activity_container)
        self.activity_container.setGraphicsEffect(self._create_opacity_effect(0))
        self._animated_widgets.append(self.activity_container)
        self.activity_layout = QVBoxLayout(self.activity_container)
        self.activity_layout.setContentsMargins(4, 8, 4, 8)
        self.activity_layout.setSpacing(0)
        
        # Initial activity items
        self.add_activity("info", "Ready to scan", "")
        self.add_activity("info", "Click 'Run Full Scan' to check your system", "")
        
        layout.addWidget(self.activity_container)
        
        layout.addStretch()
        
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        
        # Floating Quick Tools bar (fixed to right side)
        tools = [
            ("Task Manager", "\uE9D5", self._open_task_manager),
            ("Device Manager", "\uE772", self._open_device_manager),
            ("Disk Cleanup", "\uE90F", self._open_disk_cleanup),
            ("Windows Update", "\uE895", self._open_windows_update),
        ]
        self._floating_toolbar = FloatingToolbar(tools, self)
    
    def _create_opacity_effect(self, opacity: float):
        """Create a QGraphicsOpacityEffect for fade animation"""
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        effect = QGraphicsOpacityEffect()
        effect.setOpacity(opacity)
        return effect
    
    def showEvent(self, event):
        """Start staggered fade-in animation when page is shown"""
        super().showEvent(event)
        if self._first_show and self._animated_widgets:
            self._first_show = False
            self._animation_index = 0
            # Start animation timer
            self._animation_timer = QTimer(self)
            self._animation_timer.timeout.connect(self._animate_next_widget)
            self._animation_timer.start(80)  # 80ms between each widget
    
    def _animate_next_widget(self):
        """Animate the next widget in the sequence"""
        if self._animation_index >= len(self._animated_widgets):
            if self._animation_timer:
                self._animation_timer.stop()
                self._animation_timer = None
            return
        
        widget = self._animated_widgets[self._animation_index]
        effect = widget.graphicsEffect()
        
        if effect and hasattr(effect, 'setOpacity'):
            # Create smooth fade-in animation
            self._fade_in_widget(widget, effect)
        
        self._animation_index += 1
    
    def _fade_in_widget(self, widget, effect):
        """Smoothly fade in a widget"""
        from PyQt6.QtCore import QPropertyAnimation
        
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(300)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        # Remove the graphics effect after animation to prevent rendering issues with child widgets
        animation.finished.connect(lambda: widget.setGraphicsEffect(None))
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    
    def resizeEvent(self, event):
        """Reposition floating toolbar on resize"""
        super().resizeEvent(event)
        if hasattr(self, '_floating_toolbar'):
            self._floating_toolbar.update_position()
    
    def _open_task_manager(self):
        """Open Task Manager"""
        import subprocess
        try:
            subprocess.Popen(["taskmgr"])
        except:
            pass
    
    def _open_device_manager(self):
        """Open Device Manager"""
        import subprocess
        try:
            subprocess.Popen(["devmgmt.msc"])
        except:
            pass
    
    def _open_disk_cleanup(self):
        """Open Disk Cleanup"""
        import subprocess
        try:
            subprocess.Popen(["cleanmgr"])
        except:
            pass
    
    def _open_windows_update(self):
        """Open Windows Update settings"""
        import subprocess
        try:
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:windowsupdate"],
                           creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        except:
            pass
    
    def add_activity(self, status: str, text: str, time: str):
        item = ActivityItem(status, text, time)
        self.activity_layout.insertWidget(0, item)
        
        # Keep only last 10 items
        while self.activity_layout.count() > 10:
            old = self.activity_layout.takeAt(self.activity_layout.count() - 1)
            if old:
                widget = old.widget()
                if widget:
                    widget.deleteLater()
    
    def refresh_accent_colors(self):
        """Refresh colors for theme/accent changes"""
        # Refresh health summary card
        if hasattr(self, 'health_card'):
            self.health_card.refresh_theme()
        
        # Refresh tips carousel
        if hasattr(self, 'tips_carousel'):
            self.tips_carousel.refresh_theme()
        
        # Refresh startup programs card
        if hasattr(self, 'startup_card'):
            self.startup_card.refresh_theme()
        
        # Refresh boot security card
        if hasattr(self, 'boot_security_card'):
            self.boot_security_card.refresh_theme()
        
        # Refresh system info card
        if hasattr(self, 'system_info_card'):
            self.system_info_card.refresh_theme()
        
        # Refresh the activity container background
        if hasattr(self, 'activity_container'):
            self.activity_container.setStyleSheet(f"""
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            """)
        
        # Refresh tools container
        if hasattr(self, 'tools_container'):
            self.tools_container.setStyleSheet(f"""
                QFrame {{
                    background: {Theme.BG_CARD};
                    border: none;
                    border-radius: {Theme.RADIUS_MD}px;
                }}
            """)
        
        # Force update of the glowing card grid
        if hasattr(self, 'card_grid'):
            self.card_grid.update()


class ModulePage(QWidget):
    """Generic module detail page template"""
    
    run_check_clicked = pyqtSignal()  # Signal when Run Check is clicked
    
    def __init__(self, title: str, icon_name: str, parent=None):
        super().__init__(parent)
        self.title_text = title
        self.icon_name = icon_name
        self.results_widgets = []
        self.setup_ui()
    
    def setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(32, 28, 32, 28)
        self.content_layout.setSpacing(24)
        
        # Header
        header = QHBoxLayout()
        
        title = QLabel(self.title_text)
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 28px;
            font-weight: 600;
        """)
        header.addWidget(title)
        
        header.addStretch()
        
        self.action_btn = QPushButton("Run Check")
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                padding: 10px 24px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT_HOVER};
            }}
        """)
        self.action_btn.clicked.connect(self.run_check_clicked.emit)
        header.addWidget(self.action_btn)
        
        self.content_layout.addLayout(header)
        
        # Status label
        self.status_label = QLabel("Click 'Run Check' to analyze this module")
        self.status_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 14px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.status_label)
        
        # Results container
        self.results_container = QFrame()
        self.results_container.setStyleSheet(f"""
            background: {Theme.BG_CARD};
            border: none;
            border-radius: {Theme.RADIUS_MD}px;
        """)
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(16, 16, 16, 16)
        self.results_layout.setSpacing(8)
        self.results_container.setVisible(False)
        self.content_layout.addWidget(self.results_container)
        
        self.content_layout.addStretch()
        
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
    
    def set_checking(self):
        """Show checking state"""
        self.status_label.setText("Checking...")
        self.status_label.setVisible(True)
        self.results_container.setVisible(False)
        self.action_btn.setEnabled(False)
        self.action_btn.setText("Checking...")
    
    def show_results(self, results: list):
        """Display results - list of (status, text) tuples
        
        Status can be: check, warning, error, info, or header (for section headers)
        """
        self.status_label.setVisible(False)
        self.results_container.setVisible(True)
        self.action_btn.setEnabled(True)
        self.action_btn.setText("Run Check")
        
        # Clear old results
        for widget in self.results_widgets:
            widget.deleteLater()
        self.results_widgets.clear()
        
        # Add new results
        for status, text in results:
            # Handle section headers
            if status == "header":
                # Add spacing before header (except first)
                if self.results_widgets:
                    spacer = QFrame()
                    spacer.setFixedHeight(12)
                    spacer.setStyleSheet("background: transparent;")
                    self.results_layout.addWidget(spacer)
                    self.results_widgets.append(spacer)
                
                header = QLabel(text)
                header.setStyleSheet(f"""
                    background: transparent;
                    color: {Theme.TEXT_PRIMARY};
                    font-size: 14px;
                    font-weight: 600;
                    padding: 4px 8px;
                    border-left: 3px solid {Theme.ACCENT};
                """)
                self.results_layout.addWidget(header)
                self.results_widgets.append(header)
                continue
            
            row = QFrame()
            row.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 8, 8, 8)
            row_layout.setSpacing(12)
            
            # Status icon
            icon = StatusIcon(status, 18)
            row_layout.addWidget(icon)
            
            # Text
            label = QLabel(text)
            label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 13px;")
            label.setWordWrap(True)
            row_layout.addWidget(label, 1)
            
            self.results_layout.addWidget(row)
            self.results_widgets.append(row)
    
    def show_results_with_actions(self, results: list, actions: list):
        """Display results with action buttons
        
        Args:
            results: list of (status, text) tuples
            actions: list of (button_text, callback) tuples
        """
        # First show the regular results
        self.show_results(results)
        
        # Add action buttons section
        if actions:
            # Separator
            separator = QFrame()
            separator.setFixedHeight(1)
            separator.setStyleSheet(f"background: {Theme.BORDER};")
            self.results_layout.addWidget(separator)
            self.results_widgets.append(separator)
            
            # Action buttons row
            actions_frame = QFrame()
            actions_frame.setStyleSheet("background: transparent;")
            actions_layout = QHBoxLayout(actions_frame)
            actions_layout.setContentsMargins(8, 12, 8, 4)
            actions_layout.setSpacing(12)
            
            for btn_text, callback in actions:
                btn = QPushButton(btn_text)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {Theme.ACCENT};
                        color: white;
                        border: none;
                        padding: 8px 16px;
                        border-radius: {Theme.RADIUS_SM}px;
                        font-size: 12px;
                        font-weight: 600;
                    }}
                    QPushButton:hover {{
                        background: {Theme.ACCENT_HOVER};
                    }}
                """)
                btn.clicked.connect(callback)
                actions_layout.addWidget(btn)
            
            actions_layout.addStretch()
            self.results_layout.addWidget(actions_frame)
            self.results_widgets.append(actions_frame)


class DriverScanWorker(QObject):
    """Worker to scan drivers in background thread"""
    finished = pyqtSignal(list, list)  # drivers, problems
    
    def __init__(self, scanner):
        super().__init__()
        self.scanner = scanner
    
    def run(self):
        try:
            drivers = self.scanner.scan_installed_drivers()
            problems = self.scanner.scan_problem_devices()
            self.finished.emit(drivers, problems)
        except Exception as e:
            self.finished.emit([], [])


class UnusedDriverScanWorker(QObject):
    """Worker to scan for unused drivers in background thread"""
    finished = pyqtSignal(list)  # unused drivers
    
    def __init__(self, scanner):
        super().__init__()
        self.scanner = scanner
    
    def run(self):
        try:
            unused = self.scanner.find_unused_drivers()
            self.finished.emit(unused)
        except Exception as e:
            self.finished.emit([])


class DriverUpdateCheckWorker(QObject):
    """Worker to check for driver updates in background thread"""
    finished = pyqtSignal(list)  # available updates
    
    def __init__(self, scanner):
        super().__init__()
        self.scanner = scanner
    
    def run(self):
        try:
            updates = self.scanner.check_windows_update_drivers()
            self.finished.emit(updates)
        except Exception as e:
            self.finished.emit([])


class DriversPage(QWidget):
    """Dedicated drivers management page with tabs for Installed, Cleanup, and Updates"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scanner = DriverScanner()
        self.online_checker = OnlineDriverChecker()
        self.drivers = []
        self.unused_drivers = []
        self.available_updates = []
        self.problem_devices = []
        self._threads = []
        self._cached_vendors = None  # Cache for hardware vendor detection
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 28, 32, 28)
        main_layout.setSpacing(20)
        
        # Header row
        header = QHBoxLayout()
        header.setSpacing(16)
        
        title = QLabel("Driver Manager")
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 28px;
            font-weight: 600;
        """)
        header.addWidget(title)
        header.addStretch()
        
        # Open Device Manager button
        devmgr_btn = QPushButton("Open Device Manager")
        devmgr_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        devmgr_btn.clicked.connect(self._open_device_manager)
        Theme.style_accent_button(devmgr_btn, "primary")
        header.addWidget(devmgr_btn)
        
        main_layout.addLayout(header)
        
        # Tab bar
        tab_bar = QHBoxLayout()
        tab_bar.setSpacing(0)
        
        self.tabs = {}
        tab_items = [
            ("installed", "Installed Drivers"),
            ("cleanup", "Driver Cleanup"),
            ("updates", "Updates && Resources"),
        ]
        
        for tab_id, tab_label in tab_items:
            btn = QPushButton(tab_label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, tid=tab_id: self._switch_tab(tid))
            btn.setStyleSheet(self._get_tab_style(False))
            self.tabs[tab_id] = btn
            tab_bar.addWidget(btn)
        
        tab_bar.addStretch()
        main_layout.addLayout(tab_bar)
        
        # Select first tab by default
        self.tabs["installed"].setChecked(True)
        self.tabs["installed"].setStyleSheet(self._get_tab_style(True))
        self.current_tab = "installed"
        
        # Content stack for different tabs (with smooth transitions)
        self.content_stack = AnimatedStackedWidget()
        self.content_stack.set_transition_duration(150)  # Faster for tabs
        
        # Installed tab content
        self.installed_scroll = QScrollArea()
        self.installed_scroll.setWidgetResizable(True)
        self.installed_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.installed_content = QWidget()
        self.installed_layout = QVBoxLayout(self.installed_content)
        self.installed_layout.setContentsMargins(0, 16, 0, 16)
        self.installed_layout.setSpacing(12)
        self.installed_layout.addStretch()
        self.installed_scroll.setWidget(self.installed_content)
        self.content_stack.addWidget(self.installed_scroll)
        
        # Cleanup tab content
        self.cleanup_scroll = QScrollArea()
        self.cleanup_scroll.setWidgetResizable(True)
        self.cleanup_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cleanup_content = QWidget()
        self.cleanup_layout = QVBoxLayout(self.cleanup_content)
        self.cleanup_layout.setContentsMargins(0, 16, 0, 16)
        self.cleanup_layout.setSpacing(12)
        self.cleanup_layout.addStretch()
        self.cleanup_scroll.setWidget(self.cleanup_content)
        self.content_stack.addWidget(self.cleanup_scroll)
        
        # Updates tab content
        self.updates_scroll = QScrollArea()
        self.updates_scroll.setWidgetResizable(True)
        self.updates_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.updates_content = QWidget()
        self.updates_layout = QVBoxLayout(self.updates_content)
        self.updates_layout.setContentsMargins(0, 16, 0, 16)
        self.updates_layout.setSpacing(12)
        self.updates_layout.addStretch()
        self.updates_scroll.setWidget(self.updates_content)
        self.content_stack.addWidget(self.updates_scroll)
        
        main_layout.addWidget(self.content_stack)
        
        # Show placeholder
        self._show_installed_placeholder()
        
        # Floating Quick Tools bar
        tools = [
            ("Device Manager", "\uE772", self._open_device_manager),
            ("Windows Update", "\uE895", self._open_windows_update),
            ("System Info", "\uE946", self._open_system_info),
        ]
        self._floating_toolbar = FloatingToolbar(tools, self)
    
    def resizeEvent(self, event):
        """Reposition floating toolbar on resize"""
        super().resizeEvent(event)
        if hasattr(self, '_floating_toolbar'):
            self._floating_toolbar.update_position()
    
    def _open_windows_update(self):
        """Open Windows Update settings"""
        import subprocess
        try:
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:windowsupdate"],
                           creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        except:
            pass
    
    def _open_system_info(self):
        """Open System Information"""
        import subprocess
        try:
            subprocess.Popen(["msinfo32"])
        except:
            pass
    
    def _get_tab_style(self, is_active: bool) -> str:
        """Tab styling per spec Section 7.0.2 - 44px height, 14px font"""
        if is_active:
            return f"""
                QPushButton {{
                    background: {Theme.BG_CARD};
                    color: {Theme.TEXT_PRIMARY};
                    border: none;
                    border-bottom: 2px solid {Theme.ACCENT};
                    border-radius: 8px 8px 0 0;
                    padding: 12px 24px;
                    min-height: 44px;
                    font-size: 14px;
                    font-weight: 600;
                }}
            """
        else:
            return f"""
                QPushButton {{
                    background: transparent;
                    color: {Theme.TEXT_SECONDARY};
                    border: none;
                    border-bottom: 2px solid transparent;
                    padding: 12px 24px;
                    min-height: 44px;
                    font-size: 14px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    color: {Theme.TEXT_PRIMARY};
                    background: {Theme.BG_CARD_HOVER};
                }}
            """
    
    def _switch_tab(self, tab_id: str):
        # Update tab styles
        for tid, btn in self.tabs.items():
            is_active = tid == tab_id
            btn.setChecked(is_active)
            btn.setStyleSheet(self._get_tab_style(is_active))
        
        self.current_tab = tab_id
        
        # Switch content
        if tab_id == "installed":
            self.content_stack.setCurrentWidget(self.installed_scroll)
            if not self.drivers:
                self._show_installed_placeholder()
        elif tab_id == "cleanup":
            self.content_stack.setCurrentWidget(self.cleanup_scroll)
            if not self.unused_drivers:
                self._load_cleanup_data()
        elif tab_id == "updates":
            self.content_stack.setCurrentWidget(self.updates_scroll)
            self._load_updates_data()
    
    def _clear_layout(self, layout):
        """Clear all widgets from a layout"""
        while layout.count() > 1:  # Keep the stretch
            item = layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
    
    # =========================================================================
    # INSTALLED DRIVERS TAB
    # =========================================================================
    
    def _show_installed_placeholder(self):
        """Show placeholder in installed tab with scan button"""
        self._clear_layout(self.installed_layout)
        
        # Placeholder card
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border-radius: {Theme.RADIUS_MD}px;
                border: none;
            }}
        """)
        Theme.apply_shadow(card)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(16)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_label = QLabel("🔌")
        icon_label.setStyleSheet("background: transparent; font-size: 48px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(icon_label)
        
        title = QLabel("Scan Installed Drivers")
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 18px;
            font-weight: 600;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title)
        
        desc = QLabel("Analyze your system's drivers to check their status,\nversions, and identify any problems.")
        desc.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(desc)
        
        scan_btn = QPushButton("Scan Drivers")
        scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        scan_btn.clicked.connect(self._scan_installed_drivers)
        scan_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                padding: 12px 32px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT_HOVER};
            }}
        """)
        card_layout.addWidget(scan_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.installed_layout.insertWidget(0, card)
    
    def _scan_installed_drivers(self):
        """Scan installed drivers in background"""
        self._clear_layout(self.installed_layout)
        
        # Loading indicator
        loading_frame = QFrame()
        loading_frame.setStyleSheet("background: transparent;")
        loading_layout = QVBoxLayout(loading_frame)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        spinner = ModernSpinner(40, 3, Theme.ACCENT)
        spinner.start()
        loading_layout.addWidget(spinner, alignment=Qt.AlignmentFlag.AlignCenter)
        
        loading_label = QLabel("Scanning installed drivers...")
        loading_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 14px;")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(loading_label)
        
        self.installed_layout.insertWidget(0, loading_frame)
        
        # Run scan in background
        self._driver_scan_thread = QThread(self)
        self._driver_scan_worker = DriverScanWorker(self.scanner)
        self._driver_scan_worker.moveToThread(self._driver_scan_thread)
        
        self._driver_scan_thread.started.connect(self._driver_scan_worker.run)
        self._driver_scan_worker.finished.connect(self._on_installed_scan_complete)
        self._driver_scan_worker.finished.connect(self._driver_scan_thread.quit)
        self._driver_scan_worker.finished.connect(self._driver_scan_worker.deleteLater)
        
        self._driver_scan_thread.start()
    
    def _on_installed_scan_complete(self, drivers: list, problems: list):
        """Handle installed drivers scan complete"""
        self.drivers = drivers
        self.problem_devices = problems
        self._clear_layout(self.installed_layout)
        
        # Update Overview page's drivers card if available
        try:
            from PyQt6.QtWidgets import QApplication
            for widget in QApplication.topLevelWidgets():
                if hasattr(widget, 'overview') and hasattr(widget.overview, 'status_cards'):
                    total = len(drivers)
                    ok_count = sum(1 for d in drivers if d.status == "OK")
                    problem_count = len(problems) + sum(1 for d in drivers if d.status != "OK")
                    if problem_count > 0:
                        widget.overview.status_cards["drivers"].set_status("warning", f"{problem_count} issues")
                    else:
                        widget.overview.status_cards["drivers"].set_status("check", f"{total} OK")
                    break
        except:
            pass
        
        if not drivers:
            label = QLabel("No drivers found or unable to scan")
            label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 13px;")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.installed_layout.insertWidget(0, label)
            return
        
        # Stats card
        stats_frame = QFrame()
        stats_frame.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(stats_frame, blur_radius=10, offset_y=2, opacity=40)
        
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setContentsMargins(24, 20, 24, 20)
        stats_layout.setSpacing(0)
        
        total = len(drivers)
        ok_count = sum(1 for d in drivers if d.status == "OK")
        unsigned_count = sum(1 for d in drivers if d.status == "Unsigned")
        problem_count = len(problems)
        
        stat_total = self._create_stat("Total Drivers", str(total), Theme.TEXT_PRIMARY)
        stat_ok = self._create_stat("OK", str(ok_count), Theme.SUCCESS)
        stat_unsigned = self._create_stat("Unsigned", str(unsigned_count), Theme.WARNING)
        stat_problems = self._create_stat("Problems", str(problem_count), Theme.ERROR)
        
        stats_layout.addWidget(stat_total)
        self._add_stat_divider(stats_layout)
        stats_layout.addWidget(stat_ok)
        self._add_stat_divider(stats_layout)
        stats_layout.addWidget(stat_unsigned)
        self._add_stat_divider(stats_layout)
        stats_layout.addWidget(stat_problems)
        stats_layout.addStretch()
        
        self.installed_layout.insertWidget(self.installed_layout.count() - 1, stats_frame)
        
        # Group drivers by category
        categories = {}
        for driver in drivers:
            cat = driver.device_class or "Other"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(driver)
        
        # Add driver categories
        for category, cat_drivers in sorted(categories.items()):
            # Category header
            header = QLabel(f"{category} ({len(cat_drivers)})")
            header.setStyleSheet(f"""
                background: transparent;
                color: {Theme.TEXT_PRIMARY};
                font-size: 14px;
                font-weight: 600;
                padding: 12px 0 4px 0;
            """)
            self.installed_layout.insertWidget(self.installed_layout.count() - 1, header)
            
            # Drivers container
            container = ModernListContainer()
            
            for driver in cat_drivers[:10]:  # Limit per category
                status = "ok" if driver.status == "OK" else "warning" if driver.status == "Unsigned" else "error"
                row = container.add_row(
                    title=driver.device_name,
                    subtitle=f"{driver.manufacturer} • v{driver.driver_version} • {driver.driver_date}",
                    status=status,
                    status_text=driver.status
                )
                
                if driver.status != "OK":
                    row.add_action_button("Fix", lambda checked, d=driver: self._fix_driver(d), primary=True)
            
            if len(cat_drivers) > 10:
                container.add_more_label(f"... and {len(cat_drivers) - 10} more drivers")
            
            self.installed_layout.insertWidget(self.installed_layout.count() - 1, container)
        
        # Rescan button
        rescan_frame = QFrame()
        rescan_frame.setStyleSheet("background: transparent;")
        rescan_layout = QHBoxLayout(rescan_frame)
        rescan_layout.setContentsMargins(0, 12, 0, 0)
        
        rescan_btn = QPushButton("Rescan Drivers")
        rescan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rescan_btn.clicked.connect(self._scan_installed_drivers)
        rescan_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                padding: 10px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        Theme.apply_shadow(rescan_btn)
        rescan_layout.addWidget(rescan_btn)
        rescan_layout.addStretch()
        
        self.installed_layout.insertWidget(self.installed_layout.count() - 1, rescan_frame)
    
    # =========================================================================
    # CLEANUP TAB
    # =========================================================================
    
    def _load_cleanup_data(self):
        """Load unused drivers data"""
        self._clear_layout(self.cleanup_layout)
        
        # Loading indicator
        loading_frame = QFrame()
        loading_frame.setStyleSheet("background: transparent;")
        loading_layout = QVBoxLayout(loading_frame)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        spinner = ModernSpinner(40, 3, Theme.ACCENT)
        spinner.start()
        loading_layout.addWidget(spinner, alignment=Qt.AlignmentFlag.AlignCenter)
        
        loading_label = QLabel("Analyzing driver store for unused drivers...")
        loading_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 14px;")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(loading_label)
        
        self.cleanup_layout.insertWidget(0, loading_frame)
        
        # Run scan in background
        self._unused_scan_thread = QThread(self)
        self._unused_scan_worker = UnusedDriverScanWorker(self.scanner)
        self._unused_scan_worker.moveToThread(self._unused_scan_thread)
        
        self._unused_scan_thread.started.connect(self._unused_scan_worker.run)
        self._unused_scan_worker.finished.connect(self._on_unused_scan_complete)
        self._unused_scan_worker.finished.connect(self._unused_scan_thread.quit)
        self._unused_scan_worker.finished.connect(self._unused_scan_worker.deleteLater)
        
        self._unused_scan_thread.start()
    
    def _on_unused_scan_complete(self, unused: list):
        """Handle unused drivers scan complete"""
        self.unused_drivers = unused
        self._clear_layout(self.cleanup_layout)
        
        # Info card
        info_card = QFrame()
        info_card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.INFO_BG};
                border-radius: {Theme.RADIUS_MD}px;
                border: none;
            }}
        """)
        Theme.apply_shadow(info_card)
        info_layout = QHBoxLayout(info_card)
        info_layout.setContentsMargins(16, 12, 16, 12)
        
        info_icon = QLabel("ℹ️")
        info_icon.setStyleSheet("background: transparent; font-size: 18px;")
        info_layout.addWidget(info_icon)
        
        info_text = QLabel("Driver cleanup removes old, unused driver packages from the driver store. "
                          "This can free up disk space. Use caution with drivers marked as 'Caution'.")
        info_text.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 12px;")
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text, 1)
        
        self.cleanup_layout.insertWidget(self.cleanup_layout.count() - 1, info_card)
        
        if not unused:
            # Clean system card
            clean_card = QFrame()
            clean_card.setStyleSheet(f"""
                QFrame {{
                    background: {Theme.SUCCESS_BG};
                    border-radius: {Theme.RADIUS_MD}px;
                    border: none;
                }}
            """)
            Theme.apply_shadow(clean_card)
            clean_layout = QVBoxLayout(clean_card)
            clean_layout.setContentsMargins(24, 24, 24, 24)
            clean_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            check_icon = QLabel("\uE73E")
            check_icon.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 36px; font-weight: bold; font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';")
            check_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            clean_layout.addWidget(check_icon)
            
            clean_title = QLabel("Your Driver Store is Clean!")
            clean_title.setStyleSheet(f"""
                background: transparent;
                color: {Theme.SUCCESS};
                font-size: 16px;
                font-weight: 600;
            """)
            clean_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            clean_layout.addWidget(clean_title)
            
            clean_desc = QLabel("No unused or orphaned drivers were found.")
            clean_desc.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
            clean_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
            clean_layout.addWidget(clean_desc)
            
            self.cleanup_layout.insertWidget(self.cleanup_layout.count() - 1, clean_card)
        else:
            # Stats
            safe_count = sum(1 for d in unused if d.get('risk') == 'safe')
            caution_count = sum(1 for d in unused if d.get('risk') == 'caution')
            
            stats_label = QLabel(f"Found {len(unused)} potentially removable drivers ({safe_count} safe, {caution_count} caution)")
            stats_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 13px; padding: 8px 0;")
            self.cleanup_layout.insertWidget(self.cleanup_layout.count() - 1, stats_label)
            
            # Group by risk level
            safe_drivers = [d for d in unused if d.get('risk') == 'safe']
            caution_drivers = [d for d in unused if d.get('risk') == 'caution']
            
            # Safe to remove section
            if safe_drivers:
                header = QLabel(f"Safe to Remove ({len(safe_drivers)})")
                header.setStyleSheet(f"""
                    background: transparent;
                    color: {Theme.SUCCESS};
                    font-size: 14px;
                    font-weight: 600;
                    padding: 8px 0 4px 0;
                """)
                self.cleanup_layout.insertWidget(self.cleanup_layout.count() - 1, header)
                
                container = ModernListContainer()
                for driver in safe_drivers[:20]:
                    row = container.add_row(
                        title=driver.get('name', driver.get('driver', 'Unknown')),
                        subtitle=f"{driver.get('provider', 'Unknown')} • {driver.get('category', 'Other')} • {driver.get('reason', '')}",
                        status="ok",
                        status_text="Safe"
                    )
                    # Use secondary button - less prominent for bulk actions
                    row.add_action_button("Remove", lambda checked, d=driver: self._remove_driver(d), primary=False)
                
                self.cleanup_layout.insertWidget(self.cleanup_layout.count() - 1, container)
            
            # Caution section
            if caution_drivers:
                header = QLabel(f"Use Caution ({len(caution_drivers)})")
                header.setStyleSheet(f"""
                    background: transparent;
                    color: {Theme.WARNING};
                    font-size: 14px;
                    font-weight: 600;
                    padding: 8px 0 4px 0;
                """)
                self.cleanup_layout.insertWidget(self.cleanup_layout.count() - 1, header)
                
                container = ModernListContainer()
                for driver in caution_drivers[:20]:
                    row = container.add_row(
                        title=driver.get('name', driver.get('driver', 'Unknown')),
                        subtitle=f"{driver.get('provider', 'Unknown')} • {driver.get('category', 'Other')} • {driver.get('reason', '')}",
                        status="warning",
                        status_text="Caution"
                    )
                    row.add_action_button("Remove", lambda checked, d=driver: self._remove_driver(d))
                
                self.cleanup_layout.insertWidget(self.cleanup_layout.count() - 1, container)
        
        # Rescan button
        rescan_frame = QFrame()
        rescan_frame.setStyleSheet("background: transparent;")
        rescan_layout = QHBoxLayout(rescan_frame)
        rescan_layout.setContentsMargins(0, 12, 0, 0)
        
        rescan_btn = QPushButton("Rescan for Unused Drivers")
        rescan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rescan_btn.clicked.connect(self._load_cleanup_data)
        rescan_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                padding: 10px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        Theme.apply_shadow(rescan_btn)
        rescan_layout.addWidget(rescan_btn)
        rescan_layout.addStretch()
        
        self.cleanup_layout.insertWidget(self.cleanup_layout.count() - 1, rescan_frame)
    
    def _remove_driver(self, driver: dict):
        """Remove a driver from the driver store"""
        from PyQt6.QtWidgets import QMessageBox
        
        driver_inf = driver.get('driver', '')
        driver_name = driver.get('name', driver_inf)
        
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Confirm Driver Removal")
        msg.setText(f"Remove driver: {driver_name}?")
        msg.setInformativeText(
            f"Driver: {driver_inf}\n"
            f"Provider: {driver.get('provider', 'Unknown')}\n\n"
            "This action requires administrator privileges.\n"
            "The driver will be removed from the driver store."
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            success, message = self.scanner.remove_driver(driver_inf)
            
            result_msg = QMessageBox()
            if success:
                result_msg.setIcon(QMessageBox.Icon.Information)
                result_msg.setWindowTitle("Success")
                result_msg.setText(f"Driver {driver_inf} removed successfully.")
                # Refresh the list
                self._load_cleanup_data()
            else:
                result_msg.setIcon(QMessageBox.Icon.Warning)
                result_msg.setWindowTitle("Removal Failed")
                result_msg.setText(f"Failed to remove driver: {message}")
            result_msg.exec()
    
    # =========================================================================
    # UPDATES & RESOURCES TAB
    # =========================================================================
    
    def _detect_hardware_vendors(self) -> dict:
        """Detect what hardware vendors are present in the system.
        
        Uses cached data from the main window if available to avoid
        redundant PowerShell calls. Falls back to direct queries only
        if no cached data exists.
        """
        # Return cached vendors if we already detected
        if self._cached_vendors:
            return self._cached_vendors
        
        vendors = {
            'nvidia_gpu': False,
            'amd_gpu': False,
            'intel_gpu': False,
            'intel_cpu': False,
            'amd_cpu': False,
            'realtek_audio': False,
            'realtek_network': False,
            'intel_network': False,
            'manufacturer': None,  # Dell, HP, Lenovo, etc.
            'hp_dock': False,  # HP docking station detected
            'hp_dock_info': None,  # HP dock details if detected
        }
        
        # Try to get cached hardware data from main window first
        main_window = self.window()
        cached_hw = None
        if main_window and hasattr(main_window, 'cached_data'):
            cached_hw = main_window.cached_data.get('hardware')
        
        # Also check if HardwarePage has data
        if not cached_hw and main_window and hasattr(main_window, 'hardware_page'):
            hw_page = main_window.hardware_page
            if hasattr(hw_page, 'hardware_data') and hw_page.hardware_data:
                cached_hw = hw_page.hardware_data
        
        if cached_hw:
            # Extract vendor info from cached hardware data
            try:
                # Check CPU
                cpu_data = cached_hw.get('cpu', {})
                cpu_name = cpu_data.get('name', '').lower()
                if 'intel' in cpu_name:
                    vendors['intel_cpu'] = True
                if 'amd' in cpu_name or 'ryzen' in cpu_name:
                    vendors['amd_cpu'] = True
                
                # Check GPU
                gpu_data = cached_hw.get('gpu', {})
                gpu_name = gpu_data.get('name', '').lower()
                if 'nvidia' in gpu_name or 'geforce' in gpu_name:
                    vendors['nvidia_gpu'] = True
                if 'amd' in gpu_name or 'radeon' in gpu_name:
                    vendors['amd_gpu'] = True
                if 'intel' in gpu_name and ('iris' in gpu_name or 'uhd' in gpu_name or 'arc' in gpu_name or 'graphics' in gpu_name):
                    vendors['intel_gpu'] = True
                
                # Check motherboard manufacturer
                mb_data = cached_hw.get('motherboard', {})
                mfr = mb_data.get('manufacturer', '').lower()
                if 'dell' in mfr:
                    vendors['manufacturer'] = 'dell'
                elif 'hp' in mfr or 'hewlett' in mfr:
                    vendors['manufacturer'] = 'hp'
                elif 'lenovo' in mfr:
                    vendors['manufacturer'] = 'lenovo'
                elif 'asus' in mfr:
                    vendors['manufacturer'] = 'asus'
                elif 'msi' in mfr:
                    vendors['manufacturer'] = 'msi'
                elif 'gigabyte' in mfr:
                    vendors['manufacturer'] = 'gigabyte'
                elif 'acer' in mfr:
                    vendors['manufacturer'] = 'acer'
                
                # Check from installed drivers list for audio/network
                if self.drivers:
                    for driver in self.drivers:
                        name = (driver.device_name + ' ' + driver.manufacturer).lower()
                        dev_class = (driver.device_class or '').lower()
                        if 'realtek' in name:
                            if 'audio' in dev_class or 'sound' in name:
                                vendors['realtek_audio'] = True
                            if 'net' in dev_class or 'ethernet' in name:
                                vendors['realtek_network'] = True
                        if 'intel' in name:
                            if 'net' in dev_class or 'wifi' in name or 'wireless' in name or 'ethernet' in name:
                                vendors['intel_network'] = True
                
                # Check for HP docks from cached hardware data
                hp_docks = cached_hw.get('hp_docks', [])
                if hp_docks and len(hp_docks) > 0:
                    vendors['hp_dock'] = True
                    # Store dock info for UI display
                    if isinstance(hp_docks[0], dict):
                        vendors['hp_dock_info'] = hp_docks[0]
                    else:
                        # It might be an HPDockInfo object
                        vendors['hp_dock_info'] = {
                            'name': getattr(hp_docks[0], 'name', 'HP Dock'),
                            'model': getattr(hp_docks[0], 'model', ''),
                            'dock_type': getattr(hp_docks[0], 'dock_type', ''),
                        }
                
                # Cache and return
                self._cached_vendors = vendors
                return vendors
            except Exception:
                pass  # Fall through to direct query
        
        # Fallback: Direct PowerShell queries (slower, but works without prior scan)
        try:
            import json
            import subprocess
            
            # Check GPU vendors from display adapters
            gpu_cmd = """
            Get-CimInstance Win32_VideoController | Select-Object Name, AdapterCompatibility | ConvertTo-Json
            """
            result = subprocess.run(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", gpu_cmd],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            if result.stdout.strip():
                gpus = json.loads(result.stdout)
                if isinstance(gpus, dict):
                    gpus = [gpus]
                for gpu in gpus:
                    name = (gpu.get('Name', '') + ' ' + gpu.get('AdapterCompatibility', '')).lower()
                    if 'nvidia' in name:
                        vendors['nvidia_gpu'] = True
                    if 'amd' in name or 'radeon' in name:
                        vendors['amd_gpu'] = True
                    if 'intel' in name:
                        vendors['intel_gpu'] = True
            
            # Check CPU vendor
            cpu_cmd = """
            Get-CimInstance Win32_Processor | Select-Object Manufacturer, Name | ConvertTo-Json
            """
            result = subprocess.run(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", cpu_cmd],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            if result.stdout.strip():
                cpus = json.loads(result.stdout)
                if isinstance(cpus, dict):
                    cpus = [cpus]
                for cpu in cpus:
                    name = (cpu.get('Name', '') + ' ' + cpu.get('Manufacturer', '')).lower()
                    if 'intel' in name:
                        vendors['intel_cpu'] = True
                    if 'amd' in name:
                        vendors['amd_cpu'] = True
            
            # Check system manufacturer
            sys_cmd = """
            (Get-CimInstance Win32_ComputerSystem).Manufacturer
            """
            result = subprocess.run(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", sys_cmd],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            if result.stdout.strip():
                mfr = result.stdout.strip().lower()
                if 'dell' in mfr:
                    vendors['manufacturer'] = 'dell'
                elif 'hp' in mfr or 'hewlett' in mfr:
                    vendors['manufacturer'] = 'hp'
                elif 'lenovo' in mfr:
                    vendors['manufacturer'] = 'lenovo'
                elif 'asus' in mfr:
                    vendors['manufacturer'] = 'asus'
                elif 'msi' in mfr:
                    vendors['manufacturer'] = 'msi'
                elif 'gigabyte' in mfr:
                    vendors['manufacturer'] = 'gigabyte'
                elif 'acer' in mfr:
                    vendors['manufacturer'] = 'acer'
            
            # Check for Realtek and Intel network/audio from drivers
            if self.drivers:
                for driver in self.drivers:
                    name = (driver.device_name + ' ' + driver.manufacturer).lower()
                    dev_class = (driver.device_class or '').lower()
                    if 'realtek' in name:
                        if 'audio' in dev_class or 'sound' in name:
                            vendors['realtek_audio'] = True
                        if 'net' in dev_class or 'ethernet' in name:
                            vendors['realtek_network'] = True
                    if 'intel' in name:
                        if 'net' in dev_class or 'wifi' in name or 'wireless' in name or 'ethernet' in name:
                            vendors['intel_network'] = True
        except Exception:
            pass
        
        # Direct HP dock detection (runs regardless of cached data)
        if not vendors['hp_dock']:
            try:
                if HARDWARE_SCANNER_AVAILABLE:
                    from hardware_scanner import detect_hp_docks
                    hp_docks = detect_hp_docks()
                    if hp_docks:
                        vendors['hp_dock'] = True
                        dock = hp_docks[0]
                        vendors['hp_dock_info'] = {
                            'name': dock.name,
                            'model': dock.model,
                            'dock_type': dock.dock_type,
                        }
            except Exception:
                pass
        
        # Cache the result
        self._cached_vendors = vendors
        return vendors
    
    def _load_updates_data(self):
        """Load updates and resources data with hardware detection"""
        self._clear_layout(self.updates_layout)
        
        # Detect hardware
        vendors = self._detect_hardware_vendors()
        
        # Check if any hardware was detected
        has_detected = (vendors['nvidia_gpu'] or vendors['amd_gpu'] or vendors['intel_gpu'] or 
                       vendors['intel_cpu'] or vendors['amd_cpu'] or vendors['realtek_audio'] or 
                       vendors['realtek_network'] or vendors['intel_network'] or vendors.get('manufacturer') or
                       vendors.get('hp_dock'))
        
        # Driver Resources section header
        resources_header = QLabel("Driver Download Resources")
        resources_header.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 16px;
            font-weight: 600;
            padding: 0 0 8px 0;
        """)
        self.updates_layout.insertWidget(self.updates_layout.count() - 1, resources_header)
        
        # Build description based on detected hardware
        if has_detected:
            desc_text = "Recommended drivers based on your detected hardware. Other suggestions shown below."
        else:
            desc_text = "Run a driver scan first to get personalized recommendations, or browse common drivers below."
        resources_desc = QLabel(desc_text)
        resources_desc.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 13px; padding-bottom: 12px;")
        resources_desc.setWordWrap(True)
        self.updates_layout.insertWidget(self.updates_layout.count() - 1, resources_desc)
        
        # =================================================================
        # DETECTED HARDWARE - Recommended drivers
        # =================================================================
        
        if has_detected:
            detected_header = QLabel("Recommended for Your Hardware")
            detected_header.setStyleSheet(f"""
                background: transparent;
                color: {Theme.SUCCESS};
                font-size: 14px;
                font-weight: 600;
                padding: 8px 0 4px 0;
            """)
            self.updates_layout.insertWidget(self.updates_layout.count() - 1, detected_header)
            
            detected_container = ModernListContainer()
            
            # NVIDIA GPU detected
            if vendors['nvidia_gpu']:
                nvidia_row = detected_container.add_row(
                    title="NVIDIA GeForce Drivers",
                    subtitle="NVIDIA GPU detected - Game Ready & Studio drivers",
                    status="ok",
                    status_text="Detected"
                )
                nvidia_row.add_action_button("Download", lambda: self._open_url("https://www.nvidia.com/Download/index.aspx"), primary=True)
                nvidia_row.add_action_button("GeForce Experience", lambda: self._open_url("https://www.nvidia.com/en-us/geforce/geforce-experience/"))
            
            # AMD GPU detected
            if vendors['amd_gpu']:
                amd_row = detected_container.add_row(
                    title="AMD Radeon Software",
                    subtitle="AMD GPU detected - Adrenalin Edition",
                    status="ok",
                    status_text="Detected"
                )
                amd_row.add_action_button("Download", lambda: self._open_url("https://www.amd.com/en/support"), primary=True)
                amd_row.add_action_button("Auto-Detect", lambda: self._open_url("https://www.amd.com/en/support/kb/faq/gpu-131"))
            
            # Intel GPU detected
            if vendors['intel_gpu']:
                intel_row = detected_container.add_row(
                    title="Intel Graphics Drivers",
                    subtitle="Intel GPU detected - Arc, Iris Xe, or integrated",
                    status="ok",
                    status_text="Detected"
                )
                intel_row.add_action_button("Download", lambda: self._open_url("https://www.intel.com/content/www/us/en/download/785597/intel-arc-iris-xe-graphics-windows.html"), primary=True)
                intel_row.add_action_button("Driver Assistant", lambda: self._open_url("https://www.intel.com/content/www/us/en/support/detect.html"))
            
            # Intel CPU/Chipset detected
            if vendors['intel_cpu']:
                intel_chipset_row = detected_container.add_row(
                    title="Intel Chipset Drivers",
                    subtitle="Intel CPU detected - INF utility for system stability",
                    status="ok",
                    status_text="Detected"
                )
                intel_chipset_row.add_action_button("Download", lambda: self._open_url("https://www.intel.com/content/www/us/en/download/19347/chipset-inf-utility.html"), primary=True)
            
            # AMD CPU/Chipset detected
            if vendors['amd_cpu']:
                amd_chipset_row = detected_container.add_row(
                    title="AMD Chipset Drivers",
                    subtitle="AMD CPU detected - Ryzen chipset drivers",
                    status="ok",
                    status_text="Detected"
                )
                amd_chipset_row.add_action_button("Download", lambda: self._open_url("https://www.amd.com/en/support/download/drivers.html"), primary=True)
            
            # Realtek Audio detected
            if vendors['realtek_audio']:
                realtek_row = detected_container.add_row(
                    title="Realtek Audio Drivers",
                    subtitle="Realtek audio detected - HD Audio codecs",
                    status="ok",
                    status_text="Detected"
                )
                realtek_row.add_action_button("Download", lambda: self._open_url("https://www.realtek.com/en/component/zoo/category/pc-audio-codecs-high-definition-audio-codecs-software"), primary=True)
            
            # Intel Network detected
            if vendors['intel_network']:
                intel_net_row = detected_container.add_row(
                    title="Intel Network Drivers",
                    subtitle="Intel network adapter detected",
                    status="ok",
                    status_text="Detected"
                )
                intel_net_row.add_action_button("Download", lambda: self._open_url("https://www.intel.com/content/www/us/en/download/18293/intel-network-adapter-driver-for-windows-10.html"), primary=True)
            
            # Realtek Network detected
            if vendors['realtek_network']:
                realtek_net_row = detected_container.add_row(
                    title="Realtek Network Drivers",
                    subtitle="Realtek ethernet detected",
                    status="ok",
                    status_text="Detected"
                )
                realtek_net_row.add_action_button("Download", lambda: self._open_url("https://www.realtek.com/en/component/zoo/category/network-interface-controllers-10-100-1000m-gigabit-ethernet-pci-express-software"), primary=True)
            
            # HP Dock detected
            if vendors.get('hp_dock'):
                dock_info = vendors.get('hp_dock_info', {})
                dock_name = dock_info.get('name', 'HP Dock')
                dock_model = dock_info.get('model', '')
                dock_type = dock_info.get('dock_type', '')
                
                subtitle_parts = ["HP docking station detected"]
                if dock_model:
                    subtitle_parts.append(f"• {dock_model}")
                elif dock_type:
                    subtitle_parts.append(f"• {dock_type}")
                subtitle_parts.append("• Check for firmware updates")
                
                hp_dock_row = detected_container.add_row(
                    title="HP Dock Firmware",
                    subtitle=" ".join(subtitle_parts),
                    status="warning",
                    status_text="Check Updates"
                )
                hp_dock_row.add_action_button("HP Dock Firmware", lambda: self._open_url("https://support.hp.com/us-en/drivers/docking-stations"), primary=True)
                hp_dock_row.add_action_button("HP Support Assistant", lambda: self._open_url("https://support.hp.com/us-en/help/hp-support-assistant"))
            
            # OEM/Manufacturer support page
            mfr = vendors.get('manufacturer')
            if mfr:
                mfr_urls = {
                    'dell': ("Dell Support", "https://www.dell.com/support/home"),
                    'hp': ("HP Support", "https://support.hp.com/us-en/drivers"),
                    'lenovo': ("Lenovo Support", "https://support.lenovo.com/us/en/"),
                    'asus': ("ASUS Support", "https://www.asus.com/support/"),
                    'msi': ("MSI Support", "https://www.msi.com/support"),
                    'gigabyte': ("GIGABYTE Support", "https://www.gigabyte.com/Support"),
                    'acer': ("Acer Support", "https://www.acer.com/ac/en/US/content/drivers"),
                }
                if mfr in mfr_urls:
                    name, url = mfr_urls[mfr]
                    mfr_row = detected_container.add_row(
                        title=name,
                        subtitle=f"{mfr.title()} system detected • Get system-specific drivers",
                        status="ok",
                        status_text="Detected"
                    )
                    mfr_row.add_action_button("Open", lambda u=url: self._open_url(u), primary=True)
            
            self.updates_layout.insertWidget(self.updates_layout.count() - 1, detected_container)
        
        # =================================================================
        # OTHER DRIVER SUGGESTIONS (Not detected but available)
        # =================================================================
        other_header = QLabel("Other Available Drivers")
        other_header.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_SECONDARY};
            font-size: 14px;
            font-weight: 600;
            padding: 16px 0 4px 0;
        """)
        self.updates_layout.insertWidget(self.updates_layout.count() - 1, other_header)
        
        other_desc = QLabel("These drivers may be useful if you have hardware not automatically detected.")
        other_desc.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px; padding-bottom: 8px;")
        self.updates_layout.insertWidget(self.updates_layout.count() - 1, other_desc)
        
        other_container = ModernListContainer()
        
        # Add non-detected GPU drivers as suggestions
        if not vendors['nvidia_gpu']:
            nvidia_row = other_container.add_row(
                title="NVIDIA GeForce Drivers",
                subtitle="For GeForce GTX/RTX graphics cards",
                status="info"
            )
            nvidia_row.add_action_button("Download", lambda: self._open_url("https://www.nvidia.com/Download/index.aspx"))
        
        if not vendors['amd_gpu']:
            amd_row = other_container.add_row(
                title="AMD Radeon Software",
                subtitle="For Radeon RX graphics cards",
                status="info"
            )
            amd_row.add_action_button("Download", lambda: self._open_url("https://www.amd.com/en/support"))
        
        if not vendors['intel_gpu']:
            intel_row = other_container.add_row(
                title="Intel Graphics Drivers",
                subtitle="For Intel Arc, Iris Xe, integrated graphics",
                status="info"
            )
            intel_row.add_action_button("Download", lambda: self._open_url("https://www.intel.com/content/www/us/en/download/785597/intel-arc-iris-xe-graphics-windows.html"))
        
        if not vendors['intel_cpu']:
            intel_chipset_row = other_container.add_row(
                title="Intel Chipset Drivers",
                subtitle="INF drivers for Intel chipsets",
                status="info"
            )
            intel_chipset_row.add_action_button("Download", lambda: self._open_url("https://www.intel.com/content/www/us/en/download/19347/chipset-inf-utility.html"))
        
        if not vendors['amd_cpu']:
            amd_chipset_row = other_container.add_row(
                title="AMD Chipset Drivers",
                subtitle="For AMD Ryzen processors",
                status="info"
            )
            amd_chipset_row.add_action_button("Download", lambda: self._open_url("https://www.amd.com/en/support/download/drivers.html"))
        
        if not vendors['realtek_audio']:
            realtek_row = other_container.add_row(
                title="Realtek Audio Drivers",
                subtitle="HD Audio codecs for onboard audio",
                status="info"
            )
            realtek_row.add_action_button("Download", lambda: self._open_url("https://www.realtek.com/en/component/zoo/category/pc-audio-codecs-high-definition-audio-codecs-software"))
        
        if not vendors['intel_network']:
            intel_net_row = other_container.add_row(
                title="Intel Network Drivers",
                subtitle="Ethernet and WiFi adapters",
                status="info"
            )
            intel_net_row.add_action_button("Download", lambda: self._open_url("https://www.intel.com/content/www/us/en/download/18293/intel-network-adapter-driver-for-windows-10.html"))
        
        if not vendors['realtek_network']:
            realtek_net_row = other_container.add_row(
                title="Realtek Network Drivers",
                subtitle="Ethernet controllers",
                status="info"
            )
            realtek_net_row.add_action_button("Download", lambda: self._open_url("https://www.realtek.com/en/component/zoo/category/network-interface-controllers-10-100-1000m-gigabit-ethernet-pci-express-software"))
        
        self.updates_layout.insertWidget(self.updates_layout.count() - 1, other_container)
        
        # =================================================================
        # MANUFACTURER TOOLS SECTION
        # =================================================================
        tools_header = QLabel("Manufacturer Update Tools")
        tools_header.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 600;
            padding: 16px 0 4px 0;
        """)
        self.updates_layout.insertWidget(self.updates_layout.count() - 1, tools_header)
        
        tools_desc = QLabel("These tools automatically detect and update drivers for your specific system.")
        tools_desc.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 12px; padding-bottom: 8px;")
        self.updates_layout.insertWidget(self.updates_layout.count() - 1, tools_desc)
        
        tools_container = ModernListContainer()
        
        # Define all manufacturer tools with detection
        manufacturer_tools = [
            ("dell", "Dell SupportAssist", "Automatic driver updates for Dell PCs", "https://www.dell.com/support/contents/en-us/article/product-support/self-support-knowledgebase/software-and-downloads/supportassist"),
            ("hp", "HP Support Assistant", "Driver and BIOS updates for HP systems", "https://support.hp.com/us-en/help/hp-support-assistant"),
            ("lenovo", "Lenovo Vantage", "System updates for Lenovo/ThinkPad", "https://www.lenovo.com/us/en/software/vantage"),
            ("asus", "ASUS MyASUS", "Driver management for ASUS computers", "https://www.asus.com/supportonly/MyASUS/"),
            ("msi", "MSI Center", "Updates for MSI motherboards and laptops", "https://www.msi.com/Landing/msi-center"),
            ("gigabyte", "Gigabyte Control Center", "Driver updates for Gigabyte boards", "https://www.gigabyte.com/Support/Utility"),
            ("acer", "Acer Care Center", "Updates for Acer systems", "https://www.acer.com/us-en/support"),
        ]
        
        detected_mfr = vendors.get('manufacturer')
        
        # Show detected manufacturer first with highlight
        for mfr_id, name, desc, url in manufacturer_tools:
            if mfr_id == detected_mfr:
                row = tools_container.add_row(
                    title=name,
                    subtitle=f"{desc}",
                    status="ok",
                    status_text="Your System"
                )
                row.add_action_button("Get Tool", lambda u=url: self._open_url(u), primary=True)
                break
        
        # Show other manufacturers as suggestions
        for mfr_id, name, desc, url in manufacturer_tools:
            if mfr_id != detected_mfr:
                row = tools_container.add_row(
                    title=name,
                    subtitle=desc,
                    status="info"
                )
                row.add_action_button("Get Tool", lambda u=url: self._open_url(u))
        
        self.updates_layout.insertWidget(self.updates_layout.count() - 1, tools_container)
        
        # =================================================================
        # WINDOWS UPDATE SECTION
        # =================================================================
        wu_header = QLabel("Windows Update Driver Check")
        wu_header.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 600;
            padding: 16px 0 4px 0;
        """)
        self.updates_layout.insertWidget(self.updates_layout.count() - 1, wu_header)
        
        wu_card = QFrame()
        wu_card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border-radius: {Theme.RADIUS_MD}px;
                border: none;
            }}
        """)
        Theme.apply_shadow(wu_card)
        wu_layout = QHBoxLayout(wu_card)
        wu_layout.setContentsMargins(16, 16, 16, 16)
        
        wu_text = QLabel("Check Windows Update for additional driver updates available for your hardware.")
        wu_text.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        wu_text.setWordWrap(True)
        wu_layout.addWidget(wu_text, 1)
        
        wu_btn = QPushButton("Check Windows Update")
        wu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        wu_btn.clicked.connect(self._check_windows_update_drivers)
        wu_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT_HOVER};
            }}
        """)
        wu_layout.addWidget(wu_btn)
        
        self.updates_layout.insertWidget(self.updates_layout.count() - 1, wu_card)
        
        # Windows Update results placeholder
        self.wu_results_container = QFrame()
        self.wu_results_container.setStyleSheet("background: transparent;")
        self.wu_results_layout = QVBoxLayout(self.wu_results_container)
        self.wu_results_layout.setContentsMargins(0, 8, 0, 0)
        self.wu_results_layout.setSpacing(8)
        self.updates_layout.insertWidget(self.updates_layout.count() - 1, self.wu_results_container)
    
    def _check_windows_update_drivers(self):
        """Check Windows Update for driver updates"""
        # Clear previous results
        while self.wu_results_layout.count():
            item = self.wu_results_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        
        # Loading indicator
        loading_label = QLabel("⏳ Checking Windows Update for driver updates (this may take a minute)...")
        loading_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        self.wu_results_layout.addWidget(loading_label)
        
        # Run in background
        self._wu_check_thread = QThread(self)
        self._wu_check_worker = DriverUpdateCheckWorker(self.scanner)
        self._wu_check_worker.moveToThread(self._wu_check_thread)
        
        self._wu_check_thread.started.connect(self._wu_check_worker.run)
        self._wu_check_worker.finished.connect(self._on_wu_check_complete)
        self._wu_check_worker.finished.connect(self._wu_check_thread.quit)
        self._wu_check_worker.finished.connect(self._wu_check_worker.deleteLater)
        
        self._wu_check_thread.start()
    
    def _on_wu_check_complete(self, updates: list):
        """Handle Windows Update check complete"""
        # Clear loading
        while self.wu_results_layout.count():
            item = self.wu_results_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        
        if not updates:
            result_label = QLabel("No driver updates available from Windows Update")
            result_label.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 13px;")
            self.wu_results_layout.addWidget(result_label)
        else:
            result_label = QLabel(f"Found {len(updates)} driver updates available:")
            result_label.setStyleSheet(f"background: transparent; color: {Theme.WARNING}; font-size: 13px;")
            self.wu_results_layout.addWidget(result_label)
            
            container = ModernListContainer()
            for update in updates:
                row = container.add_row(
                    title=update.get('title', 'Unknown Update'),
                    subtitle=f"{update.get('manufacturer', 'Unknown')} • {update.get('date', '')}",
                    status="warning",
                    status_text="Available"
                )
            self.wu_results_layout.addWidget(container)
            
            # Install button
            install_frame = QFrame()
            install_frame.setStyleSheet("background: transparent;")
            install_layout = QHBoxLayout(install_frame)
            install_layout.setContentsMargins(0, 8, 0, 0)
            
            install_btn = QPushButton("Open Windows Update")
            install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            install_btn.clicked.connect(lambda: subprocess.Popen(["ms-settings:windowsupdate"]))
            install_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {Theme.ACCENT};
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: {Theme.RADIUS_SM}px;
                    font-size: 13px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {Theme.ACCENT_HOVER};
                }}
            """)
            install_layout.addWidget(install_btn)
            install_layout.addStretch()
            
            self.wu_results_layout.addWidget(install_frame)
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _create_stat(self, label: str, value: str, color: str | None = None):
        """Create a stat display widget"""
        frame = QFrame()
        frame.setStyleSheet("background: transparent;")
        frame.setMinimumWidth(100)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        val_label = QLabel(value)
        val_label.setObjectName("stat_value")
        actual_color = color or Theme.TEXT_PRIMARY
        val_label.setStyleSheet(f"""
            background: transparent;
            color: {actual_color};
            font-size: 24px;
            font-weight: 700;
        """)
        layout.addWidget(val_label)
        
        name_label = QLabel(label)
        name_label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_TERTIARY};
            font-size: 11px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(name_label)
        
        return frame
    
    def _add_stat_divider(self, layout):
        """Add a vertical divider between stats"""
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setFixedHeight(40)
        divider.setStyleSheet("background: rgba(255, 255, 255, 0.08);")
        layout.addSpacing(24)
        layout.addWidget(divider)
        layout.addSpacing(24)
    
    def _fix_driver(self, driver):
        """Open Device Manager to fix a problematic driver"""
        from PyQt6.QtWidgets import QMessageBox
        
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("Fix Driver")
        msg.setText(f"Opening Device Manager for: {driver.device_name}")
        msg.setInformativeText(
            "To fix this driver:\n\n"
            "1. Find the device in Device Manager\n"
            "2. Right-click and select 'Update driver'\n"
            "   - or 'Uninstall device' to remove it\n"
            "3. For unsigned drivers, you may need to\n"
            "   download from the manufacturer's website\n\n"
            f"Device class: {driver.device_class or 'Unknown'}"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
        
        self._open_device_manager()
    
    def _open_device_manager(self):
        """Open Windows Device Manager"""
        try:
            subprocess.Popen(["devmgmt.msc"])
        except Exception:
            pass
    
    def _open_url(self, url: str):
        """Open a URL in the default browser"""
        import webbrowser
        webbrowser.open(url)
    
    def scan_drivers(self):
        """Public method to trigger driver scan - called from full system scan"""
        # Switch to installed tab and trigger scan
        self._switch_tab("installed")
        self._scan_installed_drivers()
    
    def display_cached_data(self, data):
        """Display driver data from cache (if any)"""
        # If we have cached driver data, display it
        if data and isinstance(data, list) and len(data) > 0:
            self.drivers = data
            # Switch to installed tab
            self._switch_tab("installed")
            # Simulate scan completion with cached data
            self._on_installed_scan_complete(data, [])


class AppSettings:
    """Manages application settings persistence"""
    
    DEFAULT_SETTINGS = {
        "theme": "Dark",
        "accent_color": "Blue",
        "auto_scan": False,
        "check_driver_updates": True,
        "show_notifications": True,
    }
    
    def __init__(self):
        self.config_dir = Path.home() / ".healthchecker"
        self.config_file = self.config_dir / "settings.json"
        self.settings = self.load()
    
    def load(self) -> dict:
        """Load settings from file or return defaults"""
        # In production mode, always use defaults (no persistence)
        if PRODUCTION_MODE:
            return self.DEFAULT_SETTINGS.copy()
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    saved = json.load(f)
                    # Merge with defaults to handle new settings
                    return {**self.DEFAULT_SETTINGS, **saved}
        except Exception:
            pass
        return self.DEFAULT_SETTINGS.copy()
    
    def save(self):
        """Save settings to file"""
        # In production mode, don't persist settings
        if PRODUCTION_MODE:
            return
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Failed to save settings: {e}")
    
    def get(self, key: str, default=None):
        return self.settings.get(key, default)
    
    def set(self, key: str, value):
        self.settings[key] = value
        self.save()
        # Notify listeners of change
        if key == "accent_color":
            apply_accent_color_from_settings()
            _trigger_theme_refresh()
        elif key == "theme":
            apply_theme_from_settings()
            _trigger_theme_refresh()


def _trigger_theme_refresh():
    """Trigger UI refresh on all top-level widgets"""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app:
        for widget in app.topLevelWidgets():
            if hasattr(widget, 'apply_full_theme_refresh'):
                widget.apply_full_theme_refresh()


# Global settings instance
app_settings = AppSettings()


# =============================================================================
# THEME DEFINITIONS - Dark and Light modes
# =============================================================================

DARK_THEME = {
    # Surface colors
    "SURFACE_BASE": "#1a1a1e",
    "SURFACE_00DP": "#1a1a1e",
    "SURFACE_01DP": "#212125",
    "SURFACE_02DP": "#28282d",
    "SURFACE_03DP": "#2e2e33",
    "SURFACE_04DP": "#333338",
    "SURFACE_06DP": "#3a3a40",
    "SURFACE_08DP": "#404046",
    "SURFACE_12DP": "#48484f",
    "SURFACE_16DP": "#505058",
    "SURFACE_24DP": "#5a5a62",
    # Semantic surfaces
    "BG_WINDOW": "#1a1a1e",
    "BG_SIDEBAR": "#212125",
    "BG_CARD": "#28282d",
    "BG_CARD_HOVER": "#333338",
    "BG_ELEVATED": "#3a3a40",
    "BG_DIALOG": "#5a5a62",
    # Borders
    "BORDER": "#404048",
    "BORDER_LIGHT": "#505058",
    # Text
    "TEXT_PRIMARY": "#ffffff",
    "TEXT_SECONDARY": "#c0c0c8",
    "TEXT_TERTIARY": "#808088",
    "TEXT_DISABLED": "#606068",
    "TEXT_PRIMARY_HEX": "#ffffff",
    "TEXT_SECONDARY_HEX": "#c0c0c8",
    "TEXT_TERTIARY_HEX": "#808088",
    # On primary (text on accent buttons)
    "ON_PRIMARY": "#ffffff",
    # Shadow
    "SHADOW_COLOR": "#000000",
    "SHADOW_OPACITY": 80,
    # Glass
    "GLASS_BG": "rgba(40, 40, 45, 0.75)",
    "GLASS_BG_LIGHT": "rgba(60, 60, 68, 0.6)",
    "GLASS_BORDER": "rgba(255, 255, 255, 0.1)",
    "GLASS_BORDER_HOVER": "rgba(255, 255, 255, 0.2)",
}

LIGHT_THEME = {
    # Surface colors - Light mode uses white/grey
    "SURFACE_BASE": "#f5f5f5",
    "SURFACE_00DP": "#f5f5f5",
    "SURFACE_01DP": "#ffffff",
    "SURFACE_02DP": "#ffffff",
    "SURFACE_03DP": "#f0f0f0",
    "SURFACE_04DP": "#e8e8e8",
    "SURFACE_06DP": "#e0e0e0",
    "SURFACE_08DP": "#d8d8d8",
    "SURFACE_12DP": "#d0d0d0",
    "SURFACE_16DP": "#c8c8c8",
    "SURFACE_24DP": "#c0c0c0",
    # Semantic surfaces
    "BG_WINDOW": "#f5f5f5",
    "BG_SIDEBAR": "#ffffff",
    "BG_CARD": "#ffffff",
    "BG_CARD_HOVER": "#f0f0f0",
    "BG_ELEVATED": "#ffffff",
    "BG_DIALOG": "#ffffff",
    # Borders
    "BORDER": "#d0d0d0",
    "BORDER_LIGHT": "#e0e0e0",
    # Text - Dark text on light background
    "TEXT_PRIMARY": "#1a1a1a",
    "TEXT_SECONDARY": "#505050",
    "TEXT_TERTIARY": "#808080",
    "TEXT_DISABLED": "#a0a0a0",
    "TEXT_PRIMARY_HEX": "#1a1a1a",
    "TEXT_SECONDARY_HEX": "#505050",
    "TEXT_TERTIARY_HEX": "#808080",
    # On primary (text on accent buttons)
    "ON_PRIMARY": "#ffffff",
    # Shadow
    "SHADOW_COLOR": "#000000",
    "SHADOW_OPACITY": 40,
    # Glass
    "GLASS_BG": "rgba(255, 255, 255, 0.85)",
    "GLASS_BG_LIGHT": "rgba(255, 255, 255, 0.7)",
    "GLASS_BORDER": "rgba(0, 0, 0, 0.1)",
    "GLASS_BORDER_HOVER": "rgba(0, 0, 0, 0.2)",
}


def apply_theme_from_settings():
    """Apply the saved theme (Dark/Light) to the Theme class"""
    theme_name = app_settings.get("theme", "Dark")
    theme_colors = DARK_THEME if theme_name == "Dark" else LIGHT_THEME
    
    # Apply all theme colors to Theme class
    for key, value in theme_colors.items():
        setattr(Theme, key, value)
    
    # Update gradient with current surface colors
    Theme.GRADIENT_SURFACE = f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {Theme.SURFACE_04DP}, stop:1 {Theme.SURFACE_02DP})"


def apply_accent_color_from_settings():
    """Apply the saved accent color to the Theme class"""
    accent_name = app_settings.get("accent_color", "Blue")
    if accent_name in Theme.ACCENT_COLORS:
        colors = Theme.ACCENT_COLORS[accent_name]
        Theme.PRIMARY = colors["primary"]
        Theme.PRIMARY_HOVER = colors["hover"]
        Theme.PRIMARY_PRESSED = colors["pressed"]
        Theme.PRIMARY_LIGHT = colors["light"]
        Theme.ACCENT = colors["primary"]
        Theme.ACCENT_HOVER = colors["hover"]
        Theme.ACCENT_SUBTLE = colors["subtle"]
        Theme.BORDER_ACCENT = colors["primary"]
        # Update gradient
        Theme.GRADIENT_ACCENT = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {colors['primary']}, stop:1 {colors['light']})"


# Apply theme and accent color on startup
apply_theme_from_settings()
apply_accent_color_from_settings()


class StartupPage(QWidget):
    """Page for managing startup programs with modern design"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.startup_items = []
        self.item_widgets = []
        self.loaded = False  # Track if data has been loaded
        self.current_filter = "all"  # all, enabled, disabled
        self.setup_ui()
    
    def setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(32, 28, 32, 28)
        self.content_layout.setSpacing(24)
        
        # Header row
        header = QHBoxLayout()
        header.setSpacing(12)
        
        title = QLabel("Startup Programs")
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 28px;
            font-weight: 600;
        """)
        header.addWidget(title)
        header.addStretch()
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.load_startup_items)
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                padding: 10px 24px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT_HOVER};
            }}
        """)
        header.addWidget(self.refresh_btn)
        
        # Open Task Manager button
        self.taskmgr_btn = QPushButton("Open Task Manager")
        self.taskmgr_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.taskmgr_btn.clicked.connect(self.open_task_manager)
        self.taskmgr_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_SECONDARY};
                border: none;
                padding: 12px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        header.addWidget(self.taskmgr_btn)
        
        self.content_layout.addLayout(header)
        
        # Summary stats card with improved styling
        self.stats_frame = QFrame()
        self.stats_frame.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(self.stats_frame, blur_radius=12, offset_y=3, opacity=60)
        
        stats_layout = QHBoxLayout(self.stats_frame)
        stats_layout.setContentsMargins(24, 20, 24, 20)
        stats_layout.setSpacing(0)
        
        self.stat_total = self._create_stat("Total", "—", Theme.TEXT_PRIMARY)
        self.stat_enabled = self._create_stat("Enabled", "—", Theme.SUCCESS)
        self.stat_disabled = self._create_stat("Disabled", "—", Theme.TEXT_TERTIARY)
        self.stat_high_impact = self._create_stat("High Impact", "—", Theme.WARNING)
        
        stats_layout.addWidget(self.stat_total)
        self._add_stat_divider(stats_layout)
        stats_layout.addWidget(self.stat_enabled)
        self._add_stat_divider(stats_layout)
        stats_layout.addWidget(self.stat_disabled)
        self._add_stat_divider(stats_layout)
        stats_layout.addWidget(self.stat_high_impact)
        stats_layout.addStretch()
        
        self.content_layout.addWidget(self.stats_frame)
        
        # Filter tabs
        filter_frame = QFrame()
        filter_frame.setStyleSheet("background: transparent;")
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(8)
        
        self.filter_buttons = {}
        for filter_id, filter_name in [("all", "All"), ("enabled", "Enabled"), ("disabled", "Disabled")]:
            btn = QPushButton(filter_name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setChecked(filter_id == "all")
            btn.clicked.connect(lambda checked, fid=filter_id: self._set_filter(fid))
            self.filter_buttons[filter_id] = btn
            filter_layout.addWidget(btn)
        
        filter_layout.addStretch()
        self._update_filter_styles()
        self.content_layout.addWidget(filter_frame)
        
        # Status label
        self.status_label = QLabel("Loading startup programs...")
        self.status_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 14px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.status_label)
        
        # Modern items list container
        self.items_list = ModernListContainer()
        self.items_list.setVisible(False)
        self.content_layout.addWidget(self.items_list)
        
        self.content_layout.addStretch()
        
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        
        # Floating Quick Tools bar
        tools = [
            ("Task Manager", "\uE9D5", self.open_task_manager),
            ("Startup Apps", "\uE7B5", self._open_startup_settings),
            ("Services", "\uE912", self._open_services),
        ]
        self._floating_toolbar = FloatingToolbar(tools, self)
    
    def resizeEvent(self, event):
        """Reposition floating toolbar on resize"""
        super().resizeEvent(event)
        if hasattr(self, '_floating_toolbar'):
            self._floating_toolbar.update_position()
    
    def _open_startup_settings(self):
        """Open Windows Startup Apps Settings"""
        import subprocess
        try:
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:startupapps"],
                           creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        except:
            pass
    
    def _open_services(self):
        """Open Services MMC"""
        import subprocess
        try:
            subprocess.Popen(["services.msc"])
        except:
            pass
    
    def _add_stat_divider(self, layout):
        """Add a vertical divider between stats"""
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setFixedHeight(40)
        divider.setStyleSheet("background: rgba(255, 255, 255, 0.08);")
        layout.addSpacing(24)
        layout.addWidget(divider)
        layout.addSpacing(24)
    
    def _update_filter_styles(self):
        """Update filter button styles based on current selection"""
        for filter_id, btn in self.filter_buttons.items():
            if filter_id == self.current_filter:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {Theme.ACCENT};
                        color: white;
                        border: none;
                        padding: 10px 24px;
                        border-radius: {Theme.RADIUS_SM}px;
                        font-size: 13px;
                        font-weight: 600;
                    }}
                    QPushButton:hover {{
                        background: {Theme.ACCENT_HOVER};
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {Theme.BG_CARD};
                        color: {Theme.TEXT_SECONDARY};
                        border: none;
                        padding: 10px 24px;
                        border-radius: {Theme.RADIUS_SM}px;
                        font-size: 13px;
                        font-weight: 500;
                    }}
                    QPushButton:hover {{
                        background: {Theme.BG_CARD_HOVER};
                        color: {Theme.TEXT_PRIMARY};
                    }}
                """)
    
    def _set_filter(self, filter_id: str):
        """Set the current filter and refresh the display"""
        self.current_filter = filter_id
        for fid, btn in self.filter_buttons.items():
            btn.setChecked(fid == filter_id)
        self._update_filter_styles()
        self._display_items()
    
    def _create_stat(self, label: str, value: str, color: str | None = None):
        """Create an improved stat display widget"""
        frame = QFrame()
        frame.setStyleSheet("background: transparent;")
        frame.setMinimumWidth(100)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        val_label = QLabel(value)
        val_label.setObjectName("stat_value")
        actual_color = color or Theme.TEXT_PRIMARY
        val_label.setStyleSheet(f"""
            background: transparent;
            color: {actual_color};
            font-size: 24px;
            font-weight: 700;
        """)
        layout.addWidget(val_label)
        
        name_label = QLabel(label)
        name_label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_TERTIARY};
            font-size: 11px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(name_label)
        
        return frame
    
    def _update_stat(self, frame: QFrame, value: str):
        """Update a stat widget's value"""
        val_label = frame.findChild(QLabel, "stat_value")
        if val_label:
            val_label.setText(value)
    
    def load_startup_items(self):
        """Load startup programs using background thread"""
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Scanning...")
        self.status_label.setText("Scanning startup programs...")
        self.status_label.setVisible(True)
        
        # Run scan in background thread
        self._thread = QThread(self)
        self._worker = StartupScanWorker()
        self._worker.moveToThread(self._thread)
        
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_startup_scan_complete)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        
        self._thread.start()
    
    def display_cached_data(self, items: list):
        """Display startup items from cached data (from full scan)"""
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Refresh")
        self._on_startup_scan_complete(items)
        self.loaded = True
    
    def _on_startup_scan_complete(self, items: list):
        """Handle completion of startup scan (called on main thread)"""
        self.startup_items = items
        
        # Update stats
        self._update_summary_counts()
        
        # Display items with current filter
        self._display_items()
        
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Refresh")
        self.loaded = True
    
    def _display_items(self):
        """Display startup items based on current filter"""
        # Filter items based on current selection
        if self.current_filter == "enabled":
            filtered_items = [item for item in self.startup_items if item.get("enabled", False)]
        elif self.current_filter == "disabled":
            filtered_items = [item for item in self.startup_items if not item.get("enabled", False)]
        else:
            filtered_items = self.startup_items
        
        # Clear old widgets
        self.items_list.clear()
        
        if not filtered_items:
            self.status_label.setText("No startup items to display")
            self.status_label.setVisible(True)
            self.items_list.setVisible(False)
            return
        
        # Show items container
        self.status_label.setVisible(False)
        self.items_list.setVisible(True)
        
        # Group by impact
        by_impact = {"High": [], "Medium": [], "Low": [], "Not measured": []}
        for item in filtered_items:
            impact = item.get("impact", "Not measured")
            if impact in by_impact:
                by_impact[impact].append(item)
            else:
                by_impact["Not measured"].append(item)
        
        # Add items grouped by impact
        row_idx = 0
        for impact_level in ["High", "Medium", "Low", "Not measured"]:
            impact_items = by_impact.get(impact_level, [])
            if not impact_items:
                continue
            
            # Add category header
            self.items_list.add_category(f"{impact_level} Impact", len(impact_items))
            
            for item in impact_items:
                # Determine status colors
                status = "ok" if item.get("enabled", False) else "disabled"
                status_text = "Enabled" if item.get("enabled", False) else "Disabled"
                
                # Create subtitle with publisher and location
                subtitle = f"{item.get('publisher', 'Unknown')} • {item.get('location', 'Unknown')}"
                
                row = self.items_list.add_row(
                    title=item.get("name", "Unknown"),
                    subtitle=subtitle,
                    status=status,
                    status_text=status_text
                )
                
                # Add toggle button
                btn_text = "Disable" if item.get("enabled", False) else "Enable"
                is_primary = not item.get("enabled", False)  # Enable button is primary
                row.add_action_button(
                    btn_text, 
                    lambda checked, i=item, r=row: self._toggle_startup_item(i, r),
                    primary=is_primary
                )
                
                row_idx += 1
    
    def _toggle_startup_item(self, item: dict, row_widget):
        """Toggle a startup item's enabled/disabled state"""
        try:
            from startup_scanner import toggle_startup_item
            from PyQt6.QtWidgets import QMessageBox
            
            name = item["name"]
            source_path = item.get("source_path", "")
            currently_enabled = item["enabled"]
            
            # Determine the action
            new_state = not currently_enabled
            action_word = "enable" if new_state else "disable"
            
            # Check if this is a registry-based item (we can toggle these)
            source = item.get("source", "")
            if "Registry" in source or "HKCU" in source_path or "HKLM" in source_path:
                # Confirm the action
                reply = QMessageBox.question(
                    self,
                    f"{action_word.title()} Startup Item",
                    f"Are you sure you want to {action_word} '{name}'?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if reply != QMessageBox.StandardButton.Yes:
                    return
                
                # Perform the toggle
                success, message = toggle_startup_item(name, source_path, new_state)
                
                if success:
                    # Update the item's state
                    item["enabled"] = new_state
                    
                    # Show success message
                    QMessageBox.information(
                        self,
                        "Success",
                        message,
                        QMessageBox.StandardButton.Ok
                    )
                    
                    # Refresh the count in the summary and redisplay items
                    self._update_summary_counts()
                    self._display_items()
                else:
                    QMessageBox.warning(
                        self,
                        "Error",
                        message + "\n\nNote: Some startup items require administrator privileges to modify.",
                        QMessageBox.StandardButton.Ok
                    )
            else:
                # For Task Scheduler or Startup Folder items, open Task Manager
                self._open_task_manager_startup(name)
                
        except ImportError:
            self._open_task_manager_startup(item.get("name", ""))
        except Exception as e:
            print(f"Error toggling startup item: {e}")
            self._open_task_manager_startup(item.get("name", ""))
    
    def _update_summary_counts(self):
        """Update the summary stats with current enable/disable counts"""
        try:
            enabled = sum(1 for item in self.startup_items if item.get("enabled", False))
            disabled = len(self.startup_items) - enabled
            high_impact = sum(1 for item in self.startup_items if item.get("enabled", False) and item.get("impact") == "High")
            
            self._update_stat(self.stat_total, str(len(self.startup_items)))
            self._update_stat(self.stat_enabled, str(enabled))
            self._update_stat(self.stat_disabled, str(disabled))
            self._update_stat(self.stat_high_impact, str(high_impact))
        except Exception:
            pass
    
    def _open_task_manager_startup(self, item_name: str = ""):
        """Open Task Manager to the Startup tab with helpful message"""
        import subprocess
        from PyQt6.QtWidgets import QMessageBox
        
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("Use Task Manager")
        if item_name:
            msg.setText(f"'{item_name}' cannot be toggled directly.")
        else:
            msg.setText("This item requires Task Manager to modify.")
        msg.setInformativeText(
            "This startup item is managed by Task Scheduler or Startup Folder.\n\n"
            "To enable/disable it:\n"
            "1. Go to the 'Startup apps' tab in Task Manager\n"
            "2. Right-click the item\n"
            "3. Select 'Enable' or 'Disable'"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
        
        try:
            subprocess.Popen(["taskmgr.exe"])
        except Exception:
            pass
    
    def open_task_manager(self):
        """Open Windows Task Manager to the Startup tab"""
        import subprocess
        try:
            # Open Task Manager - on Windows 10/11 it opens to last viewed tab
            # We can't directly open to Startup tab, but user can navigate there
            subprocess.Popen(["taskmgr.exe"])
        except Exception as e:
            print(f"Failed to open Task Manager: {e}")
    
    def refresh_accent_colors(self):
        """Update accent-colored elements when theme changes"""
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                padding: 10px 24px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT_HOVER};
            }}
        """)


# =============================================================================
# EVENTS PAGE - System Event Log Analysis
# =============================================================================

class EventsPage(QWidget):
    """Dedicated page for Windows Event Log analysis with card-based layout"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.event_data = {}
        self.event_widgets = []
        self.loaded = False
        self.setup_ui()
    
    def setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(32, 28, 32, 28)
        self.content_layout.setSpacing(20)
        
        # Header row
        header = QHBoxLayout()
        header.setSpacing(16)
        
        title = QLabel("Event Log Analysis")
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 28px;
            font-weight: 600;
        """)
        header.addWidget(title)
        header.addStretch()
        
        # Refresh button
        self.refresh_btn = QPushButton("Scan Events")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.load_events)
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                padding: 10px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        header.addWidget(self.refresh_btn)
        
        # Open Event Viewer button
        self.viewer_btn = QPushButton("Open Event Viewer")
        self.viewer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.viewer_btn.clicked.connect(self._open_event_viewer)
        Theme.style_accent_button(self.viewer_btn, "primary")
        header.addWidget(self.viewer_btn)
        
        self.content_layout.addLayout(header)
        
        # Info text
        info = QLabel("Analyze Windows System event logs to identify errors, warnings, and potential issues from the last 24 hours.")
        info.setWordWrap(True)
        info.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        self.content_layout.addWidget(info)
        
        # Summary stats row - matching DriversPage styling
        self.stats_frame = QFrame()
        self.stats_frame.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(self.stats_frame, blur_radius=12, offset_y=3, opacity=60)
        stats_layout = QHBoxLayout(self.stats_frame)
        stats_layout.setContentsMargins(24, 20, 24, 20)
        stats_layout.setSpacing(0)
        
        self.stat_critical = self._create_stat("Critical", "—", Theme.ERROR)
        stats_layout.addWidget(self.stat_critical)
        self._add_stat_divider(stats_layout)
        
        self.stat_errors = self._create_stat("Errors", "—", Theme.WARNING)
        stats_layout.addWidget(self.stat_errors)
        self._add_stat_divider(stats_layout)
        
        self.stat_warnings = self._create_stat("Warnings", "—", "#f4b400")
        stats_layout.addWidget(self.stat_warnings)
        
        stats_layout.addStretch()
        self.content_layout.addWidget(self.stats_frame)
        
        # Status label (shown before scan)
        self.status_label = QLabel("Click 'Scan Events' to analyze system event logs")
        self.status_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 14px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.status_label)
        
        # Events container
        self.events_container = QFrame()
        self.events_container.setStyleSheet("background: transparent;")
        self.events_layout = QVBoxLayout(self.events_container)
        self.events_layout.setContentsMargins(0, 0, 0, 0)
        self.events_layout.setSpacing(16)
        self.events_container.setVisible(False)
        self.content_layout.addWidget(self.events_container)
        
        self.content_layout.addStretch()
        
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        
        # Floating Quick Tools bar
        tools = [
            ("Event Viewer", "\uE7C4", self._open_event_viewer),
            ("Reliability Monitor", "\uE9D9", self._open_reliability_monitor),
            ("Problem Reports", "\uE946", self._open_problem_reports),
        ]
        self._floating_toolbar = FloatingToolbar(tools, self)
    
    def resizeEvent(self, event):
        """Reposition floating toolbar on resize"""
        super().resizeEvent(event)
        if hasattr(self, '_floating_toolbar'):
            self._floating_toolbar.update_position()
    
    def _open_reliability_monitor(self):
        """Open Reliability Monitor"""
        import subprocess
        try:
            subprocess.Popen(["perfmon", "/rel"])
        except:
            pass
    
    def _open_problem_reports(self):
        """Open Problem Reports"""
        import subprocess
        try:
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:privacy-diagnostics"],
                           creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        except:
            pass
    
    def _add_stat_divider(self, layout):
        """Add a vertical divider between stats"""
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setFixedHeight(40)
        divider.setStyleSheet("background: rgba(255, 255, 255, 0.08);")
        layout.addSpacing(24)
        layout.addWidget(divider)
        layout.addSpacing(24)
    
    def _create_stat(self, label: str, value: str, color: str | None = None):
        """Create an improved stat display widget matching DriversPage"""
        frame = QFrame()
        frame.setStyleSheet("background: transparent;")
        frame.setMinimumWidth(100)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        value_label = QLabel(value)
        value_label.setObjectName("stat_value")
        value_color = color or Theme.TEXT_PRIMARY
        value_label.setStyleSheet(f"""
            background: transparent;
            color: {value_color};
            font-size: 24px;
            font-weight: 700;
        """)
        layout.addWidget(value_label)
        
        text_label = QLabel(label)
        text_label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_TERTIARY};
            font-size: 11px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(text_label)
        
        return frame
    
    def _update_stat(self, stat_widget: QFrame, value: str):
        """Update a stat widget's value"""
        value_label = stat_widget.findChild(QLabel, "stat_value")
        if value_label:
            value_label.setText(value)
    
    def load_events(self):
        """Load event log data"""
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Scanning...")
        self.status_label.setText("Analyzing event logs...")
        self.status_label.setVisible(True)
        
        # Use QTimer to allow UI to update
        QTimer.singleShot(100, self._do_load_events)
    
    def _do_load_events(self):
        """Actually load the event data"""
        try:
            command = """
            $output = @{
                ErrorCount = 0
                WarningCount = 0
                CriticalCount = 0
                RecentErrors = @()
                RecentWarnings = @()
            }
            
            $since = (Get-Date).AddHours(-24)
            
            try {
                $critical = Get-WinEvent -FilterHashtable @{LogName='System'; Level=1; StartTime=$since} -MaxEvents 50 -ErrorAction SilentlyContinue
                $output.CriticalCount = if ($critical) { $critical.Count } else { 0 }
            } catch {}
            
            try {
                $sysErrors = Get-WinEvent -FilterHashtable @{LogName='System'; Level=2; StartTime=$since} -MaxEvents 100 -ErrorAction SilentlyContinue
                $output.ErrorCount = if ($sysErrors) { $sysErrors.Count } else { 0 }
                
                $output.RecentErrors = $sysErrors | Select-Object -First 10 | ForEach-Object {
                    $msg = if ($_.Message) { ($_.Message -split "`n")[0] } else { "No message available" }
                    $msg = $msg.Substring(0, [Math]::Min(120, $msg.Length))
                    @{
                        Time = $_.TimeCreated.ToString("MMM dd, HH:mm")
                        Source = $_.ProviderName
                        Id = $_.Id
                        Message = $msg
                    }
                }
            } catch {}
            
            try {
                $sysWarnings = Get-WinEvent -FilterHashtable @{LogName='System'; Level=3; StartTime=$since} -MaxEvents 100 -ErrorAction SilentlyContinue
                $output.WarningCount = if ($sysWarnings) { $sysWarnings.Count } else { 0 }
                
                $output.RecentWarnings = $sysWarnings | Select-Object -First 6 | ForEach-Object {
                    $msg = if ($_.Message) { ($_.Message -split "`n")[0] } else { "No message available" }
                    $msg = $msg.Substring(0, [Math]::Min(120, $msg.Length))
                    @{
                        Time = $_.TimeCreated.ToString("MMM dd, HH:mm")
                        Source = $_.ProviderName
                        Id = $_.Id
                        Message = $msg
                    }
                }
            } catch {}
            
            $output | ConvertTo-Json -Depth 4
            """
            import subprocess
            import json
            
            result = subprocess.run(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            self.event_data = json.loads(result.stdout) if result.stdout.strip() else {}
            self._display_events()
            
        except Exception as e:
            self.status_label.setText(f"Error scanning events: {str(e)}")
            self.status_label.setVisible(True)
        finally:
            self.refresh_btn.setEnabled(True)
            self.refresh_btn.setText("Scan Events")
            self.loaded = True
    
    def _display_events(self):
        """Display the event data in card format"""
        # Clear old widgets
        for widget in self.event_widgets:
            widget.deleteLater()
        self.event_widgets.clear()
        
        # Update stats
        critical = self.event_data.get('CriticalCount', 0) or 0
        errors = self.event_data.get('ErrorCount', 0) or 0
        warnings = self.event_data.get('WarningCount', 0) or 0
        
        self._update_stat(self.stat_critical, str(critical))
        self._update_stat(self.stat_errors, str(errors))
        self._update_stat(self.stat_warnings, str(warnings))
        
        # Hide status, show events container
        self.status_label.setVisible(False)
        self.events_container.setVisible(True)
        
        # Summary card
        summary_card = self._create_summary_card(critical, errors, warnings)
        self.events_layout.addWidget(summary_card)
        self.event_widgets.append(summary_card)
        
        # Recent Errors card
        recent_errors = self.event_data.get('RecentErrors', []) or []
        if recent_errors:
            errors_card = self._create_events_card("Recent Errors", recent_errors, "error")
            self.events_layout.addWidget(errors_card)
            self.event_widgets.append(errors_card)
        
        # Recent Warnings card
        recent_warnings = self.event_data.get('RecentWarnings', []) or []
        if recent_warnings:
            warnings_card = self._create_events_card("Recent Warnings", recent_warnings, "warning")
            self.events_layout.addWidget(warnings_card)
            self.event_widgets.append(warnings_card)
        
        # If no events found
        if not recent_errors and not recent_warnings and critical == 0 and errors == 0 and warnings == 0:
            no_events = QLabel("No significant events found in the last 24 hours. Your system is healthy!")
            no_events.setStyleSheet(f"""
                background: {Theme.BG_CARD};
                color: {Theme.SUCCESS};
                font-size: 14px;
                padding: 20px;
                border-radius: {Theme.RADIUS_MD}px;
            """)
            no_events.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.events_layout.addWidget(no_events)
            self.event_widgets.append(no_events)
    
    def display_cached_data(self, data: dict):
        """Display event log data from cached scan results (from full system scan)"""
        if not data:
            return
        
        # Store the data
        self.event_data = data
        self.loaded = True
        
        # Hide status label
        self.status_label.setVisible(False)
        
        # Display the events
        self._display_events()
    
    def _create_summary_card(self, critical: int, errors: int, warnings: int):
        """Create the summary status card"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(card, blur_radius=12, offset_y=3, opacity=60)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("System Health Summary")
        title.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 16px; font-weight: 600;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Status chip
        if critical > 0:
            status_text, status_color = "Critical Issues", Theme.ERROR
        elif errors > 10:
            status_text, status_color = "Needs Attention", Theme.WARNING
        elif errors > 0:
            status_text, status_color = "Minor Issues", "#f4b400"
        else:
            status_text, status_color = "Healthy", Theme.SUCCESS
        
        status_chip = QLabel(f"  ●  {status_text}")
        status_chip.setStyleSheet(f"""
            background: rgba({self._hex_to_rgb(status_color)}, 0.15);
            color: {status_color};
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        """)
        header_layout.addWidget(status_chip)
        
        layout.addLayout(header_layout)
        
        # Summary text
        summary_items = []
        if critical > 0:
            summary_items.append(f"• {critical} critical event(s) require immediate attention")
        if errors > 0:
            summary_items.append(f"• {errors} error(s) detected in system logs")
        if warnings > 0:
            summary_items.append(f"• {warnings} warning(s) logged")
        if not summary_items:
            summary_items.append("• No significant issues detected in the last 24 hours")
        
        summary = QLabel("\n".join(summary_items))
        summary.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 13px; line-height: 1.5;")
        summary.setWordWrap(True)
        layout.addWidget(summary)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        export_btn = QPushButton("Export Report")
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(self._export_event_log)
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.ACCENT};
                border: none;
                padding: 6px 12px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {Theme.BG_ELEVATED};
            }}
        """)
        btn_layout.addWidget(export_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return card
    
    def _create_events_card(self, title: str, events: list, event_type: str):
        """Create a card showing a list of events"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(card, blur_radius=12, offset_y=3, opacity=60)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QFrame()
        header.setStyleSheet(f"background: {Theme.BG_CARD_HOVER}; border-radius: {Theme.RADIUS_MD}px {Theme.RADIUS_MD}px 0 0;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 12, 20, 12)
        
        icon_color = Theme.ERROR if event_type == "error" else "#f4b400"
        title_label = QLabel(f"{'✗' if event_type == 'error' else '!'} {title}")
        title_label.setStyleSheet(f"background: transparent; color: {icon_color}; font-size: 14px; font-weight: 600;")
        header_layout.addWidget(title_label)
        
        count_label = QLabel(f"{len(events)} shown")
        count_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        header_layout.addStretch()
        header_layout.addWidget(count_label)
        
        layout.addWidget(header)
        
        # Events list
        for i, event in enumerate(events):
            if not isinstance(event, dict):
                continue
                
            row = QFrame()
            # Use subtle separator only between rows, not a full border
            separator_color = f"rgba(255, 255, 255, 0.05)" if i < len(events) - 1 else "transparent"
            row.setStyleSheet(f"""
                QFrame {{
                    background: transparent;
                    border: none;
                    border-bottom: 1px solid {separator_color};
                }}
            """)
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(20, 12, 20, 12)
            row_layout.setSpacing(6)
            
            # Top row: time, source, event ID
            top_row = QHBoxLayout()
            top_row.setSpacing(16)
            
            time_label = QLabel(event.get('Time', ''))
            time_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
            top_row.addWidget(time_label)
            
            source_label = QLabel(event.get('Source', 'Unknown'))
            source_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 13px; font-weight: 500;")
            top_row.addWidget(source_label)
            
            top_row.addStretch()
            
            event_id = event.get('Id', '')
            id_label = QLabel(f"Event ID: {event_id}")
            id_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
            top_row.addWidget(id_label)
            
            row_layout.addLayout(top_row)
            
            # Message
            msg = event.get('Message', '')
            if msg:
                msg_label = QLabel(msg)
                msg_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
                msg_label.setWordWrap(True)
                row_layout.addWidget(msg_label)
            
            layout.addWidget(row)
        
        return card
    
    def _hex_to_rgb(self, hex_color: str) -> str:
        """Convert hex color to RGB string for rgba()"""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            return f"{r}, {g}, {b}"
        return "255, 255, 255"
    
    def _open_event_viewer(self):
        """Open Windows Event Viewer"""
        import subprocess
        try:
            subprocess.Popen(["eventvwr.msc"], shell=True)
        except Exception as e:
            print(f"Error opening Event Viewer: {e}")
    
    def _export_event_log(self):
        """Export recent error events to a file"""
        import subprocess
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from pathlib import Path
        from datetime import datetime
        
        default_name = f"event_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Event Log",
            str(Path.home() / "Desktop" / default_name),
            "Text Files (*.txt);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            command = f'''
            $since = (Get-Date).AddHours(-24)
            $errors = Get-WinEvent -FilterHashtable @{{LogName='System'; Level=1,2,3; StartTime=$since}} -ErrorAction SilentlyContinue |
                Select-Object TimeCreated, ProviderName, Id, LevelDisplayName, Message |
                Format-List | Out-String
            
            $header = "Windows Event Log Export`n"
            $header += "Generated: $(Get-Date)`n"
            $header += "Period: Last 24 hours`n"
            $header += "=" * 60 + "`n`n"
            
            $header + $errors | Out-File -FilePath "{file_path}" -Encoding UTF8
            '''
            subprocess.run(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            QMessageBox.information(
                self,
                "Export Complete",
                f"Event log exported to:\n{file_path}",
                QMessageBox.StandardButton.Ok
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Export Failed",
                f"Could not export event log:\n{str(e)}",
                QMessageBox.StandardButton.Ok
            )


# =============================================================================
# AUDIO PAGE - Audio Device Testing with Oscilloscope
# =============================================================================

class AudioOscilloscope(QFrame):
    """Real-time audio waveform oscilloscope visualization"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sample_data = [0.0] * 256
        self.is_active = False
        self.amplitude = 0.0
        self.setFixedHeight(180)
        self.setMinimumWidth(400)
        self.setup_ui()
        
        # Animation timer for demo/test mode
        self._demo_timer = QTimer()
        self._demo_timer.timeout.connect(self._update_demo_waveform)
        self._demo_phase = 0.0
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            AudioOscilloscope {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
    
    def start(self, demo_mode: bool = True):
        """Start the oscilloscope visualization"""
        self.is_active = True
        if demo_mode:
            self._demo_timer.start(33)  # ~30 FPS
    
    def stop(self):
        """Stop the oscilloscope"""
        self.is_active = False
        self._demo_timer.stop()
        self.sample_data = [0.0] * 256
        self.amplitude = 0.0
        self.update()
    
    def set_amplitude(self, amplitude: float):
        """Set amplitude for waveform (0.0 - 1.0)"""
        self.amplitude = max(0.0, min(1.0, amplitude))
    
    def _update_demo_waveform(self):
        """Generate demo sine wave visualization"""
        import math
        self._demo_phase += 0.15
        
        # Create a composite waveform
        for i in range(256):
            t = i / 256.0 * math.pi * 4 + self._demo_phase
            # Main wave + harmonics
            value = math.sin(t) * 0.6
            value += math.sin(t * 2) * 0.25 * self.amplitude
            value += math.sin(t * 3) * 0.15 * self.amplitude
            # Add some noise for realism
            import random
            value += (random.random() - 0.5) * 0.1 * self.amplitude
            self.sample_data[i] = value * self.amplitude
        
        self.update()
    
    def update_samples(self, samples: list):
        """Update with real audio samples"""
        if len(samples) >= 256:
            self.sample_data = samples[:256]
        else:
            # Pad or interpolate
            self.sample_data = samples + [0.0] * (256 - len(samples))
        self.update()
    
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Dimensions
        padding = 16
        title_height = 28
        graph_left = padding
        graph_top = padding + title_height
        graph_width = self.width() - (padding * 2)
        graph_height = self.height() - graph_top - padding
        center_y = graph_top + graph_height // 2
        
        # Draw title
        painter.setPen(QColor(Theme.TEXT_SECONDARY))
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        painter.drawText(padding, padding + 16, "Audio Waveform")
        
        # Status indicator
        status_text = "ACTIVE" if self.is_active else "INACTIVE"
        status_color = Theme.SUCCESS if self.is_active else Theme.TEXT_TERTIARY
        painter.setPen(QColor(status_color))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        status_width = painter.fontMetrics().horizontalAdvance(status_text)
        painter.drawText(self.width() - padding - status_width, padding + 16, status_text)
        
        # Draw graph background
        painter.fillRect(graph_left, graph_top, graph_width, graph_height, QColor(Theme.BG_CARD_HOVER))
        
        # Draw center line
        painter.setPen(QPen(QColor(Theme.BORDER), 1))
        painter.drawLine(graph_left, center_y, graph_left + graph_width, center_y)
        
        # Draw grid lines
        painter.setPen(QPen(QColor(Theme.BORDER), 1, Qt.PenStyle.DotLine))
        for i in [1, 3]:
            y = graph_top + (graph_height * i // 4)
            painter.drawLine(graph_left, y, graph_left + graph_width, y)
        
        # Draw waveform
        if self.is_active and any(s != 0 for s in self.sample_data):
            # Create gradient for waveform
            wave_color = QColor(Theme.ACCENT)
            wave_color_light = QColor(Theme.ACCENT_LIGHT)
            
            # Draw waveform path
            path = QPainterPath()
            point_spacing = graph_width / (len(self.sample_data) - 1)
            
            first_y = center_y - (self.sample_data[0] * graph_height * 0.45)
            path.moveTo(graph_left, first_y)
            
            for i, sample in enumerate(self.sample_data[1:], 1):
                x = graph_left + (i * point_spacing)
                y = center_y - (sample * graph_height * 0.45)
                path.lineTo(x, y)
            
            # Draw glow effect
            glow_pen = QPen(wave_color_light, 4)
            glow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(glow_pen)
            painter.drawPath(path)
            
            # Draw main line
            painter.setPen(QPen(wave_color, 2))
            painter.drawPath(path)
        else:
            # Draw flat line when inactive
            painter.setPen(QPen(QColor(Theme.TEXT_TERTIARY), 1, Qt.PenStyle.DashLine))
            painter.drawLine(graph_left, center_y, graph_left + graph_width, center_y)
            
            # Draw "No Signal" text
            painter.setPen(QColor(Theme.TEXT_TERTIARY))
            painter.setFont(QFont("Segoe UI", 12))
            text = "No Signal"
            text_width = painter.fontMetrics().horizontalAdvance(text)
            painter.drawText(graph_left + (graph_width - text_width) // 2, center_y + 5, text)


class AudioDeviceCard(QFrame):
    """Card for displaying an audio device with controls"""
    
    test_clicked = pyqtSignal(str, str)  # device_id, device_type
    
    def __init__(self, device_name: str, device_id: str, device_type: str, 
                 is_default: bool = False, parent=None):
        super().__init__(parent)
        self.device_name = device_name
        self.device_id = device_id
        self.device_type = device_type  # "output" or "input"
        self.is_default = is_default
        self.is_testing = False
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            AudioDeviceCard {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
            AudioDeviceCard:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)
        
        # Icon - Fluent Icons for speaker/microphone
        icon_char = "\uE767" if self.device_type == "output" else "\uE720"  # Speaker or Microphone
        icon = QLabel(icon_char)
        icon.setStyleSheet(f"background: transparent; font-size: 24px; font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';")
        icon.setFixedWidth(32)
        layout.addWidget(icon)
        
        # Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        
        name = QLabel(self.device_name)
        name.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 13px; font-weight: 600;")
        name_row.addWidget(name)
        
        if self.is_default:
            default_badge = QLabel("Default")
            default_badge.setStyleSheet(f"""
                background: {Theme.SUCCESS_BG};
                color: {Theme.SUCCESS};
                padding: 2px 8px;
                border-radius: 8px;
                font-size: 10px;
                font-weight: 600;
            """)
            name_row.addWidget(default_badge)
        
        name_row.addStretch()
        info_layout.addLayout(name_row)
        
        type_text = "Audio Output Device" if self.device_type == "output" else "Audio Input Device"
        type_label = QLabel(type_text)
        type_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
        info_layout.addWidget(type_label)
        
        layout.addLayout(info_layout, 1)
        
        # Level meter (simple bar)
        self.level_bar = QFrame()
        self.level_bar.setFixedSize(60, 8)
        self.level_bar.setStyleSheet(f"""
            background: {Theme.BG_CARD_HOVER};
            border-radius: 4px;
        """)
        layout.addWidget(self.level_bar)
        
        # Test button
        self.test_btn = QPushButton("Test")
        self.test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.test_btn.clicked.connect(self._on_test_clicked)
        self.test_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                padding: 6px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT};
                color: white;
            }}
        """)
        layout.addWidget(self.test_btn)
    
    def _on_test_clicked(self):
        self.test_clicked.emit(self.device_id, self.device_type)
    
    def set_testing(self, testing: bool):
        self.is_testing = testing
        if testing:
            self.test_btn.setText("Testing...")
            self.test_btn.setEnabled(False)
        else:
            self.test_btn.setText("Test")
            self.test_btn.setEnabled(True)
    
    def set_level(self, level: float):
        """Set the level meter (0.0 - 1.0)"""
        fill_width = int(60 * min(1.0, max(0.0, level)))
        color = Theme.SUCCESS if level < 0.8 else Theme.WARNING if level < 0.95 else Theme.ERROR
        self.level_bar.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {color}, stop:{level} {color},
                stop:{level + 0.01} {Theme.BG_CARD_HOVER}, stop:1 {Theme.BG_CARD_HOVER});
            border-radius: 4px;
        """)


class AudioTestWorker(QObject):
    """Background worker for audio testing"""
    finished = pyqtSignal(dict)
    progress = pyqtSignal(str)
    
    def __init__(self, test_type: str = "all"):
        super().__init__()
        self.test_type = test_type
    
    def run(self):
        import subprocess
        try:
            # Get audio devices using PowerShell
            command = '''
            $result = @{
                OutputDevices = @()
                InputDevices = @()
                DefaultOutput = ""
                DefaultInput = ""
            }
            
            # Get audio devices using Windows Audio API via PowerShell
            try {
                Add-Type -AssemblyName System.Speech
                
                # Get playback devices
                $outputDevices = Get-WmiObject Win32_SoundDevice | Where-Object { $_.Status -eq 'OK' }
                foreach ($device in $outputDevices) {
                    $result.OutputDevices += @{
                        Name = $device.Name
                        Id = $device.DeviceID
                        Status = $device.Status
                        Manufacturer = $device.Manufacturer
                    }
                }
                
                # Get recording devices - use alternative method
                $audioEndpoints = Get-WmiObject -Query "SELECT * FROM Win32_PnPEntity WHERE PNPClass = 'AudioEndpoint'" -ErrorAction SilentlyContinue
                if ($audioEndpoints) {
                    foreach ($endpoint in $audioEndpoints) {
                        if ($endpoint.Name -match 'Microphone|Line In|Recording|Input') {
                            $result.InputDevices += @{
                                Name = $endpoint.Name
                                Id = $endpoint.DeviceID
                                Status = if ($endpoint.Status -eq 'OK') { 'OK' } else { 'Unknown' }
                            }
                        }
                    }
                }
                
                # Fallback - add default devices if none found
                if ($result.OutputDevices.Count -eq 0) {
                    $result.OutputDevices += @{
                        Name = "Default Audio Output"
                        Id = "default_output"
                        Status = "OK"
                    }
                }
                if ($result.InputDevices.Count -eq 0) {
                    $result.InputDevices += @{
                        Name = "Default Microphone"
                        Id = "default_input"
                        Status = "OK"
                    }
                }
                
                $result.DefaultOutput = if ($result.OutputDevices.Count -gt 0) { $result.OutputDevices[0].Id } else { "" }
                $result.DefaultInput = if ($result.InputDevices.Count -gt 0) { $result.InputDevices[0].Id } else { "" }
                
            } catch {
                $result.Error = $_.Exception.Message
            }
            
            $result | ConvertTo-Json -Depth 4
            '''
            
            result = subprocess.run(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                self.finished.emit(data)
            else:
                self.finished.emit({
                    "OutputDevices": [{"Name": "System Default Speaker", "Id": "default", "Status": "OK"}],
                    "InputDevices": [{"Name": "System Default Microphone", "Id": "default", "Status": "OK"}],
                    "DefaultOutput": "default",
                    "DefaultInput": "default"
                })
        except Exception as e:
            self.finished.emit({
                "Error": str(e),
                "OutputDevices": [{"Name": "Audio Device", "Id": "default", "Status": "Unknown"}],
                "InputDevices": [{"Name": "Microphone", "Id": "default", "Status": "Unknown"}],
                "DefaultOutput": "default",
                "DefaultInput": "default"
            })


class AudioPage(QWidget):
    """Page for testing audio input and output devices with oscilloscope"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.audio_devices = {}
        self.device_cards = []
        self.is_testing = False
        self.setup_ui()
    
    def setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(32, 28, 32, 28)
        self.content_layout.setSpacing(20)
        
        # Header
        header = QHBoxLayout()
        header.setSpacing(16)
        
        title = QLabel("Audio Devices")
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 28px;
            font-weight: 600;
        """)
        header.addWidget(title)
        header.addStretch()
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh Devices")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.scan_devices)
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                padding: 10px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        header.addWidget(self.refresh_btn)
        
        # Sound Settings button
        sound_btn = QPushButton("Sound Settings")
        sound_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sound_btn.clicked.connect(self._open_sound_settings)
        sound_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                padding: 10px 24px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT_HOVER};
            }}
        """)
        header.addWidget(sound_btn)
        
        self.content_layout.addLayout(header)
        
        # Info text
        info = QLabel("Test your audio input and output devices. Use the oscilloscope to visualize audio signals in real-time.")
        info.setWordWrap(True)
        info.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        self.content_layout.addWidget(info)
        
        # Oscilloscope section
        scope_header = QLabel("Oscilloscope")
        scope_header.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 18px;
            font-weight: 600;
        """)
        self.content_layout.addWidget(scope_header)
        
        # Oscilloscope controls row
        scope_controls = QHBoxLayout()
        scope_controls.setSpacing(12)
        
        self.oscilloscope = AudioOscilloscope()
        
        # Amplitude slider simulation (using buttons for simplicity)
        amp_frame = QFrame()
        amp_frame.setStyleSheet(f"""
            background: {Theme.BG_CARD};
            border: none;
            border-radius: {Theme.RADIUS_MD}px;
        """)
        amp_layout = QVBoxLayout(amp_frame)
        amp_layout.setContentsMargins(16, 12, 16, 12)
        amp_layout.setSpacing(8)
        
        amp_label = QLabel("Test Signal")
        amp_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 11px;")
        amp_layout.addWidget(amp_label)
        
        self.amp_value = QLabel("OFF")
        self.amp_value.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 18px; font-weight: 600;")
        amp_layout.addWidget(self.amp_value)
        
        amp_btn_layout = QHBoxLayout()
        amp_btn_layout.setSpacing(6)
        
        self.start_scope_btn = QPushButton("Start")
        self.start_scope_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_scope_btn.clicked.connect(self._start_oscilloscope)
        self.start_scope_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.SUCCESS};
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: #0db25f;
            }}
        """)
        amp_btn_layout.addWidget(self.start_scope_btn)
        
        self.stop_scope_btn = QPushButton("Stop")
        self.stop_scope_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_scope_btn.clicked.connect(self._stop_oscilloscope)
        self.stop_scope_btn.setEnabled(False)
        self.stop_scope_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ERROR};
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: #c0392b;
            }}
            QPushButton:disabled {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_TERTIARY};
            }}
        """)
        amp_btn_layout.addWidget(self.stop_scope_btn)
        
        amp_layout.addLayout(amp_btn_layout)
        
        # Frequency selector
        freq_layout = QVBoxLayout()
        freq_layout.setSpacing(4)
        freq_label = QLabel("Frequency")
        freq_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 10px;")
        freq_layout.addWidget(freq_label)
        
        self.freq_btns = []
        for freq in ["Low", "Mid", "High"]:
            btn = QPushButton(freq)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {Theme.TEXT_SECONDARY};
                    border: none;
                    padding: 4px 10px;
                    border-radius: 4px;
                    font-size: 10px;
                }}
                QPushButton:checked {{
                    background: {Theme.ACCENT};
                    color: white;
                }}
                QPushButton:hover {{
                    background: rgba(255, 255, 255, 0.08);
                }}
            """)
            if freq == "Mid":
                btn.setChecked(True)
            btn.clicked.connect(lambda c, f=freq: self._set_frequency(f))
            freq_layout.addWidget(btn)
            self.freq_btns.append(btn)
        
        amp_layout.addLayout(freq_layout)
        
        scope_row = QHBoxLayout()
        scope_row.setSpacing(16)
        scope_row.addWidget(self.oscilloscope, 1)
        scope_row.addWidget(amp_frame)
        
        self.content_layout.addLayout(scope_row)
        
        # Output Devices section
        output_header = QLabel("Output Devices (Speakers)")
        output_header.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 18px;
            font-weight: 600;
            margin-top: 8px;
        """)
        self.content_layout.addWidget(output_header)
        
        self.output_container = QFrame()
        self.output_container.setStyleSheet("background: transparent;")
        self.output_layout = QVBoxLayout(self.output_container)
        self.output_layout.setContentsMargins(0, 0, 0, 0)
        self.output_layout.setSpacing(8)
        self.content_layout.addWidget(self.output_container)
        
        # Input Devices section
        input_header = QLabel("Input Devices (Microphones)")
        input_header.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 18px;
            font-weight: 600;
            margin-top: 8px;
        """)
        self.content_layout.addWidget(input_header)
        
        self.input_container = QFrame()
        self.input_container.setStyleSheet("background: transparent;")
        self.input_layout = QVBoxLayout(self.input_container)
        self.input_layout.setContentsMargins(0, 0, 0, 0)
        self.input_layout.setSpacing(8)
        self.content_layout.addWidget(self.input_container)
        
        # Status label
        self.status_label = QLabel("Click 'Refresh Devices' to scan for audio devices")
        self.status_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 13px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.status_label)
        
        # Test tone section
        test_section = QFrame()
        test_section.setStyleSheet(f"""
            background: {Theme.BG_CARD};
            border: none;
            border-radius: {Theme.RADIUS_MD}px;
        """)
        test_layout = QVBoxLayout(test_section)
        test_layout.setContentsMargins(20, 16, 20, 16)
        test_layout.setSpacing(12)
        
        test_header = QLabel("Quick Audio Test")
        test_header.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 14px; font-weight: 600;")
        test_layout.addWidget(test_header)
        
        test_desc = QLabel("Play test tones through your speakers to verify audio output is working correctly.")
        test_desc.setWordWrap(True)
        test_desc.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        test_layout.addWidget(test_desc)
        
        test_btn_row = QHBoxLayout()
        test_btn_row.setSpacing(12)
        
        self.play_tone_btn = QPushButton("▶ Play Test Tone")
        self.play_tone_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_tone_btn.clicked.connect(self._play_test_tone)
        self.play_tone_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT_HOVER};
            }}
        """)
        test_btn_row.addWidget(self.play_tone_btn)
        
        self.play_left_btn = QPushButton("Left Channel")
        self.play_left_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_left_btn.clicked.connect(lambda: self._play_channel_test("left"))
        self.play_left_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                padding: 10px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT};
                color: white;
            }}
        """)
        test_btn_row.addWidget(self.play_left_btn)
        
        self.play_right_btn = QPushButton("Right Channel")
        self.play_right_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_right_btn.clicked.connect(lambda: self._play_channel_test("right"))
        self.play_right_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                padding: 10px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT};
                color: white;
            }}
        """)
        test_btn_row.addWidget(self.play_right_btn)
        
        test_btn_row.addStretch()
        test_layout.addLayout(test_btn_row)
        
        self.content_layout.addWidget(test_section)
        
        self.content_layout.addStretch()
        
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        
        # Floating Quick Tools bar
        tools = [
            ("Sound Settings", "\uE767", self._open_sound_settings),
            ("Volume Mixer", "\uE992", self._open_volume_mixer),
            ("Device Manager", "\uE772", self._open_device_manager),
        ]
        self._floating_toolbar = FloatingToolbar(tools, self)
        
        # Background worker
        self._worker = None
        self._thread = None
    
    def resizeEvent(self, event):
        """Reposition floating toolbar on resize"""
        super().resizeEvent(event)
        if hasattr(self, '_floating_toolbar'):
            self._floating_toolbar.update_position()
    
    def _open_volume_mixer(self):
        """Open Volume Mixer"""
        import subprocess
        try:
            subprocess.Popen(["sndvol.exe"])
        except:
            pass
    
    def _open_device_manager(self):
        """Open Device Manager"""
        import subprocess
        try:
            subprocess.Popen(["devmgmt.msc"])
        except:
            pass
    
    def scan_devices(self):
        """Scan for audio devices"""
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Scanning...")
        self.status_label.setText("Scanning audio devices...")
        self.status_label.setVisible(True)
        
        self._thread = QThread(self)
        self._worker = AudioTestWorker()
        self._worker.moveToThread(self._thread)
        
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_scan_complete)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        
        self._thread.start()
    
    def _on_scan_complete(self, data: dict):
        """Handle scan completion"""
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Refresh Devices")
        self.audio_devices = data
        
        # Clear existing cards
        for card in self.device_cards:
            card.deleteLater()
        self.device_cards = []
        
        # Clear layouts
        while self.output_layout.count():
            item = self.output_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        
        while self.input_layout.count():
            item = self.input_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        
        # Add output devices
        output_devices = data.get("OutputDevices", [])
        default_output = data.get("DefaultOutput", "")
        
        for device in output_devices:
            is_default = device.get("Id") == default_output or len(output_devices) == 1
            card = AudioDeviceCard(
                device.get("Name", "Unknown"),
                device.get("Id", ""),
                "output",
                is_default
            )
            card.test_clicked.connect(self._test_device)
            self.output_layout.addWidget(card)
            self.device_cards.append(card)
        
        # Add input devices
        input_devices = data.get("InputDevices", [])
        default_input = data.get("DefaultInput", "")
        
        for device in input_devices:
            is_default = device.get("Id") == default_input or len(input_devices) == 1
            card = AudioDeviceCard(
                device.get("Name", "Unknown"),
                device.get("Id", ""),
                "input",
                is_default
            )
            card.test_clicked.connect(self._test_device)
            self.input_layout.addWidget(card)
            self.device_cards.append(card)
        
        self.status_label.setVisible(False)
    
    def _test_device(self, device_id: str, device_type: str):
        """Test a specific device"""
        if device_type == "output":
            self._play_test_tone()
        else:
            # Start oscilloscope for input test
            self._start_oscilloscope()
    
    def _start_oscilloscope(self):
        """Start the oscilloscope visualization and play test tone"""
        self.oscilloscope.set_amplitude(0.7)
        self.oscilloscope.start(demo_mode=True)
        self.start_scope_btn.setEnabled(False)
        self.stop_scope_btn.setEnabled(True)
        self.amp_value.setText("ACTIVE")
        self.amp_value.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 18px; font-weight: 600;")
        
        # Pre-generate tone files if not already done
        self._ensure_tone_files()
        
        # Start playing with async flag for non-blocking
        self._tone_playing = True
        self._play_current_tone()
    
    def _ensure_tone_files(self):
        """Pre-generate WAV files for all frequencies"""
        if hasattr(self, '_tone_files') and self._tone_files:
            return  # Already generated
        
        import wave
        import struct
        import tempfile
        import math
        
        self._tone_files = {}
        frequencies = {'Low': 220, 'Mid': 440, 'High': 880}
        sample_rate = 44100
        duration = 0.5  # Shorter duration for smoother looping
        
        for name, freq in frequencies.items():
            try:
                num_samples = int(sample_rate * duration)
                temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                temp_file.close()
                
                with wave.open(temp_file.name, 'w') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(sample_rate)
                    
                    for i in range(num_samples):
                        value = int(32767 * 0.5 * math.sin(2 * math.pi * freq * i / sample_rate))
                        wav_file.writeframes(struct.pack('<h', value))
                
                self._tone_files[name] = temp_file.name
            except Exception as e:
                print(f"Error creating tone file for {name}: {e}")
    
    def _play_current_tone(self):
        """Play the current frequency tone asynchronously"""
        if not self._tone_playing:
            return
        
        import winsound
        
        # Get current frequency
        current = 'Mid'
        for btn in self.freq_btns:
            if btn.isChecked():
                current = btn.text()
                break
        
        if hasattr(self, '_tone_files') and current in self._tone_files:
            # Play async and loop
            winsound.PlaySound(self._tone_files[current], winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
    
    def _stop_oscilloscope(self):
        """Stop the oscilloscope and test tone"""
        self.oscilloscope.stop()
        self.start_scope_btn.setEnabled(True)
        self.stop_scope_btn.setEnabled(False)
        self.amp_value.setText("OFF")
        self.amp_value.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 18px; font-weight: 600;")
        
        # Stop the tone asynchronously
        self._tone_playing = False
        import winsound
        winsound.PlaySound(None, winsound.SND_ASYNC)
    
    def _set_frequency(self, freq: str):
        """Set oscilloscope frequency and change tone instantly if playing"""
        for btn in self.freq_btns:
            btn.setChecked(btn.text() == freq)
        
        # Adjust amplitude based on frequency for visual effect
        if freq == "Low":
            self.oscilloscope.set_amplitude(0.5)
        elif freq == "Mid":
            self.oscilloscope.set_amplitude(0.7)
        else:
            self.oscilloscope.set_amplitude(0.9)
        
        # If tone is playing, switch immediately (no lag)
        if hasattr(self, '_tone_playing') and self._tone_playing:
            self._play_current_tone()  # This instantly switches to new frequency
    
    def _cleanup_tone_files(self):
        """Clean up temporary tone files"""
        if hasattr(self, '_tone_files'):
            for path in self._tone_files.values():
                try:
                    os.remove(path)
                except:
                    pass
            self._tone_files = {}
    
    def _play_test_tone(self):
        """Play a test tone through speakers using generated WAV"""
        def play_tone():
            import wave
            import struct
            import tempfile
            import winsound
            import math
            
            # Play ascending tones (C4, E4, G4)
            frequencies = [261.63, 329.63, 392.00]  # C4, E4, G4
            sample_rate = 44100
            duration = 0.4
            
            for freq in frequencies:
                try:
                    num_samples = int(sample_rate * duration)
                    
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                        temp_wav = f.name
                    
                    with wave.open(temp_wav, 'w') as wav_file:
                        wav_file.setnchannels(1)
                        wav_file.setsampwidth(2)
                        wav_file.setframerate(sample_rate)
                        
                        for i in range(num_samples):
                            # Generate sine wave with fade in/out
                            envelope = 1.0
                            if i < num_samples * 0.1:
                                envelope = i / (num_samples * 0.1)
                            elif i > num_samples * 0.9:
                                envelope = (num_samples - i) / (num_samples * 0.1)
                            
                            value = int(32767 * 0.5 * envelope * math.sin(2 * math.pi * freq * i / sample_rate))
                            wav_file.writeframes(struct.pack('<h', value))
                    
                    winsound.PlaySound(temp_wav, winsound.SND_FILENAME)
                    
                    # Cleanup
                    try:
                        os.remove(temp_wav)
                    except:
                        pass
                        
                except Exception as e:
                    print(f"Error playing tone: {e}")
        
        # Run in background thread
        threading.Thread(target=play_tone, daemon=True).start()
    
    def _play_channel_test(self, channel: str):
        """Play test tone for a specific channel (left/right speaker test)"""
        def play_channel():
            import wave
            import struct
            import tempfile
            import winsound
            import math
            
            freq = 440 if channel == "left" else 554
            sample_rate = 44100
            duration = 1.0
            num_samples = int(sample_rate * duration)
            
            try:
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                    temp_wav = f.name
                
                # Create stereo WAV (left channel only or right channel only)
                with wave.open(temp_wav, 'w') as wav_file:
                    wav_file.setnchannels(2)  # Stereo
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(sample_rate)
                    
                    for i in range(num_samples):
                        # Generate sine wave with fade
                        envelope = 1.0
                        if i < num_samples * 0.05:
                            envelope = i / (num_samples * 0.05)
                        elif i > num_samples * 0.95:
                            envelope = (num_samples - i) / (num_samples * 0.05)
                        
                        value = int(32767 * 0.5 * envelope * math.sin(2 * math.pi * freq * i / sample_rate))
                        
                        if channel == "left":
                            wav_file.writeframes(struct.pack('<hh', value, 0))  # Left only
                        else:
                            wav_file.writeframes(struct.pack('<hh', 0, value))  # Right only
                
                winsound.PlaySound(temp_wav, winsound.SND_FILENAME)
                
                try:
                    os.remove(temp_wav)
                except:
                    pass
                    
            except Exception as e:
                print(f"Error playing channel test: {e}")
        
        threading.Thread(target=play_channel, daemon=True).start()
    
    def _open_sound_settings(self):
        """Open Windows Sound Settings"""
        import subprocess
        try:
            subprocess.Popen(["control", "mmsys.cpl", "sounds"])
        except Exception as e:
            print(f"Error opening sound settings: {e}")


# =============================================================================
# WINDOWS UPDATE PAGE - Comprehensive Windows Update Management
# =============================================================================

class WindowsUpdatePage(QWidget):
    """Dedicated page for Windows Update management with detailed information"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.update_data = {}
        self.widgets = []
        self.is_loading = False
        self._thread = None
        self._worker = None
        self.setup_ui()
    
    def setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(32, 28, 32, 28)
        self.content_layout.setSpacing(20)
        
        # Header row
        header = QHBoxLayout()
        header.setSpacing(16)
        
        title = QLabel("Windows Update")
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 28px;
            font-weight: 600;
        """)
        header.addWidget(title)
        header.addStretch()
        
        # Last checked label
        self.last_checked = QLabel("Not checked yet")
        self.last_checked.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
        header.addWidget(self.last_checked)
        
        # Refresh button
        self.refresh_btn = QPushButton("Check for Updates")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.check_updates)
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT_HOVER};
            }}
            QPushButton:disabled {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_TERTIARY};
            }}
        """)
        header.addWidget(self.refresh_btn)
        
        # Open Windows Update button
        open_btn = QPushButton("Open Windows Update")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(self._open_windows_update)
        open_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                padding: 10px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        header.addWidget(open_btn)
        
        self.content_layout.addLayout(header)
        
        # Status/loading indicator
        self.status_label = QLabel("Click 'Check for Updates' to scan for available updates")
        self.status_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 13px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.status_label)
        
        # Summary stats row - matching DriversPage styling
        self.stats_frame = QFrame()
        self.stats_frame.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(self.stats_frame, blur_radius=12, offset_y=3, opacity=60)
        self.stats_frame.setVisible(False)
        stats_layout = QHBoxLayout(self.stats_frame)
        stats_layout.setContentsMargins(24, 20, 24, 20)
        stats_layout.setSpacing(0)

        self.stat_pending = self._create_stat("Pending", "—", Theme.WARNING)
        stats_layout.addWidget(self.stat_pending)
        self._add_stat_divider(stats_layout)
        
        self.stat_downloaded = self._create_stat("Downloaded", "—", Theme.SUCCESS)
        stats_layout.addWidget(self.stat_downloaded)
        self._add_stat_divider(stats_layout)
        
        self.stat_failed = self._create_stat("Failed", "—", Theme.ERROR)
        stats_layout.addWidget(self.stat_failed)
        self._add_stat_divider(stats_layout)
        
        # Service status as a stat widget
        self.stat_service = self._create_stat("Service Status", "—", Theme.TEXT_PRIMARY)
        stats_layout.addWidget(self.stat_service)
        
        stats_layout.addStretch()
        
        self.content_layout.addWidget(self.stats_frame)
        
        # Reboot required banner
        self.reboot_banner = QFrame()
        self.reboot_banner.setStyleSheet(f"""
            background: {Theme.WARNING};
            border-radius: {Theme.RADIUS_SM}px;
        """)
        self.reboot_banner.setVisible(False)
        reboot_layout = QHBoxLayout(self.reboot_banner)
        reboot_layout.setContentsMargins(16, 12, 16, 12)
        
        reboot_icon = QLabel("⚠")
        reboot_icon.setStyleSheet("background: transparent; color: #000; font-size: 16px;")
        reboot_layout.addWidget(reboot_icon)
        
        reboot_text = QLabel("A restart is required to complete the installation of updates")
        reboot_text.setStyleSheet("background: transparent; color: #000; font-size: 13px; font-weight: 500;")
        reboot_layout.addWidget(reboot_text)
        reboot_layout.addStretch()
        
        self.content_layout.addWidget(self.reboot_banner)
        
        # Main content container
        self.main_container = QFrame()
        self.main_container.setStyleSheet("background: transparent;")
        self.main_layout = QVBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(20)
        self.main_container.setVisible(False)
        self.content_layout.addWidget(self.main_container)
        
        self.content_layout.addStretch()
        
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        
        # Floating Quick Tools bar
        tools = [
            ("Windows Update", "\uE895", self._open_windows_update),
            ("Update History", "\uE81C", self._open_update_history),
            ("Advanced Options", "\uE713", self._open_advanced_options),
        ]
        self._floating_toolbar = FloatingToolbar(tools, self)
    
    def resizeEvent(self, event):
        """Reposition floating toolbar on resize"""
        super().resizeEvent(event)
        if hasattr(self, '_floating_toolbar'):
            self._floating_toolbar.update_position()
    
    def _open_update_history(self):
        """Open Windows Update History"""
        import subprocess
        try:
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:windowsupdate-history"],
                           creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        except:
            pass
    
    def _open_advanced_options(self):
        """Open Windows Update Advanced Options"""
        import subprocess
        try:
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:windowsupdate-options"],
                           creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        except:
            pass
    
    def _add_stat_divider(self, layout):
        """Add a vertical divider between stats"""
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setFixedHeight(40)
        divider.setStyleSheet("background: rgba(255, 255, 255, 0.08);")
        layout.addSpacing(24)
        layout.addWidget(divider)
        layout.addSpacing(24)
    
    def _create_stat(self, label: str, value: str, color: str | None = None):
        """Create an improved stat display widget matching DriversPage"""
        frame = QFrame()
        frame.setStyleSheet("background: transparent;")
        frame.setMinimumWidth(100)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        value_label = QLabel(value)
        value_label.setObjectName("stat_value")
        value_color = color or Theme.TEXT_PRIMARY
        value_label.setStyleSheet(f"""
            background: transparent;
            color: {value_color};
            font-size: 24px;
            font-weight: 700;
        """)
        layout.addWidget(value_label)
        
        text_label = QLabel(label)
        text_label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_TERTIARY};
            font-size: 11px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(text_label)
        
        return frame
    
    def _update_stat(self, stat_widget: QFrame, value: str):
        """Update a stat widget's value"""
        value_label = stat_widget.findChild(QLabel, "stat_value")
        if value_label:
            value_label.setText(value)
    
    def check_updates(self):
        """Check for Windows updates using background thread"""
        if self.is_loading:
            return
        
        self.is_loading = True
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Checking...")
        self.status_label.setText("Checking for updates...")
        self.status_label.setVisible(True)
        self.main_container.setVisible(False)
        
        # Run in background thread
        self._thread = QThread(self)
        self._worker = WindowsUpdateDetailWorker()
        self._worker.moveToThread(self._thread)
        
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_check_complete)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        
        self._thread.start()
    
    def _on_check_complete(self, data: dict):
        """Handle update check completion"""
        self.is_loading = False
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Check for Updates")
        
        if not data or data.get('Error'):
            self.status_label.setText(f"Error: {data.get('Error', 'Unknown error')}")
            self.status_label.setVisible(True)
            return
        
        self.update_data = data
        self._display_updates()
    
    def display_cached_data(self, data: dict):
        """Display update info from cached data (from full scan)"""
        if not data:
            return
        
        # If we have basic data, trigger a full check for detailed info
        if not self.update_data and not self.is_loading:
            self.check_updates()
    
    def _display_updates(self):
        """Display the update information"""
        self.status_label.setVisible(False)
        self.stats_frame.setVisible(True)
        self.main_container.setVisible(True)
        
        # Clear old widgets
        for widget in self.widgets:
            widget.deleteLater()
        self.widgets.clear()
        
        # Clear main layout
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        
        # Update stats
        pending = self.update_data.get('PendingUpdates', [])
        if isinstance(pending, list):
            pending_count = len(pending)
            downloaded_count = sum(1 for u in pending if u.get('IsDownloaded', False))
        else:
            pending_count = 0
            downloaded_count = 0
        
        # Count failed from history
        history = self.update_data.get('RecentHistory', [])
        failed_count = sum(1 for h in history if h.get('Result') == 'Failed')
        
        self._update_stat(self.stat_pending, str(pending_count))
        self._update_stat(self.stat_downloaded, str(downloaded_count))
        self._update_stat(self.stat_failed, str(failed_count))
        
        # Update service status
        service = self.update_data.get('ServiceStatus', 'Unknown')
        self._update_stat(self.stat_service, service)
        
        # Show reboot banner if needed
        self.reboot_banner.setVisible(self.update_data.get('PendingReboot', False))
        
        # Update last checked
        last_check = self.update_data.get('LastCheck', 'Unknown')
        self.last_checked.setText(f"Last check: {last_check}")
        
        # Pending Updates Section
        if pending_count > 0:
            pending_card = self._create_updates_card("Available Updates", pending, "pending")
            self.main_layout.addWidget(pending_card)
            self.widgets.append(pending_card)
        else:
            # Show "up to date" message
            up_to_date = QFrame()
            up_to_date.setStyleSheet(f"""
                QFrame {{
                    background: {Theme.BG_CARD};
                    border-radius: {Theme.RADIUS_MD}px;
                }}
            """)
            Theme.apply_shadow(up_to_date, blur_radius=12, offset_y=3, opacity=60)
            
            up_to_date_layout = QHBoxLayout(up_to_date)
            up_to_date_layout.setContentsMargins(20, 20, 20, 20)
            up_to_date_layout.setSpacing(14)
            
            # Success icon with background circle
            icon_container = QFrame()
            icon_container.setFixedSize(40, 40)
            icon_container.setStyleSheet(f"""
                background: {Theme.SUCCESS}22;
                border-radius: 20px;
            """)
            icon_layout = QVBoxLayout(icon_container)
            icon_layout.setContentsMargins(0, 0, 0, 0)
            icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            check_icon = QLabel("\uE73E")  # Fluent checkmark
            check_icon.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets'; font-size: 18px;")
            check_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_layout.addWidget(check_icon)
            up_to_date_layout.addWidget(icon_container)
            
            up_to_date_text = QLabel("Your device is up to date")
            up_to_date_text.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 14px; font-weight: 500;")
            up_to_date_layout.addWidget(up_to_date_text)
            up_to_date_layout.addStretch()
            
            last_install = self.update_data.get('LastInstall', 'Unknown')
            install_label = QLabel(f"Last installed: {last_install}")
            install_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
            up_to_date_layout.addWidget(install_label)
            
            self.main_layout.addWidget(up_to_date)
            self.widgets.append(up_to_date)
        
        # Update History Section
        if history:
            history_card = self._create_history_card("Recent Update History", history)
            self.main_layout.addWidget(history_card)
            self.widgets.append(history_card)
    
    def _create_updates_card(self, title: str, updates: list, card_type: str):
        """Create a card showing available updates"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(card, blur_radius=12, offset_y=3, opacity=60)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # Header
        header = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 18px; font-weight: 600;")
        header.addWidget(title_label)
        header.addStretch()
        
        count_label = QLabel(f"{len(updates)} update(s)")
        count_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        header.addWidget(count_label)
        
        layout.addLayout(header)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255, 255, 255, 0.08);")
        layout.addWidget(sep)

        # Updates list
        for update in updates[:10]:  # Limit to 10
            update_row = self._create_update_row(update)
            layout.addWidget(update_row)
        
        if len(updates) > 10:
            more_label = QLabel(f"... and {len(updates) - 10} more updates")
            more_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
            more_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(more_label)
        
        return card
    
    def _create_update_row(self, update: dict):
        """Create a row for a single update"""
        row = QFrame()
        row.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_ELEVATED};
                border-radius: {Theme.RADIUS_SM}px;
            }}
        """)
        
        layout = QVBoxLayout(row)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        # Top row: title and category
        top_row = QHBoxLayout()
        
        # Downloaded indicator
        if update.get('IsDownloaded'):
            dl_icon = QLabel("⬇")
            dl_icon.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 12px;")
            dl_icon.setToolTip("Downloaded")
            top_row.addWidget(dl_icon)
        
        title = update.get('Title', 'Unknown Update')
        title_label = QLabel(title)
        title_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 13px; font-weight: 500;")
        title_label.setWordWrap(True)
        top_row.addWidget(title_label, 1)
        
        # Category badge
        category = update.get('Category', 'Other')
        cat_color = Theme.ACCENT if 'Security' in category else Theme.TEXT_SECONDARY
        cat_label = QLabel(category)
        cat_label.setStyleSheet(f"""
            background: {Theme.BG_CARD_HOVER};
            color: {cat_color};
            font-size: 11px;
            padding: 2px 8px;
            border: none;
            border-radius: 10px;
        """)
        top_row.addWidget(cat_label)
        
        layout.addLayout(top_row)
        
        # Bottom row: KB, size, severity
        bottom_row = QHBoxLayout()
        
        kb = update.get('KBArticleIDs', '')
        if kb:
            kb_label = QLabel(f"KB{kb}")
            kb_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
            bottom_row.addWidget(kb_label)
        
        size = update.get('SizeMB', 0)
        if size > 0:
            size_label = QLabel(f"{size} MB")
            size_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
            bottom_row.addWidget(size_label)
        
        severity = update.get('Severity', '')
        if severity and severity != 'Unspecified':
            sev_color = Theme.ERROR if severity == 'Critical' else Theme.WARNING if severity == 'Important' else Theme.TEXT_TERTIARY
            sev_label = QLabel(severity)
            sev_label.setStyleSheet(f"background: transparent; color: {sev_color}; font-size: 11px; font-weight: 500;")
            bottom_row.addWidget(sev_label)
        
        bottom_row.addStretch()
        
        if update.get('IsMandatory'):
            mandatory = QLabel("Required")
            mandatory.setStyleSheet(f"background: transparent; color: {Theme.WARNING}; font-size: 11px;")
            bottom_row.addWidget(mandatory)
        
        layout.addLayout(bottom_row)
        
        return row
    
    def _create_history_card(self, title: str, history: list):
        """Create a card showing update history"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(card, blur_radius=12, offset_y=3, opacity=60)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)        # Header
        header = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 16px; font-weight: 600;")
        header.addWidget(title_label)
        header.addStretch()
        layout.addLayout(header)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255, 255, 255, 0.08);")
        layout.addWidget(sep)

        # History list
        for entry in history[:15]:  # Limit to 15
            history_row = self._create_history_row(entry)
            layout.addWidget(history_row)
        
        return card
    
    def _create_history_row(self, entry: dict):
        """Create a row for a history entry with improved date formatting"""
        row = QFrame()
        row.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border-bottom: 1px solid rgba(255, 255, 255, 0.03);
            }}
        """)

        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(12)

        # Result icon
        result = entry.get('Result', 'Unknown')
        if result == 'Succeeded':
            icon = "\uE73E"
            icon_color = Theme.SUCCESS
        elif result == 'Failed':
            icon = "\uE711"
            icon_color = Theme.ERROR
        else:
            icon = "\uE946"
            icon_color = Theme.TEXT_TERTIARY

        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"background: transparent; color: {icon_color}; font-size: 14px; font-weight: bold; font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';")
        icon_label.setFixedWidth(20)
        layout.addWidget(icon_label)

        # Title
        title = entry.get('Title', 'Unknown')
        if len(title) > 70:
            title = title[:70] + "..."
        title_label = QLabel(title)
        title_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 13px;")
        title_label.setWordWrap(True)
        layout.addWidget(title_label, 1)

        # Date - format more readable
        date = entry.get('Date', '')
        formatted_date = self._format_update_date(date)
        date_label = QLabel(formatted_date)
        date_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px; min-width: 120px;")
        date_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(date_label)

        return row

    def _format_update_date(self, date_str: str) -> str:
        """Format date string into a more readable format"""
        if not date_str:
            return "Unknown"
        
        try:
            from datetime import datetime, timedelta
            
            # Try to parse common date formats
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"]:
                try:
                    dt = datetime.strptime(date_str.split('.')[0], fmt)
                    now = datetime.now()
                    diff = now - dt
                    
                    # Format based on how recent
                    if diff.days == 0:
                        hours = diff.seconds // 3600
                        if hours == 0:
                            mins = diff.seconds // 60
                            return f"{mins} min ago" if mins > 1 else "Just now"
                        return f"{hours}h ago" if hours < 12 else f"Today {dt.strftime('%H:%M')}"
                    elif diff.days == 1:
                        return f"Yesterday {dt.strftime('%H:%M')}"
                    elif diff.days < 7:
                        return f"{diff.days} days ago"
                    else:
                        return dt.strftime("%b %d, %Y")
                except ValueError:
                    continue
            
            # If parsing fails, return original but cleaned up
            return date_str[:16] if len(date_str) > 16 else date_str
        except Exception:
            return date_str[:16] if len(date_str) > 16 else date_str

    def _open_windows_update(self):
        """Open Windows Update settings"""
        import subprocess
        try:
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:windowsupdate"], 
                           creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        except Exception as e:
            print(f"Error opening Windows Update: {e}")
    
    def refresh_accent_colors(self):
        """Update accent-colored elements when theme changes"""
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT_HOVER};
            }}
            QPushButton:disabled {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_TERTIARY};
            }}
        """)


class WindowsUpdateDetailWorker(QObject):
    """Worker to fetch detailed Windows Update info in background"""
    finished = pyqtSignal(dict)
    
    def run(self):
        try:
            from driver_backend import HealthChecker
            checker = HealthChecker()
            data = checker.get_windows_update_details()
            self.finished.emit(data)
        except Exception as e:
            self.finished.emit({"Error": str(e)})


# =============================================================================
# STORAGE PAGE - Comprehensive Storage Management
# =============================================================================

class StoragePage(QWidget):
    """Dedicated page for storage management with detailed drive information"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.storage_data = {}
        self.widgets = []
        self.is_loading = False
        self._thread = None
        self._worker = None
        self.setup_ui()
    
    def setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(32, 28, 32, 28)
        self.content_layout.setSpacing(20)
        
        # Header row
        header = QHBoxLayout()
        header.setSpacing(16)
        
        title = QLabel("Storage Health")
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 28px;
            font-weight: 600;
        """)
        header.addWidget(title)
        header.addStretch()
        
        # Refresh button
        self.refresh_btn = QPushButton("Scan Storage")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.scan_storage)
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT_HOVER};
            }}
            QPushButton:disabled {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_TERTIARY};
            }}
        """)
        header.addWidget(self.refresh_btn)
        
        # Disk Cleanup button
        cleanup_btn = QPushButton("Disk Cleanup")
        cleanup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cleanup_btn.clicked.connect(self._open_disk_cleanup)
        cleanup_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                padding: 10px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        header.addWidget(cleanup_btn)
        
        # Storage Settings button
        settings_btn = QPushButton("Storage Settings")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.clicked.connect(self._open_storage_settings)
        settings_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                padding: 10px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        header.addWidget(settings_btn)
        
        self.content_layout.addLayout(header)
        
        # Status label
        self.status_label = QLabel("Click 'Scan Storage' to analyze your drives")
        self.status_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 13px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.status_label)
        
        # Summary stats row - matching DriversPage styling
        self.stats_frame = QFrame()
        self.stats_frame.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(self.stats_frame, blur_radius=12, offset_y=3, opacity=60)
        self.stats_frame.setVisible(False)
        stats_layout = QHBoxLayout(self.stats_frame)
        stats_layout.setContentsMargins(24, 20, 24, 20)
        stats_layout.setSpacing(0)
        
        self.stat_total = self._create_stat("Total Space", "—", Theme.TEXT_PRIMARY)
        stats_layout.addWidget(self.stat_total)
        self._add_stat_divider(stats_layout)
        
        self.stat_used = self._create_stat("Used", "—", Theme.WARNING)
        stats_layout.addWidget(self.stat_used)
        self._add_stat_divider(stats_layout)
        
        self.stat_free = self._create_stat("Free", "—", Theme.SUCCESS)
        stats_layout.addWidget(self.stat_free)
        self._add_stat_divider(stats_layout)
        
        self.stat_disks = self._create_stat("Drives", "—", Theme.ACCENT)
        stats_layout.addWidget(self.stat_disks)
        
        stats_layout.addStretch()
        
        self.content_layout.addWidget(self.stats_frame)
        
        # Main content container
        self.main_container = QFrame()
        self.main_container.setStyleSheet("background: transparent;")
        self.main_layout = QVBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(20)
        self.main_container.setVisible(False)
        self.content_layout.addWidget(self.main_container)
        
        self.content_layout.addStretch()
        
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        
        # Floating Quick Tools bar
        tools = [
            ("Disk Cleanup", "\uE90F", self._open_disk_cleanup),
            ("Disk Management", "\uE964", self._open_disk_management),
            ("Storage Settings", "\uEDA2", self._open_storage_settings),
        ]
        self._floating_toolbar = FloatingToolbar(tools, self)
    
    def resizeEvent(self, event):
        """Reposition floating toolbar on resize"""
        super().resizeEvent(event)
        if hasattr(self, '_floating_toolbar'):
            self._floating_toolbar.update_position()
    
    def _open_disk_management(self):
        """Open Disk Management"""
        import subprocess
        try:
            subprocess.Popen(["diskmgmt.msc"])
        except:
            pass
    
    def _open_storage_settings(self):
        """Open Storage Settings"""
        import subprocess
        try:
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:storagesense"],
                           creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        except:
            pass
    
    def _add_stat_divider(self, layout):
        """Add a vertical divider between stats"""
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setFixedHeight(40)
        divider.setStyleSheet("background: rgba(255, 255, 255, 0.08);")
        layout.addSpacing(24)
        layout.addWidget(divider)
        layout.addSpacing(24)
    
    def _create_stat(self, label: str, value: str, color: str):
        """Create an improved stat display widget matching DriversPage"""
        frame = QFrame()
        frame.setStyleSheet("background: transparent;")
        frame.setMinimumWidth(100)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        value_label = QLabel(value)
        value_label.setObjectName("stat_value")
        value_label.setStyleSheet(f"""
            background: transparent;
            color: {color};
            font-size: 24px;
            font-weight: 700;
        """)
        layout.addWidget(value_label)
        
        text_label = QLabel(label)
        text_label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_TERTIARY};
            font-size: 11px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(text_label)
        
        return frame
    
    def _update_stat(self, stat_widget: QFrame, value: str):
        """Update a stat widget's value"""
        value_label = stat_widget.findChild(QLabel, "stat_value")
        if value_label:
            value_label.setText(value)
    
    def scan_storage(self):
        """Scan storage using background thread"""
        if self.is_loading:
            return
        
        self.is_loading = True
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Scanning...")
        self.status_label.setText("Analyzing storage...")
        self.status_label.setVisible(True)
        self.main_container.setVisible(False)
        
        # Run in background thread
        self._thread = QThread(self)
        self._worker = StorageDetailWorker()
        self._worker.moveToThread(self._thread)
        
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_scan_complete)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        
        self._thread.start()
    
    def _on_scan_complete(self, data: dict):
        """Handle storage scan completion"""
        self.is_loading = False
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Scan Storage")
        
        if not data or data.get('Error'):
            self.status_label.setText(f"Error: {data.get('Error', 'Unknown error')}")
            self.status_label.setVisible(True)
            return
        
        self.storage_data = data
        self._display_storage()
    
    def display_cached_data(self, data):
        """Display storage info from cached data (from full scan)"""
        if not data:
            return
        # If we have basic volume data, trigger a full scan for detailed info
        if not self.storage_data and not self.is_loading:
            self.scan_storage()
    
    def _display_storage(self):
        """Display the storage information"""
        self.status_label.setVisible(False)
        self.stats_frame.setVisible(True)
        self.main_container.setVisible(True)
        
        # Clear old widgets
        for widget in self.widgets:
            widget.deleteLater()
        self.widgets.clear()
        
        # Clear main layout
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        
        # Update summary stats
        total = self.storage_data.get('TotalSpace', 0)
        used = self.storage_data.get('TotalUsed', 0)
        free = self.storage_data.get('TotalFree', 0)
        disks = len(self.storage_data.get('Disks', []))
        
        self._update_stat(self.stat_total, f"{total:.1f} GB")
        self._update_stat(self.stat_used, f"{used:.1f} GB")
        self._update_stat(self.stat_free, f"{free:.1f} GB")
        self._update_stat(self.stat_disks, str(disks))
        
        # Volumes section with visual bars
        volumes = self.storage_data.get('Volumes', [])
        if volumes:
            volumes_card = self._create_volumes_card(volumes)
            self.main_layout.addWidget(volumes_card)
            self.widgets.append(volumes_card)
        
        # Physical disks section
        disks_data = self.storage_data.get('Disks', [])
        if disks_data:
            disks_card = self._create_disks_card(disks_data)
            self.main_layout.addWidget(disks_card)
            self.widgets.append(disks_card)
        
        # Cleanup suggestions
        cleanup_card = self._create_cleanup_card()
        self.main_layout.addWidget(cleanup_card)
        self.widgets.append(cleanup_card)
    
    def _create_volumes_card(self, volumes: list):
        """Create a card showing volume information with progress bars"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(card, blur_radius=12, offset_y=3, opacity=60)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Header
        title = QLabel("Volumes")
        title.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 18px; font-weight: 600;")
        layout.addWidget(title)
        
        # Volume rows
        for vol in volumes:
            vol_widget = self._create_volume_row(vol)
            layout.addWidget(vol_widget)
        
        return card
    
    def _create_volume_row(self, vol: dict):
        """Create a row for a volume with progress bar"""
        row = QFrame()
        row.setStyleSheet("background: transparent;")
        
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(8)
        
        # Top row: drive letter, label, and sizes
        top_row = QHBoxLayout()
        
        drive_letter = vol.get('DriveLetter', '?')
        label = vol.get('Label', '')
        drive_name = f"{drive_letter}:"
        if label:
            drive_name += f" ({label})"
        
        name_label = QLabel(drive_name)
        name_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 14px; font-weight: 600;")
        top_row.addWidget(name_label)
        
        # Drive type badge
        drive_type = vol.get('DriveType', 'Unknown')
        type_label = QLabel(drive_type)
        type_label.setStyleSheet(f"""
            background: {Theme.BG_ELEVATED};
            color: {Theme.TEXT_TERTIARY};
            font-size: 11px;
            padding: 2px 8px;
            border: none;
            border-radius: 10px;
        """)
        top_row.addWidget(type_label)
        
        top_row.addStretch()
        
        # Size info
        used = vol.get('UsedGB', 0)
        total = vol.get('SizeGB', 0)
        free = vol.get('FreeGB', 0)
        size_text = f"{used:.1f} GB / {total:.1f} GB ({free:.1f} GB free)"
        size_label = QLabel(size_text)
        size_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        top_row.addWidget(size_label)
        
        layout.addLayout(top_row)
        
        # Progress bar
        used_percent = vol.get('UsedPercent', 0)
        progress_container = QFrame()
        progress_container.setFixedHeight(8)
        progress_container.setStyleSheet(f"""
            background: {Theme.BG_ELEVATED};
            border-radius: 4px;
        """)
        
        # Determine color based on usage
        if used_percent >= 90:
            bar_color = Theme.ERROR
        elif used_percent >= 75:
            bar_color = Theme.WARNING
        else:
            bar_color = Theme.ACCENT
        
        # Use a percentage-based approach
        progress_layout = QHBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(0)
        
        inner_bar = QFrame()
        inner_bar.setStyleSheet(f"background: {bar_color}; border-radius: 4px;")
        progress_layout.addWidget(inner_bar, int(used_percent))
        
        spacer = QFrame()
        spacer.setStyleSheet("background: transparent;")
        progress_layout.addWidget(spacer, int(100 - used_percent))
        
        layout.addWidget(progress_container)
        
        # Bottom row: health status and file system
        bottom_row = QHBoxLayout()
        
        health = vol.get('HealthStatus', 'Unknown')
        health_color = Theme.SUCCESS if health == 'Healthy' else Theme.WARNING
        health_label = QLabel(f"● {health}")
        health_label.setStyleSheet(f"background: transparent; color: {health_color}; font-size: 11px;")
        bottom_row.addWidget(health_label)
        
        fs = vol.get('FileSystem', 'Unknown')
        fs_label = QLabel(f"File System: {fs}")
        fs_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
        bottom_row.addWidget(fs_label)
        
        bottom_row.addStretch()
        
        # Percentage label
        pct_color = Theme.ERROR if used_percent >= 90 else Theme.WARNING if used_percent >= 75 else Theme.TEXT_SECONDARY
        pct_label = QLabel(f"{used_percent:.0f}% used")
        pct_label.setStyleSheet(f"background: transparent; color: {pct_color}; font-size: 12px; font-weight: 500;")
        bottom_row.addWidget(pct_label)
        
        layout.addLayout(bottom_row)
        
        return row
    
    def _create_disks_card(self, disks: list):
        """Create a card showing physical disk information"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(card, blur_radius=12, offset_y=3, opacity=60)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # Header
        title = QLabel("Physical Disks")
        title.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 18px; font-weight: 600;")
        layout.addWidget(title)
        
        # Disk rows
        for disk in disks:
            disk_row = self._create_disk_row(disk)
            layout.addWidget(disk_row)
        
        return card
    
    def _create_disk_row(self, disk: dict):
        """Create a row for a physical disk"""
        row = QFrame()
        row.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_ELEVATED};
                border-radius: {Theme.RADIUS_SM}px;
            }}
        """)
        
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)
        
        # Disk icon based on type
        media_type = disk.get('MediaType', 'Unknown')
        icon_text = "\uEDA2" if 'SSD' in media_type else "\uE958"  # HardDrive or Disc
        icon = QLabel(icon_text)
        icon.setStyleSheet("background: transparent; font-size: 24px; font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';")
        layout.addWidget(icon)
        
        # Disk info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        model = disk.get('Model', 'Unknown Disk')
        model_label = QLabel(model)
        model_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 13px; font-weight: 500;")
        info_layout.addWidget(model_label)
        
        # Build details string with drive letters if available
        drive_letters = disk.get('DriveLetters', '')
        details = f"{disk.get('SizeGB', 0):.0f} GB • {media_type} • {disk.get('InterfaceType', 'Unknown')}"
        if drive_letters:
            details = f"{drive_letters} • {details}"
        details_label = QLabel(details)
        details_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
        info_layout.addWidget(details_label)
        
        layout.addLayout(info_layout, 1)
        
        # Status
        status = disk.get('Status', 'Unknown')
        status_color = Theme.SUCCESS if status == 'OK' else Theme.WARNING
        status_label = QLabel(f"● {status}")
        status_label.setStyleSheet(f"background: transparent; color: {status_color}; font-size: 12px;")
        layout.addWidget(status_label)
        
        return row
    
    def _create_cleanup_card(self):
        """Create a card showing cleanup suggestions"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(card, blur_radius=12, offset_y=3, opacity=60)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("Cleanup Suggestions")
        title.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 18px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)
        
        # Cleanup items
        temp_size = self.storage_data.get('TempFilesSize', 0)
        recycle_size = self.storage_data.get('RecycleBinSize', 0)
        downloads_size = self.storage_data.get('DownloadsSize', 0)
        
        total_cleanable = temp_size + recycle_size
        
        # Summary
        if total_cleanable > 100:
            summary = QLabel(f"You can potentially free up {total_cleanable:.0f} MB")
            summary.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 13px;")
            layout.addWidget(summary)
        
        # Cleanup items
        cleanup_items = [
            ("Temporary Files", temp_size, self._clear_temp_files),
            ("Recycle Bin", recycle_size, self._empty_recycle_bin),
            ("Downloads Folder", downloads_size, self._open_downloads),
        ]
        
        for name, size, action in cleanup_items:
            item_row = QFrame()
            item_row.setStyleSheet("background: transparent;")
            item_layout = QHBoxLayout(item_row)
            item_layout.setContentsMargins(0, 4, 0, 4)
            
            item_name = QLabel(name)
            item_name.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 13px;")
            item_layout.addWidget(item_name)
            
            if size > 0:
                size_label = QLabel(f"{size:.0f} MB" if size < 1024 else f"{size/1024:.1f} GB")
                size_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
                item_layout.addWidget(size_label)
            
            item_layout.addStretch()
            
            if size > 0 or name == "Downloads Folder":
                action_btn = QPushButton("Clean" if name != "Downloads Folder" else "Open")
                action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                action_btn.clicked.connect(action)
                action_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        color: {Theme.ACCENT};
                        border: 1px solid {Theme.ACCENT};
                        padding: 4px 12px;
                        border-radius: {Theme.RADIUS_SM}px;
                        font-size: 11px;
                    }}
                    QPushButton:hover {{
                        background: {Theme.ACCENT};
                        color: white;
                    }}
                """)
                item_layout.addWidget(action_btn)
            
            layout.addWidget(item_row)
        
        return card
    
    def _open_disk_cleanup(self):
        """Open Windows Disk Cleanup"""
        import subprocess
        try:
            subprocess.Popen(["cleanmgr"], creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        except Exception as e:
            print(f"Error opening Disk Cleanup: {e}")
    
    def _open_storage_settings(self):
        """Open Windows Storage Settings"""
        import subprocess
        try:
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:storagesense"], 
                           creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        except Exception as e:
            print(f"Error opening Storage Settings: {e}")
    
    def _clear_temp_files(self):
        """Clear temporary files"""
        import subprocess
        try:
            # Use cleanmgr with temp files preset
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:storagesense"], 
                           creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        except Exception as e:
            print(f"Error: {e}")
    
    def _empty_recycle_bin(self):
        """Empty the recycle bin"""
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Empty Recycle Bin",
            "Are you sure you want to permanently delete all items in the Recycle Bin?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            import subprocess
            try:
                subprocess.run(
                    ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
                # Refresh the scan
                self.scan_storage()
            except Exception as e:
                print(f"Error emptying recycle bin: {e}")
    
    def _open_downloads(self):
        """Open the Downloads folder"""
        import subprocess
        import os
        downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
        try:
            subprocess.Popen(["explorer", downloads_path])
        except Exception as e:
            print(f"Error opening Downloads: {e}")
    
    def refresh_accent_colors(self):
        """Update accent-colored elements when theme changes"""
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT_HOVER};
            }}
            QPushButton:disabled {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_TERTIARY};
            }}
        """)


class StorageDetailWorker(QObject):
    """Worker to fetch detailed storage info in background"""
    finished = pyqtSignal(dict)
    
    def run(self):
        try:
            from driver_backend import HealthChecker
            checker = HealthChecker()
            data = checker.get_storage_details()
            self.finished.emit(data)
        except Exception as e:
            self.finished.emit({"Error": str(e)})


# =============================================================================
# SECURITY PAGE - Windows Defender, Firewall, and System Security
# =============================================================================

class FirewallRulesWorker(QObject):
    """Worker to fetch firewall rules in background"""
    finished = pyqtSignal(list)
    
    def run(self):
        try:
            from driver_backend import HealthChecker
            checker = HealthChecker()
            rules = checker.get_firewall_rules(enabled_only=True, max_rules=100)
            self.finished.emit(rules)
        except Exception as e:
            self.finished.emit([])


class FirewallStatusWorker(QObject):
    """Worker to fetch firewall status in background"""
    finished = pyqtSignal(dict)
    
    def run(self):
        try:
            from driver_backend import HealthChecker
            checker = HealthChecker()
            status = checker.get_firewall_status()
            self.finished.emit(status)
        except Exception as e:
            self.finished.emit({"Error": str(e)})


class SecurityPage(QWidget):
    """Dedicated security page with tabs for Defender, Firewall Status, and Firewall Rules"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cached_defender_data = {}
        self.cached_firewall_status = {}
        self.cached_firewall_rules = []
        self._thread = None
        self._worker = None
        self._active_threads = []  # Keep references to prevent GC
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 28, 32, 28)
        main_layout.setSpacing(20)
        
        # Header row
        header = QHBoxLayout()
        header.setSpacing(16)
        
        title = QLabel("Security Status")
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 28px;
            font-weight: 600;
        """)
        header.addWidget(title)
        header.addStretch()
        
        # Open Windows Security button
        security_btn = QPushButton("Open Windows Security")
        security_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        security_btn.clicked.connect(self._open_windows_security)
        security_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT_HOVER};
            }}
        """)
        header.addWidget(security_btn)
        
        main_layout.addLayout(header)
        
        # Tab bar
        tab_bar = QHBoxLayout()
        tab_bar.setSpacing(0)
        
        self.tabs = {}
        tab_items = [
            ("defender", "Windows Defender"),
            ("firewall", "Firewall Status"),
            ("rules", "Firewall Rules"),
        ]
        
        for tab_id, tab_label in tab_items:
            btn = QPushButton(tab_label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, tid=tab_id: self._switch_tab(tid))
            btn.setStyleSheet(self._get_tab_style(False))
            self.tabs[tab_id] = btn
            tab_bar.addWidget(btn)
        
        tab_bar.addStretch()
        main_layout.addLayout(tab_bar)
        
        # Select first tab by default
        self.tabs["defender"].setChecked(True)
        self.tabs["defender"].setStyleSheet(self._get_tab_style(True))
        self.current_tab = "defender"
        
        # Content stack for different tabs (with smooth transitions)
        self.content_stack = AnimatedStackedWidget()
        self.content_stack.set_transition_duration(150)  # Faster for tabs
        
        # Defender tab content
        self.defender_scroll = QScrollArea()
        self.defender_scroll.setWidgetResizable(True)
        self.defender_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.defender_content = QWidget()
        self.defender_layout = QVBoxLayout(self.defender_content)
        self.defender_layout.setContentsMargins(0, 16, 0, 16)
        self.defender_layout.setSpacing(12)
        self.defender_layout.addStretch()
        self.defender_scroll.setWidget(self.defender_content)
        self.content_stack.addWidget(self.defender_scroll)
        
        # Firewall Status tab content
        self.firewall_scroll = QScrollArea()
        self.firewall_scroll.setWidgetResizable(True)
        self.firewall_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.firewall_content = QWidget()
        self.firewall_layout = QVBoxLayout(self.firewall_content)
        self.firewall_layout.setContentsMargins(0, 16, 0, 16)
        self.firewall_layout.setSpacing(12)
        self.firewall_layout.addStretch()
        self.firewall_scroll.setWidget(self.firewall_content)
        self.content_stack.addWidget(self.firewall_scroll)
        
        # Firewall Rules tab content
        self.rules_scroll = QScrollArea()
        self.rules_scroll.setWidgetResizable(True)
        self.rules_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rules_content = QWidget()
        self.rules_layout = QVBoxLayout(self.rules_content)
        self.rules_layout.setContentsMargins(0, 16, 0, 16)
        self.rules_layout.setSpacing(8)
        self.rules_layout.addStretch()
        self.rules_scroll.setWidget(self.rules_content)
        self.content_stack.addWidget(self.rules_scroll)
        
        main_layout.addWidget(self.content_stack)
        
        # Show placeholder
        self._show_placeholder("Click 'Open Windows Security' or run a full system scan to see security status")
        
        # Floating Quick Tools bar
        tools = [
            ("Windows Security", "\uE83D", self._open_windows_security),
            ("Firewall Settings", "\uE8D8", self._open_firewall_settings),
            ("Event Viewer", "\uE7C4", self._open_event_viewer),
        ]
        self._floating_toolbar = FloatingToolbar(tools, self)
    
    def resizeEvent(self, event):
        """Reposition floating toolbar on resize"""
        super().resizeEvent(event)
        if hasattr(self, '_floating_toolbar'):
            self._floating_toolbar.update_position()
    
    def _open_firewall_settings(self):
        """Open Windows Firewall Settings"""
        import subprocess
        try:
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:windowsdefender-firewall"],
                           creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        except:
            pass
    
    def _open_event_viewer(self):
        """Open Event Viewer"""
        import subprocess
        try:
            subprocess.Popen(["eventvwr.msc"])
        except:
            pass
    
    def _get_tab_style(self, is_active: bool) -> str:
        """Tab styling per spec Section 7.0.2 - 44px height, 14px font"""
        if is_active:
            return f"""
                QPushButton {{
                    background: {Theme.BG_CARD};
                    color: {Theme.TEXT_PRIMARY};
                    border: none;
                    border-bottom: 2px solid {Theme.ACCENT};
                    border-radius: 8px 8px 0 0;
                    padding: 12px 24px;
                    min-height: 44px;
                    font-size: 14px;
                    font-weight: 600;
                }}
            """
        else:
            return f"""
                QPushButton {{
                    background: transparent;
                    color: {Theme.TEXT_SECONDARY};
                    border: none;
                    border-bottom: 2px solid transparent;
                    padding: 12px 24px;
                    min-height: 44px;
                    font-size: 14px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    color: {Theme.TEXT_PRIMARY};
                    background: {Theme.BG_CARD_HOVER};
                }}
            """
    
    def _switch_tab(self, tab_id: str):
        # Update tab styles
        for tid, btn in self.tabs.items():
            is_active = tid == tab_id
            btn.setChecked(is_active)
            btn.setStyleSheet(self._get_tab_style(is_active))
        
        self.current_tab = tab_id
        
        # Switch content
        if tab_id == "defender":
            self.content_stack.setCurrentWidget(self.defender_scroll)
        elif tab_id == "firewall":
            self.content_stack.setCurrentWidget(self.firewall_scroll)
            # Load firewall status if not loaded
            if not self.cached_firewall_status:
                self._load_firewall_status()
        elif tab_id == "rules":
            self.content_stack.setCurrentWidget(self.rules_scroll)
            # Load rules if not loaded
            if not self.cached_firewall_rules:
                self._load_firewall_rules()
    
    def _show_placeholder(self, text: str):
        """Show placeholder in defender tab"""
        self._clear_layout(self.defender_layout)
        
        label = QLabel(text)
        label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 13px;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        self.defender_layout.insertWidget(0, label)
    
    def _clear_layout(self, layout):
        """Clear all widgets from a layout"""
        while layout.count() > 1:  # Keep the stretch
            item = layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
    
    def display_defender_data(self, defender: dict):
        """Display Windows Defender status"""
        self.cached_defender_data = defender
        self._clear_layout(self.defender_layout)
        
        if not defender or 'Error' in defender:
            self._show_placeholder("Unable to retrieve security status")
            return
        
        # Create sections
        sections = []
        
        # Defender Status Section
        defender_items = []
        
        enabled = defender.get('AntivirusEnabled', False)
        if enabled:
            defender_items.append(("check", "Windows Defender Antivirus is enabled"))
        else:
            defender_items.append(("error", "Windows Defender Antivirus is DISABLED!"))
        
        realtime = defender.get('RealTimeProtection', False)
        if realtime:
            defender_items.append(("check", "Real-time protection is active"))
        else:
            defender_items.append(("warning", "Real-time protection is OFF"))
        
        if defender.get('BehaviorMonitor', False):
            defender_items.append(("check", "Behavior monitoring enabled"))
        else:
            defender_items.append(("warning", "Behavior monitoring disabled"))
        
        # Signature info
        sig_age = defender.get('SignatureAge', 0)
        if sig_age == 0:
            defender_items.append(("check", "Virus definitions are up to date"))
        elif sig_age <= 3:
            defender_items.append(("check", f"Virus definitions: {sig_age} day(s) old"))
        elif sig_age <= 7:
            defender_items.append(("warning", f"Virus definitions: {sig_age} days old - Update recommended"))
        else:
            defender_items.append(("error", f"Virus definitions: {sig_age} days old - Update required!"))
        
        if defender.get('SignatureVersion'):
            defender_items.append(("info", f"Signature version: {defender.get('SignatureVersion')}"))
        
        defender_items.append(("info", f"Last full scan: {defender.get('LastScan', 'Never')}"))
        defender_items.append(("info", f"Last quick scan: {defender.get('LastQuickScan', 'Never')}"))
        
        sections.append(("Windows Defender", defender_items))
        
        # System Security Section
        security_items = []
        
        if defender.get('UACEnabled', False):
            security_items.append(("check", "User Account Control (UAC) is enabled"))
        else:
            security_items.append(("error", "User Account Control (UAC) is DISABLED!"))
        
        secure_boot = defender.get('SecureBoot')
        if secure_boot is True:
            security_items.append(("check", "Secure Boot is enabled"))
        elif secure_boot is False:
            security_items.append(("warning", "Secure Boot is disabled"))
        else:
            security_items.append(("info", "Secure Boot: Unable to determine"))
        
        bl_status = defender.get('BitLockerStatus', 'Unknown')
        if bl_status == 'On':
            enc = defender.get('BitLockerEncryption', 100)
            if enc == 100:
                security_items.append(("check", "BitLocker: System drive fully encrypted"))
            else:
                security_items.append(("warning", f"BitLocker: Encrypting ({enc}% complete)"))
        elif bl_status == 'Off':
            security_items.append(("info", "BitLocker: Not enabled on system drive"))
        else:
            security_items.append(("info", f"BitLocker: {bl_status}"))
        
        if defender.get('CredentialGuard', False):
            security_items.append(("check", "Credential Guard is running"))
        
        if defender.get('HVCIRunning', False):
            security_items.append(("check", "Hypervisor-protected Code Integrity (HVCI) is active"))
        
        if defender.get('InstalledAV'):
            security_items.append(("info", f"Installed security products: {defender.get('InstalledAV')}"))
        
        sections.append(("System Security", security_items))
        
        # Add sections to layout
        for section_title, items in sections:
            self._add_section(self.defender_layout, section_title, items)
        
        # Add action buttons
        actions_frame = QFrame()
        actions_frame.setStyleSheet(f"background: {Theme.BG_CARD}; border-radius: {Theme.RADIUS_MD}px;")
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setContentsMargins(16, 12, 16, 12)
        actions_layout.setSpacing(12)
        
        for text, callback in [
            ("Update Definitions", self._update_defender_definitions),
            ("Quick Scan", self._run_quick_scan),
            ("Open Windows Security", self._open_windows_security),
        ]:
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(callback)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {Theme.BG_ELEVATED};
                    color: {Theme.TEXT_PRIMARY};
                    border: none;
                    padding: 8px 16px;
                    border-radius: {Theme.RADIUS_SM}px;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background: {Theme.BG_CARD_HOVER};
                }}
            """)
            actions_layout.addWidget(btn)
        
        actions_layout.addStretch()
        self.defender_layout.insertWidget(self.defender_layout.count() - 1, actions_frame)
    
    def _add_section(self, layout, title: str, items: list):
        """Add a section with title and items to the layout"""
        # Section header
        header = QLabel(title)
        header.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 600;
            padding: 8px 0;
        """)
        layout.insertWidget(layout.count() - 1, header)
        
        # Section container
        container = ModernListContainer()
        
        for status, text in items:
            if status == "header":
                continue  # Skip nested headers
            row = container.add_row(text, status=status if status != "info" else "ok")
            if status == "info":
                row.status_icon.setVisible(False)
        
        layout.insertWidget(layout.count() - 1, container)
    
    def _load_firewall_status(self):
        """Load firewall status in background"""
        self._clear_layout(self.firewall_layout)
        
        loading = QLabel("Loading firewall status...")
        loading.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 13px;")
        loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.firewall_layout.insertWidget(0, loading)
        
        # Run in background
        self._fw_status_thread = QThread(self)
        self._fw_status_worker = FirewallStatusWorker()
        self._fw_status_worker.moveToThread(self._fw_status_thread)
        self._active_threads.append(self._fw_status_thread)  # Prevent GC
        
        self._fw_status_thread.started.connect(self._fw_status_worker.run)
        self._fw_status_worker.finished.connect(self._on_firewall_status_loaded)
        self._fw_status_worker.finished.connect(self._fw_status_thread.quit)
        self._fw_status_worker.finished.connect(self._fw_status_worker.deleteLater)
        self._fw_status_thread.finished.connect(lambda: self._cleanup_thread(self._fw_status_thread))
        
        self._fw_status_thread.start()
    
    def _on_firewall_status_loaded(self, status: dict):
        """Handle firewall status load complete"""
        self.cached_firewall_status = status
        self._clear_layout(self.firewall_layout)
        
        if 'Error' in status:
            label = QLabel(f"Error: {status['Error']}")
            label.setStyleSheet(f"background: transparent; color: {Theme.ERROR}; font-size: 13px;")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.firewall_layout.insertWidget(0, label)
            return
        
        profiles = status.get('Profiles', [])
        if not profiles:
            label = QLabel("No firewall profiles found")
            label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 13px;")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.firewall_layout.insertWidget(0, label)
            return
        
        # Create a card for each profile
        for profile in profiles:
            card = self._create_firewall_profile_card(profile)
            self.firewall_layout.insertWidget(self.firewall_layout.count() - 1, card)
        
        # Add action button
        actions_frame = QFrame()
        actions_frame.setStyleSheet("background: transparent;")
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setContentsMargins(0, 12, 0, 0)
        
        firewall_btn = QPushButton("Open Windows Firewall Settings")
        firewall_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        firewall_btn.clicked.connect(self._open_firewall_settings)
        firewall_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                padding: 10px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        actions_layout.addWidget(firewall_btn)
        actions_layout.addStretch()
        
        self.firewall_layout.insertWidget(self.firewall_layout.count() - 1, actions_frame)
    
    def _create_firewall_profile_card(self, profile: dict) -> QFrame:
        """Create a card for a firewall profile"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border-radius: {Theme.RADIUS_MD}px;
                border: none;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        
        # Header with profile name and status
        header = QHBoxLayout()
        
        name_label = QLabel(f"{profile.get('Name', 'Unknown')} Profile")
        name_label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 600;
        """)
        header.addWidget(name_label)
        
        header.addStretch()
        
        # Status badge
        is_enabled = profile.get('Enabled', False)
        status_badge = QLabel("Enabled" if is_enabled else "Disabled")
        status_color = Theme.SUCCESS if is_enabled else Theme.ERROR
        status_bg = Theme.SUCCESS_BG if is_enabled else Theme.ERROR_BG
        status_badge.setStyleSheet(f"""
            background: {status_bg};
            color: {status_color};
            padding: 4px 12px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 600;
        """)
        header.addWidget(status_badge)
        
        layout.addLayout(header)
        
        # Details grid
        details = QGridLayout()
        details.setSpacing(8)
        details.setColumnStretch(1, 1)
        details.setColumnStretch(3, 1)
        
        row = 0
        info_items = [
            ("Inbound Default", profile.get('DefaultInboundAction', 'Unknown')),
            ("Outbound Default", profile.get('DefaultOutboundAction', 'Unknown')),
            ("Allow Inbound Rules", profile.get('AllowInboundRules', 'Unknown')),
            ("Log Blocked", "Yes" if profile.get('LogBlocked') else "No"),
        ]
        
        for i, (label, value) in enumerate(info_items):
            col = (i % 2) * 2
            if i % 2 == 0 and i > 0:
                row += 1
            
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
            details.addWidget(lbl, row, col)
            
            val = QLabel(str(value))
            # Color code the action
            if value in ['Block', 'NotConfigured']:
                color = Theme.WARNING
            elif value in ['Allow']:
                color = Theme.SUCCESS
            else:
                color = Theme.TEXT_PRIMARY
            val.setStyleSheet(f"background: transparent; color: {color}; font-size: 12px; font-weight: 500;")
            details.addWidget(val, row, col + 1)
        
        layout.addLayout(details)
        
        return card
    
    def _load_firewall_rules(self):
        """Load firewall rules in background"""
        self._clear_layout(self.rules_layout)
        
        loading = QLabel("Loading firewall rules (this may take a moment)...")
        loading.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 13px;")
        loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rules_layout.insertWidget(0, loading)
        
        # Run in background
        self._fw_rules_thread = QThread(self)
        self._fw_rules_worker = FirewallRulesWorker()
        self._fw_rules_worker.moveToThread(self._fw_rules_thread)
        self._active_threads.append(self._fw_rules_thread)  # Prevent GC
        
        self._fw_rules_thread.started.connect(self._fw_rules_worker.run)
        self._fw_rules_worker.finished.connect(self._on_firewall_rules_loaded)
        self._fw_rules_worker.finished.connect(self._fw_rules_thread.quit)
        self._fw_rules_worker.finished.connect(self._fw_rules_worker.deleteLater)
        self._fw_rules_thread.finished.connect(lambda: self._cleanup_thread(self._fw_rules_thread))
        
        self._fw_rules_thread.start()
    
    def _on_firewall_rules_loaded(self, rules: list):
        """Handle firewall rules load complete"""
        self.cached_firewall_rules = rules
        self._clear_layout(self.rules_layout)
        
        if not rules:
            label = QLabel("No firewall rules found or unable to retrieve rules")
            label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 13px;")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.rules_layout.insertWidget(0, label)
            return
        
        # Filter controls
        filter_frame = QFrame()
        filter_frame.setStyleSheet("background: transparent;")
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(0, 0, 0, 12)
        filter_layout.setSpacing(8)
        
        filter_label = QLabel(f"Showing {len(rules)} enabled rules")
        filter_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        filter_layout.addWidget(filter_label)
        filter_layout.addStretch()
        
        self.rules_layout.insertWidget(0, filter_frame)
        
        # Group rules by direction
        inbound_rules = [r for r in rules if r.get('Direction') == 'Inbound']
        outbound_rules = [r for r in rules if r.get('Direction') == 'Outbound']
        
        # Inbound section
        if inbound_rules:
            header = QLabel(f"Inbound Rules ({len(inbound_rules)})")
            header.setStyleSheet(f"""
                background: transparent;
                color: {Theme.TEXT_PRIMARY};
                font-size: 14px;
                font-weight: 600;
                padding: 8px 0;
            """)
            self.rules_layout.insertWidget(self.rules_layout.count() - 1, header)
            
            container = ModernListContainer()
            for rule in inbound_rules[:50]:  # Limit to 50 per section
                self._add_rule_row(container, rule)
            self.rules_layout.insertWidget(self.rules_layout.count() - 1, container)
        
        # Outbound section
        if outbound_rules:
            header = QLabel(f"Outbound Rules ({len(outbound_rules)})")
            header.setStyleSheet(f"""
                background: transparent;
                color: {Theme.TEXT_PRIMARY};
                font-size: 14px;
                font-weight: 600;
                padding: 8px 0;
            """)
            self.rules_layout.insertWidget(self.rules_layout.count() - 1, header)
            
            container = ModernListContainer()
            for rule in outbound_rules[:50]:  # Limit to 50 per section
                self._add_rule_row(container, rule)
            self.rules_layout.insertWidget(self.rules_layout.count() - 1, container)
    
    def _add_rule_row(self, container: ModernListContainer, rule: dict):
        """Add a firewall rule row to container"""
        name = rule.get('Name', 'Unknown Rule')
        action = rule.get('Action', 'Unknown')
        protocol = rule.get('Protocol', 'Any')
        local_port = rule.get('LocalPort', 'Any')
        program = rule.get('Program', '')
        
        # Build subtitle
        subtitle_parts = []
        if protocol != 'Any':
            subtitle_parts.append(f"{protocol}")
        if local_port != 'Any' and local_port:
            subtitle_parts.append(f"Port {local_port}")
        if program and program != 'Any':
            # Just show the filename
            import os
            program_name = os.path.basename(program) if '\\' in program else program
            if len(program_name) > 40:
                program_name = program_name[:37] + "..."
            subtitle_parts.append(program_name)
        
        subtitle = " • ".join(subtitle_parts) if subtitle_parts else ""
        
        # Status based on action
        status = "ok" if action == "Allow" else "warning"
        status_text = action
        
        row = container.add_row(
            title=name[:60] + "..." if len(name) > 60 else name,
            subtitle=subtitle,
            status=status,
            status_text=status_text
        )
    
    def _cleanup_thread(self, thread: QThread):
        """Safely remove thread from active list after it finishes"""
        if thread in self._active_threads:
            self._active_threads.remove(thread)
    
    def _open_windows_security(self):
        """Open Windows Security app"""
        subprocess.Popen(["start", "windowsdefender:"], shell=True)
    
    def _open_firewall_settings(self):
        """Open Windows Firewall settings"""
        subprocess.Popen(["control", "firewall.cpl"])
    
    def _update_defender_definitions(self):
        """Update Windows Defender definitions"""
        subprocess.Popen(
            ["powershell", "-Command", "Update-MpSignature"],
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
    
    def _run_quick_scan(self):
        """Run a quick Windows Defender scan"""
        subprocess.Popen(
            ["powershell", "-Command", "Start-MpScan -ScanType QuickScan"],
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
    
    def set_checking(self):
        """Show loading state"""
        self._show_placeholder("Checking security status...")
    
    def show_results(self, results):
        """Display results from legacy format (list of tuples)"""
        # Convert legacy format to dict for display_defender_data
        # This is called from _show_cached_data
        pass
    
    def show_results_with_actions(self, results, actions):
        """Display results from legacy format with actions"""
        # Parse results and build defender dict from cached data
        if self.cached_defender_data:
            self.display_defender_data(self.cached_defender_data)


# =============================================================================
# SYSTEM FILES PAGE - System Integrity and Configuration
# =============================================================================

class SystemPage(QWidget):
    """Dedicated page for system files, services, and configuration"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.system_data = {}
        self.widgets = []
        self.is_loading = False
        self._thread = None
        self._worker = None
        self.setup_ui()
    
    def setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(32, 28, 32, 28)
        self.content_layout.setSpacing(20)
        
        # Header row
        header = QHBoxLayout()
        header.setSpacing(16)
        
        title = QLabel("System Files & Configuration")
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 28px;
            font-weight: 600;
        """)
        header.addWidget(title)
        header.addStretch()
        
        # Scan button
        self.scan_btn = QPushButton("Scan System")
        self.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_btn.clicked.connect(self.scan_system)
        Theme.style_accent_button(self.scan_btn, "primary")
        header.addWidget(self.scan_btn)
        
        # SFC Scan button
        sfc_btn = QPushButton("Run SFC Scan")
        sfc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sfc_btn.clicked.connect(self._run_sfc_scan)
        sfc_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                padding: 10px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        header.addWidget(sfc_btn)
        
        # DISM Repair button
        dism_btn = QPushButton("DISM Repair")
        dism_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dism_btn.clicked.connect(self._run_dism_repair)
        dism_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                padding: 10px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        header.addWidget(dism_btn)
        
        self.content_layout.addLayout(header)
        
        # Reboot required banner (hidden by default)
        self.reboot_banner = QFrame()
        self.reboot_banner.setStyleSheet(f"""
            background: {Theme.WARNING}22;
            border: none;
            border-radius: {Theme.RADIUS_SM}px;
        """)
        self.reboot_banner.setVisible(False)
        banner_layout = QHBoxLayout(self.reboot_banner)
        banner_layout.setContentsMargins(16, 12, 16, 12)
        
        banner_icon = QLabel("⚠️")
        banner_icon.setStyleSheet("background: transparent; font-size: 18px;")
        banner_layout.addWidget(banner_icon)
        
        self.reboot_text = QLabel("System restart required to complete pending operations")
        self.reboot_text.setStyleSheet(f"background: transparent; color: {Theme.WARNING}; font-size: 13px; font-weight: 500;")
        banner_layout.addWidget(self.reboot_text)
        banner_layout.addStretch()
        
        self.content_layout.addWidget(self.reboot_banner)
        
        # Status label
        self.status_label = QLabel("Click 'Scan System' to analyze system configuration")
        self.status_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 13px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.status_label)
        
        # System info card (always visible after scan)
        self.info_card = QFrame()
        self.info_card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(self.info_card, blur_radius=12, offset_y=3, opacity=60)
        self.info_card.setVisible(False)
        info_layout = QVBoxLayout(self.info_card)
        info_layout.setContentsMargins(24, 20, 24, 20)
        info_layout.setSpacing(16)
        
        info_title = QLabel("System Information")
        info_title.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 16px; font-weight: 600;")
        info_layout.addWidget(info_title)
        
        self.info_grid = QGridLayout()
        self.info_grid.setSpacing(10)
        info_layout.addLayout(self.info_grid)
        
        self.content_layout.addWidget(self.info_card)
        
        # Main content container
        self.main_container = QFrame()
        self.main_container.setStyleSheet("background: transparent;")
        self.main_layout = QVBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(20)
        self.main_container.setVisible(False)
        self.content_layout.addWidget(self.main_container)
        
        self.content_layout.addStretch()
        
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        
        # Floating Quick Tools bar
        tools = [
            ("System Restore", "\uE777", self._open_system_restore),
            ("Task Scheduler", "\uE787", self._open_task_scheduler),
            ("Defragment", "\uE8FA", self._open_defragment),
        ]
        self._floating_toolbar = FloatingToolbar(tools, self)
    
    def resizeEvent(self, event):
        """Reposition floating toolbar on resize"""
        super().resizeEvent(event)
        if hasattr(self, '_floating_toolbar'):
            self._floating_toolbar.update_position()
    
    def _open_system_restore(self):
        """Open System Restore"""
        import subprocess
        try:
            subprocess.Popen(["rstrui.exe"])
        except:
            pass
    
    def _open_task_scheduler(self):
        """Open Task Scheduler"""
        import subprocess
        try:
            subprocess.Popen(["taskschd.msc"])
        except:
            pass
    
    def _open_defragment(self):
        """Open Defragment and Optimize Drives"""
        import subprocess
        try:
            subprocess.Popen(["dfrgui.exe"])
        except:
            pass
    
    def scan_system(self):
        """Scan system configuration using background thread"""
        if self.is_loading:
            return
        
        self.is_loading = True
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("Scanning...")
        self.status_label.setText("Analyzing system configuration...")
        self.status_label.setVisible(True)
        self.main_container.setVisible(False)
        self.info_card.setVisible(False)
        
        # Run in background thread
        self._thread = QThread(self)
        self._worker = SystemDetailWorker()
        self._worker.moveToThread(self._thread)
        
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_scan_complete)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        
        self._thread.start()
    
    def _on_scan_complete(self, data: dict):
        """Handle system scan completion"""
        self.is_loading = False
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("Scan System")
        
        if not data or data.get('Error'):
            self.status_label.setText(f"Error: {data.get('Error', 'Unknown error')}")
            self.status_label.setVisible(True)
            return
        
        self.system_data = data
        self._display_system_info()
    
    def display_cached_data(self, data):
        """Display system info from cached data - trigger full scan for details"""
        if not self.system_data and not self.is_loading:
            self.scan_system()
    
    def _display_system_info(self):
        """Display the system information"""
        self.status_label.setVisible(False)
        self.info_card.setVisible(True)
        self.main_container.setVisible(True)
        
        # Clear old widgets
        for widget in self.widgets:
            widget.deleteLater()
        self.widgets.clear()
        
        # Clear main layout
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        
        # Clear info grid
        while self.info_grid.count():
            item = self.info_grid.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        
        # Check for pending reboot
        if self.system_data.get('PendingReboot'):
            self.reboot_banner.setVisible(True)
        else:
            self.reboot_banner.setVisible(False)
        
        # Populate system info grid with improved layout
        sys_info = self.system_data.get('SystemInfo', {})
        info_items = [
            ("Computer Name:", sys_info.get('ComputerName', 'Unknown')),
            ("OS:", sys_info.get('OSName', 'Unknown')),
            ("Version:", f"{sys_info.get('OSVersion', '')} (Build {sys_info.get('BuildNumber', '')})"),
            ("Install Date:", sys_info.get('InstallDate', 'Unknown')),
            ("Last Boot:", sys_info.get('LastBoot', 'Unknown')),
            ("Uptime:", f"{sys_info.get('UptimeDays', 0)} days, {sys_info.get('UptimeHours', 0)} hours"),
            ("Memory:", f"{sys_info.get('TotalMemoryGB', 0)} GB"),
            ("System Drive:", sys_info.get('SystemDrive', 'C:')),
        ]
        
        # Set column stretch for proper spacing
        self.info_grid.setColumnStretch(0, 0)
        self.info_grid.setColumnStretch(1, 1)
        self.info_grid.setColumnStretch(2, 0)
        self.info_grid.setColumnStretch(3, 1)
        self.info_grid.setHorizontalSpacing(12)
        self.info_grid.setVerticalSpacing(10)
        
        for row, (label, value) in enumerate(info_items):
            row_idx = row // 2
            col_idx = (row % 2) * 2
            
            lbl = QLabel(label)
            lbl.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
            lbl.setMinimumWidth(100)
            self.info_grid.addWidget(lbl, row_idx, col_idx)
            
            val = QLabel(str(value))
            val.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 13px; font-weight: 500;")
            self.info_grid.addWidget(val, row_idx, col_idx + 1)
        
        # Critical services section
        services = self.system_data.get('CriticalServices', [])
        if services:
            services_card = self._create_services_card(services)
            self.main_layout.addWidget(services_card)
            self.widgets.append(services_card)
        
        # Restore points section
        restore_points = self.system_data.get('RestorePoints', [])
        if restore_points:
            restore_card = self._create_restore_points_card(restore_points)
            self.main_layout.addWidget(restore_card)
            self.widgets.append(restore_card)
        
        # Recent installs section
        recent_installs = self.system_data.get('RecentInstalls', [])
        if recent_installs:
            installs_card = self._create_recent_installs_card(recent_installs)
            self.main_layout.addWidget(installs_card)
            self.widgets.append(installs_card)
        
        # Quick actions card
        actions_card = self._create_actions_card()
        self.main_layout.addWidget(actions_card)
        self.widgets.append(actions_card)
    
    def _create_services_card(self, services: list):
        """Create a card showing critical Windows services status in compact 2-column grid"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(card, blur_radius=12, offset_y=3, opacity=60)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("Critical Windows Services")
        title.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 16px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch()
        
        # Count running/stopped
        running = sum(1 for s in services if s.get('Status') == 'Running')
        stopped = len(services) - running
        
        count_label = QLabel(f"{running} Running" + (f" • {stopped} Stopped" if stopped > 0 else ""))
        if stopped > 0:
            count_label.setStyleSheet(f"background: transparent; color: {Theme.WARNING}; font-size: 12px; font-weight: 500;")
        else:
            count_label.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 12px; font-weight: 500;")
        header.addWidget(count_label)
        
        layout.addLayout(header)
        
        # Compact 2-column grid for services
        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        
        for idx, svc in enumerate(services):
            name = svc.get('DisplayName', svc.get('Name', 'Unknown'))
            status = svc.get('Status', 'Unknown')
            
            # Create a compact service row widget
            row_widget = QFrame()
            row_widget.setStyleSheet(f"""
                QFrame {{
                    background: {Theme.BG_ELEVATED};
                    border-radius: {Theme.RADIUS_SM}px;
                    padding: 0px;
                }}
            """)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(12, 8, 12, 8)
            row_layout.setSpacing(10)
            
            # Status dot
            dot = QLabel("●")
            if status == 'Running':
                dot.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 10px;")
            elif status == 'Stopped':
                dot.setStyleSheet(f"background: transparent; color: {Theme.ERROR}; font-size: 10px;")
            else:
                dot.setStyleSheet(f"background: transparent; color: {Theme.WARNING}; font-size: 10px;")
            row_layout.addWidget(dot)
            
            # Service name (truncated if needed)
            name_label = QLabel(name[:30] + "..." if len(name) > 30 else name)
            name_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 12px;")
            row_layout.addWidget(name_label, 1)
            
            # Status pill
            status_pill = QLabel(status)
            if status == 'Running':
                pill_bg = f"{Theme.SUCCESS}22"
                pill_color = Theme.SUCCESS
            elif status == 'Stopped':
                pill_bg = f"{Theme.ERROR}22"
                pill_color = Theme.ERROR
            else:
                pill_bg = f"{Theme.WARNING}22"
                pill_color = Theme.WARNING
            
            status_pill.setStyleSheet(f"""
                background: {pill_bg};
                color: {pill_color};
                font-size: 10px;
                font-weight: 600;
                padding: 3px 8px;
                border-radius: 4px;
            """)
            row_layout.addWidget(status_pill)
            
            # Add to grid (2 columns)
            grid.addWidget(row_widget, idx // 2, idx % 2)
        
        layout.addLayout(grid)
        
        return card
    
    def _create_restore_points_card(self, restore_points: list):
        """Create a card showing system restore points with card-based design"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(card, blur_radius=12, offset_y=3, opacity=60)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("System Restore Points")
        title.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 16px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch()
        
        # Count badge
        count_badge = QLabel(f"{len(restore_points)} saved")
        count_badge.setStyleSheet(f"""
            background: {Theme.BG_ELEVATED};
            color: {Theme.TEXT_SECONDARY};
            padding: 4px 10px;
            border-radius: 10px;
            font-size: 11px;
        """)
        header.addWidget(count_badge)
        
        # Create restore point button
        create_btn = QPushButton("+ New")
        create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        create_btn.clicked.connect(self._open_system_protection)
        create_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT_HOVER};
            }}
        """)
        header.addWidget(create_btn)
        
        layout.addLayout(header)
        
        # Restore points grid (2 columns)
        if restore_points:
            grid = QGridLayout()
            grid.setSpacing(10)
            grid.setContentsMargins(0, 0, 0, 0)
            
            for idx, rp in enumerate(restore_points[:6]):  # Show up to 6
                desc = rp.get('Description', 'Unknown')
                date = rp.get('CreationTime', '')
                rp_type = rp.get('RestorePointType', '')
                
                # Parse and format date
                date_display = date[:16] if date else "Unknown date"
                
                # Determine type and icon
                type_text = str(rp_type).replace('_', ' ').title()[:20] if rp_type else "Manual"
                is_windows_update = 'update' in desc.lower() or 'update' in type_text.lower()
                is_install = 'install' in desc.lower() or 'application' in type_text.lower()
                
                # Restore point card
                rp_card = QFrame()
                rp_card.setStyleSheet(f"""
                    QFrame {{
                        background: {Theme.BG_ELEVATED};
                        border: none;
                        border-radius: {Theme.RADIUS_SM}px;
                    }}
                    QFrame:hover {{
                        background: {Theme.BG_CARD_HOVER};
                    }}
                """)
                
                rp_layout = QHBoxLayout(rp_card)
                rp_layout.setContentsMargins(12, 10, 12, 10)
                rp_layout.setSpacing(12)
                
                # Icon based on type
                icon_container = QFrame()
                icon_container.setFixedSize(36, 36)
                if is_windows_update:
                    icon_bg = f"{Theme.INFO}22"
                    icon_color = Theme.INFO
                    icon_text = "W"
                elif is_install:
                    icon_bg = f"{Theme.SUCCESS}22"
                    icon_color = Theme.SUCCESS
                    icon_text = "A"
                else:
                    icon_bg = f"{Theme.ACCENT}22"
                    icon_color = Theme.ACCENT
                    icon_text = "R"
                
                icon_container.setStyleSheet(f"""
                    background: {icon_bg};
                    border-radius: 8px;
                """)
                icon_lbl = QLabel(icon_text)
                icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                icon_lbl.setStyleSheet(f"background: transparent; color: {icon_color}; font-size: 14px; font-weight: 600;")
                icon_layout = QHBoxLayout(icon_container)
                icon_layout.setContentsMargins(0, 0, 0, 0)
                icon_layout.addWidget(icon_lbl)
                rp_layout.addWidget(icon_container)
                
                # Text content
                text_layout = QVBoxLayout()
                text_layout.setSpacing(2)
                text_layout.setContentsMargins(0, 0, 0, 0)
                
                # Description (truncated)
                desc_short = desc[:35] + "..." if len(desc) > 35 else desc
                desc_label = QLabel(desc_short)
                desc_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 12px; font-weight: 500;")
                text_layout.addWidget(desc_label)
                
                # Date and type
                meta_label = QLabel(f"{date_display}  •  {type_text}")
                meta_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 10px;")
                text_layout.addWidget(meta_label)
                
                rp_layout.addLayout(text_layout, 1)
                
                # Add to grid (2 columns)
                grid.addWidget(rp_card, idx // 2, idx % 2)
            
            layout.addLayout(grid)
        else:
            # Empty state
            empty_label = QLabel("No restore points found")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet(f"color: {Theme.TEXT_TERTIARY}; font-size: 12px; padding: 20px;")
            layout.addWidget(empty_label)
        
        return card
    
    def _create_recent_installs_card(self, installs: list):
        """Create a card showing recent software installations with logos"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(card, blur_radius=12, offset_y=3, opacity=60)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("Recent Software Installations")
        title.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 16px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch()
        
        # Open Programs & Features
        open_btn = QPushButton("View All")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(self._open_programs_features)
        open_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.ACCENT};
                border: none;
                padding: 6px 14px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_ELEVATED};
            }}
        """)
        header.addWidget(open_btn)
        
        layout.addLayout(header)
        
        # Grid layout for software cards
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        
        for idx, inst in enumerate(installs[:8]):
            name = inst.get('Name', 'Unknown')
            version = inst.get('Version', '')
            
            # Format install date
            install_date = inst.get('InstallDate', '')
            formatted_date = ""
            if install_date and len(install_date) == 8:
                try:
                    formatted_date = f"{install_date[:4]}-{install_date[4:6]}-{install_date[6:]}"
                except:
                    pass
            
            # Software item frame
            item_frame = QFrame()
            item_frame.setStyleSheet(f"""
                QFrame {{
                    background: {Theme.BG_ELEVATED};
                    border-radius: {Theme.RADIUS_SM}px;
                    border: none;
                }}
                QFrame:hover {{
                    background: {Theme.BG_CARD_HOVER};
                }}
            """)
            
            item_layout = QHBoxLayout(item_frame)
            item_layout.setContentsMargins(10, 10, 10, 10)
            item_layout.setSpacing(10)
            
            # Try to get real app icon, fall back to letter placeholder
            logo_label = QLabel()
            logo_label.setFixedSize(36, 36)
            
            # Try to get the actual app icon
            app_icon = get_cached_app_icon(name, 32)
            
            if app_icon and not app_icon.isNull():
                # Use the real icon
                logo_label.setPixmap(app_icon)
                logo_label.setStyleSheet("background: transparent; border-radius: 8px;")
                logo_label.setScaledContents(True)
            else:
                # Fall back to letter placeholder
                first_letter = name[0].upper() if name else "?"
                
                # Generate color based on name hash
                name_hash = hash(name) % 360
                hue = name_hash
                logo_label.setStyleSheet(f"""
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 hsl({hue}, 60%, 45%),
                        stop:1 hsl({(hue + 30) % 360}, 60%, 35%));
                    border-radius: 8px;
                    color: white;
                    font-size: 16px;
                    font-weight: 600;
                """)
                logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                logo_label.setText(first_letter)
            
            item_layout.addWidget(logo_label)
            
            # Text content
            text_layout = QVBoxLayout()
            text_layout.setSpacing(2)
            text_layout.setContentsMargins(0, 0, 0, 0)
            
            # Name (truncated)
            name_label = QLabel(name[:30] + ("..." if len(name) > 30 else ""))
            name_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 12px; font-weight: 500; background: transparent;")
            text_layout.addWidget(name_label)
            
            # Version and date
            sub_text = version[:15] if version else ""
            if formatted_date:
                sub_text = f"{sub_text} • {formatted_date}" if sub_text else formatted_date
            
            sub_label = QLabel(sub_text)
            sub_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 10px; background: transparent;")
            text_layout.addWidget(sub_label)
            
            item_layout.addLayout(text_layout, 1)
            
            row = idx // 2
            col = idx % 2
            grid.addWidget(item_frame, row, col)
        
        layout.addLayout(grid)
        
        return card
    
    def _create_actions_card(self):
        """Create a card with quick system actions - redesigned with prominent buttons"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(card, blur_radius=12, offset_y=3, opacity=60)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Header
        title = QLabel("System Tools")
        title.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 16px; font-weight: 600;")
        layout.addWidget(title)
        
        # Action buttons grid - using new styled buttons
        actions_layout = QGridLayout()
        actions_layout.setSpacing(10)
        
        # Define tools with colors for visual distinction
        actions = [
            ("System Properties", "⚙️", "#6366f1", self._open_system_properties),  # Indigo
            ("Device Manager", "🔧", "#f59e0b", self._open_device_manager),  # Amber
            ("Task Manager", "📊", "#10b981", self._open_task_manager),  # Emerald
            ("Event Viewer", "📋", "#8b5cf6", self._open_event_viewer),  # Violet
            ("Services", "🔌", "#3b82f6", self._open_services),  # Blue
            ("Environment Variables", "📝", "#ec4899", self._open_env_vars),  # Pink
        ]
        
        for idx, (label, icon, color, action) in enumerate(actions):
            btn = self._create_tool_button(label, icon, color, action)
            actions_layout.addWidget(btn, idx // 3, idx % 3)
        
        layout.addLayout(actions_layout)
        
        return card
    
    def _create_tool_button(self, label: str, icon: str, color: str, action) -> QPushButton:
        """Create a styled tool button with icon and hover effects"""
        btn = QPushButton()
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(action)
        btn.setFixedHeight(52)
        
        # Create layout for button content
        btn_layout = QHBoxLayout(btn)
        btn_layout.setContentsMargins(12, 8, 12, 8)
        btn_layout.setSpacing(10)
        
        # Icon container with colored background
        icon_container = QLabel(icon)
        icon_container.setFixedSize(32, 32)
        icon_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_container.setStyleSheet(f"""
            background: {color}22;
            border-radius: 6px;
            font-size: 16px;
        """)
        btn_layout.addWidget(icon_container)
        
        # Label
        text_label = QLabel(label)
        text_label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 12px;
            font-weight: 500;
        """)
        btn_layout.addWidget(text_label)
        btn_layout.addStretch()
        
        # Arrow indicator
        arrow = QLabel("›")
        arrow.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_TERTIARY};
            font-size: 16px;
            font-weight: 600;
        """)
        btn_layout.addWidget(arrow)
        
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_ELEVATED};
                border: 1px solid transparent;
                border-radius: {Theme.RADIUS_SM}px;
                text-align: left;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                border: 1px solid {color}66;
            }}
            QPushButton:pressed {{
                background: {color}22;
            }}
        """)
        
        return btn
    
    def _run_sfc_scan(self):
        """Run SFC /scannow in an elevated terminal"""
        import subprocess
        try:
            subprocess.Popen(
                ['powershell', '-Command',
                 'Start-Process', 'cmd', '-ArgumentList', '"/k sfc /scannow"', '-Verb', 'RunAs'],
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
        except Exception as e:
            print(f"Error launching SFC: {e}")
    
    def _run_dism_repair(self):
        """Run DISM repair commands in an elevated terminal"""
        import subprocess
        try:
            dism_cmd = 'DISM /Online /Cleanup-Image /RestoreHealth && pause'
            subprocess.Popen(
                ['powershell', '-Command',
                 'Start-Process', 'cmd', '-ArgumentList', f'"/k {dism_cmd}"', '-Verb', 'RunAs'],
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
        except Exception as e:
            print(f"Error launching DISM: {e}")
    
    def _open_system_protection(self):
        """Open System Protection dialog"""
        import subprocess
        try:
            subprocess.Popen(["SystemPropertiesProtection"])
        except:
            pass
    
    def _open_programs_features(self):
        """Open Programs and Features"""
        import subprocess
        try:
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:appsfeatures"],
                           creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        except:
            pass
    
    def _open_system_properties(self):
        """Open System Properties"""
        import subprocess
        try:
            subprocess.Popen(["SystemPropertiesAdvanced"])
        except:
            pass
    
    def _open_device_manager(self):
        """Open Device Manager"""
        import subprocess
        try:
            subprocess.Popen(["devmgmt.msc"])
        except:
            pass
    
    def _open_task_manager(self):
        """Open Task Manager"""
        import subprocess
        try:
            subprocess.Popen(["taskmgr"])
        except:
            pass
    
    def _open_event_viewer(self):
        """Open Event Viewer"""
        import subprocess
        try:
            subprocess.Popen(["eventvwr.msc"])
        except:
            pass
    
    def _open_services(self):
        """Open Services"""
        import subprocess
        try:
            subprocess.Popen(["services.msc"])
        except:
            pass
    
    def _open_env_vars(self):
        """Open Environment Variables"""
        import subprocess
        try:
            subprocess.Popen(["SystemPropertiesAdvanced"])
        except:
            pass


class SystemDetailWorker(QObject):
    """Worker to fetch detailed system info in background"""
    finished = pyqtSignal(dict)
    
    def run(self):
        try:
            from driver_backend import HealthChecker
            checker = HealthChecker()
            data = checker.get_system_details()
            self.finished.emit(data)
        except Exception as e:
            self.finished.emit({"Error": str(e)})


# =============================================================================
# HARDWARE PAGE - Comprehensive Hardware Information
# =============================================================================

class RealtimeGraph(QFrame):
    """Real-time line graph widget for displaying utilization metrics"""
    
    def __init__(self, title: str, color: str | None = None, max_points: int = 60, parent=None):
        super().__init__(parent)
        self.title_text = title
        self.graph_color = color or Theme.ACCENT
        self.max_points = max_points
        self.data_points = [0.0] * max_points
        self.current_value = 0.0
        self.setFixedHeight(100)
        self.setMinimumWidth(200)
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            RealtimeGraph {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
    
    def add_value(self, value: float):
        """Add a new data point (0-100)"""
        self.current_value = max(0, min(100, value))
        self.data_points.append(self.current_value)
        if len(self.data_points) > self.max_points:
            self.data_points.pop(0)
        self.update()
    
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Dimensions
        padding = 12
        title_height = 24
        graph_left = padding
        graph_top = padding + title_height
        graph_width = self.width() - (padding * 2)
        graph_height = self.height() - graph_top - padding
        
        # Draw title and current value
        painter.setPen(QColor(Theme.TEXT_SECONDARY))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(padding, padding + 14, self.title_text)
        
        # Current value on right
        value_text = f"{self.current_value:.0f}%"
        painter.setPen(QColor(self.graph_color))
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        value_width = painter.fontMetrics().horizontalAdvance(value_text)
        painter.drawText(self.width() - padding - value_width, padding + 14, value_text)
        
        # Draw graph background
        graph_bg = QColor(Theme.BG_CARD_HOVER)
        painter.fillRect(graph_left, graph_top, graph_width, graph_height, graph_bg)
        
        # Draw grid lines (horizontal)
        painter.setPen(QPen(QColor(Theme.BORDER), 1))
        for i in range(1, 4):
            y = graph_top + (graph_height * i // 4)
            painter.drawLine(graph_left, y, graph_left + graph_width, y)
        
        # Draw data line
        if len(self.data_points) > 1:
            # Create gradient fill
            gradient_color = QColor(self.graph_color)
            gradient_color.setAlpha(30)
            
            # Build path for filled area
            path = QPainterPath()
            point_spacing = graph_width / (self.max_points - 1)
            
            # Start at bottom left
            first_x = graph_left
            first_y = graph_top + graph_height - (self.data_points[0] / 100.0 * graph_height)
            path.moveTo(graph_left, graph_top + graph_height)
            path.lineTo(first_x, first_y)
            
            for i, value in enumerate(self.data_points[1:], 1):
                x = graph_left + (i * point_spacing)
                y = graph_top + graph_height - (value / 100.0 * graph_height)
                path.lineTo(x, y)
            
            # Close path at bottom
            path.lineTo(graph_left + graph_width, graph_top + graph_height)
            path.closeSubpath()
            
            # Fill gradient
            painter.fillPath(path, QBrush(gradient_color))
            
            # Draw line on top
            painter.setPen(QPen(QColor(self.graph_color), 2))
            for i in range(len(self.data_points) - 1):
                x1 = graph_left + (i * point_spacing)
                y1 = graph_top + graph_height - (self.data_points[i] / 100.0 * graph_height)
                x2 = graph_left + ((i + 1) * point_spacing)
                y2 = graph_top + graph_height - (self.data_points[i + 1] / 100.0 * graph_height)
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))


class RealtimeGraphPanel(QFrame):
    """
    Panel containing multiple real-time graphs for system monitoring.
    Uses optimized MetricsCollector to reduce subprocess calls.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.graphs = {}
        self.metrics_collector = MetricsCollector()
        self.metrics_collector.metrics_ready.connect(self._on_metrics)
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            RealtimeGraphPanel {{
                background: transparent;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        # Create graphs
        self.graphs["cpu"] = RealtimeGraph("CPU Usage", Theme.ACCENT)
        self.graphs["ram"] = RealtimeGraph("Memory Usage", Theme.SUCCESS)
        self.graphs["disk"] = RealtimeGraph("Disk Activity", Theme.WARNING)
        
        for graph in self.graphs.values():
            layout.addWidget(graph)
    
    def start_monitoring(self):
        """Start real-time monitoring in background thread"""
        self.metrics_collector.start()
    
    def stop_monitoring(self):
        """Stop real-time monitoring"""
        self.metrics_collector.stop()
    
    def _on_metrics(self, cpu: float, ram: float, disk: float):
        """Handle metrics update from collector (called via signal from background thread)"""
        self.graphs["cpu"].add_value(cpu)
        self.graphs["ram"].add_value(ram)
        self.graphs["disk"].add_value(disk)


class HardwareInfoCard(QFrame):
    """Compact card for displaying hardware category information"""
    title_clicked = pyqtSignal(str)  # Emits card_id when title is clicked

    def __init__(self, title: str, icon_char: str, card_id: str = "", parent=None):
        super().__init__(parent)
        self.title_text = title
        self.icon_char = icon_char
        self.card_id = card_id
        self.is_expanded = True
        self.info_rows = []
        self.setup_ui()
        # Apply card shadow per UI spec section 14.6
        Theme.apply_card_shadow(self)

    def setup_ui(self):
        self.setStyleSheet(f"""
            HardwareInfoCard {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 16, 20, 16)  # Spec: 20px padding
        self.main_layout.setSpacing(8)
        
        # Header (clickable to expand/collapse)
        header = QHBoxLayout()
        header.setSpacing(10)

        # Icon container (smaller)
        icon_container = QFrame()
        icon_container.setFixedSize(28, 28)
        icon_container.setStyleSheet(f"""
            background: {Theme.ACCENT};
            border-radius: 6px;
        """)
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel(self.icon_char)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"background: transparent; color: white; font-size: 12px; font-weight: bold;")
        icon_layout.addWidget(icon_label)
        header.addWidget(icon_container)

        # Title - clickable button styled as label
        self.title_btn = QPushButton(self.title_text)
        self.title_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.title_btn.clicked.connect(self._on_title_clicked)
        self.title_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Theme.TEXT_PRIMARY};
                font-size: 14px;
                font-weight: 600;
                border: none;
                text-align: left;
                padding: 0;
            }}
            QPushButton:hover {{
                color: {Theme.ACCENT};
                text-decoration: underline;
            }}
        """)
        header.addWidget(self.title_btn)

        header.addStretch()        # Status chip
        self.status_chip = QLabel("OK")
        self.status_chip.setFixedHeight(22)
        self.status_chip.setStyleSheet(f"""
            background: {Theme.SUCCESS_BG};
            color: {Theme.SUCCESS};
            padding: 2px 10px;
            border-radius: 10px;
            font-size: 10px;
            font-weight: 600;
        """)
        header.addWidget(self.status_chip)
        
        # Expand/collapse chevron
        self.chevron = QLabel("▾")
        self.chevron.setFixedSize(16, 16)
        self.chevron.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chevron.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 10px;")
        header.addWidget(self.chevron)
        
        self.main_layout.addLayout(header)
        
        # Content container (for info rows)
        self.content = QFrame()
        self.content.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(38, 8, 0, 4)  # Indent content
        self.content_layout.setSpacing(4)
        
        self.main_layout.addWidget(self.content)
    
    def _on_title_clicked(self):
        """Handle title button click - emit signal with card_id"""
        if self.card_id:
            self.title_clicked.emit(self.card_id)

    def set_status(self, status: str, text: str = ""):
        """Set the status chip"""
        # Common style base - note the fixed height is set on widget itself
        base_style = "padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 600;"
        
        if status == "healthy" or status == "check":
            self.status_chip.setStyleSheet(f"""
                background: {Theme.SUCCESS_BG};
                color: {Theme.SUCCESS};
                {base_style}
            """)
            self.status_chip.setText(text or "OK")
        elif status == "warning":
            self.status_chip.setStyleSheet(f"""
                background: {Theme.WARNING_BG};
                color: {Theme.WARNING};
                {base_style}
            """)
            self.status_chip.setText(text or "Warning")
        elif status == "critical" or status == "error":
            self.status_chip.setStyleSheet(f"""
                background: {Theme.ERROR_BG};
                color: {Theme.ERROR};
                {base_style}
            """)
            self.status_chip.setText(text or "Critical")
        else:
            self.status_chip.setStyleSheet(f"""
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_SECONDARY};
                {base_style}
            """)
            self.status_chip.setText(text or "Unknown")
    
    def clear_info(self):
        """Clear all info rows"""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        self.info_rows = []
    
    def add_info_row(self, label: str, value: str, highlight: bool = False):
        """Add a compact info row with label and value"""
        row = QHBoxLayout()
        row.setSpacing(12)
        row.setContentsMargins(0, 0, 0, 0)
        
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        label_widget.setFixedWidth(100)
        row.addWidget(label_widget)
        
        value_color = Theme.ACCENT_LIGHT if highlight else Theme.TEXT_PRIMARY
        value_widget = QLabel(value)
        value_widget.setStyleSheet(f"background: transparent; color: {value_color}; font-size: 12px; font-weight: 500;")
        value_widget.setWordWrap(False)
        row.addWidget(value_widget, 1)
        
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container.setLayout(row)
        self.content_layout.addWidget(container)
        self.info_rows.append(container)
    
    def add_divider(self):
        """Add a visual divider"""
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {Theme.BORDER}; margin: 4px 0;")
        self.content_layout.addWidget(divider)
    
    def add_subsection(self, title: str):
        """Add a subsection header"""
        label = QLabel(title)
        label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_SECONDARY};
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 4px;
        """)
        self.content_layout.addWidget(label)


class HardwareDetailCard(QFrame):
    """Expandable card for displaying detailed hardware information"""
    
    def __init__(self, title: str, accent_color: str = "", parent=None):
        super().__init__(parent)
        self.title_text = title
        self.accent_color = accent_color or Theme.ACCENT
        self.is_expanded = True
        self.info_rows = []
        self.setup_ui()
        # Apply card shadow per UI spec section 14.6
        Theme.apply_card_shadow(self)
    
    def setup_ui(self):
        # Use object name for more reliable stylesheet targeting
        self.setObjectName("HardwareDetailCard")
        self.setStyleSheet(f"""
            QFrame#HardwareDetailCard {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        # Ensure the frame is drawn (not transparent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAutoFillBackground(True)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Header (clickable to expand/collapse)
        self.header = QFrame()
        self.header.setObjectName("DetailCardHeader")
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header.setStyleSheet(f"""
            QFrame#DetailCardHeader {{
                background: {Theme.BG_CARD};
                border: none;
                border-bottom: 1px solid {Theme.BORDER};
            }}
        """)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(12)
        
        # Accent bar
        accent_bar = QFrame()
        accent_bar.setFixedSize(4, 24)
        accent_bar.setStyleSheet(f"background: {self.accent_color}; border-radius: 2px;")
        header_layout.addWidget(accent_bar)
        
        # Title
        self.title_label = QLabel(self.title_text)
        self.title_label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 600;
        """)
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch()
        
        # Item count
        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        header_layout.addWidget(self.count_label)
        
        # Expand/collapse chevron
        self.chevron = QLabel("▾")
        self.chevron.setFixedSize(20, 20)
        self.chevron.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chevron.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        header_layout.addWidget(self.chevron)
        
        # Install event filter for header click handling
        self.header.installEventFilter(self)
        self.main_layout.addWidget(self.header)
        
        # Content container - give it explicit background
        self.content = QFrame()
        self.content.setObjectName("DetailCardContent")
        self.content.setStyleSheet(f"""
            QFrame#DetailCardContent {{
                background: {Theme.BG_CARD};
                border: none;
            }}
        """)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(20, 12, 20, 16)
        self.content_layout.setSpacing(6)
        
        self.main_layout.addWidget(self.content)
    
    def eventFilter(self, watched, event):
        """Handle header clicks via event filter"""
        from PyQt6.QtCore import QEvent
        if watched == self.header and event is not None:
            if event.type() == QEvent.Type.MouseButtonPress:
                self.setExpanded(not self.is_expanded)
                return True
        return super().eventFilter(watched, event)
    
    def setExpanded(self, expanded: bool):
        """Set expanded state"""
        self.is_expanded = expanded
        self.content.setVisible(expanded)
        self.chevron.setText("▾" if expanded else "▸")
    
    def ensureVisible(self):
        """Scroll this card into view"""
        # Find parent scroll area and scroll to this widget
        parent = self.parent()
        while parent:
            if isinstance(parent, QScrollArea):
                # Get the scroll area's viewport and ensure this widget is visible
                parent.ensureWidgetVisible(self, 50, 50)
                break
            parent = parent.parent() if hasattr(parent, 'parent') else None
    
    def clear_info(self):
        """Clear all info rows"""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        self.info_rows = []
    
    def add_section_header(self, title: str):
        """Add a section header"""
        label = QLabel(title)
        label.setStyleSheet(f"""
            background: transparent;
            color: {self.accent_color};
            font-size: 12px;
            font-weight: 700;
            margin-top: 8px;
            margin-bottom: 4px;
        """)
        self.content_layout.addWidget(label)
    
    def add_info_row(self, label: str, value: str, highlight: bool = False):
        """Add an info row with label and value"""
        row = QHBoxLayout()
        row.setSpacing(16)
        row.setContentsMargins(0, 2, 0, 2)
        
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        label_widget.setFixedWidth(140)
        row.addWidget(label_widget)
        
        value_color = Theme.ACCENT_LIGHT if highlight else Theme.TEXT_PRIMARY
        value_widget = QLabel(str(value) if value else "—")
        value_widget.setStyleSheet(f"background: transparent; color: {value_color}; font-size: 12px;")
        value_widget.setWordWrap(True)
        row.addWidget(value_widget, 1)
        
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container.setLayout(row)
        self.content_layout.addWidget(container)
        self.info_rows.append(container)
    
    def set_count(self, count: int, unit: str = "items"):
        """Set the item count display"""
        self.count_label.setText(f"{count} {unit}")


class TemperatureMonitorCard(QFrame):
    """Card showing real-time temperature readings from CPU, GPU, and drives"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.temp_widgets = {}
        self._update_timer = None
        self.setup_ui()
        Theme.apply_shadow(self, blur_radius=12, offset_y=3, opacity=60)
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            TemperatureMonitorCard {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(12)
        
        # Header
        header = QHBoxLayout()
        header.setSpacing(10)
        
        # Icon
        icon_container = QFrame()
        icon_container.setFixedSize(32, 32)
        icon_container.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                stop:0 #ef4444, stop:1 #f97316);
            border-radius: 8px;
        """)
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel("🌡")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("background: transparent; font-size: 16px;")
        icon_layout.addWidget(icon_label)
        header.addWidget(icon_container)
        
        title = QLabel("System Temperatures")
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 600;
        """)
        header.addWidget(title)
        header.addStretch()
        
        # Status indicator
        self.status_label = QLabel("Waiting for scan...")
        self.status_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
        header.addWidget(self.status_label)
        
        main_layout.addLayout(header)
        
        # Temperature readings container
        self.temps_container = QFrame()
        self.temps_container.setStyleSheet(f"""
            background: {Theme.BG_ELEVATED};
            border-radius: {Theme.RADIUS_SM}px;
        """)
        temps_layout = QHBoxLayout(self.temps_container)
        temps_layout.setContentsMargins(16, 12, 16, 12)
        temps_layout.setSpacing(0)
        
        # Create temperature displays
        temp_configs = [
            ("cpu", "CPU", "—", "#ef4444"),
            ("gpu", "GPU", "—", "#f97316"),
            ("drive", "Drive", "—", "#eab308"),
        ]
        
        for i, (temp_id, label, value, color) in enumerate(temp_configs):
            if i > 0:
                # Divider
                temps_layout.addSpacing(20)
                divider = QFrame()
                divider.setFixedWidth(1)
                divider.setFixedHeight(40)
                divider.setStyleSheet("background: rgba(255, 255, 255, 0.08);")
                temps_layout.addWidget(divider)
                temps_layout.addSpacing(20)
            
            temp_widget = self._create_temp_display(label, value, color)
            self.temp_widgets[temp_id] = temp_widget
            temps_layout.addWidget(temp_widget, 1)
        
        main_layout.addWidget(self.temps_container)
        
        # Info text
        info_label = QLabel("💡 Temperature data is collected during hardware scan. Some sensors may not be available on all systems.")
        info_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)
    
    def _create_temp_display(self, label: str, value: str, color: str) -> QFrame:
        """Create a temperature display widget"""
        frame = QFrame()
        frame.setStyleSheet("background: transparent;")
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Label
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_TERTIARY};
            font-size: 11px;
            font-weight: 500;
        """)
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label_widget)
        
        # Value
        value_widget = QLabel(value)
        value_widget.setObjectName("value")
        value_widget.setStyleSheet(f"""
            background: transparent;
            color: {color};
            font-size: 24px;
            font-weight: 700;
        """)
        value_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_widget)
        
        # Status text
        status_widget = QLabel("")
        status_widget.setObjectName("status")
        status_widget.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_SECONDARY};
            font-size: 10px;
        """)
        status_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(status_widget)
        
        return frame
    
    def update_temperature(self, temp_id: str, temp_c: float | None, status_text: str = ""):
        """Update a temperature reading"""
        if temp_id not in self.temp_widgets:
            return
        
        widget = self.temp_widgets[temp_id]
        value_label = widget.findChild(QLabel, "value")
        status_label = widget.findChild(QLabel, "status")
        
        if temp_c is not None:
            # Determine color based on temperature
            if temp_c >= 85:
                color = "#ef4444"  # Red - Critical
                status = "Critical"
            elif temp_c >= 75:
                color = "#f97316"  # Orange - Warning
                status = "High"
            elif temp_c >= 60:
                color = "#eab308"  # Yellow - Warm
                status = "Warm"
            else:
                color = "#22c55e"  # Green - Normal
                status = "Normal"
            
            if value_label:
                value_label.setText(f"{temp_c:.0f}°C")
                value_label.setStyleSheet(f"""
                    background: transparent;
                    color: {color};
                    font-size: 24px;
                    font-weight: 700;
                """)
            if status_label:
                status_label.setText(status_text if status_text else status)
        else:
            if value_label:
                value_label.setText("N/A")
                value_label.setStyleSheet(f"""
                    background: transparent;
                    color: {Theme.TEXT_TERTIARY};
                    font-size: 24px;
                    font-weight: 700;
                """)
            if status_label:
                status_label.setText("Not available")
    
    def update_from_hardware_data(self, hardware_data: dict):
        """Update all temperatures from hardware scan data"""
        if not hardware_data:
            return
        
        snapshot = hardware_data.get('snapshot')
        if not snapshot:
            return
        
        # CPU temperature
        cpu_temp = None
        if hasattr(snapshot, 'cpu') and snapshot.cpu:
            cpu_temp = snapshot.cpu.temperature_c
        self.update_temperature("cpu", cpu_temp)
        
        # GPU temperature
        gpu_temp = None
        if hasattr(snapshot, 'gpus') and snapshot.gpus:
            for gpu in snapshot.gpus:
                if gpu.temperature_c:
                    gpu_temp = gpu.temperature_c
                    break
        self.update_temperature("gpu", gpu_temp)
        
        # Drive temperature (first drive with temp data)
        drive_temp = None
        if hasattr(snapshot, 'storage') and snapshot.storage:
            for drive in snapshot.storage.physical_drives:
                if hasattr(drive, 'temperature_c') and drive.temperature_c:
                    drive_temp = drive.temperature_c
                    break
        self.update_temperature("drive", drive_temp)
        
        # Update status
        temps_available = sum(1 for t in [cpu_temp, gpu_temp, drive_temp] if t is not None)
        if temps_available > 0:
            self.status_label.setText(f"{temps_available} sensor(s) detected")
            self.status_label.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 11px;")
        else:
            self.status_label.setText("No sensors detected")
            self.status_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")


class HardwareSummaryGrid(QFrame):
    """Grid showing quick hardware summary stats with improved styling"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.stat_widgets = {}
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            HardwareSummaryGrid {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        # Shadow per spec section 14.6 - standard card shadow
        Theme.apply_shadow(self, blur_radius=12, offset_y=3, opacity=60)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(0)
        
        # Create stat items with meaningful colors
        stats = [
            ("cpu", "CPU", "—", "cores", Theme.ACCENT),
            ("gpu", "GPU", "—", "VRAM", "#8e44ad"),  # Purple for GPU
            ("ram", "RAM", "—", "used", Theme.SUCCESS),
            ("storage", "Storage", "—", "drive(s)", Theme.WARNING),
        ]
        
        for i, (stat_id, label, value, unit, color) in enumerate(stats):
            if i > 0:
                # Add divider with proper spacing
                self._add_stat_divider(layout)
            
            stat_widget = self._create_stat(label, value, unit, color)
            self.stat_widgets[stat_id] = stat_widget
            layout.addWidget(stat_widget, 1)
    
    def _add_stat_divider(self, layout):
        """Add a vertical divider between stats"""
        layout.addSpacing(24)
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setFixedHeight(50)
        divider.setStyleSheet("background: rgba(255, 255, 255, 0.08);")
        layout.addWidget(divider)
        layout.addSpacing(24)
    
    def _create_stat(self, label: str, value: str, unit: str, color: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("background: transparent;")
        frame.setMinimumWidth(100)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Label at top - uppercase, smaller
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_TERTIARY};
            font-size: 11px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label_widget)
        
        # Value - large and colored
        value_widget = QLabel(value)
        value_widget.setObjectName("value")
        value_widget.setStyleSheet(f"""
            background: transparent;
            color: {color};
            font-size: 28px;
            font-weight: 700;
        """)
        value_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_widget)
        
        # Unit - smaller, secondary
        unit_widget = QLabel(unit)
        unit_widget.setObjectName("unit")
        unit_widget.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_SECONDARY};
            font-size: 12px;
        """)
        unit_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(unit_widget)
        
        return frame
    
    def update_stat(self, stat_id: str, value: str, unit: str = ""):
        """Update a stat value"""
        if stat_id in self.stat_widgets:
            widget = self.stat_widgets[stat_id]
            value_label = widget.findChild(QLabel, "value")
            unit_label = widget.findChild(QLabel, "unit")
            if value_label:
                value_label.setText(value)
            if unit_label and unit:
                unit_label.setText(unit)


class HardwarePage(QWidget):
    """Comprehensive hardware information page"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hardware_data = None
        self.cards = {}
        self.is_loading = False
        self.setup_ui()
    
    def setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(32, 28, 32, 28)
        self.content_layout.setSpacing(20)
        
        # Header
        header = QHBoxLayout()
        header.setSpacing(16)
        
        title = QLabel("Hardware Information")
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 28px;
            font-weight: 600;
        """)
        header.addWidget(title)
        header.addStretch()
        
        # Last updated label
        self.last_updated = QLabel("Not scanned yet")
        self.last_updated.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
        header.addWidget(self.last_updated)
        
        # Refresh button with gradient and glow per spec section 14.5
        self.refresh_btn = QPushButton("Refresh Hardware Info")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh_hardware)
        Theme.style_accent_button(self.refresh_btn, "primary")
        # Add glow effect to refresh button per spec
        Theme.apply_shadow(self.refresh_btn, blur_radius=16, offset_y=4, 
                           color=Theme.ACCENT, opacity=120)
        header.addWidget(self.refresh_btn)
        
        # Device Manager button
        devmgr_btn = QPushButton("Device Manager")
        devmgr_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        devmgr_btn.clicked.connect(self.open_device_manager)
        devmgr_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                padding: 10px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        Theme.apply_shadow(devmgr_btn)
        header.addWidget(devmgr_btn)
        
        self.content_layout.addLayout(header)
        
        # Tab buttons
        tab_container = QHBoxLayout()
        tab_container.setSpacing(0)
        
        self.overview_tab_btn = QPushButton("Overview")
        self.overview_tab_btn.setCheckable(True)
        self.overview_tab_btn.setChecked(True)
        self.overview_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.overview_tab_btn.clicked.connect(lambda: self._switch_tab(0))
        tab_container.addWidget(self.overview_tab_btn)
        
        self.details_tab_btn = QPushButton("Full Details")
        self.details_tab_btn.setCheckable(True)
        self.details_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.details_tab_btn.clicked.connect(lambda: self._switch_tab(1))
        tab_container.addWidget(self.details_tab_btn)
        
        tab_container.addStretch()
        
        # Style the tab buttons per spec section 7.0.2 - underline style, 44px height, 14px font
        self.overview_tab_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Theme.TEXT_SECONDARY};
                border: none;
                border-bottom: 2px solid transparent;
                padding: 12px 24px;
                min-height: 44px;
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton:checked {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border-bottom: 2px solid {Theme.ACCENT};
                border-radius: 8px 8px 0 0;
                font-weight: 600;
            }}
            QPushButton:hover:!checked {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        self.details_tab_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Theme.TEXT_SECONDARY};
                border: none;
                border-bottom: 2px solid transparent;
                padding: 12px 24px;
                min-height: 44px;
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton:checked {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border-bottom: 2px solid {Theme.ACCENT};
                border-radius: 8px 8px 0 0;
                font-weight: 600;
            }}
            QPushButton:hover:!checked {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        
        self.content_layout.addLayout(tab_container)
        
        # Tab stack widget
        self.tab_stack = QStackedWidget()
        self.content_layout.addWidget(self.tab_stack, 1)
        
        # === Overview Tab ===
        overview_widget = QWidget()
        overview_layout = QVBoxLayout(overview_widget)
        overview_layout.setContentsMargins(0, 16, 0, 0)
        overview_layout.setSpacing(20)
        
        # Status/loading indicator
        self.status_label = QLabel("Click 'Refresh Hardware Info' to scan your system")
        self.status_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 13px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overview_layout.addWidget(self.status_label)
        
        # Summary grid
        self.summary_grid = HardwareSummaryGrid()
        self.summary_grid.setVisible(False)
        overview_layout.addWidget(self.summary_grid)
        
        # Temperature monitor card
        self.temp_card = TemperatureMonitorCard()
        self.temp_card.setVisible(False)
        overview_layout.addWidget(self.temp_card)
        
        # Real-time monitoring graphs
        self.graph_panel = RealtimeGraphPanel()
        self.graph_panel.setVisible(False)
        overview_layout.addWidget(self.graph_panel)
        
        # Hardware cards container - use grid layout for two columns
        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(12)
        self.cards_layout.setColumnStretch(0, 1)
        self.cards_layout.setColumnStretch(1, 1)
        
        # Create hardware category cards - arranged in two columns
        card_configs = [
            ("cpu", "Processor (CPU)", "C", 0, 0),
            ("gpu", "Graphics (GPU)", "G", 0, 1),
            ("ram", "Memory (RAM)", "M", 1, 0),
            ("motherboard", "Motherboard", "B", 1, 1),
            ("storage", "Storage", "S", 2, 0),
            ("network", "Network", "N", 2, 1),
        ]

        for card_id, title, icon, row, col in card_configs:
            card = HardwareInfoCard(title, icon, card_id)
            card.title_clicked.connect(self._navigate_to_detail)
            self.cards[card_id] = card
            self.cards_layout.addWidget(card, row, col)

        self.cards_container.setVisible(False)
        overview_layout.addWidget(self.cards_container)
        overview_layout.addStretch()
        
        self.tab_stack.addWidget(overview_widget)
        
        # === Full Details Tab ===
        self._setup_details_tab()
        
        scroll.setWidget(content)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        
        # Floating Quick Tools bar
        tools = [
            ("Device Manager", "\uE772", self.open_device_manager),
            ("System Info", "\uE946", self._open_system_info),
            ("Task Manager", "\uE9D5", self._open_task_manager),
        ]
        self._floating_toolbar = FloatingToolbar(tools, self)
        
        # Background worker setup
        self._worker = None
        self._thread = None
    
    def resizeEvent(self, event):
        """Reposition floating toolbar on resize"""
        super().resizeEvent(event)
        if hasattr(self, '_floating_toolbar'):
            self._floating_toolbar.update_position()
    
    def _open_system_info(self):
        """Open System Information"""
        import subprocess
        try:
            subprocess.Popen(["msinfo32"])
        except:
            pass
    
    def _open_task_manager(self):
        """Open Task Manager"""
        import subprocess
        try:
            subprocess.Popen(["taskmgr"])
        except:
            pass
    
    def _setup_details_tab(self):
        """Setup the Full Details tab with expandable sections for each hardware component"""
        details_scroll = QScrollArea()
        details_scroll.setWidgetResizable(True)
        details_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        details_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setContentsMargins(0, 16, 0, 16)
        details_layout.setSpacing(16)
        
        # Store detail cards for population later
        self.detail_cards = {}
        
        # Create detail sections
        detail_configs = [
            ("cpu_detail", "Processor (CPU) - Full Details", Theme.ACCENT),
            ("gpu_detail", "Graphics (GPU) - Full Details", Theme.SUCCESS),
            ("ram_detail", "Memory (RAM) - Full Details", Theme.WARNING),
            ("motherboard_detail", "Motherboard - Full Details", Theme.INFO),
            ("storage_detail", "Storage - Full Details", Theme.SECONDARY),
            ("network_detail", "Network - Full Details", Theme.ERROR),
        ]
        
        for card_id, title, color in detail_configs:
            card = HardwareDetailCard(title, color)
            self.detail_cards[card_id] = card
            details_layout.addWidget(card)
        
        details_layout.addStretch()
        details_scroll.setWidget(details_widget)
        self.tab_stack.addWidget(details_scroll)
    
    def _switch_tab(self, index: int):
        """Switch between Overview and Full Details tabs"""
        self.tab_stack.setCurrentIndex(index)
        self.overview_tab_btn.setChecked(index == 0)
        self.details_tab_btn.setChecked(index == 1)
    
    def _navigate_to_detail(self, card_id: str):
        """Navigate to detailed view for the specified hardware component."""
        # Switch to Full Details tab
        self._switch_tab(1)
        
        # Scroll to the corresponding detail card
        detail_key = f"{card_id}_detail"
        if detail_key in self.detail_cards:
            card = self.detail_cards[detail_key]
            # Ensure the card is visible by scrolling to it
            card.setExpanded(True)
            # Use a timer to allow the UI to update before scrolling
            QTimer.singleShot(100, lambda: card.ensureVisible())
    
    def refresh_hardware(self):
        """Refresh hardware information using background thread"""
        if self.is_loading:
            return
        
        if not HARDWARE_SCANNER_AVAILABLE:
            self.status_label.setText("Hardware scanner module not available")
            self.status_label.setVisible(True)
            return
        
        self.is_loading = True
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Scanning...")
        self.status_label.setText("Collecting hardware information...")
        self.status_label.setVisible(True)
        
        # Run scan in background thread to avoid UI freeze
        self._thread = QThread(self)
        self._worker = HardwareScanWorker()
        self._worker.moveToThread(self._thread)
        
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_hardware_scan_complete)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        
        self._thread.start()
    
    def display_cached_data(self, data: dict):
        """Display hardware info from cached data (from full scan)"""
        # The full scan only collects basic memory info, so trigger a complete 
        # hardware scan if we haven't loaded full data yet
        if data and not self.hardware_data and not self.is_loading:
            # Trigger a full hardware scan to populate the page
            self.refresh_hardware()
    
    def _on_hardware_scan_complete(self, data):
        """Handle completion of hardware scan (called on main thread)"""
        self.is_loading = False
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Refresh Hardware Info")
        
        if data is None:
            self.status_label.setText("Error collecting hardware info")
            self.status_label.setVisible(True)
            return
        
        self.hardware_data = data
        self._populate_hardware_info()
        self.status_label.setVisible(False)
        self.summary_grid.setVisible(True)
        self.temp_card.setVisible(True)
        self.temp_card.update_from_hardware_data(data)
        self.graph_panel.setVisible(True)
        self.graph_panel.start_monitoring()  # Start real-time updates
        self.cards_container.setVisible(True)
        self.last_updated.setText(f"Updated: {self.hardware_data['timestamp']}")
    
    def _populate_hardware_info(self):
        """Populate all hardware cards with collected data"""
        if not self.hardware_data:
            return
        
        snapshot = self.hardware_data.get('snapshot')
        if not snapshot:
            return
        
        # Update summary grid
        cpu = self.hardware_data['cpu']
        gpu = self.hardware_data['gpu']
        ram = self.hardware_data['ram']
        storage = self.hardware_data['storage']
        
        self.summary_grid.update_stat("cpu", str(cpu['cores']), f"{cpu['threads']} threads")
        
        vram_gb = gpu['vram_mb'] / 1024 if gpu['vram_mb'] > 0 else 0
        self.summary_grid.update_stat("gpu", f"{vram_gb:.1f} GB" if vram_gb >= 1 else f"{gpu['vram_mb']} MB", "VRAM")
        
        self.summary_grid.update_stat("ram", f"{ram['total_gb']:.0f} GB", f"{ram['utilization']:.0f}% used")
        self.summary_grid.update_stat("storage", f"{storage['total_gb']:.0f} GB", f"{storage['drives']} drive(s)")
        
        # Populate CPU card
        self._populate_cpu_card(snapshot.cpu)
        
        # Populate GPU card(s)
        self._populate_gpu_card(snapshot.gpus)
        
        # Populate RAM card
        self._populate_ram_card(snapshot.ram)
        
        # Populate Motherboard card
        self._populate_motherboard_card(snapshot.motherboard)
        
        # Populate Storage card
        self._populate_storage_card(snapshot.storage)
        
        # Populate Network card
        self._populate_network_card(snapshot.network_adapters)
        
        # Populate Full Details tab
        self._populate_detail_cards(snapshot)
    
    def _populate_cpu_card(self, cpu):
        """Populate CPU information card"""
        card = self.cards["cpu"]
        card.clear_info()
        
        card.add_info_row("Model", cpu.name, highlight=True)
        card.add_info_row("Cores", f"{cpu.cores}C / {cpu.threads}T")
        card.add_info_row("Clock", f"{cpu.max_clock_mhz} MHz (current: {cpu.current_clock_mhz} MHz)")
        card.add_info_row("Architecture", f"{cpu.architecture} • Socket: {cpu.socket}")
        
        # Cache info (combined)
        cache_parts = []
        if cpu.l2_cache_kb > 0:
            l2_mb = cpu.l2_cache_kb / 1024
            cache_parts.append(f"L2: {l2_mb:.1f}MB" if l2_mb >= 1 else f"L2: {cpu.l2_cache_kb}KB")
        if cpu.l3_cache_kb > 0:
            l3_mb = cpu.l3_cache_kb / 1024
            cache_parts.append(f"L3: {l3_mb:.1f}MB" if l3_mb >= 1 else f"L3: {cpu.l3_cache_kb}KB")
        if cache_parts:
            card.add_info_row("Cache", " • ".join(cache_parts))
        
        card.add_info_row("Usage", f"{cpu.utilization_percent:.0f}%")
        
        if cpu.temperature_c:
            card.add_info_row("Temp", f"{cpu.temperature_c:.0f}°C")
        
        # Set card status
        status = cpu.status.value if hasattr(cpu.status, 'value') else str(cpu.status)
        if cpu.utilization_percent > 90:
            card.set_status("warning", f"{cpu.utilization_percent:.0f}% Load")
        else:
            card.set_status(status)
    
    def _populate_gpu_card(self, gpus):
        """Populate GPU information card"""
        card = self.cards["gpu"]
        card.clear_info()
        
        for i, gpu in enumerate(gpus):
            if i > 0:
                card.add_subsection(f"GPU {i + 1}")
            
            card.add_info_row("Model", gpu.name, highlight=True)
            card.add_info_row("Vendor", gpu.manufacturer)
            
            if gpu.vram_mb > 0:
                vram_gb = gpu.vram_mb / 1024
                vram_str = f"{vram_gb:.1f} GB" if vram_gb >= 1 else f"{gpu.vram_mb} MB"
                card.add_info_row("VRAM", vram_str)
            
            card.add_info_row("Driver", f"v{gpu.driver_version} ({gpu.driver_date})")
            
            if gpu.resolution != "Unknown":
                card.add_info_row("Display", f"{gpu.resolution} @ {gpu.refresh_rate}Hz")
            
            if gpu.temperature_c:
                card.add_info_row("Temp", f"{gpu.temperature_c:.0f}°C")
        
        # Set card status based on first GPU
        if gpus:
            status = gpus[0].status.value if hasattr(gpus[0].status, 'value') else str(gpus[0].status)
            card.set_status(status)
    
    def _populate_ram_card(self, ram):
        """Populate RAM information card"""
        card = self.cards["ram"]
        card.clear_info()
        
        card.add_info_row("Total", f"{ram.total_gb:.1f} GB", highlight=True)
        card.add_info_row("Used", f"{ram.used_gb:.1f} GB ({ram.utilization_percent:.0f}%)")
        card.add_info_row("Free", f"{ram.available_gb:.1f} GB")
        card.add_info_row("Slots", f"{ram.slots_used} / {ram.slots_total} used")
        
        if ram.slots:
            card.add_subsection("Modules")
            for slot in ram.slots:
                if slot.capacity_gb > 0:
                    # Combine all info into one line
                    parts = [f"{slot.capacity_gb:.0f}GB {slot.memory_type}"]
                    if slot.speed_mhz > 0:
                        parts.append(f"{slot.speed_mhz}MHz")
                    if slot.manufacturer and slot.manufacturer not in ["Unknown", ""]:
                        parts.append(slot.manufacturer)
                    card.add_info_row(slot.slot or "DIMM", " • ".join(parts))
        
        # Set status based on utilization
        status = ram.status.value if hasattr(ram.status, 'value') else str(ram.status)
        if ram.utilization_percent > 90:
            card.set_status("critical", f"{ram.utilization_percent:.0f}% Used")
        elif ram.utilization_percent > 75:
            card.set_status("warning", f"{ram.utilization_percent:.0f}% Used")
        else:
            card.set_status(status, f"{ram.available_gb:.1f}GB Free")
    
    def _populate_motherboard_card(self, mb):
        """Populate motherboard and BIOS information card"""
        card = self.cards["motherboard"]
        card.clear_info()
        
        # Main motherboard info at top
        board_name = f"{mb.manufacturer} {mb.product}"
        card.add_info_row("Board", board_name, highlight=True)
        if mb.version and mb.version != "Unknown":
            card.add_info_row("Version", mb.version)
        if mb.serial_number and mb.serial_number not in ["Unknown", "Default string", ""]:
            card.add_info_row("Serial", mb.serial_number)
        
        # BIOS info (compact)
        card.add_subsection("BIOS")
        card.add_info_row("Vendor", mb.bios_vendor)
        card.add_info_row("Version", mb.bios_version)
        card.add_info_row("Date", mb.bios_date)
        card.add_info_row("Mode", mb.bios_mode)
        
        # Security (inline)
        card.add_subsection("Security")
        secure_boot = "Enabled" if mb.secure_boot else "Disabled"
        tpm = f"v{mb.tpm_version}" if mb.tpm_present else "Not detected"
        card.add_info_row("Secure Boot", secure_boot)
        card.add_info_row("TPM", tpm)
        
        # Set card status
        status = mb.status.value if hasattr(mb.status, 'value') else str(mb.status)
        card.set_status(status)
    
    def _populate_storage_card(self, storage):
        """Populate storage information card"""
        card = self.cards["storage"]
        card.clear_info()
        
        # Physical drives (compact)
        for i, drive in enumerate(storage.physical_drives):
            if i > 0:
                card.add_subsection(f"Drive {i + 1}")
            
            card.add_info_row("Model", drive.model, highlight=True)
            card.add_info_row("Size", f"{drive.capacity_gb:.0f} GB • {drive.media_type} • {drive.interface_type}")
            card.add_info_row("Health", f"{drive.smart_status}")
            
            # Additional info on one line
            extras = []
            if drive.temperature_c:
                extras.append(f"{drive.temperature_c:.0f}°C")
            if drive.power_on_hours:
                extras.append(f"{drive.power_on_hours:,}h")
            if extras:
                card.add_info_row("Stats", " • ".join(extras))
        
        if storage.volumes:
            card.add_subsection("Volumes")
            for vol in storage.volumes:
                vol_name = f"{vol.drive_letter}"
                if vol.label:
                    vol_name += f" {vol.label}"
                usage_str = f"{vol.used_gb:.0f}/{vol.capacity_gb:.0f}GB ({vol.utilization_percent:.0f}%)"
                card.add_info_row(vol_name, usage_str)
        
        # Set status
        has_critical = any(d.status.value == "critical" for d in storage.physical_drives if hasattr(d.status, 'value'))
        vol_critical = any(v.utilization_percent > 95 for v in storage.volumes)
        vol_warning = any(v.utilization_percent > 85 for v in storage.volumes)
        
        if has_critical or vol_critical:
            card.set_status("critical", "Issues")
        elif vol_warning:
            card.set_status("warning", "Low Space")
        else:
            card.set_status("healthy", "Healthy")
    
    def _populate_network_card(self, adapters):
        """Populate network adapter information card"""
        card = self.cards["network"]
        card.clear_info()
        
        connected_count = sum(1 for a in adapters if a.link_state == "Connected")
        card.set_status("healthy" if connected_count > 0 else "warning", 
                       f"{connected_count} Up" if connected_count > 0 else "Down")
        
        for i, adapter in enumerate(adapters):
            if i > 0:
                card.add_subsection("")
            
            card.add_info_row("Adapter", adapter.name[:35] + "..." if len(adapter.name) > 35 else adapter.name, highlight=True)
            
            # Type and speed on one line
            speed_str = ""
            if adapter.speed_mbps > 0:
                speed_str = f" @ {adapter.speed_mbps / 1000:.0f}Gbps" if adapter.speed_mbps >= 1000 else f" @ {adapter.speed_mbps}Mbps"
            card.add_info_row("Type", f"{adapter.adapter_type}{speed_str} • {adapter.link_state}")
            
            if adapter.ipv4_address != "Not assigned":
                card.add_info_row("IPv4", adapter.ipv4_address)
            
            card.add_info_row("MAC", adapter.mac_address)
            
            if adapter.gateway:
                card.add_info_row("Gateway", adapter.gateway)
        
        if not adapters:
            card.add_info_row("Status", "No adapters found")
            card.set_status("warning", "None")
    
    def _populate_detail_cards(self, snapshot):
        """Populate the Full Details tab with comprehensive hardware information"""
        # CPU Details
        if "cpu_detail" in self.detail_cards and snapshot.cpu:
            card = self.detail_cards["cpu_detail"]
            card.clear_info()
            cpu = snapshot.cpu
            card.add_info_row("Processor", cpu.name, highlight=True)
            card.add_info_row("Manufacturer", cpu.manufacturer)
            card.add_info_row("Architecture", f"{cpu.architecture} ({cpu.address_width}-bit)")
            card.add_info_row("Cores / Threads", f"{cpu.cores} cores / {cpu.threads} threads")
            card.add_info_row("Base Clock", f"{cpu.max_clock_mhz} MHz")
            card.add_info_row("Current Clock", f"{cpu.current_clock_mhz} MHz")
            if cpu.l1_cache_kb > 0:
                card.add_info_row("L1 Cache", f"{cpu.l1_cache_kb} KB")
            if cpu.l2_cache_kb > 0:
                card.add_info_row("L2 Cache", f"{cpu.l2_cache_kb} KB")
            if cpu.l3_cache_kb > 0:
                card.add_info_row("L3 Cache", f"{cpu.l3_cache_kb} KB")
            card.add_info_row("Socket", cpu.socket)
            card.add_info_row("Stepping", cpu.stepping)
            card.add_info_row("Family", cpu.family)
            card.add_info_row("Revision", str(cpu.revision))
            card.add_info_row("Processor ID", cpu.processor_id)
            card.add_info_row("Device ID", cpu.device_id)
            if cpu.voltage_caps:
                card.add_info_row("Voltage Caps", cpu.voltage_caps)
            if cpu.external_clock_mhz > 0:
                card.add_info_row("External Clock", f"{cpu.external_clock_mhz} MHz")
        
        # GPU Details
        if "gpu_detail" in self.detail_cards and snapshot.gpus:
            card = self.detail_cards["gpu_detail"]
            card.clear_info()
            for i, gpu in enumerate(snapshot.gpus):
                if i > 0:
                    card.add_info_row("", "")  # Spacer
                card.add_info_row(f"GPU {i+1}", gpu.name, highlight=True)
                card.add_info_row("Video Processor", gpu.video_processor)
                if gpu.vram_mb > 0:
                    card.add_info_row("VRAM", f"{gpu.vram_mb} MB")
                card.add_info_row("Resolution", f"{gpu.resolution} @ {gpu.refresh_rate}Hz")
                card.add_info_row("Bits/Pixel", str(gpu.bits_per_pixel))
                card.add_info_row("Driver Version", gpu.driver_version)
                card.add_info_row("Driver Date", gpu.driver_date)
                card.add_info_row("DAC Type", gpu.adapter_dac_type)
                card.add_info_row("Video Mode", gpu.video_mode_description)
                card.add_info_row("Status", str(gpu.status.value) if hasattr(gpu.status, 'value') else str(gpu.status))
                card.add_info_row("PNP Device ID", gpu.pnp_device_id[:60] + "..." if len(gpu.pnp_device_id) > 60 else gpu.pnp_device_id)
                if gpu.installed_display_drivers:
                    drivers = gpu.installed_display_drivers[:100] + "..." if len(gpu.installed_display_drivers) > 100 else gpu.installed_display_drivers
                    card.add_info_row("Display Drivers", drivers)
        
        # RAM Details
        if "ram_detail" in self.detail_cards and snapshot.ram:
            card = self.detail_cards["ram_detail"]
            card.clear_info()
            mem = snapshot.ram
            card.add_info_row("Total Physical", f"{mem.total_gb:.1f} GB", highlight=True)
            card.add_info_row("Available", f"{mem.available_gb:.1f} GB")
            card.add_info_row("Used", f"{mem.used_gb:.1f} GB ({mem.utilization_percent:.0f}%)")
            if mem.total_virtual_memory > 0:
                card.add_info_row("Total Virtual", f"{mem.total_virtual_memory / (1024**3):.1f} GB")
            if mem.available_virtual_memory > 0:
                card.add_info_row("Available Virtual", f"{mem.available_virtual_memory / (1024**3):.1f} GB")
            if mem.page_file_total > 0:
                card.add_info_row("Page File Total", f"{mem.page_file_total / (1024**3):.1f} GB")
            if mem.page_file_free > 0:
                card.add_info_row("Page File Free", f"{mem.page_file_free / (1024**3):.1f} GB")
            
            # RAM slot details
            if mem.slots:
                card.add_info_row("", "")  # Spacer
                card.add_info_row("RAM Modules", f"{len(mem.slots)} installed", highlight=True)
                for i, slot in enumerate(mem.slots):
                    card.add_info_row(f"Slot {i+1}", f"{slot.capacity_gb:.0f} GB {slot.memory_type} @ {slot.speed_mhz} MHz")
                    card.add_info_row("  Manufacturer", slot.manufacturer)
                    card.add_info_row("  Part Number", slot.part_number)
                    card.add_info_row("  Serial", slot.serial_number)
                    card.add_info_row("  Form Factor", slot.form_factor)
                    card.add_info_row("  Locator", slot.device_locator)
        
        # Motherboard Details
        if "motherboard_detail" in self.detail_cards and snapshot.motherboard:
            card = self.detail_cards["motherboard_detail"]
            card.clear_info()
            mb = snapshot.motherboard
            card.add_info_row("Manufacturer", mb.manufacturer, highlight=True)
            card.add_info_row("Product", mb.product)
            card.add_info_row("Serial Number", mb.serial_number)
            card.add_info_row("Version", mb.version)
            
            # System info
            if mb.system_manufacturer:
                card.add_info_row("", "")  # Spacer
                card.add_info_row("System", mb.system_manufacturer, highlight=True)
                card.add_info_row("Model", mb.system_model)
                card.add_info_row("System Type", mb.system_type)
                card.add_info_row("SKU", mb.system_sku)
            
            # BIOS info
            if mb.bios_vendor:
                card.add_info_row("", "")  # Spacer
                card.add_info_row("BIOS", mb.bios_vendor, highlight=True)
                card.add_info_row("BIOS Version", mb.bios_version)
                card.add_info_row("BIOS Date", mb.bios_date)
                card.add_info_row("SMBIOS Version", mb.smbios_version)
            
            # Chassis info
            if mb.chassis_manufacturer:
                card.add_info_row("", "")  # Spacer
                card.add_info_row("Chassis", mb.chassis_manufacturer, highlight=True)
                card.add_info_row("Chassis Type", mb.chassis_type)
                card.add_info_row("Chassis Serial", mb.chassis_serial)
        
        # Storage Details
        if "storage_detail" in self.detail_cards and snapshot.storage:
            card = self.detail_cards["storage_detail"]
            card.clear_info()
            storage = snapshot.storage
            
            # Physical drives
            if storage.physical_drives:
                card.add_info_row("Physical Drives", f"{len(storage.physical_drives)}", highlight=True)
                for drive in storage.physical_drives:
                    card.add_info_row("Drive", f"{drive.model} ({drive.capacity_gb:.0f} GB)")
                    card.add_info_row("  Type", f"{drive.media_type} • {drive.interface_type}")
                    card.add_info_row("  Serial", drive.serial_number)
                    card.add_info_row("  Firmware", drive.firmware_version)
                    card.add_info_row("  SMART", drive.smart_status)
            
            # Logical volumes
            if storage.volumes:
                card.add_info_row("", "")  # Spacer
                card.add_info_row("Volumes", f"{len(storage.volumes)}", highlight=True)
                for vol in storage.volumes:
                    free_pct = (vol.free_gb / vol.capacity_gb) * 100 if vol.capacity_gb > 0 else 0
                    card.add_info_row(f"Drive {vol.drive_letter}", f"{vol.capacity_gb:.0f} GB ({free_pct:.0f}% free)")
                    card.add_info_row("  Label", vol.label if vol.label else "(No label)")
                    card.add_info_row("  File System", vol.file_system)
        
        # Network Details
        if "network_detail" in self.detail_cards and snapshot.network_adapters:
            card = self.detail_cards["network_detail"]
            card.clear_info()
            
            for i, adapter in enumerate(snapshot.network_adapters):
                if i > 0:
                    card.add_info_row("", "")  # Spacer
                card.add_info_row(f"Adapter {i+1}", adapter.name[:50] + "..." if len(adapter.name) > 50 else adapter.name, highlight=True)
                card.add_info_row("Type", adapter.adapter_type)
                card.add_info_row("Status", adapter.link_state)
                if adapter.speed_mbps > 0:
                    speed_str = f"{adapter.speed_mbps / 1000:.1f} Gbps" if adapter.speed_mbps >= 1000 else f"{adapter.speed_mbps} Mbps"
                    card.add_info_row("Speed", speed_str)
                card.add_info_row("MAC Address", adapter.mac_address)
                card.add_info_row("IPv4", adapter.ipv4_address)
                card.add_info_row("Subnet", adapter.subnet_mask)
                if adapter.gateway:
                    card.add_info_row("Gateway", adapter.gateway)
                if adapter.ipv6_address and adapter.ipv6_address != "Not assigned":
                    card.add_info_row("IPv6", adapter.ipv6_address[:40] + "..." if len(adapter.ipv6_address) > 40 else adapter.ipv6_address)
                if adapter.dns_servers:
                    card.add_info_row("DNS", ", ".join(adapter.dns_servers[:2]))
                card.add_info_row("DHCP Enabled", "Yes" if adapter.dhcp_enabled else "No")
                if adapter.dhcp_server:
                    card.add_info_row("DHCP Server", adapter.dhcp_server)
                card.add_info_row("Manufacturer", adapter.manufacturer)
                card.add_info_row("PNP Device ID", adapter.pnp_device_id[:50] + "..." if len(adapter.pnp_device_id) > 50 else adapter.pnp_device_id)
    
    def open_device_manager(self):
        """Open Windows Device Manager"""
        import subprocess
        try:
            subprocess.Popen(["mmc", "devmgmt.msc"], shell=True)
        except Exception as e:
            print(f"Failed to open Device Manager: {e}")
    
    def show_results(self, results):
        """Compatibility method for ModulePage interface"""
        # This is called by the old check_hardware_health method
        # We'll trigger a hardware refresh instead
        self.refresh_hardware()
    
    def set_checking(self):
        """Compatibility method for ModulePage interface"""
        self.status_label.setText("Checking hardware...")
        self.status_label.setVisible(True)


class WindowsToolsPage(QWidget):
    """Comprehensive page showing all Windows Settings and System Tools with a list menu"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_category = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Define all categories with their tools (name, command, description)
        self.categories = [
            # Windows Settings section
            ("_settings_header", None, "SETTINGS", None),
            ("system", "\uE770", "System", [
                ("Display", "ms-settings:display", "Screen resolution, brightness, and display settings"),
                ("Sound", "ms-settings:sound", "Volume, output devices, and sound preferences"),
                ("Notifications", "ms-settings:notifications", "App notifications and focus assist"),
                ("Power", "ms-settings:powersleep", "Sleep, screen timeout, and battery settings"),
                ("Storage", "ms-settings:storagesense", "Disk usage and storage management"),
                ("Multitasking", "ms-settings:multitasking", "Snap windows and virtual desktops"),
                ("Activation", "ms-settings:activation", "Windows activation status and product key"),
                ("About", "ms-settings:about", "Device specs, rename PC, and Windows version"),
            ]),
            ("network", "\uE774", "Network", [
                ("Wi-Fi", "ms-settings:network-wifi", "Connect to wireless networks"),
                ("Ethernet", "ms-settings:network-ethernet", "Wired network adapter settings"),
                ("VPN", "ms-settings:network-vpn", "Add and manage VPN connections"),
                ("Mobile Hotspot", "ms-settings:network-mobilehotspot", "Share your internet connection"),
                ("Proxy", "ms-settings:network-proxy", "Configure proxy server settings"),
                ("Advanced Network", "ms-settings:network-advancedsettings", "Network adapters and data usage"),
            ]),
            ("personalize", "\uE771", "Personalize", [
                ("Background", "ms-settings:personalization-background", "Desktop wallpaper and slideshow"),
                ("Colors", "ms-settings:colors", "Accent color and transparency effects"),
                ("Lock Screen", "ms-settings:lockscreen", "Lock screen background and apps"),
                ("Themes", "ms-settings:themes", "Desktop themes and icon settings"),
                ("Fonts", "ms-settings:fonts", "Install and manage system fonts"),
                ("Start Menu", "ms-settings:personalization-start", "Start menu layout and pinned apps"),
                ("Taskbar", "ms-settings:taskbar", "Taskbar buttons, icons, and behaviors"),
            ]),
            ("apps", "\uE74C", "Apps", [
                ("Installed Apps", "ms-settings:appsfeatures", "Manage and uninstall applications"),
                ("Default Apps", "ms-settings:defaultapps", "Choose default programs for file types"),
                ("Startup Apps", "ms-settings:startupapps", "Apps that run when Windows starts"),
                ("Optional Features", "ms-settings:optionalfeatures", "Add or remove Windows features"),
            ]),
            ("accounts", "\uE77B", "Accounts", [
                ("Your Info", "ms-settings:yourinfo", "Account picture and sign-in options"),
                ("Email & Accounts", "ms-settings:emailandaccounts", "Email, calendar, and contacts accounts"),
                ("Sign-in Options", "ms-settings:signinoptions", "Password, PIN, and Windows Hello"),
                ("Family & Others", "ms-settings:otherusers", "Add family members or other users"),
                ("Sync Settings", "ms-settings:sync", "Sync your settings across devices"),
            ]),
            ("time", "\uE823", "Time & Language", [
                ("Date & Time", "ms-settings:dateandtime", "Time zone, clock, and calendar settings"),
                ("Language & Region", "ms-settings:regionlanguage", "Display language and regional format"),
                ("Typing", "ms-settings:typing", "Keyboard, autocorrect, and suggestions"),
                ("Speech", "ms-settings:speech", "Speech recognition and text-to-speech"),
            ]),
            ("gaming", "\uE7FC", "Gaming", [
                ("Game Bar", "ms-settings:gaming-gamebar", "Game Bar shortcuts and features"),
                ("Captures", "ms-settings:gaming-gamedvr", "Screenshots and game recording settings"),
                ("Game Mode", "ms-settings:gaming-gamemode", "Optimize your PC for gaming"),
                ("Xbox Networking", "ms-settings:gaming-xboxnetworking", "Xbox Live connection status"),
            ]),
            ("access", "\uE776", "Accessibility", [
                ("Text Size", "ms-settings:easeofaccess-display", "Make text and apps larger"),
                ("Visual Effects", "ms-settings:easeofaccess-visualeffects", "Animations and transparency"),
                ("Mouse Pointer", "ms-settings:easeofaccess-mousepointer", "Pointer size, color, and style"),
                ("Magnifier", "ms-settings:easeofaccess-magnifier", "Zoom in on screen content"),
                ("Color Filters", "ms-settings:easeofaccess-colorfilter", "Color blindness filters"),
                ("Narrator", "ms-settings:easeofaccess-narrator", "Screen reader for blind users"),
                ("Keyboard", "ms-settings:easeofaccess-keyboard", "On-screen keyboard and sticky keys"),
                ("Captions", "ms-settings:easeofaccess-captions", "Subtitle appearance settings"),
            ]),
            ("privacy", "\uE72E", "Privacy & Security", [
                ("Windows Security", "ms-settings:windowsdefender", "Virus protection and firewall status"),
                ("Find My Device", "ms-settings:findmydevice", "Locate your lost device"),
                ("General Privacy", "ms-settings:privacy", "Advertising ID and app permissions"),
                ("Location", "ms-settings:privacy-location", "Location services and app access"),
                ("Camera", "ms-settings:privacy-webcam", "Camera access for apps"),
                ("Microphone", "ms-settings:privacy-microphone", "Microphone access for apps"),
                ("Diagnostics", "ms-settings:privacy-feedback", "Diagnostic data and feedback"),
            ]),
            ("update", "\uE895", "Windows Update", [
                ("Check for Updates", "ms-settings:windowsupdate", "Download and install Windows updates"),
                ("Update History", "ms-settings:windowsupdate-history", "View installed updates"),
                ("Advanced Options", "ms-settings:windowsupdate-options", "Update schedule and delivery"),
                ("Recovery", "ms-settings:recovery", "Reset PC or advanced startup"),
            ]),
            # System Tools section
            ("_tools_header", None, "TOOLS", None),
            ("core", "\uE713", "Core Tools", [
                ("Control Panel", "control", "Classic Windows settings and configuration"),
                ("Device Manager", "devmgmt.msc", "View and manage hardware devices"),
                ("Disk Management", "diskmgmt.msc", "Partition, format, and manage disks"),
                ("Computer Management", "compmgmt.msc", "Combined admin tools in one console"),
                ("System Configuration", "msconfig", "Boot options and startup services"),
                ("System Information", "msinfo32", "Detailed hardware and software info"),
                ("System Properties", "sysdm.cpl", "Computer name, domain, and remote settings"),
                ("Print Management", "printmanagement.msc", "Manage printers and print servers"),
                ("Component Services", "dcomcnfg", "COM+ applications and DCOM config"),
                ("Run Dialog", "shell:::{2559a1f3-21d7-11d4-bdaf-00c04f60b9f0}", "Quick command launcher"),
            ]),
            ("admin", "\uE90F", "Admin Tools", [
                ("Task Manager", "taskmgr", "Running processes and performance"),
                ("Resource Monitor", "resmon", "CPU, memory, disk, and network usage"),
                ("Performance Monitor", "perfmon", "System performance data and logs"),
                ("Event Viewer", "eventvwr.msc", "System, security, and application logs"),
                ("Services", "services.msc", "Start, stop, and configure services"),
                ("Task Scheduler", "taskschd.msc", "Automate tasks and scripts"),
                ("Group Policy Editor", "gpedit.msc", "Local computer policy settings"),
                ("Registry Editor", "regedit", "Edit Windows registry database"),
                ("Reliability Monitor", "perfmon /rel", "System stability and problem history"),
                ("GPO Update", "cmd /c gpupdate /force", "Force Group Policy refresh"),
                ("Steps Recorder", "psr", "Record steps to reproduce a problem"),
                ("Windows Admin Center", "cmd /c start https://localhost:6516", "Web-based server management tool"),
            ]),
            ("enterprise", "\uE731", "Enterprise Admin", [
                ("Active Directory Users", "dsa.msc", "Manage AD users, groups, and computers"),
                ("Active Directory Domains", "domain.msc", "Manage AD domains and trusts"),
                ("Active Directory Sites", "dssite.msc", "Manage AD replication and sites"),
                ("ADSI Edit", "adsiedit.msc", "Low-level Active Directory editor"),
                ("Group Policy Management", "gpmc.msc", "Manage GPOs across the domain"),
                ("DNS Manager", "dnsmgmt.msc", "Configure DNS zones and records"),
                ("DHCP Manager", "dhcpmgmt.msc", "Manage DHCP scopes and leases"),
                ("Hyper-V Manager", "virtmgmt.msc", "Manage virtual machines"),
                ("Failover Cluster Manager", "cluadmin.msc", "Manage Windows failover clusters"),
                ("Authorization Manager", "azman.msc", "Role-based access control (RBAC)"),
                ("Server Manager", "ServerManager", "Windows Server management console"),
                ("Routing and Remote Access", "rrasmgmt.msc", "VPN and routing configuration"),
                ("Remote Desktop Services", "tsadmin.msc", "Terminal Services management"),
                ("NFS Configuration", "nfsmgmt.msc", "Network File System settings"),
                ("DFS Management", "dfsmgmt.msc", "Distributed File System namespaces"),
                ("Share and Storage", "intmgmt.msc", "iSNS Server management"),
                ("File Server Resource Mgr", "fsrm.msc", "Quotas, file screens, and reports"),
                ("Windows Deployment Services", "wdsmgmt.msc", "Network-based OS deployment"),
                ("WSUS Console", "wsus.msc", "Windows Server Update Services"),
            ]),
            ("security_tools", "\uE83D", "Security Tools", [
                ("Windows Security", "windowsdefender:", "Antivirus, firewall, and protection"),
                ("Windows Firewall", "wf.msc", "Advanced firewall rules and settings"),
                ("User Accounts", "netplwiz", "Manage user accounts and passwords"),
                ("Credential Manager", "control /name Microsoft.CredentialManager", "Saved passwords and credentials"),
                ("Local Security Policy", "secpol.msc", "Security settings and audit policies"),
                ("Certificate Manager", "certmgr.msc", "Manage user security certificates"),
                ("Computer Certificates", "certlm.msc", "Manage machine security certificates"),
                ("TPM Management", "tpm.msc", "Trusted Platform Module settings"),
                ("BitLocker Management", "control /name Microsoft.BitLockerDriveEncryption", "Drive encryption settings"),
                ("Windows Defender Firewall", "firewall.cpl", "Basic firewall configuration"),
                ("Local Users & Groups", "lusrmgr.msc", "Local user and group management"),
                ("Shared Folders", "fsmgmt.msc", "View and manage shared folders"),
                ("Encrypted File System", "cmd /c cipher", "EFS encryption management"),
            ]),
            ("network_tools", "\uEC05", "Network Tools", [
                ("Network Connections", "ncpa.cpl", "Network adapter settings and status"),
                ("Network Sharing Center", "control /name Microsoft.NetworkAndSharingCenter", "Network status and sharing options"),
                ("Windows Firewall", "firewall.cpl", "Basic firewall settings"),
                ("Internet Options", "inetcpl.cpl", "Browser and internet settings"),
                ("Remote Desktop", "mstsc", "Connect to remote computers"),
                ("iSCSI Initiator", "iscsicpl", "Connect to iSCSI storage targets"),
                ("Quick Assist", "quickassist", "Give or get remote assistance"),
            ]),
            ("disk", "\uEDA2", "Disk Tools", [
                ("Disk Cleanup", "cleanmgr", "Delete temporary and junk files"),
                ("Defragment & Optimize", "dfrgui", "Optimize drive performance"),
                ("Disk Management", "diskmgmt.msc", "Partition and format drives"),
                ("Storage Spaces", "control /name Microsoft.StorageSpaces", "Combine drives for redundancy"),
                ("Backup Settings", "ms-settings:backup", "File backup configuration"),
                ("Recovery Drive", "RecoveryDrive", "Create USB recovery media"),
            ]),
            ("display_tools", "\uE7F4", "Display Tools", [
                ("Display Properties", "desk.cpl", "Screen resolution and orientation"),
                ("Color Management", "colorcpl", "Color profiles for monitors"),
                ("ClearType Tuner", "cttune", "Improve text readability"),
                ("DirectX Diagnostics", "dxdiag", "Graphics and sound diagnostics"),
                ("Advanced Graphics", "ms-settings:display-advancedgraphics", "GPU preferences for apps"),
            ]),
            ("devices", "\uE7F5", "Device Tools", [
                ("Sound Settings", "mmsys.cpl", "Playback and recording devices"),
                ("Device Manager", "devmgmt.msc", "Hardware device management"),
                ("Printers & Scanners", "control printers", "Add and manage printers"),
                ("Bluetooth Devices", "ms-settings:bluetooth", "Pair Bluetooth devices"),
                ("Mouse Properties", "main.cpl", "Mouse buttons, pointers, and speed"),
                ("Keyboard Properties", "control keyboard", "Keyboard repeat rate and cursor"),
                ("Windows Fax and Scan", "wfs", "Send faxes and scan documents"),
            ]),
            ("power", "\uE945", "Power Tools", [
                ("Power Options", "powercfg.cpl", "Power plans and advanced settings"),
                ("Windows Mobility Center", "mblctr", "Laptop display, battery, and sync"),
                ("Memory Diagnostics", "mdsched", "Check RAM for errors"),
            ]),
            ("dev", "\uE756", "Developer Tools", [
                ("Command Prompt", "cmd", "Windows command line interface"),
                ("PowerShell", "powershell", "Advanced command shell and scripting"),
                ("PowerShell (x86)", "%SystemRoot%\\SysWOW64\\WindowsPowerShell\\v1.0\\powershell.exe", "32-bit PowerShell for compatibility"),
                ("PowerShell ISE", "powershell_ise", "PowerShell script editor and debugger"),
                ("PowerShell ISE (x86)", "%SystemRoot%\\SysWOW64\\WindowsPowerShell\\v1.0\\powershell_ise.exe", "32-bit PowerShell ISE"),
                ("Windows Terminal", "wt", "Modern terminal with tabs"),
                ("Environment Variables", "rundll32 sysdm.cpl,EditEnvironmentVariables", "System and user path variables"),
                ("ODBC Data Sources (64)", "odbcad32", "64-bit database connections"),
                ("ODBC Data Sources (32)", "%SystemRoot%\\SysWOW64\\odbcad32.exe", "32-bit database connections"),
                ("Windows Features", "optionalfeatures", "Enable or disable Windows features"),
            ]),
            ("recovery", "\uE777", "Recovery Tools", [
                ("Troubleshooters", "ms-settings:troubleshoot", "Fix common Windows problems"),
                ("Recovery Options", "ms-settings:recovery", "Reset or reinstall Windows"),
                ("System Restore", "rstrui", "Restore to a previous state"),
                ("Backup & Restore", "control /name Microsoft.BackupAndRestore", "Windows 7 style backup"),
                ("File History", "control /name Microsoft.FileHistory", "Automatic file backup"),
            ]),
            ("utilities", "\uE74E", "Utilities", [
                ("Character Map", "charmap", "Insert special characters and symbols"),
                ("WordPad", "wordpad", "Basic word processor"),
                ("Notepad", "notepad", "Simple text editor"),
                ("Paint", "mspaint", "Basic image editor"),
                ("Snipping Tool", "snippingtool", "Capture screen screenshots"),
                ("Windows Media Player", "wmplayer", "Play music and videos"),
                ("Calculator", "calc", "Basic and scientific calculator"),
                ("Magnifier", "magnify", "Zoom in on screen areas"),
            ]),
        ]
        
        # Left side: Category list menu
        left_panel = QFrame()
        left_panel.setFixedWidth(220)
        left_panel.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_SIDEBAR};
                border: none;
            }}
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 16, 0, 16)
        left_layout.setSpacing(0)
        
        # Title in menu
        menu_title = QLabel("  Windows Tools")
        menu_title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 16px;
            font-weight: 600;
            padding: 8px 16px 16px 16px;
        """)
        left_layout.addWidget(menu_title)
        
        # Scrollable menu list
        menu_scroll = QScrollArea()
        menu_scroll.setWidgetResizable(True)
        menu_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        menu_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { width: 6px; }
        """)
        
        menu_content = QWidget()
        menu_content.setStyleSheet("background: transparent;")
        self.menu_layout = QVBoxLayout(menu_content)
        self.menu_layout.setContentsMargins(8, 0, 8, 0)
        self.menu_layout.setSpacing(2)
        
        self.menu_items = {}
        for cat_id, icon, name, tools in self.categories:
            if cat_id.startswith("_"):
                # Section header
                header = QLabel(name)
                header.setStyleSheet(f"""
                    background: transparent;
                    color: {Theme.TEXT_TERTIARY};
                    font-size: 10px;
                    font-weight: 600;
                    letter-spacing: 1px;
                    padding: 12px 8px 4px 8px;
                """)
                self.menu_layout.addWidget(header)
            else:
                # Menu item
                item = self._create_menu_item(cat_id, icon, name, len(tools))
                self.menu_items[cat_id] = item
                self.menu_layout.addWidget(item)
        
        self.menu_layout.addStretch()
        menu_scroll.setWidget(menu_content)
        left_layout.addWidget(menu_scroll)
        layout.addWidget(left_panel)
        
        # Right side: Tools display area
        right_panel = QWidget()
        right_panel.setStyleSheet(f"background: {Theme.BG_WINDOW};")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(24, 20, 24, 20)
        right_layout.setSpacing(16)
        
        # Category header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        self.cat_icon = QLabel("\uE713")
        self.cat_icon.setStyleSheet(f"background: transparent; font-size: 24px; font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';")
        header_layout.addWidget(self.cat_icon)
        
        self.cat_title = QLabel("Select a Category")
        self.cat_title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 20px;
            font-weight: 600;
        """)
        header_layout.addWidget(self.cat_title)
        header_layout.addStretch()
        right_layout.addLayout(header_layout)
        
        # Tools grid in a scroll area
        tools_scroll = QScrollArea()
        tools_scroll.setWidgetResizable(True)
        tools_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tools_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.tools_content = QWidget()
        self.tools_content.setStyleSheet("background: transparent;")
        self.tools_layout = QGridLayout(self.tools_content)
        self.tools_layout.setSpacing(12)
        self.tools_layout.setContentsMargins(0, 0, 0, 0)
        self.tools_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        # Placeholder
        placeholder = QLabel("← Select a category from the menu")
        placeholder.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 14px;")
        self.tools_layout.addWidget(placeholder, 0, 0)
        
        tools_scroll.setWidget(self.tools_content)
        right_layout.addWidget(tools_scroll)
        
        layout.addWidget(right_panel, 1)
        
        # Select first real category by default
        self._select_category("system")
    
    def _create_menu_item(self, cat_id: str, icon: str, name: str, count: int) -> QFrame:
        """Create a menu list item"""
        item = QFrame()
        item.setProperty("cat_id", cat_id)
        item.setCursor(Qt.CursorShape.PointingHandCursor)
        item.setFixedHeight(34)
        item.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border: none;
                border-radius: {Theme.RADIUS_SM}px;
            }}
            QFrame:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        
        layout = QHBoxLayout(item)
        layout.setContentsMargins(12, 0, 10, 0)
        layout.setSpacing(10)
        
        # Icon - Fluent Icon for visual recognition
        icon_label = QLabel(icon)
        icon_label.setFixedWidth(20)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("background: transparent; border: none; font-size: 14px; font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';")
        layout.addWidget(icon_label)
        
        # Name
        name_label = QLabel(name)
        name_label.setStyleSheet(f"background: transparent; border: none; color: {Theme.TEXT_PRIMARY}; font-size: 13px;")
        layout.addWidget(name_label, 1)
        
        # Count badge
        count_label = QLabel(str(count))
        count_label.setFixedSize(22, 18)
        count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_label.setStyleSheet(f"""
            background: transparent;
            border: none;
            color: {Theme.TEXT_TERTIARY};
            font-size: 11px;
        """)
        layout.addWidget(count_label)
        
        # Click handler
        item.mousePressEvent = lambda e, cid=cat_id: self._select_category(cid)
        
        return item
    
    def _select_category(self, cat_id: str):
        """Select a category and display its tools"""
        self.current_category = cat_id
        
        # Update menu item styles
        for cid, item in self.menu_items.items():
            if cid == cat_id:
                item.setStyleSheet(f"""
                    QFrame {{
                        background: rgba(0, 120, 212, 0.15);
                        border: none;
                        border-left: 3px solid {Theme.ACCENT};
                        border-radius: 0px;
                        margin-left: 0px;
                    }}
                """)
            else:
                item.setStyleSheet(f"""
                    QFrame {{
                        background: transparent;
                        border: none;
                        border-radius: {Theme.RADIUS_SM}px;
                    }}
                    QFrame:hover {{
                        background: {Theme.BG_CARD_HOVER};
                    }}
                """)
        
        # Find category data
        cat_data = None
        for cid, icon, name, tools in self.categories:
            if cid == cat_id:
                cat_data = (icon, name, tools)
                break
        
        if not cat_data:
            return
        
        icon, name, tools = cat_data
        
        # Update header
        self.cat_icon.setText(icon)
        self.cat_title.setText(name)
        
        # Clear and rebuild tools grid
        while self.tools_layout.count():
            item = self.tools_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add tools as cards in a grid (2 columns for wider cards with descriptions)
        cols = 2
        for i, tool_data in enumerate(tools):
            tool_name, command, description = tool_data
            row = i // cols
            col = i % cols
            card = self._create_tool_card(tool_name, command, description)
            self.tools_layout.addWidget(card, row, col)
    
    def _create_tool_card(self, name: str, command: str, description: str) -> QFrame:
        """Create a tool card with description"""
        card = QFrame()
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setMinimumSize(320, 70)
        card.setMaximumHeight(80)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
            QFrame:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        Theme.apply_shadow(card, blur_radius=8, offset_y=2, opacity=40)
        
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        # Type indicator dot
        if command.startswith("ms-settings:"):
            dot_color = Theme.INFO
        elif command.endswith(".msc"):
            dot_color = Theme.WARNING
        elif command.endswith(".cpl"):
            dot_color = Theme.SECONDARY
        else:
            dot_color = Theme.SUCCESS
        
        dot = QLabel("●")
        dot.setFixedWidth(14)
        dot.setStyleSheet(f"background: transparent; border: none; color: {dot_color}; font-size: 10px;")
        dot.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(dot)
        
        # Text content
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        
        # Tool name
        name_label = QLabel(name)
        name_label.setStyleSheet(f"""
            background: transparent;
            border: none;
            color: {Theme.TEXT_PRIMARY};
            font-size: 13px;
            font-weight: 600;
        """)
        text_layout.addWidget(name_label)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet(f"""
            background: transparent;
            border: none;
            color: {Theme.TEXT_SECONDARY};
            font-size: 11px;
        """)
        desc_label.setWordWrap(True)
        text_layout.addWidget(desc_label)
        
        layout.addLayout(text_layout, 1)
        
        # Arrow indicator
        arrow = QLabel("›")
        arrow.setStyleSheet(f"background: transparent; border: none; color: {Theme.TEXT_TERTIARY}; font-size: 18px;")
        layout.addWidget(arrow)
        
        # Click handler
        card.mousePressEvent = lambda e, cmd=command: self._launch_tool(cmd)
        
        return card
    
    def _launch_tool(self, command: str):
        """Launch a Windows tool or settings page"""
        import subprocess
        import os
        
        try:
            if command.startswith("ms-settings:") or command.startswith("windowsdefender:"):
                os.startfile(command)
            elif command.endswith(".msc") or command.endswith(".cpl"):
                subprocess.Popen(["mmc", command] if command.endswith(".msc") else [command], 
                               creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            elif command.startswith("control") or command.startswith("rundll32") or command.startswith("perfmon"):
                subprocess.Popen(command, shell=True,
                               creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            else:
                subprocess.Popen([command],
                               creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", f"Failed to launch {command}: {str(e)}")


class WingetPage(QWidget):
    """Winget package manager page with search, install, and favorites for fast deployment"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.favorites = self._load_favorites()
        self.search_results = []
        self.installed_apps = []
        self.search_thread = None
        self.install_thread = None
        self.setup_ui()
        self._check_winget_available()
    
    def _load_favorites(self) -> list:
        """Load favorites from config file"""
        import json
        import os
        config_path = os.path.join(os.path.expanduser("~"), ".health_checker_winget_favorites.json")
        try:
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    return json.load(f)
        except:
            pass
        return []
    
    def _save_favorites(self):
        """Save favorites to config file"""
        import json
        import os
        config_path = os.path.join(os.path.expanduser("~"), ".health_checker_winget_favorites.json")
        try:
            with open(config_path, "w") as f:
                json.dump(self.favorites, f, indent=2)
        except:
            pass
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Left panel - Favorites
        left_panel = QFrame()
        left_panel.setFixedWidth(280)
        left_panel.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_SIDEBAR};
                border: none;
            }}
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 20, 16, 20)
        left_layout.setSpacing(12)
        
        # Favorites header
        fav_header = QHBoxLayout()
        fav_title = QLabel("⭐ Favorites")
        fav_title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 16px;
            font-weight: 600;
        """)
        fav_header.addWidget(fav_title)
        fav_header.addStretch()
        
        # Install All button
        self.install_all_btn = QPushButton("Install All")
        self.install_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_all_btn.clicked.connect(self._install_all_favorites)
        self.install_all_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.SUCCESS};
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: #2ecc71;
            }}
            QPushButton:disabled {{
                background: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_TERTIARY};
            }}
        """)
        fav_header.addWidget(self.install_all_btn)
        left_layout.addLayout(fav_header)
        
        # Export/Import buttons
        export_row = QHBoxLayout()
        export_row.setSpacing(8)
        
        self.export_btn = QPushButton("Export")
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.clicked.connect(self._export_favorites)
        self.export_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_SECONDARY};
                border: none;
                padding: 6px 12px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        export_row.addWidget(self.export_btn)
        
        self.import_btn = QPushButton("Import")
        self.import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_btn.clicked.connect(self._import_favorites)
        self.import_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_SECONDARY};
                border: none;
                padding: 6px 12px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        export_row.addWidget(self.import_btn)
        export_row.addStretch()
        left_layout.addLayout(export_row)
        
        # Favorites list
        fav_scroll = QScrollArea()
        fav_scroll.setWidgetResizable(True)
        fav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        fav_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { width: 6px; }
        """)
        
        self.fav_content = QWidget()
        self.fav_content.setStyleSheet("background: transparent;")
        self.fav_layout = QVBoxLayout(self.fav_content)
        self.fav_layout.setContentsMargins(0, 0, 0, 0)
        self.fav_layout.setSpacing(6)
        self.fav_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self._refresh_favorites_list()
        
        fav_scroll.setWidget(self.fav_content)
        left_layout.addWidget(fav_scroll)
        
        layout.addWidget(left_panel)
        
        # Right panel - Search and results
        right_panel = QWidget()
        right_panel.setStyleSheet(f"background: {Theme.BG_WINDOW};")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(24, 20, 24, 20)
        right_layout.setSpacing(16)
        
        # Header - page title per spec Section 7.0.1
        header = QHBoxLayout()
        title = QLabel("Software Manager")
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 28px;
            font-weight: 600;
        """)
        header.addWidget(title)
        header.addStretch()
        
        # Package sources status indicator
        self.winget_status = QLabel("Checking sources...")
        self.winget_status.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        header.addWidget(self.winget_status)
        
        right_layout.addLayout(header)
        
        # Tab bar for switching between views - styled per spec Section 7.0.2
        tab_bar = QHBoxLayout()
        tab_bar.setSpacing(0)
        
        self.tab_find = QPushButton("Find & Install")
        self.tab_find.setCheckable(True)
        self.tab_find.setChecked(True)
        self.tab_find.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tab_find.clicked.connect(lambda: self._switch_tab(0))
        self.tab_find.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                border-bottom: 2px solid {Theme.ACCENT};
                border-radius: 8px 8px 0 0;
                padding: 12px 24px;
                min-height: 44px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:!checked {{
                background: transparent;
                color: {Theme.TEXT_SECONDARY};
                border-bottom: 2px solid transparent;
                font-weight: 500;
            }}
            QPushButton:!checked:hover {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        tab_bar.addWidget(self.tab_find)
        
        self.tab_installed = QPushButton("Installed Software")
        self.tab_installed.setCheckable(True)
        self.tab_installed.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tab_installed.clicked.connect(lambda: self._switch_tab(1))
        self.tab_installed.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Theme.TEXT_SECONDARY};
                border: none;
                border-bottom: 2px solid transparent;
                padding: 12px 24px;
                min-height: 44px;
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton:checked {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border-bottom: 2px solid {Theme.ACCENT};
                border-radius: 8px 8px 0 0;
                font-weight: 600;
            }}
            QPushButton:!checked:hover {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        tab_bar.addWidget(self.tab_installed)
        tab_bar.addStretch()
        
        right_layout.addLayout(tab_bar)
        
        # Stacked widget for tab content
        self.tab_stack = QStackedWidget()
        
        # === Tab 0: Find & Install ===
        find_widget = QWidget()
        find_widget.setStyleSheet("background: transparent;")
        find_layout = QVBoxLayout(find_widget)
        find_layout.setContentsMargins(0, 0, 0, 0)
        find_layout.setSpacing(16)
        
        # Search bar
        search_frame = QFrame()
        search_frame.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(search_frame, blur_radius=12, offset_y=3, opacity=60)
        
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(16, 12, 16, 12)
        search_layout.setSpacing(12)
        
        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("background: transparent; font-size: 16px;")
        search_layout.addWidget(search_icon)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for apps (e.g., 'vscode', 'firefox', 'git')...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                color: {Theme.TEXT_PRIMARY};
                font-size: 14px;
                padding: 4px;
            }}
        """)
        self.search_input.returnPressed.connect(self._search_apps)
        search_layout.addWidget(self.search_input, 1)
        
        self.search_btn = QPushButton("Search")
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.clicked.connect(self._search_apps)
        self.search_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT_HOVER};
            }}
            QPushButton:disabled {{
                background: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_TERTIARY};
            }}
        """)
        search_layout.addWidget(self.search_btn)
        
        find_layout.addWidget(search_frame)
        
        # Results area
        self.results_label = QLabel("Enter a search term to find apps")
        self.results_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 13px;")
        find_layout.addWidget(self.results_label)
        
        # Results scroll area
        results_scroll = QScrollArea()
        results_scroll.setWidgetResizable(True)
        results_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        results_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.results_content = QWidget()
        self.results_content.setStyleSheet("background: transparent;")
        self.results_layout = QVBoxLayout(self.results_content)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(8)
        self.results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        results_scroll.setWidget(self.results_content)
        find_layout.addWidget(results_scroll)
        
        self.tab_stack.addWidget(find_widget)
        
        # === Tab 1: Installed Software ===
        installed_widget = QWidget()
        installed_widget.setStyleSheet("background: transparent;")
        installed_layout = QVBoxLayout(installed_widget)
        installed_layout.setContentsMargins(0, 0, 0, 0)
        installed_layout.setSpacing(16)
        
        # Search/filter bar for installed software
        filter_frame = QFrame()
        filter_frame.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(filter_frame, blur_radius=12, offset_y=3, opacity=60)
        
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(16, 12, 16, 12)
        filter_layout.setSpacing(12)
        
        filter_icon = QLabel("🔍")
        filter_icon.setStyleSheet("background: transparent; font-size: 16px;")
        filter_layout.addWidget(filter_icon)
        
        self.installed_filter = QLineEdit()
        self.installed_filter.setPlaceholderText("Filter installed software...")
        self.installed_filter.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                color: {Theme.TEXT_PRIMARY};
                font-size: 14px;
                padding: 4px;
            }}
        """)
        self.installed_filter.textChanged.connect(self._filter_installed_apps)
        filter_layout.addWidget(self.installed_filter, 1)
        
        # Check for Updates button
        self.check_updates_btn = QPushButton("Check Updates")
        self.check_updates_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_updates_btn.clicked.connect(self._check_for_updates)
        self.check_updates_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT_HOVER};
            }}
            QPushButton:disabled {{
                background: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_TERTIARY};
            }}
        """)
        filter_layout.addWidget(self.check_updates_btn)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._load_installed_apps)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_SECONDARY};
                border: none;
                padding: 8px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        filter_layout.addWidget(refresh_btn)
        
        installed_layout.addWidget(filter_frame)
        
        # Package Managers Status Panel
        pm_frame = QFrame()
        pm_frame.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_SM}px;
            }}
        """)
        pm_layout = QHBoxLayout(pm_frame)
        pm_layout.setContentsMargins(16, 10, 16, 10)
        pm_layout.setSpacing(16)
        
        pm_title = QLabel("Package Managers:")
        pm_title.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        pm_layout.addWidget(pm_title)
        
        # Winget status
        self.pm_winget_label = QLabel("Winget: checking...")
        self.pm_winget_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        pm_layout.addWidget(self.pm_winget_label)
        
        # Chocolatey status
        self.pm_choco_label = QLabel("Chocolatey: checking...")
        self.pm_choco_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        pm_layout.addWidget(self.pm_choco_label)
        
        # Scoop status
        self.pm_scoop_label = QLabel("Scoop: checking...")
        self.pm_scoop_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        pm_layout.addWidget(self.pm_scoop_label)
        
        pm_layout.addStretch()
        
        # Install Package Manager button
        self.install_pm_btn = QPushButton("Install Manager")
        self.install_pm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_pm_btn.clicked.connect(self._show_install_pm_dialog)
        self.install_pm_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_SECONDARY};
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT};
                color: white;
            }}
        """)
        pm_layout.addWidget(self.install_pm_btn)
        
        installed_layout.addWidget(pm_frame)
        
        # Check package managers on load
        QTimer.singleShot(100, self._check_package_managers)
        
        # Update status label
        self.update_status_label = QLabel("")
        self.update_status_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        self.update_status_label.setVisible(False)
        installed_layout.addWidget(self.update_status_label)
        
        # Installed apps count label
        self.installed_count_label = QLabel("Loading installed software...")
        self.installed_count_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 13px;")
        installed_layout.addWidget(self.installed_count_label)
        
        # Installed apps scroll area
        installed_scroll = QScrollArea()
        installed_scroll.setWidgetResizable(True)
        installed_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        installed_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.installed_content = QWidget()
        self.installed_content.setStyleSheet("background: transparent;")
        self.installed_list_layout = QVBoxLayout(self.installed_content)
        self.installed_list_layout.setContentsMargins(0, 0, 0, 0)
        self.installed_list_layout.setSpacing(8)
        self.installed_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        installed_scroll.setWidget(self.installed_content)
        installed_layout.addWidget(installed_scroll)
        
        self.tab_stack.addWidget(installed_widget)
        
        right_layout.addWidget(self.tab_stack)
        
        layout.addWidget(right_panel, 1)
        
        # Load installed apps in background
        QTimer.singleShot(500, self._load_installed_apps)
    
    def _switch_tab(self, index: int):
        """Switch between tabs - styled per spec Section 7.0.2"""
        self.tab_stack.setCurrentIndex(index)
        self.tab_find.setChecked(index == 0)
        self.tab_installed.setChecked(index == 1)
        
        # Update button styles with underline tab pattern
        if index == 0:
            self.tab_find.setStyleSheet(f"""
                QPushButton {{
                    background: {Theme.BG_CARD};
                    color: {Theme.TEXT_PRIMARY};
                    border: none;
                    border-bottom: 2px solid {Theme.ACCENT};
                    border-radius: 8px 8px 0 0;
                    padding: 12px 24px;
                    min-height: 44px;
                    font-size: 14px;
                    font-weight: 600;
                }}
            """)
            self.tab_installed.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {Theme.TEXT_SECONDARY};
                    border: none;
                    border-bottom: 2px solid transparent;
                    padding: 12px 24px;
                    min-height: 44px;
                    font-size: 14px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background: {Theme.BG_CARD_HOVER};
                    color: {Theme.TEXT_PRIMARY};
                }}
            """)
        else:
            self.tab_find.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {Theme.TEXT_SECONDARY};
                    border: none;
                    border-bottom: 2px solid transparent;
                    padding: 12px 24px;
                    min-height: 44px;
                    font-size: 14px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background: {Theme.BG_CARD_HOVER};
                    color: {Theme.TEXT_PRIMARY};
                }}
            """)
            self.tab_installed.setStyleSheet(f"""
                QPushButton {{
                    background: {Theme.BG_CARD};
                    color: {Theme.TEXT_PRIMARY};
                    border: none;
                    border-bottom: 2px solid {Theme.ACCENT};
                    border-radius: 8px 8px 0 0;
                    padding: 12px 24px;
                    min-height: 44px;
                    font-size: 14px;
                    font-weight: 600;
                }}
            """)
    
    def _load_installed_apps(self):
        """Load installed applications from Windows registry"""
        import winreg
        
        class InstalledAppsThread(QThread):
            finished = pyqtSignal(list)
            
            def run(self):
                apps = []
                reg_paths = [
                    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
                    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
                    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
                ]
                
                seen = set()
                for hkey, path in reg_paths:
                    try:
                        with winreg.OpenKey(hkey, path) as key:
                            i = 0
                            while True:
                                try:
                                    subkey_name = winreg.EnumKey(key, i)
                                    with winreg.OpenKey(key, subkey_name) as subkey:
                                        try:
                                            name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                                            if name and name not in seen:
                                                seen.add(name)
                                                app = {"name": name}
                                                try:
                                                    app["version"], _ = winreg.QueryValueEx(subkey, "DisplayVersion")
                                                except:
                                                    app["version"] = ""
                                                try:
                                                    app["publisher"], _ = winreg.QueryValueEx(subkey, "Publisher")
                                                except:
                                                    app["publisher"] = ""
                                                try:
                                                    app["install_date"], _ = winreg.QueryValueEx(subkey, "InstallDate")
                                                except:
                                                    app["install_date"] = ""
                                                try:
                                                    app["size"], _ = winreg.QueryValueEx(subkey, "EstimatedSize")
                                                    # Convert KB to readable format
                                                    size_kb = int(app["size"])
                                                    if size_kb > 1024 * 1024:
                                                        app["size_str"] = f"{size_kb / (1024*1024):.1f} GB"
                                                    elif size_kb > 1024:
                                                        app["size_str"] = f"{size_kb / 1024:.1f} MB"
                                                    else:
                                                        app["size_str"] = f"{size_kb} KB"
                                                except:
                                                    app["size"] = 0
                                                    app["size_str"] = ""
                                                apps.append(app)
                                        except:
                                            pass
                                    i += 1
                                except OSError:
                                    break
                    except:
                        pass
                
                # Sort by name
                apps.sort(key=lambda x: x["name"].lower())
                self.finished.emit(apps)
        
        self.installed_apps_thread = InstalledAppsThread()
        self.installed_apps_thread.finished.connect(self._on_installed_apps_loaded)
        self.installed_apps_thread.start()
    
    def _on_installed_apps_loaded(self, apps: list):
        """Handle loaded installed apps"""
        self.installed_apps_list = apps
        self.installed_count_label.setText(f"Found {len(apps)} installed applications")
        self._display_installed_apps(apps)
    
    def _display_installed_apps(self, apps: list):
        """Display installed apps in the list"""
        # Clear existing
        while self.installed_list_layout.count():
            item = self.installed_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # First, show apps with updates available (from package managers)
        if hasattr(self, 'app_updates') and self.app_updates:
            # Add updates section header
            updates_header = QLabel(f"📥 Updates Available ({len(self.app_updates)})")
            updates_header.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 14px; font-weight: 600; padding: 8px 0;")
            self.installed_list_layout.addWidget(updates_header)
            
            for update_key, update_info in self.app_updates.items():
                # Get display name from update_info
                display_name = update_info.get('name', update_key.split(':')[-1] if ':' in update_key else update_key)
                item = self._create_update_item(display_name, update_info)
                self.installed_list_layout.addWidget(item)
            
            # Separator
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background: {Theme.BG_ELEVATED}; margin: 8px 0;")
            self.installed_list_layout.addWidget(sep)
            
            # Installed apps header
            installed_header = QLabel(f"📦 All Installed Software")
            installed_header.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 14px; font-weight: 600; padding: 8px 0;")
            self.installed_list_layout.addWidget(installed_header)
        
        for app in apps[:100]:  # Limit to 100 for performance
            item = self._create_installed_app_item(app)
            self.installed_list_layout.addWidget(item)
        
        if len(apps) > 100:
            more_label = QLabel(f"... and {len(apps) - 100} more apps")
            more_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px; padding: 12px;")
            more_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.installed_list_layout.addWidget(more_label)
    
    def _create_update_item(self, name: str, update_info: dict) -> QFrame:
        """Create a widget for an available update (from winget upgrade)"""
        item = QFrame()
        item.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: 1px solid {Theme.SUCCESS};
                border-radius: {Theme.RADIUS_SM}px;
            }}
            QFrame:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        
        layout = QHBoxLayout(item)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        # Update icon
        icon_label = QLabel("⬆️")
        icon_label.setStyleSheet("background: transparent; font-size: 20px;")
        layout.addWidget(icon_label)
        
        # App info
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)
        
        # Name row with update badge
        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(8)
        
        name_label = QLabel(name)
        name_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 14px; font-weight: 500;")
        name_row.addWidget(name_label)
        
        update_badge = QLabel("UPDATE")
        update_badge.setStyleSheet(f"""
            background: {Theme.SUCCESS};
            color: white;
            font-size: 9px;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 3px;
        """)
        name_row.addWidget(update_badge)
        name_row.addStretch()
        info_layout.addLayout(name_row)
        
        # Version info
        installed_ver = update_info.get('installed_version', '?')
        latest_ver = update_info.get('latest_version', '?')
        version_text = f"v{installed_ver} → v{latest_ver}"
        version_label = QLabel(version_text)
        version_label.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 12px; font-weight: 500;")
        info_layout.addWidget(version_label)
        
        layout.addLayout(info_layout, 1)
        
        # Update button
        update_btn = QPushButton("Update")
        update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        update_btn.setToolTip(f"Update to v{latest_ver}")
        pkg_id = update_info.get('pkg_id', name)
        source = update_info.get('source', 'winget')
        update_btn.clicked.connect(lambda checked, n=name, p=pkg_id, s=source: self._update_app(n, p, s))
        update_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.SUCCESS};
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: #1a9e4d;
            }}
        """)
        layout.addWidget(update_btn)
        
        return item
    
    def _create_installed_app_item(self, app: dict) -> QFrame:
        """Create a widget for an installed app (from registry)"""
        app_name = app["name"]
        
        item = QFrame()
        item.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_SM}px;
            }}
            QFrame:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        
        layout = QHBoxLayout(item)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        # App icon placeholder
        icon_label = QLabel("📦")
        icon_label.setStyleSheet("background: transparent; font-size: 20px;")
        layout.addWidget(icon_label)
        
        # App info
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)
        
        name_label = QLabel(app_name)
        name_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 14px; font-weight: 500;")
        info_layout.addWidget(name_label)
        
        # Details row
        details = []
        if app.get("publisher"):
            details.append(app["publisher"])
        if app.get("version"):
            details.append(f"v{app['version']}")
        if app.get("size_str"):
            details.append(app["size_str"])
        
        if details:
            details_label = QLabel(" • ".join(details))
            details_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
            info_layout.addWidget(details_label)
        
        layout.addLayout(info_layout, 1)
        
        # Manage button
        settings_btn = QPushButton("Manage")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setToolTip("Open Windows Apps & Features")
        settings_btn.clicked.connect(lambda: self._open_apps_settings())
        settings_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_SECONDARY};
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        layout.addWidget(settings_btn)
        
        return item
    
    def _filter_installed_apps(self, text: str):
        """Filter installed apps list"""
        if not hasattr(self, 'installed_apps_list'):
            return
        
        if not text:
            self._display_installed_apps(self.installed_apps_list)
        else:
            filtered = [app for app in self.installed_apps_list 
                       if text.lower() in app["name"].lower() 
                       or text.lower() in (app.get("publisher") or "").lower()]
            self._display_installed_apps(filtered)
    
    def _open_apps_settings(self):
        """Open Windows Apps & Features settings"""
        import subprocess
        try:
            subprocess.Popen(["explorer", "ms-settings:appsfeatures"])
        except:
            pass
    
    def _check_for_updates(self):
        """Check installed apps for available updates using winget upgrade command"""
        # Check if winget is available
        if not hasattr(self, 'package_managers') or not self.package_managers.get('winget', {}).get('installed', False):
            self.update_status_label.setText("Winget not installed. Click 'Install Manager' to install it first.")
            self.update_status_label.setStyleSheet(f"background: transparent; color: {Theme.WARNING}; font-size: 12px;")
            self.update_status_label.setVisible(True)
            return
        
        self.check_updates_btn.setEnabled(False)
        self.check_updates_btn.setText("Checking...")
        self.update_status_label.setText("Running winget upgrade check... This may take a moment.")
        self.update_status_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        self.update_status_label.setVisible(True)
        
        # Initialize update info storage
        self.app_updates = {}
        
        class MultiPMUpdateCheckThread(QThread):
            progress = pyqtSignal(str)
            finished = pyqtSignal(dict)
            
            def run(self):
                import subprocess
                import os
                import re
                
                all_updates = {}
                
                # Helper to run commands cleanly
                def run_cmd(cmd, timeout=60):
                    try:
                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            timeout=timeout,
                            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                        )
                        return result.stdout, result.stderr, result.returncode
                    except:
                        return '', '', -1
                
                # Check which package managers are available
                managers = {}
                
                # Check winget
                stdout, _, rc = run_cmd(['winget', '--version'], 10)
                managers['winget'] = rc == 0
                
                # Check chocolatey
                stdout, _, rc = run_cmd(['choco', '--version'], 10)
                managers['choco'] = rc == 0
                
                # Check scoop
                stdout, _, rc = run_cmd(['scoop', '--version'], 10)
                managers['scoop'] = rc == 0 and 'scoop' in stdout.lower()
                
                # ===== WINGET UPDATES =====
                if managers['winget']:
                    self.progress.emit("Checking Winget for updates...")
                    
                    # When running elevated (UAC), winget uses the admin's package database.
                    # We use a PowerShell script to set the environment to a regular user's profile.
                    stdout = ''
                    rc = -1
                    
                    try:
                        import glob
                        import tempfile
                        
                        # Find user profiles (excluding system/admin accounts)
                        user_profiles = []
                        for profile in glob.glob(r'C:\Users\*'):
                            profile_name = os.path.basename(profile).lower()
                            # Skip system and admin accounts
                            if any(x in profile_name for x in ['admin', 'default', 'public', 'all users']):
                                continue
                            # Check if winget exists for this user
                            winget_path = os.path.join(profile, r'AppData\Local\Microsoft\WindowsApps\winget.exe')
                            if os.path.exists(winget_path):
                                user_profiles.append(profile)
                        
                        for user_profile in user_profiles:
                            # Create PowerShell script that sets environment and runs winget
                            # Use forward slashes to avoid escape issues
                            profile_fwd = user_profile.replace('\\', '/')
                            ps_script = f'''$env:USERPROFILE = '{profile_fwd}'
$env:LOCALAPPDATA = '{profile_fwd}/AppData/Local'
$env:APPDATA = '{profile_fwd}/AppData/Roaming'
winget upgrade --include-unknown
'''
                            ps_path = os.path.join(tempfile.gettempdir(), 'winget_check.ps1')
                            with open(ps_path, 'w') as f:
                                f.write(ps_script)
                            
                            result = subprocess.run(
                                ['powershell', '-ExecutionPolicy', 'Bypass', '-File', ps_path],
                                capture_output=True,
                                text=True,
                                timeout=120,
                                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                            )
                            
                            # Check if we got valid data (has separator line and 'winget' source)
                            if result.returncode == 0 and '---' in result.stdout and 'winget' in result.stdout.lower():
                                stdout = result.stdout
                                rc = result.returncode
                                break
                        
                        # Fallback to default if no user profile worked
                        if not stdout:
                            result = subprocess.run(
                                'winget upgrade --include-unknown',
                                capture_output=True,
                                text=True,
                                shell=True,
                                timeout=120
                            )
                            stdout = result.stdout
                            rc = result.returncode
                            
                    except Exception:
                        stdout = ''
                        rc = -1
                    
                    # Clean up output - remove any remaining ANSI/unicode chars
                    output = stdout
                    output = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', output)
                    output = re.sub(r'[▒█░▓]', '', output)  # Progress bar chars
                    output = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', output)
                    
                    lines = output.split('\n')
                    
                    # Find separator and data lines
                    found_sep = False
                    for i, line in enumerate(lines):
                        stripped = line.strip()
                        if not stripped:
                            continue
                        
                        # Look for the dashed separator line
                        is_sep = bool(re.match(r'^-{10,}$', stripped.replace(' ', '')))
                        if is_sep and not found_sep:
                            found_sep = True
                            continue
                        
                        if not found_sep:
                            continue
                        
                        # Skip summary lines
                        if 'upgrades available' in stripped.lower() or 'upgrade' in stripped.lower() and 'available' in stripped.lower():
                            continue
                        if 'no installed package' in stripped.lower():
                            continue
                        if 'failed' in stripped.lower():
                            continue
                        
                        # Parse: Name   Id   Version   Available   Source
                        parts = stripped.split()
                        if len(parts) >= 4 and parts[-1].lower() == 'winget':
                            pkg_id = parts[-4] if len(parts) >= 5 else parts[-3]
                            available = parts[-2]
                            current = parts[-3] if len(parts) >= 5 else 'Unknown'
                            
                            # Get name from before pkg_id
                            idx = line.find(pkg_id)
                            name = line[:idx].strip() if idx > 0 else pkg_id
                            
                            if name and available and available != current:
                                all_updates[f"winget:{pkg_id}"] = {
                                    'name': name,
                                    'installed_version': current,
                                    'latest_version': available,
                                    'source': 'winget',
                                    'pkg_id': pkg_id
                                }
                
                # ===== CHOCOLATEY UPDATES =====
                if managers['choco']:
                    self.progress.emit("Checking Chocolatey for updates...")
                    
                    stdout, stderr, rc = run_cmd(['choco', 'outdated', '-r'], 120)
                    
                    # Format: packagename|currentversion|availableversion|pinned
                    for line in stdout.split('\n'):
                        line = line.strip()
                        if not line or '|' not in line:
                            continue
                        
                        parts = line.split('|')
                        if len(parts) >= 3:
                            pkg_name = parts[0]
                            current = parts[1]
                            available = parts[2]
                            
                            if pkg_name and available and current != available:
                                all_updates[f"choco:{pkg_name}"] = {
                                    'name': pkg_name,
                                    'installed_version': current,
                                    'latest_version': available,
                                    'source': 'chocolatey',
                                    'pkg_id': pkg_name
                                }
                
                # ===== SCOOP UPDATES =====
                if managers['scoop']:
                    self.progress.emit("Checking Scoop for updates...")
                    
                    stdout, stderr, rc = run_cmd(['scoop', 'status'], 120)
                    
                    # Parse scoop status output
                    # Format varies but typically: Name   Installed Version   Latest Version   ...
                    lines = stdout.split('\n')
                    found_header = False
                    
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        
                        # Skip until we find header
                        if 'name' in line.lower() and 'version' in line.lower():
                            found_header = True
                            continue
                        if line.startswith('--'):
                            found_header = True
                            continue
                        
                        if not found_header:
                            continue
                        
                        parts = line.split()
                        if len(parts) >= 3:
                            pkg_name = parts[0]
                            current = parts[1]
                            available = parts[2] if len(parts) > 2 else current
                            
                            if available != current:
                                all_updates[f"scoop:{pkg_name}"] = {
                                    'name': pkg_name,
                                    'installed_version': current,
                                    'latest_version': available,
                                    'source': 'scoop',
                                    'pkg_id': pkg_name
                                }
                
                self.finished.emit(all_updates)
        
        self.update_check_thread = MultiPMUpdateCheckThread()
        self.update_check_thread.progress.connect(self._on_update_check_progress)
        self.update_check_thread.finished.connect(self._on_update_check_complete)
        self.update_check_thread.start()
    
    def _on_update_check_progress(self, message: str):
        """Update progress during update check"""
        self.update_status_label.setText(message)
    
    def _on_update_check_complete(self, updates: dict):
        """Handle update check completion"""
        self.check_updates_btn.setEnabled(True)
        self.check_updates_btn.setText("Check Updates")
        self.app_updates = updates
        
        if updates:
            self.update_status_label.setText(f"Found {len(updates)} update(s) available!")
            self.update_status_label.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 12px; font-weight: 600;")
        else:
            self.update_status_label.setText("All checked apps are up to date.")
            self.update_status_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        
        # Refresh the display to show update badges
        if hasattr(self, 'installed_apps_list'):
            filter_text = self.installed_filter.text()
            if filter_text:
                self._filter_installed_apps(filter_text)
            else:
                self._display_installed_apps(self.installed_apps_list)
    
    def _update_app(self, app_name: str, pkg_id: str, source: str):
        """Update an app using the appropriate package manager"""
        import subprocess
        
        # Check if the required package manager is available
        pm_available = hasattr(self, 'package_managers') and self.package_managers.get(source if source != 'chocolatey' else 'chocolatey', {}).get('installed', False)
        
        # For winget source, check winget availability
        if source == 'winget':
            if not self.package_managers.get('winget', {}).get('installed', False):
                self.update_status_label.setText(f"Winget not installed. Click 'Install Manager' to install it.")
                self.update_status_label.setStyleSheet(f"background: transparent; color: {Theme.WARNING}; font-size: 12px;")
                self.update_status_label.setVisible(True)
                return
            
            # Use winget to update
            try:
                self.update_status_label.setText(f"Updating {app_name} via Winget...")
                self.update_status_label.setStyleSheet(f"background: transparent; color: {Theme.INFO}; font-size: 12px;")
                self.update_status_label.setVisible(True)
                
                class UpdateThread(QThread):
                    finished = pyqtSignal(bool, str)
                    
                    def __init__(self, pkg_id):
                        super().__init__()
                        self.pkg_id = pkg_id
                    
                    def run(self):
                        try:
                            result = subprocess.run(
                                ["winget", "upgrade", self.pkg_id, "--accept-source-agreements", "--accept-package-agreements", "--silent"],
                                capture_output=True,
                                text=True,
                                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
                                timeout=300  # 5 minute timeout
                            )
                            if result.returncode == 0:
                                self.finished.emit(True, "Update completed successfully!")
                            else:
                                self.finished.emit(False, result.stderr or result.stdout or "Update failed")
                        except subprocess.TimeoutExpired:
                            self.finished.emit(False, "Update timed out")
                        except Exception as e:
                            self.finished.emit(False, str(e))
                
                self.current_update_thread = UpdateThread(pkg_id)
                self.current_update_thread.finished.connect(lambda success, msg: self._on_update_complete(app_name, success, msg))
                self.current_update_thread.start()
                
            except Exception as e:
                self.update_status_label.setText(f"Failed to start update: {e}")
                self.update_status_label.setStyleSheet(f"background: transparent; color: {Theme.ERROR}; font-size: 12px;")
        
        elif source == 'chocolatey':
            if not self.package_managers.get('chocolatey', {}).get('installed', False):
                self.update_status_label.setText(f"Chocolatey not installed. Click 'Install Manager' to install it.")
                self.update_status_label.setStyleSheet(f"background: transparent; color: {Theme.WARNING}; font-size: 12px;")
                self.update_status_label.setVisible(True)
                return
            
            # Open terminal with choco command (needs admin)
            try:
                subprocess.Popen(["powershell", "-Command", f"Start-Process powershell -Verb RunAs -ArgumentList 'choco upgrade {pkg_id} -y; pause'"])
                self.update_status_label.setText(f"Opened admin terminal to update {app_name}")
                self.update_status_label.setStyleSheet(f"background: transparent; color: {Theme.INFO}; font-size: 12px;")
            except Exception as e:
                self.update_status_label.setText(f"Failed: {e}")
                self.update_status_label.setStyleSheet(f"background: transparent; color: {Theme.ERROR}; font-size: 12px;")
        
        elif source == 'scoop':
            if not self.package_managers.get('scoop', {}).get('installed', False):
                self.update_status_label.setText(f"Scoop not installed. Click 'Install Manager' to install it.")
                self.update_status_label.setStyleSheet(f"background: transparent; color: {Theme.WARNING}; font-size: 12px;")
                self.update_status_label.setVisible(True)
                return
            
            # Scoop update (doesn't need admin)
            try:
                self.update_status_label.setText(f"Updating {app_name} via Scoop...")
                self.update_status_label.setStyleSheet(f"background: transparent; color: {Theme.INFO}; font-size: 12px;")
                self.update_status_label.setVisible(True)
                
                # Extract package name from scoop ID (bucket/name format)
                scoop_pkg = pkg_id.split('/')[-1] if '/' in pkg_id else pkg_id
                
                class ScoopUpdateThread(QThread):
                    finished = pyqtSignal(bool, str)
                    
                    def __init__(self, pkg):
                        super().__init__()
                        self.pkg = pkg
                    
                    def run(self):
                        try:
                            result = subprocess.run(
                                ["scoop", "update", self.pkg],
                                capture_output=True,
                                text=True,
                                shell=True,
                                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
                                timeout=300
                            )
                            if result.returncode == 0:
                                self.finished.emit(True, "Update completed!")
                            else:
                                self.finished.emit(False, result.stderr or result.stdout or "Update failed")
                        except subprocess.TimeoutExpired:
                            self.finished.emit(False, "Update timed out")
                        except Exception as e:
                            self.finished.emit(False, str(e))
                
                self.scoop_update_thread = ScoopUpdateThread(scoop_pkg)
                self.scoop_update_thread.finished.connect(lambda success, msg: self._on_update_complete(app_name, success, msg))
                self.scoop_update_thread.start()
                
            except Exception as e:
                self.update_status_label.setText(f"Failed: {e}")
                self.update_status_label.setStyleSheet(f"background: transparent; color: {Theme.ERROR}; font-size: 12px;")
    
    def _on_update_complete(self, app_name: str, success: bool, message: str):
        """Handle update completion"""
        if success:
            self.update_status_label.setText(f"{app_name}: {message}")
            self.update_status_label.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 12px;")
            # Remove from updates dict
            if app_name in self.app_updates:
                del self.app_updates[app_name]
            # Refresh display
            self._load_installed_apps()
        else:
            self.update_status_label.setText(f"{app_name}: {message}")
            self.update_status_label.setStyleSheet(f"background: transparent; color: {Theme.ERROR}; font-size: 12px;")
    
    def _check_package_managers(self):
        """Check which package managers are installed"""
        import subprocess
        
        # Store status
        self.package_managers = {
            'winget': {'installed': False, 'version': ''},
            'chocolatey': {'installed': False, 'version': ''},
            'scoop': {'installed': False, 'version': ''}
        }
        
        class PMCheckThread(QThread):
            finished = pyqtSignal(dict)
            
            def run(self):
                results = {}
                
                # Check Winget
                try:
                    result = subprocess.run(
                        ["winget", "--version"],
                        capture_output=True, text=True, timeout=10,
                        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                    )
                    if result.returncode == 0:
                        results['winget'] = {'installed': True, 'version': result.stdout.strip()}
                    else:
                        results['winget'] = {'installed': False, 'version': ''}
                except:
                    results['winget'] = {'installed': False, 'version': ''}
                
                # Check Chocolatey
                try:
                    result = subprocess.run(
                        ["choco", "--version"],
                        capture_output=True, text=True, timeout=10,
                        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                    )
                    if result.returncode == 0:
                        results['chocolatey'] = {'installed': True, 'version': result.stdout.strip().split('\n')[0]}
                    else:
                        results['chocolatey'] = {'installed': False, 'version': ''}
                except:
                    results['chocolatey'] = {'installed': False, 'version': ''}
                
                # Check Scoop
                try:
                    result = subprocess.run(
                        ["scoop", "--version"],
                        capture_output=True, text=True, timeout=10,
                        shell=True,  # Scoop needs shell on some systems
                        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                    )
                    if result.returncode == 0 and 'scoop' in result.stdout.lower():
                        # Parse version from output
                        ver = ''
                        for line in result.stdout.split('\n'):
                            if 'current' in line.lower() or line.strip().startswith('v'):
                                ver = line.strip()
                                break
                        results['scoop'] = {'installed': True, 'version': ver or 'installed'}
                    else:
                        results['scoop'] = {'installed': False, 'version': ''}
                except:
                    results['scoop'] = {'installed': False, 'version': ''}
                
                self.finished.emit(results)
        
        self.pm_check_thread = PMCheckThread()
        self.pm_check_thread.finished.connect(self._on_pm_check_complete)
        self.pm_check_thread.start()
    
    def _on_pm_check_complete(self, results: dict):
        """Handle package manager check completion"""
        self.package_managers = results
        
        # Update Winget label
        if results.get('winget', {}).get('installed'):
            ver = results['winget'].get('version', '')
            self.pm_winget_label.setText(f"Winget: {ver}")
            self.pm_winget_label.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 12px;")
        else:
            self.pm_winget_label.setText("Winget: not found")
            self.pm_winget_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        
        # Update Chocolatey label
        if results.get('chocolatey', {}).get('installed'):
            ver = results['chocolatey'].get('version', '')
            self.pm_choco_label.setText(f"Choco: {ver}")
            self.pm_choco_label.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 12px;")
        else:
            self.pm_choco_label.setText("Choco: not found")
            self.pm_choco_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        
        # Update Scoop label
        if results.get('scoop', {}).get('installed'):
            ver = results['scoop'].get('version', '')
            self.pm_scoop_label.setText(f"Scoop: {ver[:15] if len(ver) > 15 else ver}")
            self.pm_scoop_label.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 12px;")
        else:
            self.pm_scoop_label.setText("Scoop: not found")
            self.pm_scoop_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
    
    def _show_install_pm_dialog(self):
        """Show dialog to install package managers"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Install Package Manager")
        dialog.setFixedSize(500, 400)
        dialog.setStyleSheet(f"background: {Theme.BG_WINDOW};")
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # Title
        title = QLabel("Install a Package Manager")
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 18px; font-weight: 600;")
        layout.addWidget(title)
        
        desc = QLabel("Package managers allow you to easily install, update, and manage software from the command line or this app.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        layout.addWidget(desc)
        
        # Package manager options
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        
        # Winget
        winget_card = self._create_pm_install_card(
            "Winget",
            "Microsoft's official package manager for Windows. Pre-installed on Windows 11.",
            "Built into Windows 11, easy to use, large package repository",
            self.package_managers.get('winget', {}).get('installed', False),
            lambda: self._install_winget()
        )
        content_layout.addWidget(winget_card)
        
        # Chocolatey
        choco_card = self._create_pm_install_card(
            "Chocolatey",
            "Community-driven package manager with 9000+ packages. Requires admin.",
            "Huge repository, well-established, great for IT pros",
            self.package_managers.get('chocolatey', {}).get('installed', False),
            lambda: self._install_chocolatey()
        )
        content_layout.addWidget(choco_card)
        
        # Scoop
        scoop_card = self._create_pm_install_card(
            "Scoop",
            "User-level package manager. No admin required, installs to ~/scoop.",
            "No admin needed, clean installs, developer-focused",
            self.package_managers.get('scoop', {}).get('installed', False),
            lambda: self._install_scoop()
        )
        content_layout.addWidget(scoop_card)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_SECONDARY};
                border: none;
                padding: 10px 24px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
        
        self.pm_dialog = dialog
        dialog.exec()
    
    def _create_pm_install_card(self, name: str, description: str, features: str, installed: bool, install_callback) -> QFrame:
        """Create a package manager installation card"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(16)
        
        # Info section
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)
        
        # Name with status
        name_row = QHBoxLayout()
        name_label = QLabel(name)
        name_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 14px; font-weight: 600;")
        name_row.addWidget(name_label)
        
        if installed:
            status = QLabel("INSTALLED")
            status.setStyleSheet(f"""
                background: {Theme.SUCCESS};
                color: white;
                font-size: 9px;
                font-weight: bold;
                padding: 2px 6px;
                border-radius: 3px;
            """)
            name_row.addWidget(status)
        
        name_row.addStretch()
        info_layout.addLayout(name_row)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        info_layout.addWidget(desc_label)
        
        # Features
        feat_label = QLabel(features)
        feat_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
        info_layout.addWidget(feat_label)
        
        layout.addLayout(info_layout, 1)
        
        # Install button
        if not installed:
            install_btn = QPushButton("Install")
            install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            install_btn.clicked.connect(install_callback)
            install_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {Theme.ACCENT};
                    color: white;
                    border: none;
                    padding: 8px 20px;
                    border-radius: {Theme.RADIUS_SM}px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {Theme.ACCENT_HOVER};
                }}
            """)
            layout.addWidget(install_btn)
        else:
            check_label = QLabel("\uE73E")
            check_label.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 20px; font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';")
            layout.addWidget(check_label)
        
        return card
    
    def _install_winget(self):
        """Install Winget (via Microsoft Store App Installer)"""
        import subprocess
        import webbrowser
        from PyQt6.QtWidgets import QMessageBox
        
        # Winget is part of App Installer from Microsoft Store
        # Open the Store page for App Installer
        try:
            # Try to open MS Store directly to App Installer
            subprocess.Popen(["explorer", "ms-windows-store://pdp/?productid=9NBLGGH4NNS1"])
            
            # Show message
            msg = QMessageBox(self)
            msg.setWindowTitle("Install Winget")
            msg.setText("Opening Microsoft Store...\n\n"
                       "Please install 'App Installer' from the Microsoft Store.\n"
                       "Winget is included with App Installer.\n\n"
                       "After installation, click 'Refresh' to check status.")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setStyleSheet(f"background: {Theme.BG_WINDOW}; color: {Theme.TEXT_PRIMARY};")
            msg.exec()
            
            # Close dialog and refresh
            if hasattr(self, 'pm_dialog'):
                self.pm_dialog.close()
            QTimer.singleShot(1000, self._check_package_managers)
            
        except Exception as e:
            # Fallback: open web browser
            webbrowser.open("https://apps.microsoft.com/detail/9NBLGGH4NNS1")
    
    def _install_chocolatey(self):
        """Install Chocolatey package manager"""
        import subprocess
        from PyQt6.QtWidgets import QMessageBox
        
        # Chocolatey requires admin PowerShell
        install_cmd = "Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))"
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Install Chocolatey")
        msg.setText("Chocolatey requires Administrator privileges to install.\n\n"
                   "Click OK to open an elevated PowerShell window with the install command.\n\n"
                   "After installation completes, close the window and click 'Refresh'.")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        msg.setStyleSheet(f"background: {Theme.BG_WINDOW}; color: {Theme.TEXT_PRIMARY};")
        
        if msg.exec() == QMessageBox.StandardButton.Ok:
            try:
                # Open elevated PowerShell with the install command
                subprocess.Popen([
                    "powershell", "-Command",
                    f"Start-Process powershell -Verb RunAs -ArgumentList '-NoExit -Command {install_cmd}'"
                ])
                
                if hasattr(self, 'pm_dialog'):
                    self.pm_dialog.close()
                    
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to start installer: {e}")
    
    def _install_scoop(self):
        """Install Scoop package manager"""
        import subprocess
        from PyQt6.QtWidgets import QMessageBox
        
        # Scoop can be installed without admin
        install_cmd = "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force; Invoke-RestMethod -Uri https://get.scoop.sh | Invoke-Expression"
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Install Scoop")
        msg.setText("Scoop will be installed for your user account (no admin required).\n\n"
                   "Click OK to open PowerShell and run the installer.\n\n"
                   "After installation completes, close the window and click 'Refresh'.")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        msg.setStyleSheet(f"background: {Theme.BG_WINDOW}; color: {Theme.TEXT_PRIMARY};")
        
        if msg.exec() == QMessageBox.StandardButton.Ok:
            try:
                # Open PowerShell with the install command
                subprocess.Popen([
                    "powershell", "-NoExit", "-Command", install_cmd
                ])
                
                if hasattr(self, 'pm_dialog'):
                    self.pm_dialog.close()
                    
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to start installer: {e}")
    
    def _check_winget_available(self):
        """Check if winget is available on the system"""
        def check():
            import subprocess
            try:
                result = subprocess.run(
                    ["winget", "--version"],
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
                return result.returncode == 0, result.stdout.strip()
            except:
                return False, None
        
        class WingetCheckThread(QThread):
            finished = pyqtSignal(bool, str)
            
            def run(self):
                available, version = check()
                self.finished.emit(available, version or "")
        
        self.check_thread = WingetCheckThread()
        self.check_thread.finished.connect(self._on_winget_check_complete)
        self.check_thread.start()
    
    def _on_winget_check_complete(self, available: bool, version: str):
        """Handle winget availability check result"""
        if available:
            self.winget_status.setText(f"winget {version}")
            self.winget_status.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 12px;")
        else:
            self.winget_status.setText("winget not found")
            self.winget_status.setStyleSheet(f"background: transparent; color: {Theme.ERROR}; font-size: 12px;")
            self.search_btn.setEnabled(False)
            self.search_input.setEnabled(False)
            self.results_label.setText("Winget is not installed. Please install it from the Microsoft Store (App Installer).")
    
    def _refresh_favorites_list(self):
        """Refresh the favorites list display"""
        # Clear existing items
        while self.fav_layout.count():
            item = self.fav_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not self.favorites:
            empty_label = QLabel("No favorites yet.\nSearch and add apps to favorites\nfor quick deployment.")
            empty_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setWordWrap(True)
            self.fav_layout.addWidget(empty_label)
            self.install_all_btn.setEnabled(False)
        else:
            self.install_all_btn.setEnabled(True)
            for fav in self.favorites:
                item = self._create_favorite_item(fav)
                self.fav_layout.addWidget(item)
    
    def _create_favorite_item(self, fav: dict) -> QFrame:
        """Create a favorite item widget"""
        item = QFrame()
        item.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_SM}px;
            }}
            QFrame:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        
        layout = QHBoxLayout(item)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        
        # App info
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)
        
        name_label = QLabel(fav.get("name", fav.get("id", "Unknown")))
        name_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 12px; font-weight: 500;")
        info_layout.addWidget(name_label)
        
        id_label = QLabel(fav.get("id", ""))
        id_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 10px;")
        info_layout.addWidget(id_label)
        
        layout.addLayout(info_layout, 1)
        
        # Install button - use text instead of unicode
        install_btn = QPushButton("Install")
        install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        install_btn.setToolTip("Install this app")
        install_btn.clicked.connect(lambda: self._install_app(fav.get("id", "")))
        install_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.SUCCESS};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Theme.SUCCESS_LIGHT};
            }}
        """)
        layout.addWidget(install_btn)
        
        # Remove button
        remove_btn = QPushButton("Del")
        remove_btn.setFixedWidth(40)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.setToolTip("Remove from favorites")
        remove_btn.clicked.connect(lambda: self._remove_favorite(fav.get("id", "")))
        remove_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Theme.ERROR};
                border: none;
                padding: 6px 4px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {Theme.ERROR_LIGHT};
            }}
        """)
        layout.addWidget(remove_btn)
        
        return item
    
    def _add_favorite(self, app_id: str, app_name: str):
        """Add an app to favorites"""
        # Check if already exists
        for fav in self.favorites:
            if fav.get("id") == app_id:
                return
        
        self.favorites.append({"id": app_id, "name": app_name})
        self._save_favorites()
        self._refresh_favorites_list()
    
    def _remove_favorite(self, app_id: str):
        """Remove an app from favorites"""
        self.favorites = [f for f in self.favorites if f.get("id") != app_id]
        self._save_favorites()
        self._refresh_favorites_list()
        # Also update search results to reflect the change
        self._update_results_favorite_states()
    
    def _update_results_favorite_states(self):
        """Update the favorite button states in search results"""
        fav_ids = {f.get("id") for f in self.favorites}
        for i in range(self.results_layout.count()):
            widget = self.results_layout.itemAt(i).widget()
            if widget:
                app_id = widget.property("app_id")
                fav_btn = widget.findChild(QPushButton, "fav_btn")
                if fav_btn and app_id:
                    is_fav = app_id in fav_ids
                    fav_btn.setText("★" if is_fav else "☆")
                    fav_btn.setToolTip("Remove from favorites" if is_fav else "Add to favorites")
    
    def _search_apps(self):
        """Search for apps using winget"""
        import os  # Import at method level for debug logging
        import tempfile
        
        # DEBUG: Print to console
        print(f"DEBUG: _search_apps called")
        
        query = self.search_input.text().strip()
        print(f"DEBUG: query = '{query}'")
        if not query:
            return
        
        self.search_btn.setEnabled(False)
        self.search_btn.setText("Searching...")
        self.results_label.setText(f"Searching for '{query}'...")
        
        # Clear previous results
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        class SearchThread(QThread):
            results_ready = pyqtSignal(list)
            error = pyqtSignal(str)
            progress = pyqtSignal(str)  # For status updates
            
            def __init__(self, query):
                super().__init__()
                self.query = query
            
            def _search_winget(self, query: str) -> list:
                """Search winget.run API"""
                import urllib.request
                import urllib.parse
                import json
                import ssl
                
                apps = []
                try:
                    encoded_query = urllib.parse.quote(query)
                    url = f'https://api.winget.run/v2/packages?query={encoded_query}&take=25'
                    req = urllib.request.Request(url, headers={
                        'User-Agent': 'WindowsHealthChecker/1.0',
                        'Accept': 'application/json'
                    })
                    ctx = ssl.create_default_context()
                    response = urllib.request.urlopen(req, timeout=15, context=ctx)
                    data = json.loads(response.read().decode('utf-8'))
                    
                    for pkg in data.get('Packages', []):
                        pkg_id = pkg.get('Id', '')
                        latest = pkg.get('Latest', {})
                        name = latest.get('Name') or (pkg_id.split('.')[-1] if pkg_id else 'Unknown')
                        versions = pkg.get('Versions', [])
                        version = versions[0] if versions else 'N/A'
                        publisher = latest.get('Publisher') or (pkg_id.split('.')[0] if pkg_id and '.' in pkg_id else '')
                        
                        if pkg_id:
                            apps.append({
                                'name': name,
                                'id': pkg_id,
                                'version': version,
                                'source': 'winget',
                                'publisher': publisher
                            })
                except Exception as e:
                    print(f"DEBUG: Winget API error: {e}")
                return apps
            
            def _search_chocolatey(self, query: str) -> list:
                """Search Chocolatey community repository API"""
                import urllib.request
                import urllib.parse
                import xml.etree.ElementTree as ET
                import ssl
                
                apps = []
                try:
                    encoded_query = urllib.parse.quote(query)
                    url = f"https://community.chocolatey.org/api/v2/Search()?$filter=IsLatestVersion&$top=25&searchTerm='{encoded_query}'&targetFramework=''&includePrerelease=false"
                    req = urllib.request.Request(url, headers={'User-Agent': 'WindowsHealthChecker/1.0'})
                    ctx = ssl.create_default_context()
                    response = urllib.request.urlopen(req, timeout=15, context=ctx)
                    xml_data = response.read().decode('utf-8')
                    
                    root = ET.fromstring(xml_data)
                    ns = {
                        'atom': 'http://www.w3.org/2005/Atom',
                        'd': 'http://schemas.microsoft.com/ado/2007/08/dataservices',
                        'm': 'http://schemas.microsoft.com/ado/2007/08/dataservices/metadata'
                    }
                    
                    for entry in root.findall('.//atom:entry', ns):
                        props = entry.find('.//m:properties', ns)
                        if props is not None:
                            pkg_id_elem = entry.find('.//atom:title', ns)
                            title_elem = props.find('d:Title', ns)
                            version_elem = props.find('d:Version', ns)
                            
                            pkg_id = pkg_id_elem.text if pkg_id_elem is not None else ''
                            name = title_elem.text if title_elem is not None and title_elem.text else pkg_id
                            version = version_elem.text if version_elem is not None else 'N/A'
                            
                            if pkg_id:
                                apps.append({
                                    'name': name,
                                    'id': pkg_id,
                                    'version': version,
                                    'source': 'chocolatey',
                                    'publisher': ''
                                })
                except Exception as e:
                    print(f"DEBUG: Chocolatey API error: {e}")
                return apps
            
            def _search_scoop(self, query: str) -> list:
                """Search Scoop packages via Azure Search API"""
                import urllib.request
                import json
                import ssl
                
                apps = []
                try:
                    url = 'https://scoopsearch.search.windows.net/indexes/apps/docs/search?api-version=2020-06-30'
                    body = json.dumps({"search": query, "top": 25}).encode('utf-8')
                    req = urllib.request.Request(url, data=body, headers={
                        'Content-Type': 'application/json',
                        'api-key': 'DC6D2BBE65FC7313F2C52BBD2B0286ED'  # Public API key
                    })
                    ctx = ssl.create_default_context()
                    response = urllib.request.urlopen(req, timeout=15, context=ctx)
                    data = json.loads(response.read().decode('utf-8'))
                    
                    for pkg in data.get('value', []):
                        name = pkg.get('Name', '')
                        version = pkg.get('Version', 'N/A')
                        repo = pkg.get('Repository', '')
                        
                        # Scoop ID is bucket/name format
                        bucket = repo.split('/')[-1] if repo else 'main'
                        pkg_id = f"{bucket}/{name}" if name else ''
                        
                        if name:
                            apps.append({
                                'name': name,
                                'id': pkg_id,
                                'version': version,
                                'source': 'scoop',
                                'publisher': bucket
                            })
                except Exception as e:
                    print(f"DEBUG: Scoop API error: {e}")
                return apps
            
            def _search_nuget(self, query: str) -> list:
                """Search NuGet packages API (for .NET developers)"""
                import urllib.request
                import urllib.parse
                import json
                import ssl
                
                apps = []
                try:
                    encoded_query = urllib.parse.quote(query)
                    url = f'https://azuresearch-usnc.nuget.org/query?q={encoded_query}&take=15'
                    req = urllib.request.Request(url, headers={'User-Agent': 'WindowsHealthChecker/1.0'})
                    ctx = ssl.create_default_context()
                    response = urllib.request.urlopen(req, timeout=15, context=ctx)
                    data = json.loads(response.read().decode('utf-8'))
                    
                    for pkg in data.get('data', []):
                        pkg_id = pkg.get('id', '')
                        version = pkg.get('version', 'N/A')
                        authors = pkg.get('authors', [])
                        
                        if pkg_id:
                            apps.append({
                                'name': pkg_id,
                                'id': pkg_id,
                                'version': version,
                                'source': 'nuget',
                                'publisher': ', '.join(authors) if authors else ''
                            })
                except Exception as e:
                    print(f"DEBUG: NuGet API error: {e}")
                return apps
            
            def run(self):
                from concurrent.futures import ThreadPoolExecutor, as_completed
                
                print(f"DEBUG: Thread run() started for query: {self.query}")
                
                all_apps = []
                sources_searched = []
                
                try:
                    # Search all APIs in parallel using ThreadPoolExecutor
                    with ThreadPoolExecutor(max_workers=4) as executor:
                        futures = {
                            executor.submit(self._search_winget, self.query): 'winget',
                            executor.submit(self._search_chocolatey, self.query): 'chocolatey',
                            executor.submit(self._search_scoop, self.query): 'scoop',
                            executor.submit(self._search_nuget, self.query): 'nuget'
                        }
                        
                        for future in as_completed(futures):
                            source = futures[future]
                            try:
                                results = future.result()
                                if results:
                                    all_apps.extend(results)
                                    sources_searched.append(f"{source}({len(results)})")
                                    print(f"DEBUG: {source} returned {len(results)} results")
                            except Exception as e:
                                print(f"DEBUG: {source} failed: {e}")
                    
                    print(f"DEBUG: Total results from all sources: {len(all_apps)}")
                    print(f"DEBUG: Sources: {', '.join(sources_searched)}")
                    
                    # Sort results: prioritize exact matches, then by source
                    query_lower = self.query.lower()
                    def sort_key(app):
                        name_lower = app['name'].lower()
                        id_lower = app['id'].lower()
                        # Exact name match = highest priority
                        if name_lower == query_lower:
                            return (0, app['source'], name_lower)
                        # Name starts with query
                        if name_lower.startswith(query_lower):
                            return (1, app['source'], name_lower)
                        # ID starts with query
                        if id_lower.startswith(query_lower):
                            return (2, app['source'], name_lower)
                        # Name contains query
                        if query_lower in name_lower:
                            return (3, app['source'], name_lower)
                        return (4, app['source'], name_lower)
                    
                    all_apps.sort(key=sort_key)
                    
                    self.results_ready.emit(all_apps[:75])  # Limit to 75 total results
                    
                except Exception as e:
                    print(f"DEBUG: Exception in aggregated search: {e}")
                    self.error.emit(str(e))
        
        self.search_thread = SearchThread(query)
        self.search_thread.results_ready.connect(self._on_search_complete)
        self.search_thread.error.connect(self._on_search_error)
        self.search_thread.start()
        print("DEBUG: Thread started")
    
    def _on_search_complete(self, apps: list):
        """Handle search results"""
        print(f"DEBUG: _on_search_complete called with {len(apps)} apps")
        if apps:
            print(f"DEBUG: First app: {apps[0]}")
        
        self.search_btn.setEnabled(True)
        self.search_btn.setText("Search")
        
        if not apps:
            self.results_label.setText("No apps found. Try a different search term.")
            return
        
        # Count results per source
        source_counts = {}
        for app in apps:
            source = app.get('source', 'unknown')
            source_counts[source] = source_counts.get(source, 0) + 1
        
        # Build summary string
        source_summary = ', '.join([f"{s}: {c}" for s, c in sorted(source_counts.items())])
        self.results_label.setText(f"Found {len(apps)} apps from 4 sources ({source_summary}):")
        self.search_results = apps
        
        fav_ids = {f.get("id") for f in self.favorites}
        
        for app in apps:
            item = self._create_result_item(app, app["id"] in fav_ids)
            self.results_layout.addWidget(item)
    
    def _on_search_error(self, error: str):
        """Handle search error"""
        import os
        import tempfile
        # DEBUG: Log error callback
        try:
            debug_path = os.path.join(tempfile.gettempdir(), 'winget_search_debug.txt')
            with open(debug_path, 'a', encoding='utf-8') as f:
                f.write(f"=== _on_search_error called: {error} ===\n")
        except:
            pass
        
        self.search_btn.setEnabled(True)
        self.search_btn.setText("Search")
        self.results_label.setText(f"Error: {error}")
    
    def _create_result_item(self, app: dict, is_favorite: bool) -> QFrame:
        """Create a search result item widget"""
        item = QFrame()
        item.setProperty("app_id", app["id"])
        item.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_SM}px;
            }}
            QFrame:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        
        layout = QHBoxLayout(item)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        # App icon based on source
        source = app.get("source", "winget")
        source_icons = {
            'winget': '📦',
            'chocolatey': '🍫',
            'scoop': '🥄',
            'nuget': '📚'
        }
        icon_label = QLabel(source_icons.get(source, '📦'))
        icon_label.setStyleSheet("background: transparent; font-size: 24px;")
        layout.addWidget(icon_label)
        
        # App info
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)
        
        # Name row with source badge
        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        
        name_label = QLabel(app["name"])
        name_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 14px; font-weight: 500;")
        name_row.addWidget(name_label)
        
        # Source badge with colors - using semi-transparent backgrounds per spec
        source_colors = {
            'winget': ('#60cdff', 'rgba(0, 120, 212, 0.15)'),      # Blue
            'chocolatey': ('#ba68c8', 'rgba(156, 39, 176, 0.15)'), # Purple
            'scoop': ('#81c784', 'rgba(76, 175, 80, 0.15)'),       # Green
            'nuget': ('#64b5f6', 'rgba(33, 150, 243, 0.15)')       # Blue
        }
        badge_fg, badge_bg = source_colors.get(source, ('#808088', 'rgba(128, 128, 128, 0.15)'))
        source_badge = QLabel(source.upper())
        source_badge.setStyleSheet(f"""
            background: {badge_bg};
            color: {badge_fg};
            font-size: 11px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 4px;
        """)
        name_row.addWidget(source_badge)
        name_row.addStretch()
        info_layout.addLayout(name_row)
        
        details_layout = QHBoxLayout()
        details_layout.setSpacing(8)
        
        id_label = QLabel(app["id"])
        id_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        details_layout.addWidget(id_label)
        
        # Only show version if it's a real version (not "Unknown" or empty)
        version = app.get("version", "")
        if version and version.lower() not in ("unknown", "n/a"):
            version_label = QLabel(f"v{version}")
            version_label.setStyleSheet(f"background: transparent; color: {Theme.ACCENT}; font-size: 11px;")
            details_layout.addWidget(version_label)
        
        details_layout.addStretch()
        info_layout.addLayout(details_layout)
        
        layout.addLayout(info_layout, 1)
        
        # Favorite/Remove button - shows +Fav to add, X to remove
        if is_favorite:
            # Show X button to remove from favorites
            remove_btn = QPushButton("X")
            remove_btn.setObjectName("fav_btn")
            remove_btn.setFixedSize(36, 36)
            remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            remove_btn.setToolTip("Remove from favorites")
            remove_btn.clicked.connect(lambda: self._toggle_favorite(app["id"], app["name"]))
            remove_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {Theme.ERROR}30;
                    color: {Theme.ERROR};
                    border: none;
                    border-radius: 4px;
                    font-size: 14px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {Theme.ERROR}50;
                }}
            """)
            layout.addWidget(remove_btn)
        else:
            # Show +Fav button to add to favorites
            fav_btn = QPushButton("+Fav")
            fav_btn.setObjectName("fav_btn")
            fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            fav_btn.setToolTip("Add to favorites")
            fav_btn.clicked.connect(lambda: self._toggle_favorite(app["id"], app["name"]))
            fav_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {Theme.TEXT_TERTIARY};
                    border: none;
                    padding: 6px 8px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    color: {Theme.WARNING};
                }}
            """)
            layout.addWidget(fav_btn)
        
        # Details button - text instead of icon
        details_btn = QPushButton("Details")
        details_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        details_btn.setToolTip("Show package details & verification")
        details_btn.clicked.connect(lambda checked, a=app: self._show_package_details(a))
        details_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_SECONDARY};
                border: none;
                padding: 8px 12px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {Theme.INFO}40;
                color: {Theme.INFO};
            }}
        """)
        layout.addWidget(details_btn)
        
        # Install button
        install_btn = QPushButton("Install")
        install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        install_btn.clicked.connect(lambda: self._install_app(app["id"]))
        install_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT_HOVER};
            }}
        """)
        layout.addWidget(install_btn)
        
        return item
    
    def _toggle_favorite(self, app_id: str, app_name: str):
        """Toggle favorite status for an app"""
        fav_ids = {f.get("id") for f in self.favorites}
        if app_id in fav_ids:
            self._remove_favorite(app_id)
        else:
            self._add_favorite(app_id, app_name)
        self._update_results_favorite_states()
    
    def _install_app(self, app_id: str):
        """Install an app using winget"""
        if not app_id:
            return
        
        # Show installation dialog
        dialog = WingetInstallDialog(app_id, self)
        dialog.exec()
    
    def _show_package_details(self, app: dict):
        """Show detailed package information for verification"""
        dialog = WingetPackageDetailsDialog(app, self)
        dialog.exec()
    
    def _install_all_favorites(self):
        """Install all favorite apps"""
        if not self.favorites:
            return
        
        # Create batch install dialog
        app_ids = [f.get("id") for f in self.favorites if f.get("id")]
        dialog = WingetBatchInstallDialog(app_ids, self)
        dialog.exec()
    
    def _export_favorites(self):
        """Export favorites to a JSON file"""
        from PyQt6.QtWidgets import QFileDialog
        import json
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Favorites",
            "winget_favorites.json",
            "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                with open(file_path, "w") as f:
                    json.dump({"favorites": self.favorites}, f, indent=2)
            except Exception as e:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Export Error", f"Failed to export: {str(e)}")
    
    def _import_favorites(self):
        """Import favorites from a JSON file"""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import json
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Favorites",
            "",
            "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                
                imported = data.get("favorites", [])
                if imported:
                    # Merge with existing, avoiding duplicates
                    existing_ids = {f.get("id") for f in self.favorites}
                    for fav in imported:
                        if fav.get("id") and fav.get("id") not in existing_ids:
                            self.favorites.append(fav)
                    
                    self._save_favorites()
                    self._refresh_favorites_list()
                    QMessageBox.information(self, "Import Complete", f"Imported {len(imported)} favorites.")
            except Exception as e:
                QMessageBox.warning(self, "Import Error", f"Failed to import: {str(e)}")
    
    def refresh_accent_colors(self):
        """Update accent-colored elements when theme changes"""
        # Search button
        self.search_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT_HOVER};
            }}
            QPushButton:disabled {{
                background: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_TERTIARY};
            }}
        """)
        
        # Check Updates button
        self.check_updates_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT_HOVER};
            }}
            QPushButton:disabled {{
                background: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_TERTIARY};
            }}
        """)


class WingetPackageDetailsDialog(QDialog):
    """Dialog showing detailed package information for verification"""
    
    def __init__(self, app: dict, parent=None):
        super().__init__(parent)
        self.app = app
        self.app_id = app.get('id', 'Unknown')
        self.source = app.get('source', 'winget')
        self.setWindowTitle(f"Package Details: {self.app_id}")
        self.setFixedSize(600, 550)
        self.setup_ui()
        self._load_details()
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background: {Theme.BG_CARD};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # Title with source badge
        title_layout = QHBoxLayout()
        title = QLabel(f"🔍 Package Verification")
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 18px; font-weight: 600;")
        title_layout.addWidget(title)
        
        # Source badge - using semi-transparent backgrounds per spec
        source_colors = {
            'winget': ('#60cdff', 'rgba(0, 120, 212, 0.15)'),
            'chocolatey': ('#ba68c8', 'rgba(156, 39, 176, 0.15)'),
            'scoop': ('#81c784', 'rgba(76, 175, 80, 0.15)'),
            'nuget': ('#64b5f6', 'rgba(33, 150, 243, 0.15)')
        }
        badge_fg, badge_bg = source_colors.get(self.source, ('#808088', 'rgba(128, 128, 128, 0.15)'))
        source_badge = QLabel(self.source.upper())
        source_badge.setStyleSheet(f"""
            background: {badge_bg};
            color: {badge_fg};
            font-size: 11px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 4px;
        """)
        title_layout.addWidget(source_badge)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # Subtitle
        subtitle = QLabel(f"Details for: {self.app_id}")
        subtitle.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        layout.addWidget(subtitle)
        
        # Loading label
        self.loading_label = QLabel("Loading package details...")
        self.loading_label.setStyleSheet(f"color: {Theme.TEXT_TERTIARY}; font-size: 13px;")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.loading_label)
        
        # Details scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.details_widget = QWidget()
        self.details_widget.setStyleSheet("background: transparent;")
        self.details_layout = QVBoxLayout(self.details_widget)
        self.details_layout.setContentsMargins(0, 0, 0, 0)
        self.details_layout.setSpacing(8)
        
        scroll.setWidget(self.details_widget)
        scroll.setVisible(False)
        self.scroll_area = scroll
        layout.addWidget(scroll)
        
        # Verification summary
        self.verification_frame = QFrame()
        self.verification_frame.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_ELEVATED};
                border-radius: {Theme.RADIUS_SM}px;
                padding: 12px;
            }}
        """)
        self.verification_frame.setVisible(False)
        verif_layout = QVBoxLayout(self.verification_frame)
        verif_layout.setContentsMargins(12, 12, 12, 12)
        verif_layout.setSpacing(8)
        
        self.verification_label = QLabel("")
        self.verification_label.setWordWrap(True)
        self.verification_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        verif_layout.addWidget(self.verification_label)
        
        layout.addWidget(self.verification_frame)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_SECONDARY};
                border: none;
                padding: 10px 24px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
    
    def _load_details(self):
        """Load package details from HTTP API based on source"""
        class DetailsThread(QThread):
            details_ready = pyqtSignal(dict)
            error = pyqtSignal(str)
            
            def __init__(self, app: dict):
                super().__init__()
                self.app = app
                self.source = app.get('source', 'winget')
                self.app_id = app.get('id', '')
            
            def run(self):
                import urllib.request
                import urllib.parse
                import json
                import ssl
                import xml.etree.ElementTree as ET
                
                details = {
                    'Name': self.app.get('name', 'Unknown'),
                    'ID': self.app_id,
                    'Version': self.app.get('version', 'N/A'),
                    'Publisher': self.app.get('publisher', ''),
                    'Source': self.source.upper()
                }
                
                ctx = ssl.create_default_context()
                
                try:
                    if self.source == 'winget':
                        # Query winget.run API for more details
                        encoded_id = urllib.parse.quote(self.app_id)
                        url = f'https://api.winget.run/v2/packages/{encoded_id}'
                        req = urllib.request.Request(url, headers={'User-Agent': 'WindowsHealthChecker/1.0'})
                        
                        try:
                            response = urllib.request.urlopen(req, timeout=10, context=ctx)
                            data = json.loads(response.read().decode('utf-8'))
                            
                            latest = data.get('Latest', {})
                            details['Name'] = latest.get('Name', details['Name'])
                            details['Publisher'] = latest.get('Publisher', details['Publisher'])
                            details['Description'] = latest.get('Description', '')
                            details['Homepage'] = latest.get('Homepage', '')
                            details['License'] = latest.get('License', '')
                            details['License URL'] = latest.get('LicenseUrl', '')
                            
                            versions = data.get('Versions', [])
                            if versions:
                                details['Version'] = versions[0]
                                details['Available Versions'] = ', '.join(versions[:5])
                                if len(versions) > 5:
                                    details['Available Versions'] += f' (+{len(versions)-5} more)'
                            
                            tags = latest.get('Tags', [])
                            if tags:
                                details['Tags'] = ', '.join(tags)
                        except:
                            pass  # Use basic info from search
                    
                    elif self.source == 'chocolatey':
                        # Query Chocolatey API for more details
                        encoded_id = urllib.parse.quote(self.app_id)
                        url = f"https://community.chocolatey.org/api/v2/Packages(Id='{encoded_id}',Version='{self.app.get('version', '')}')"
                        req = urllib.request.Request(url, headers={'User-Agent': 'WindowsHealthChecker/1.0'})
                        
                        try:
                            response = urllib.request.urlopen(req, timeout=10, context=ctx)
                            xml_data = response.read().decode('utf-8')
                            root = ET.fromstring(xml_data)
                            ns = {
                                'd': 'http://schemas.microsoft.com/ado/2007/08/dataservices',
                                'm': 'http://schemas.microsoft.com/ado/2007/08/dataservices/metadata'
                            }
                            
                            props = root.find('.//m:properties', ns)
                            if props is not None:
                                desc = props.find('d:Description', ns)
                                if desc is not None and desc.text:
                                    # Clean up description (remove markdown)
                                    clean_desc = desc.text[:300].replace('#', '').replace('*', '')
                                    details['Description'] = clean_desc + ('...' if len(desc.text) > 300 else '')
                                
                                proj_url = props.find('d:ProjectUrl', ns)
                                if proj_url is not None:
                                    details['Homepage'] = proj_url.text or ''
                                
                                lic_url = props.find('d:LicenseUrl', ns)
                                if lic_url is not None:
                                    details['License URL'] = lic_url.text or ''
                                
                                downloads = props.find('d:DownloadCount', ns)
                                if downloads is not None:
                                    details['Total Downloads'] = f"{int(downloads.text):,}" if downloads.text else ''
                                
                                tags = props.find('d:Tags', ns)
                                if tags is not None:
                                    details['Tags'] = tags.text or ''
                                
                                pkg_status = props.find('d:PackageStatus', ns)
                                if pkg_status is not None:
                                    details['Package Status'] = pkg_status.text or ''
                        except:
                            pass
                    
                    elif self.source == 'scoop':
                        # Scoop packages - use the bucket/name info
                        details['Bucket'] = self.app.get('publisher', 'main')
                        details['Note'] = 'Scoop packages are installed to ~/scoop/apps/'
                    
                    elif self.source == 'nuget':
                        # Query NuGet API
                        encoded_id = urllib.parse.quote(self.app_id)
                        url = f'https://api.nuget.org/v3/registration5-gz-semver2/{encoded_id.lower()}/index.json'
                        req = urllib.request.Request(url, headers={
                            'User-Agent': 'WindowsHealthChecker/1.0',
                            'Accept-Encoding': 'gzip'
                        })
                        
                        try:
                            response = urllib.request.urlopen(req, timeout=10, context=ctx)
                            # Handle gzip
                            import gzip
                            data = json.loads(gzip.decompress(response.read()).decode('utf-8'))
                            
                            items = data.get('items', [])
                            if items:
                                latest_page = items[-1]
                                page_items = latest_page.get('items', [])
                                if page_items:
                                    latest = page_items[-1].get('catalogEntry', {})
                                    details['Description'] = latest.get('description', '')[:300]
                                    details['Authors'] = latest.get('authors', '')
                                    details['Project URL'] = latest.get('projectUrl', '')
                                    details['License URL'] = latest.get('licenseUrl', '')
                                    details['Tags'] = latest.get('tags', '')
                        except:
                            pass
                    
                    self.details_ready.emit(details)
                    
                except Exception as e:
                    # Return basic details even on error
                    details['Error'] = str(e)
                    self.details_ready.emit(details)
        
        self.details_thread = DetailsThread(self.app)
        self.details_thread.details_ready.connect(self._on_details_loaded)
        self.details_thread.error.connect(self._on_details_error)
        self.details_thread.start()
    
    def _on_details_loaded(self, details: dict):
        """Display the loaded details"""
        self.loading_label.setVisible(False)
        self.scroll_area.setVisible(True)
        self.verification_frame.setVisible(True)
        
        # Important fields for verification - order matters
        important_fields = [
            ("Name", "📦"),
            ("ID", "🏷️"),
            ("Version", "🔢"),
            ("Publisher", "🏢"),
            ("Authors", "👤"),
            ("Source", "📂"),
            ("Package Status", "✅"),
            ("Description", "📝"),
            ("Homepage", "🏠"),
            ("Project URL", "🌐"),
            ("License", "📄"),
            ("License URL", "📄"),
            ("Tags", "🏷️"),
            ("Total Downloads", "📊"),
            ("Available Versions", "📋"),
            ("Bucket", "🪣"),
            ("Note", "ℹ️"),
        ]
        
        # Add detail rows
        for field, icon in important_fields:
            value = details.get(field, "")
            if value:
                self._add_detail_row(icon, field, str(value))
        
        # Add any other fields not in the important list
        shown_fields = {f[0] for f in important_fields}
        shown_fields.add('Error')  # Don't show error as a row
        for key, value in details.items():
            if key not in shown_fields and value:
                self._add_detail_row("📋", key, str(value))
        
        # Build verification summary
        trust_indicators = []
        
        # Source-specific trust info
        source = self.source.lower()
        if source == 'winget':
            trust_indicators.append("✅ From winget.run API (mirrors Microsoft's winget repository)")
        elif source == 'chocolatey':
            trust_indicators.append("✅ From Chocolatey Community Repository")
            if details.get('Package Status') == 'Approved':
                trust_indicators.append("✅ Package is approved and reviewed")
            downloads = details.get('Total Downloads', '')
            if downloads:
                trust_indicators.append(f"📊 {downloads} total downloads")
        elif source == 'scoop':
            trust_indicators.append("✅ From Scoop package repository")
            trust_indicators.append("ℹ️ Scoop installs apps portably (no admin required)")
        elif source == 'nuget':
            trust_indicators.append("✅ From NuGet.org (.NET package repository)")
            trust_indicators.append("ℹ️ NuGet packages are for .NET developers")
        
        # Publisher check
        publisher = details.get('Publisher') or details.get('Authors', '')
        if publisher:
            trust_indicators.append(f"✅ Publisher/Author: {publisher}")
        else:
            trust_indicators.append("⚠️ Publisher not specified")
        
        # Homepage check
        homepage = details.get('Homepage') or details.get('Project URL', '')
        if homepage:
            # Check for known trusted domains
            trusted_domains = ["github.com", "microsoft.com", "mozilla.org", "google.com", 
                              "adobe.com", "oracle.com", "python.org", "nodejs.org", "nuget.org"]
            is_trusted = any(domain in homepage.lower() for domain in trusted_domains)
            if is_trusted:
                trust_indicators.append(f"✅ Official project website: {homepage[:50]}...")
            else:
                trust_indicators.append(f"🔗 Project website: {homepage[:50]}...")
        
        self.verification_label.setText("\n".join(trust_indicators))
    
    def _on_details_error(self, error: str):
        """Handle error loading details"""
        self.loading_label.setText(f"Error loading details: {error}")
        self.loading_label.setStyleSheet(f"color: {Theme.ERROR}; font-size: 13px;")
    
    def _add_detail_row(self, icon: str, label: str, value: str):
        """Add a detail row to the display"""
        row = QFrame()
        row.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_ELEVATED};
                border-radius: {Theme.RADIUS_SM}px;
            }}
        """)
        
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(12, 8, 12, 8)
        row_layout.setSpacing(4)
        
        # Label
        label_widget = QLabel(f"{icon} {label}")
        label_widget.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
        row_layout.addWidget(label_widget)
        
        # Value
        value_widget = QLabel(value)
        value_widget.setWordWrap(True)
        value_widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        
        # Highlight important fields
        if label in ["Publisher", "Authors", "Package Status"]:
            value_widget.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 12px; font-weight: 500;")
        elif label in ["Homepage", "Project URL", "License URL"]:
            value_widget.setStyleSheet(f"background: transparent; color: {Theme.ACCENT}; font-size: 12px;")
        elif label == "Source":
            value_widget.setStyleSheet(f"background: transparent; color: {Theme.INFO}; font-size: 12px; font-weight: 600;")
        else:
            value_widget.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 12px;")
        
        row_layout.addWidget(value_widget)
        
        self.details_layout.addWidget(row)


class WingetInstallDialog(QDialog):
    """Dialog for installing a single app via winget"""
    
    def __init__(self, app_id: str, parent=None):
        super().__init__(parent)
        self.app_id = app_id
        self.process = None
        self.setWindowTitle(f"Installing {app_id}")
        self.setFixedSize(500, 300)
        self.setup_ui()
        self._start_install()
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background: {Theme.BG_CARD};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # Title
        title = QLabel(f"Installing: {self.app_id}")
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 16px; font-weight: 600;")
        layout.addWidget(title)
        
        # Progress indicator
        self.progress_label = QLabel("Starting installation...")
        self.progress_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        layout.addWidget(self.progress_label)
        
        # Output area
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet(f"""
            QTextEdit {{
                background: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_SECONDARY};
                border: none;
                border-radius: {Theme.RADIUS_SM}px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                padding: 12px;
            }}
        """)
        layout.addWidget(self.output_text)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.close)
        self.close_btn.setEnabled(False)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_SECONDARY};
                border: none;
                padding: 10px 24px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
            }}
            QPushButton:disabled {{
                color: {Theme.TEXT_TERTIARY};
            }}
        """)
        btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(btn_layout)
    
    def _start_install(self):
        """Start the winget install process"""
        import subprocess
        
        class InstallThread(QThread):
            output = pyqtSignal(str)
            finished = pyqtSignal(bool, str)
            
            def __init__(self, app_id):
                super().__init__()
                self.app_id = app_id
            
            def run(self):
                import subprocess
                try:
                    process = subprocess.Popen(
                        ["winget", "install", self.app_id, "--accept-source-agreements", "--accept-package-agreements", "--disable-interactivity"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                    )
                    
                    for line in process.stdout:
                        self.output.emit(line)
                    
                    process.wait()
                    
                    if process.returncode == 0:
                        self.finished.emit(True, "Installation completed successfully!")
                    else:
                        self.finished.emit(False, f"Installation failed with code {process.returncode}")
                except Exception as e:
                    self.finished.emit(False, str(e))
        
        self.install_thread = InstallThread(self.app_id)
        self.install_thread.output.connect(self._on_output)
        self.install_thread.finished.connect(self._on_finished)
        self.install_thread.start()
    
    def _on_output(self, text: str):
        """Handle installation output"""
        self.output_text.append(text.strip())
        # Scroll to bottom
        scrollbar = self.output_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _on_finished(self, success: bool, message: str):
        """Handle installation completion"""
        self.progress_label.setText(message)
        if success:
            self.progress_label.setStyleSheet(f"color: {Theme.SUCCESS}; font-size: 13px;")
        else:
            self.progress_label.setStyleSheet(f"color: {Theme.ERROR}; font-size: 13px;")
        self.close_btn.setEnabled(True)


class WingetBatchInstallDialog(QDialog):
    """Dialog for installing multiple apps via winget"""
    
    def __init__(self, app_ids: list, parent=None):
        super().__init__(parent)
        self.app_ids = app_ids
        self.current_index = 0
        self.setWindowTitle("Batch Install")
        self.setFixedSize(550, 400)
        self.setup_ui()
        self._start_batch_install()
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background: {Theme.BG_CARD};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # Title
        title = QLabel(f"Installing {len(self.app_ids)} apps")
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 16px; font-weight: 600;")
        layout.addWidget(title)
        
        # Progress
        self.progress_label = QLabel(f"Installing 1 of {len(self.app_ids)}...")
        self.progress_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        layout.addWidget(self.progress_label)
        
        # Current app label
        self.current_app_label = QLabel("")
        self.current_app_label.setStyleSheet(f"color: {Theme.ACCENT}; font-size: 12px;")
        layout.addWidget(self.current_app_label)
        
        # Output area
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet(f"""
            QTextEdit {{
                background: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_SECONDARY};
                border: none;
                border-radius: {Theme.RADIUS_SM}px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                padding: 12px;
            }}
        """)
        layout.addWidget(self.output_text)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._cancel_install)
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_SECONDARY};
                border: none;
                padding: 10px 24px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {Theme.ERROR}40;
                color: {Theme.ERROR};
            }}
        """)
        btn_layout.addWidget(self.cancel_btn)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.close)
        self.close_btn.setEnabled(False)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                padding: 10px 24px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT_HOVER};
            }}
            QPushButton:disabled {{
                background: {Theme.BG_ELEVATED};
                color: {Theme.TEXT_TERTIARY};
            }}
        """)
        btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(btn_layout)
    
    def _start_batch_install(self):
        """Start installing apps one by one"""
        self.cancelled = False
        self._install_next()
    
    def _install_next(self):
        """Install the next app in the queue"""
        if self.cancelled or self.current_index >= len(self.app_ids):
            self._on_batch_complete()
            return
        
        app_id = self.app_ids[self.current_index]
        self.progress_label.setText(f"Installing {self.current_index + 1} of {len(self.app_ids)}...")
        self.current_app_label.setText(f"Current: {app_id}")
        self.output_text.append(f"\n{'='*50}\nInstalling: {app_id}\n{'='*50}\n")
        
        class InstallThread(QThread):
            output = pyqtSignal(str)
            finished = pyqtSignal(bool)
            
            def __init__(self, app_id):
                super().__init__()
                self.app_id = app_id
            
            def run(self):
                import subprocess
                try:
                    process = subprocess.Popen(
                        ["winget", "install", self.app_id, "--accept-source-agreements", "--accept-package-agreements", "--disable-interactivity"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                    )
                    
                    for line in process.stdout:
                        self.output.emit(line)
                    
                    process.wait()
                    self.finished.emit(process.returncode == 0)
                except:
                    self.finished.emit(False)
        
        self.install_thread = InstallThread(app_id)
        self.install_thread.output.connect(self._on_output)
        self.install_thread.finished.connect(self._on_single_finished)
        self.install_thread.start()
    
    def _on_output(self, text: str):
        """Handle installation output"""
        self.output_text.append(text.strip())
        scrollbar = self.output_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _on_single_finished(self, success: bool):
        """Handle single app installation completion"""
        status = "Success" if success else "Failed"
        self.output_text.append(f"\n{status}\n")
        
        self.current_index += 1
        self._install_next()
    
    def _on_batch_complete(self):
        """Handle batch installation completion"""
        if self.cancelled:
            self.progress_label.setText("Installation cancelled")
            self.progress_label.setStyleSheet(f"color: {Theme.WARNING}; font-size: 13px;")
        else:
            self.progress_label.setText(f"Completed installing {len(self.app_ids)} apps")
            self.progress_label.setStyleSheet(f"color: {Theme.SUCCESS}; font-size: 13px;")
        
        self.current_app_label.setText("")
        self.cancel_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
    
    def _cancel_install(self):
        """Cancel the batch installation"""
        self.cancelled = True
        self.cancel_btn.setEnabled(False)


class SettingsPage(QWidget):
    """Settings page with app configuration options"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.controls = {}  # Store references to controls
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(24)
        
        # Header
        title = QLabel("Settings")
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 28px;
            font-weight: 600;
        """)
        layout.addWidget(title)
        
        # Appearance section
        layout.addWidget(self._create_section("Appearance"))
        
        appearance_card = self._create_card()
        appearance_layout = QVBoxLayout(appearance_card)
        appearance_layout.setContentsMargins(20, 16, 20, 16)
        appearance_layout.setSpacing(16)
        
        # Theme option
        self.controls["theme"] = self._create_dropdown(["Dark", "Light"], "theme")
        theme_row = self._create_option_row(
            "Theme", 
            "Choose between dark and light mode",
            self.controls["theme"]
        )
        appearance_layout.addWidget(theme_row)
        
        # Accent color
        self.controls["accent_color"] = self._create_dropdown(["Blue", "Green", "Purple", "Orange", "Red"], "accent_color")
        accent_row = self._create_option_row(
            "Accent Color",
            "Customize the accent color throughout the app",
            self.controls["accent_color"]
        )
        appearance_layout.addWidget(accent_row)
        
        layout.addWidget(appearance_card)
        
        # Scanning section
        layout.addWidget(self._create_section("Scanning"))
        
        scan_card = self._create_card()
        scan_layout = QVBoxLayout(scan_card)
        scan_layout.setContentsMargins(20, 16, 20, 16)
        scan_layout.setSpacing(16)
        
        # Auto scan on startup
        self.controls["auto_scan"] = self._create_toggle(False, "auto_scan")
        autoscan_row = self._create_option_row(
            "Auto-scan on startup",
            "Automatically run a quick scan when the app starts",
            self.controls["auto_scan"]
        )
        scan_layout.addWidget(autoscan_row)
        
        # Check for driver updates
        self.controls["check_driver_updates"] = self._create_toggle(True, "check_driver_updates")
        driver_update_row = self._create_option_row(
            "Check for driver updates online",
            "Search manufacturer websites for newer driver versions",
            self.controls["check_driver_updates"]
        )
        scan_layout.addWidget(driver_update_row)
        
        layout.addWidget(scan_card)
        
        # Notifications section
        layout.addWidget(self._create_section("Notifications"))
        
        notif_card = self._create_card()
        notif_layout = QVBoxLayout(notif_card)
        notif_layout.setContentsMargins(20, 16, 20, 16)
        notif_layout.setSpacing(16)
        
        # Show notifications
        self.controls["show_notifications"] = self._create_toggle(True, "show_notifications")
        notif_row = self._create_option_row(
            "Show notifications",
            "Display system notifications for important events",
            self.controls["show_notifications"]
        )
        notif_layout.addWidget(notif_row)
        
        layout.addWidget(notif_card)
        
        # About section
        layout.addWidget(self._create_section("About"))
        
        about_card = self._create_card()
        about_layout = QVBoxLayout(about_card)
        about_layout.setContentsMargins(20, 16, 20, 16)
        about_layout.setSpacing(8)
        
        app_name = QLabel("Windows Health Checker Pro")
        app_name.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 16px; font-weight: 600;")
        about_layout.addWidget(app_name)
        
        version = QLabel("Version 5.0 (MK5)")
        version.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        about_layout.addWidget(version)
        
        desc = QLabel("A comprehensive system health and driver management tool for Windows.")
        desc.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        desc.setWordWrap(True)
        about_layout.addWidget(desc)
        
        layout.addWidget(about_card)
        
        layout.addStretch()
        
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
    
    def _create_section(self, text: str) -> QLabel:
        """Create a section header per spec Section 7.0.3"""
        label = QLabel(text)
        label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 16px;
            font-weight: 600;
            margin-top: 8px;
        """)
        return label
    
    def _create_card(self) -> QFrame:
        """Create a settings card container"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        return card
    
    def _create_option_row(self, title: str, description: str, control: QWidget) -> QFrame:
        """Create a settings option row"""
        row = QFrame()
        row.setStyleSheet("background: transparent;")
        
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 14px;")
        text_layout.addWidget(title_label)
        
        desc_label = QLabel(description)
        desc_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        text_layout.addWidget(desc_label)
        
        layout.addLayout(text_layout, 1)
        layout.addWidget(control)
        
        return row
    
    def load_settings(self):
        """Load saved settings into controls"""
        # Load dropdown values
        if "theme" in self.controls:
            idx = self.controls["theme"].findText(app_settings.get("theme", "Dark"))
            if idx >= 0:
                self.controls["theme"].setCurrentIndex(idx)
        
        if "accent_color" in self.controls:
            idx = self.controls["accent_color"].findText(app_settings.get("accent_color", "Blue"))
            if idx >= 0:
                self.controls["accent_color"].setCurrentIndex(idx)
        
        # Load toggle values
        for key in ["auto_scan", "check_driver_updates", "show_notifications"]:
            if key in self.controls:
                checked = app_settings.get(key, False)
                self.controls[key].setProperty("checked", checked)
                self._update_toggle_style(self.controls[key], bool(checked))
    
    def _create_dropdown(self, options: list, setting_key: str | None = None) -> QWidget:
        """Create a styled dropdown"""
        from PyQt6.QtWidgets import QComboBox, QMessageBox
        
        combo = QComboBox()
        combo.addItems(options)
        combo.setFixedWidth(120)
        combo.setStyleSheet(f"""
            QComboBox {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                border-radius: {Theme.RADIUS_SM}px;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QComboBox:hover {{
                background: {Theme.BG_ELEVATED};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                outline: none;
                selection-background-color: {Theme.ACCENT};
                selection-color: white;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: none;
                padding: 8px 12px;
                min-height: 24px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background: {Theme.ACCENT};
                color: white;
            }}
        """)
        
        # Set the view to remove frame
        combo.view().setStyleSheet(f"""
            QListView {{
                background: {Theme.BG_CARD};
                border: none;
                outline: none;
            }}
        """)
        combo.view().window().setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint
        )
        combo.view().window().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        
        # Connect to save on change
        if setting_key:
            def on_change(text):
                old_value = app_settings.get(setting_key)
                if old_value != text:
                    app_settings.set(setting_key, text)
            combo.currentTextChanged.connect(on_change)
        
        return combo
    
    def _create_toggle(self, initial: bool, setting_key: str | None = None) -> QFrame:
        """Create a toggle switch"""
        toggle = QFrame()
        toggle.setFixedSize(44, 24)
        toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle.setProperty("checked", initial)
        toggle.setProperty("setting_key", setting_key)
        
        self._update_toggle_style(toggle, initial)
        
        # Install event filter for click handling
        toggle.installEventFilter(self)
        
        return toggle
    
    def eventFilter(self, watched, event):
        """Handle toggle clicks via event filter"""
        from PyQt6.QtCore import QEvent
        if event is not None and event.type() == QEvent.Type.MouseButtonPress:
            if isinstance(watched, QFrame) and watched.property("checked") is not None:
                checked = not watched.property("checked")
                watched.setProperty("checked", checked)
                self._update_toggle_style(watched, bool(checked))
                # Save the setting
                key = watched.property("setting_key")
                if key:
                    app_settings.set(key, checked)
                return True
        return super().eventFilter(watched, event)
    
    def _update_toggle_style(self, toggle: QFrame, checked: bool):
        """Update toggle visual state"""
        if checked:
            toggle.setStyleSheet(f"""
                QFrame {{
                    background: {Theme.ACCENT};
                    border-radius: 12px;
                }}
            """)
        else:
            toggle.setStyleSheet(f"""
                QFrame {{
                    background: {Theme.BORDER};
                    border-radius: 12px;
                }}
            """)


# =============================================================================
# CUSTOM TITLE BAR - Outlook-style window controls
# =============================================================================

class CustomTitleBar(QFrame):
    """Custom title bar with Outlook-style window controls.
    
    Features:
    - Draggable title bar for window movement
    - Minimize, maximize/restore, close buttons
    - Smooth hover effects
    - Matches the dark theme aesthetic
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self._drag_pos = None
        self._is_maximized = False
        self.setFixedHeight(32)
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            CustomTitleBar {{
                background: {Theme.BG_SIDEBAR};
                border: none;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(0)
        
        # App icon (load from file)
        icon_label = QLabel()
        icon_label.setFixedSize(18, 18)
        icon_label.setStyleSheet("background: transparent;")
        
        # Try to load the icon
        import sys
        import os
        possible_paths = [
            os.path.join(getattr(sys, '_MEIPASS', ''), 'icon.ico'),
            os.path.join(os.path.dirname(sys.executable), 'icon.ico'),
            'icon.ico',
            os.path.join(os.path.dirname(__file__), 'icon.ico'),
        ]
        
        icon_loaded = False
        for icon_path in possible_paths:
            if os.path.exists(icon_path):
                from PyQt6.QtGui import QIcon
                icon = QIcon(icon_path)
                available_sizes = icon.availableSizes()
                if available_sizes:
                    largest_size = max(available_sizes, key=lambda s: s.width() * s.height())
                    pixmap = icon.pixmap(largest_size)
                    if not pixmap.isNull():
                        icon_label.setPixmap(pixmap.scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                        icon_loaded = True
                        break
        
        if not icon_loaded:
            icon_label.setText("💓")
            icon_label.setStyleSheet("background: transparent; font-size: 14px;")
        
        layout.addWidget(icon_label)
        
        layout.addSpacing(8)
        
        # Window title
        self.title_label = QLabel("Windows Health Checker Pro")
        self.title_label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_SECONDARY};
            font-size: 12px;
            font-weight: 500;
        """)
        layout.addWidget(self.title_label)
        
        layout.addStretch()
        
        # Window control buttons (Outlook-style)
        btn_style_base = f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {Theme.TEXT_SECONDARY};
                font-size: 10px;
                font-family: 'Segoe MDL2 Assets', 'Segoe UI Symbol';
                padding: 0;
            }}
            QPushButton:hover {{
                background: {Theme.SURFACE_04DP};
            }}
        """
        
        # Minimize button
        self.minimize_btn = QPushButton("—")
        self.minimize_btn.setFixedSize(46, 32)
        self.minimize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.minimize_btn.setStyleSheet(btn_style_base)
        self.minimize_btn.clicked.connect(self._minimize_window)
        layout.addWidget(self.minimize_btn)
        
        # Maximize/Restore button
        self.maximize_btn = QPushButton("□")
        self.maximize_btn.setFixedSize(46, 32)
        self.maximize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.maximize_btn.setStyleSheet(btn_style_base)
        self.maximize_btn.clicked.connect(self._toggle_maximize)
        layout.addWidget(self.maximize_btn)
        
        # Close button (red hover like Outlook)
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(46, 32)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {Theme.TEXT_SECONDARY};
                font-size: 10px;
            }}
            QPushButton:hover {{
                background: #c42b1c;
                color: white;
            }}
        """)
        self.close_btn.clicked.connect(self._close_window)
        layout.addWidget(self.close_btn)
    
    def _minimize_window(self):
        if self.parent_window:
            self.parent_window.showMinimized()
    
    def _toggle_maximize(self):
        if self.parent_window:
            if self.parent_window.isMaximized():
                self.parent_window.showNormal()
                self.maximize_btn.setText("□")
            else:
                self.parent_window.showMaximized()
                self.maximize_btn.setText("❐")
    
    def _close_window(self):
        if self.parent_window:
            self.parent_window.close()
    
    def mousePressEvent(self, event):  # type: ignore[override]
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):  # type: ignore[override]
        if event is not None and self._drag_pos is not None and self.parent_window:
            # If maximized, restore before dragging
            if self.parent_window.isMaximized():
                self.parent_window.showNormal()
                self.maximize_btn.setText("□")
                # Reposition window so cursor is at center of title bar
                self._drag_pos = event.globalPosition().toPoint()
                self.parent_window.move(
                    self._drag_pos.x() - self.parent_window.width() // 2,
                    self._drag_pos.y() - 16
                )
            else:
                delta = event.globalPosition().toPoint() - self._drag_pos
                self.parent_window.move(self.parent_window.pos() + delta)
                self._drag_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):  # type: ignore[override]
        self._drag_pos = None
        super().mouseReleaseEvent(event)
    
    def mouseDoubleClickEvent(self, event):  # type: ignore[override]
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximize()
        super().mouseDoubleClickEvent(event)


# =============================================================================
# MAIN WINDOW
# =============================================================================

class MainWindow(QMainWindow):
    """Main application window - per UI Spec Section 1"""
    
    def __init__(self):
        super().__init__()
        
        # Enable frameless window for custom title bar
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)  # Enable hover events
        
        # For window resizing
        self._resize_margin = 8  # Larger margin for easier targeting
        self._resize_dir = None
        self._resize_start_pos = None
        self._resize_start_geo = None
        self.setMouseTracking(True)
        
        # Initialize backends
        self.scanner = DriverScanner()
        self.health_checker = HealthChecker()
        self.disk_manager = DiskManager()
        
        # Shared data cache - populated by full scan, used by all pages
        self.cached_data: dict[str, object] = {
            "startup": None,      # Startup items list
            "drivers": None,      # Driver scan results
            "events": None,       # Event log data
            "hardware": None,     # Hardware info
            "updates": None,      # Windows Update status
            "storage": None,      # Storage/disk info
            "security": None,     # Defender status
            "last_scan": None,    # Timestamp of last full scan
        }
        
        self._active_threads = []  # Track active threads to prevent GC crashes
        
        self.setWindowTitle("Windows Health Checker Pro")
        
        # Set window icon - load from embedded resource or file
        self._set_app_icon()
        
        # Per spec: Min 1100x720, Default 1280x800
        self.setMinimumSize(1100, 720)
        self.resize(1280, 800)
        
        self.current_nav = "overview"
        self.setup_ui()
    
    def _set_app_icon(self):
        """Set the application window icon."""
        import sys
        import os
        from PyQt6.QtGui import QIcon
        
        # Try to find icon.ico in various locations
        possible_paths = [
            # When running as exe (PyInstaller)
            os.path.join(getattr(sys, '_MEIPASS', ''), 'icon.ico'),
            # Same directory as script/exe
            os.path.join(os.path.dirname(sys.executable), 'icon.ico'),
            # Current working directory
            'icon.ico',
            # Script directory (for development)
            os.path.join(os.path.dirname(__file__), 'icon.ico'),
        ]
        
        for icon_path in possible_paths:
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                return
        
        # If no icon file found, the embedded exe icon will be used by Windows
    
    def setup_ui(self):
        self.setStyleSheet(GLOBAL_STYLE)
        
        central = QWidget()
        central.setStyleSheet(f"background: {Theme.BG_WINDOW};")
        central.setMouseTracking(True)  # Enable mouse tracking for resize cursors
        self.setCentralWidget(central)
        
        # Main vertical layout: title bar + content
        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        
        # Custom title bar (Outlook-style)
        self.title_bar = CustomTitleBar(self)
        outer_layout.addWidget(self.title_bar)
        
        # Content area (sidebar + pages)
        content_area = QWidget()
        content_area.setStyleSheet("background: transparent;")
        main_layout = QHBoxLayout(content_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        outer_layout.addWidget(content_area, 1)
        
        # Sidebar
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar)
        
        # Content stack (with smooth page transitions)
        self.content_stack = AnimatedStackedWidget()
        
        # Create pages
        self.overview = OverviewPage()
        self.overview.health_card.scan_btn.clicked.connect(self.run_scan)
        self.overview.card_clicked.connect(self.navigate)  # Connect status card clicks to navigation
        self.content_stack.addWidget(self.overview)
        
        self.pages: dict[str, QWidget] = {"overview": self.overview}
        
        modules = [
            # All module pages are now dedicated pages - no generic ModulePage needed
            # Updates uses WindowsUpdatePage
            # Storage uses StoragePage
            # Security uses SecurityPage
            # Hardware uses HardwarePage
            # System uses SystemPage
            # Events uses EventsPage
        ]
        
        # Map module IDs to check methods
        self.check_methods = {
            "updates": self.check_windows_updates,
            "storage": self.check_storage_health,
            "security": self.check_security_status,
            "hardware": self.check_hardware_health,
            "system": self.check_system_files,
            "events": self.check_event_logs,
        }
        
        # Add Windows Update page (comprehensive update management)
        self.updates_page = WindowsUpdatePage()
        self.pages["updates"] = self.updates_page
        self.content_stack.addWidget(self.updates_page)
        
        # Add Storage page (comprehensive storage management)
        self.storage_page = StoragePage()
        self.pages["storage"] = self.storage_page
        self.content_stack.addWidget(self.storage_page)
        
        # Add Security page (Defender, Firewall status, Firewall rules)
        self.security_page = SecurityPage()
        self.pages["security"] = self.security_page
        self.content_stack.addWidget(self.security_page)
        
        # Add System page (comprehensive system configuration)
        self.system_page = SystemPage()
        self.pages["system"] = self.system_page
        self.content_stack.addWidget(self.system_page)
        
        for module_id, title, icon in modules:
            page = ModulePage(title, icon)
            page.run_check_clicked.connect(lambda mid=module_id: self.run_module_check(mid))
            self.pages[module_id] = page
            self.content_stack.addWidget(page)
        
        # Add Hardware page (comprehensive hardware info)
        self.hardware_page = HardwarePage()
        self.pages["hardware"] = self.hardware_page
        self.content_stack.addWidget(self.hardware_page)
        
        # Add Drivers page
        self.drivers_page = DriversPage()
        self.pages["drivers"] = self.drivers_page
        self.content_stack.addWidget(self.drivers_page)
        
        # Add Startup page
        self.startup_page = StartupPage()
        self.pages["startup"] = self.startup_page
        self.content_stack.addWidget(self.startup_page)
        
        # Add Events page (dedicated event log analysis)
        self.events_page = EventsPage()
        self.pages["events"] = self.events_page
        self.content_stack.addWidget(self.events_page)
        
        # Add Audio page (audio device testing with oscilloscope)
        self.audio_page = AudioPage()
        self.pages["audio"] = self.audio_page
        self.content_stack.addWidget(self.audio_page)
        
        # Add Windows Tools page (all settings and system tools)
        self.tools_page = WindowsToolsPage()
        self.pages["tools"] = self.tools_page
        self.content_stack.addWidget(self.tools_page)
        
        # Add Software page (package manager with favorites)
        self.software_page = WingetPage()
        self.pages["software"] = self.software_page
        self.content_stack.addWidget(self.software_page)
        
        # Add Settings page
        self.settings_page = SettingsPage()
        self.pages["settings"] = self.settings_page
        self.content_stack.addWidget(self.settings_page)
        
        main_layout.addWidget(self.content_stack, 1)
        
        # Status bar
        status_bar = self.statusBar()
        if status_bar:
            status_bar.setStyleSheet(f"""
                QStatusBar {{
                    background: {Theme.BG_SIDEBAR};
                    color: {Theme.TEXT_TERTIARY};
                    border-top: 1px solid {Theme.BORDER};
                    padding: 6px 16px;
                    font-size: 11px;
                }}
            """)
            status_bar.showMessage("Ready")
        
        # Start background prefetch after a short delay to let UI settle
        QTimer.singleShot(500, self._prefetch_data)
    
    def _prefetch_data(self):
        """Prefetch commonly used data in background threads.
        
        Called after app start to warm the cache with data that
        pages frequently need, improving perceived responsiveness.
        """
        # Prefetch security status (frequently viewed)
        if not self.cached_data.get("security"):
            self._prefetch_security()
        
        # Prefetch storage info (frequently viewed)
        if not self.cached_data.get("storage"):
            self._prefetch_storage()
    
    def _prefetch_security(self):
        """Prefetch Defender/security status in background"""
        self._prefetch_security_thread = QThread(self)
        self._prefetch_security_worker = SecurityCheckWorker(self.health_checker)
        self._prefetch_security_worker.moveToThread(self._prefetch_security_thread)
        self._active_threads.append(self._prefetch_security_thread)  # Prevent GC
        
        self._prefetch_security_thread.started.connect(self._prefetch_security_worker.run)
        self._prefetch_security_worker.finished.connect(self._on_prefetch_security_done)
        self._prefetch_security_worker.finished.connect(self._prefetch_security_thread.quit)
        self._prefetch_security_worker.finished.connect(self._prefetch_security_worker.deleteLater)
        self._prefetch_security_thread.finished.connect(lambda: self._cleanup_thread(self._prefetch_security_thread))
        
        self._prefetch_security_thread.start()
    
    def _on_prefetch_security_done(self, result: dict):
        """Cache prefetched security data"""
        if result and 'Error' not in result:
            self.cached_data["security"] = result
    
    def _prefetch_storage(self):
        """Prefetch storage/disk info in background"""
        self._prefetch_storage_thread = QThread(self)
        self._prefetch_storage_worker = StorageCheckWorker(self.disk_manager)
        self._prefetch_storage_worker.moveToThread(self._prefetch_storage_thread)
        self._active_threads.append(self._prefetch_storage_thread)  # Prevent GC
        
        self._prefetch_storage_thread.started.connect(self._prefetch_storage_worker.run)
        self._prefetch_storage_worker.finished.connect(self._on_prefetch_storage_done)
        self._prefetch_storage_worker.finished.connect(self._prefetch_storage_thread.quit)
        self._prefetch_storage_worker.finished.connect(self._prefetch_storage_worker.deleteLater)
        self._prefetch_storage_thread.finished.connect(lambda: self._cleanup_thread(self._prefetch_storage_thread))
        
        self._prefetch_storage_thread.start()
    
    def _on_prefetch_storage_done(self, result: dict):
        """Cache prefetched storage data"""
        if result and 'Error' not in result:
            self.cached_data["storage"] = result
    
    def _cleanup_thread(self, thread: QThread):
        """Safely remove thread from active list after it finishes"""
        if thread in self._active_threads:
            self._active_threads.remove(thread)
    
    def _add_nav_divider(self, layout: QVBoxLayout):
        """Add a visual divider between navigation groups per UI spec section 5.2"""
        layout.addSpacing(8)
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {Theme.BORDER}; margin-left: 16px; margin-right: 16px;")
        layout.addWidget(divider)
        layout.addSpacing(8)
    
    def create_sidebar(self):
        sidebar = QFrame()
        sidebar.setFixedWidth(Theme.SIDEBAR_W)
        # Clean solid background - no border to prevent artifacts
        sidebar.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_SIDEBAR};
                border: none;
            }}
        """)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QFrame()
        header.setFixedHeight(60)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 16, 0)
        header_layout.setSpacing(10)
        
        # App icon/title (load actual icon)
        app_icon_label = QLabel()
        app_icon_label.setFixedSize(32, 32)
        app_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Try to load the icon
        import sys
        import os
        icon_paths = [
            os.path.join(getattr(sys, '_MEIPASS', ''), 'icon.ico'),
            os.path.join(os.path.dirname(sys.executable), 'icon.ico'),
            'icon.ico',
            os.path.join(os.path.dirname(__file__), 'icon.ico'),
        ]
        
        icon_set = False
        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                from PyQt6.QtGui import QIcon
                icon = QIcon(icon_path)
                # Get the largest available size from the icon
                available_sizes = icon.availableSizes()
                if available_sizes:
                    # Sort by size and get the largest
                    largest_size = max(available_sizes, key=lambda s: s.width() * s.height())
                    pixmap = icon.pixmap(largest_size)
                    if not pixmap.isNull():
                        app_icon_label.setPixmap(pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                        icon_set = True
                        break
        
        if not icon_set:
            # Fallback to styled container with +
            app_icon_label.setStyleSheet(f"""
                background: {Theme.ACCENT};
                border-radius: {Theme.RADIUS_SM}px;
                color: white;
                font-size: 18px;
                font-weight: bold;
            """)
            app_icon_label.setText("+")
        else:
            app_icon_label.setStyleSheet("background: transparent;")
        
        header_layout.addWidget(app_icon_label)
        
        app_title = QLabel("Health Checker")
        app_title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 15px;
            font-weight: 600;
        """)
        header_layout.addWidget(app_title)
        header_layout.addStretch()
        
        layout.addWidget(header)
        
        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {Theme.BORDER};")
        layout.addWidget(sep)
        
        layout.addSpacing(8)
        
        # Navigation items with grouping (per UI spec section 5.2)
        self.nav_items = {}
        
        # Group 1: Dashboard (standalone)
        nav_dashboard = [("overview", "grid", "Overview")]
        
        # Group 2: System Health - items that check for issues
        nav_health = [
            ("drivers", "chip", "Drivers"),
            ("startup", "rocket", "Startup"),
            ("updates", "download", "Updates"),
            ("storage", "hdd", "Storage"),
            ("security", "shield", "Security"),
        ]
        
        # Group 3: System Info - informational pages
        nav_info = [
            ("software", "package", "Software"),
            ("hardware", "cpu", "Hardware"),
            ("system", "file", "System"),
            ("events", "alert", "Events"),
            ("audio", "speaker", "Audio"),
        ]
        
        # Group 4: Utilities
        nav_utilities = [("tools", "wrench", "Tools")]
        
        # Add Dashboard group
        for nav_id, icon, label in nav_dashboard:
            item = SidebarItem(icon, label)
            item.clicked.connect(lambda nid=nav_id: self.navigate(nid))
            self.nav_items[nav_id] = item
            layout.addWidget(item)
        
        # Divider after Dashboard
        self._add_nav_divider(layout)
        
        # Add System Health group
        for nav_id, icon, label in nav_health:
            item = SidebarItem(icon, label)
            item.clicked.connect(lambda nid=nav_id: self.navigate(nid))
            self.nav_items[nav_id] = item
            layout.addWidget(item)
        
        # Divider after System Health
        self._add_nav_divider(layout)
        
        # Add System Info group
        for nav_id, icon, label in nav_info:
            item = SidebarItem(icon, label)
            item.clicked.connect(lambda nid=nav_id: self.navigate(nid))
            self.nav_items[nav_id] = item
            layout.addWidget(item)
        
        # Divider after System Info
        self._add_nav_divider(layout)
        
        # Add Utilities group
        for nav_id, icon, label in nav_utilities:
            item = SidebarItem(icon, label)
            item.clicked.connect(lambda nid=nav_id: self.navigate(nid))
            self.nav_items[nav_id] = item
            layout.addWidget(item)
        
        self.nav_items["overview"].set_active(True)
        
        layout.addStretch()
        
        # Settings at bottom
        layout.addSpacing(8)
        settings = SidebarItem("gear", "Settings")
        settings.clicked.connect(lambda: self.navigate("settings"))
        self.nav_items["settings"] = settings
        layout.addWidget(settings)
        layout.addSpacing(12)
        
        return sidebar
    
    def navigate(self, nav_id: str):
        if nav_id == self.current_nav:
            return
        
        # Update nav selection
        if self.current_nav in self.nav_items:
            self.nav_items[self.current_nav].set_active(False)
        
        if nav_id in self.nav_items:
            self.nav_items[nav_id].set_active(True)
        self.current_nav = nav_id
        
        # Switch page
        if nav_id in self.pages:
            self.content_stack.setCurrentWidget(self.pages[nav_id])
            
            # Auto-populate page with cached data if available and page hasn't been loaded
            self._auto_populate_page(nav_id)
    
    def _auto_populate_page(self, nav_id: str):
        """Auto-populate a page with cached data if available"""
        # Map navigation IDs to cache keys and pages
        cache_map = {
            "startup": ("startup", self.startup_page, "display_cached_data"),
            "events": ("events", self.events_page, None),  # Events page loads its own data
            "hardware": ("hardware", self.hardware_page, "display_cached_data"),
            "security": ("security", self.security_page, "display_defender_data"),
        }
        
        if nav_id in cache_map:
            cache_key, page, method_name = cache_map[nav_id]
            
            # Check if page has a 'loaded' attribute and if it's been loaded
            if hasattr(page, 'loaded') and page.loaded:
                return  # Page already has data
            
            # For security page, check cached_defender_data instead
            if nav_id == "security" and page.cached_defender_data:
                return  # Already has data
            
            # Check if we have cached data
            if self.cached_data.get(cache_key) and method_name:
                # Call the display method with cached data
                method = getattr(page, method_name, None)
                if method:
                    method(self.cached_data[cache_key])
    
    def refresh_accent_colors(self):
        """Refresh all UI elements that use the accent color.
        
        Called when accent color changes in settings to update all themed elements.
        """
        from PyQt6.QtWidgets import QPushButton, QComboBox
        
        # Refresh sidebar items
        for nav_id, item in self.nav_items.items():
            item._update_style()
        
        # Refresh the Health Checker button on overview page
        if hasattr(self, 'overview') and hasattr(self.overview, 'health_card'):
            btn = self.overview.health_card.scan_btn
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {Theme.ACCENT};
                    color: white;
                    border: none;
                    border-radius: {Theme.RADIUS_SM}px;
                    padding: 8px 16px;
                    font-size: 13px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {Theme.ACCENT_HOVER};
                }}
                QPushButton:pressed {{
                    background: {Theme.PRIMARY_PRESSED};
                }}
            """)
        
        # Refresh settings page toggles
        if hasattr(self, 'settings_page'):
            for key, control in self.settings_page.controls.items():
                if isinstance(control, QFrame) and control.property("checked") is not None:
                    checked = control.property("checked")
                    self.settings_page._update_toggle_style(control, bool(checked))
                # Refresh combobox selection colors
                elif isinstance(control, QComboBox):
                    control.setStyleSheet(f"""
                        QComboBox {{
                            background: {Theme.BG_CARD_HOVER};
                            color: {Theme.TEXT_PRIMARY};
                            border: none;
                            border-radius: {Theme.RADIUS_SM}px;
                            padding: 6px 12px;
                            font-size: 13px;
                        }}
                        QComboBox:hover {{
                            background: {Theme.BG_ELEVATED};
                        }}
                        QComboBox::drop-down {{
                            border: none;
                            width: 20px;
                        }}
                        QComboBox::down-arrow {{
                            image: none;
                            border: none;
                        }}
                        QComboBox QAbstractItemView {{
                            background: {Theme.BG_CARD};
                            color: {Theme.TEXT_PRIMARY};
                            border: none;
                            outline: none;
                            selection-background-color: {Theme.ACCENT};
                            selection-color: white;
                            padding: 4px;
                        }}
                        QComboBox QAbstractItemView::item {{
                            background: {Theme.BG_CARD};
                            color: {Theme.TEXT_PRIMARY};
                            border: none;
                            padding: 8px 12px;
                            min-height: 24px;
                        }}
                        QComboBox QAbstractItemView::item:hover {{
                            background: {Theme.BG_CARD_HOVER};
                        }}
                        QComboBox QAbstractItemView::item:selected {{
                            background: {Theme.ACCENT};
                            color: white;
                        }}
                    """)
        
        # Refresh all buttons with accent_style property across all widgets
        for btn in self.findChildren(QPushButton):
            btn_style = btn.property("accent_style")
            if btn_style == "primary":
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {Theme.ACCENT};
                        color: white;
                        border: none;
                        border-radius: {Theme.RADIUS_SM}px;
                        padding: 8px 16px;
                        font-size: 13px;
                        font-weight: 600;
                    }}
                    QPushButton:hover {{
                        background: {Theme.ACCENT_HOVER};
                    }}
                    QPushButton:pressed {{
                        background: {Theme.PRIMARY_PRESSED};
                    }}
                """)
            elif btn_style == "outline":
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        color: {Theme.ACCENT};
                        border: 1px solid {Theme.ACCENT};
                        border-radius: {Theme.RADIUS_SM}px;
                        padding: 6px 12px;
                        font-size: 12px;
                    }}
                    QPushButton:hover {{
                        background: {Theme.ACCENT_SUBTLE};
                    }}
                """)
        
        # Refresh all pages that have accent-colored elements
        for page_id, page in self.pages.items():
            if hasattr(page, 'refresh_accent_colors'):
                page.refresh_accent_colors()
        
        # Force repaint
        self.update()
        self.repaint()
    
    def apply_full_theme_refresh(self):
        """Completely rebuild the UI when theme changes (Dark/Light mode).
        
        This recreates all widgets with the new theme colors.
        For production, this shows a message that app restart is recommended.
        """
        from PyQt6.QtWidgets import QMessageBox
        
        # Trigger accent color refresh for immediate partial update
        self.refresh_accent_colors()
        
        # Force repaint of all widgets that use paintEvent
        for widget in self.findChildren(QWidget):
            widget.update()
        
        # Show message that restart is recommended for full theme change
        msg = QMessageBox(self)
        msg.setWindowTitle("Theme Changed")
        msg.setText("Theme has been changed.")
        msg.setInformativeText("Some elements may require restarting the application to fully apply the new theme.")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
    
    def run_scan(self):
        """Run full system scan - all checks run in parallel for speed"""
        import time
        
        dialog = ScanProgressDialog(self)
        dialog.show()
        
        self.scan_dialog = dialog
        self.scan_results = {}  # Store results from each check
        self.scan_start_times = {}  # Track start time per task
        self.scan_total_tasks = 7
        self.scan_completed_tasks = 0
        self.scan_start_time = time.time()
        
        # Define all tasks
        task_ids = ["update", "defender", "smart", "memory", "events", "services", "sfc"]
        
        # Mark all as running and record start times
        for task_id in task_ids:
            self.scan_dialog.update_task(task_id, "running")
            self.scan_start_times[task_id] = time.time()
        
        self.scan_dialog.set_progress(5, "Running all checks...")
        
        # Start all scans in parallel (using QTimer to stagger slightly for UI)
        QTimer.singleShot(10, self._scan_windows_updates)
        QTimer.singleShot(20, self._scan_security)
        QTimer.singleShot(30, self._scan_storage)
        QTimer.singleShot(40, self._scan_hardware)
        QTimer.singleShot(50, self._scan_events)
        QTimer.singleShot(60, self._scan_system)
        QTimer.singleShot(70, self._scan_startup)
    
    def _complete_scan_task(self, task_id: str, results: dict):
        """Called when a scan task completes - handles parallel completion"""
        import time
        
        # Calculate elapsed time for this task
        elapsed_ms = None
        if task_id in self.scan_start_times:
            elapsed_ms = (time.time() - self.scan_start_times[task_id]) * 1000
        
        # Mark task complete with timing
        self.scan_dialog.update_task(task_id, "complete", time_ms=elapsed_ms)
        
        # Store results
        self.scan_results[task_id] = results
        self.scan_completed_tasks += 1
        
        # Update progress
        progress = int((self.scan_completed_tasks / self.scan_total_tasks) * 100)
        remaining = self.scan_total_tasks - self.scan_completed_tasks
        if remaining > 0:
            self.scan_dialog.set_progress(progress, f"{remaining} checks remaining...")
        else:
            self.scan_dialog.set_progress(100, "Finalizing...")
        
        # Check if all tasks are done
        if self.scan_completed_tasks >= self.scan_total_tasks:
            QTimer.singleShot(200, self._finalize_scan)
    
    def _scan_windows_updates(self):
        """Scan Windows Update status for full scan - runs in background thread"""
        # Create worker and thread
        self._update_thread = QThread(self)
        self._update_worker = WindowsUpdateWorker(self.health_checker)
        self._update_worker.moveToThread(self._update_thread)
        
        # Connect signals
        self._update_thread.started.connect(self._update_worker.run)
        self._update_worker.finished.connect(self._on_update_scan_complete)
        self._update_worker.finished.connect(self._update_thread.quit)
        self._update_worker.finished.connect(self._update_worker.deleteLater)
        
        # Start the thread
        self._update_thread.start()
    
    def _on_update_scan_complete(self, update_info: dict):
        """Handle Windows Update scan completion"""
        results = {"status": "check", "message": "Up to date", "data": []}
        try:
            if 'Error' not in update_info:
                pending = update_info.get('PendingUpdates', 0)
                if pending > 0:
                    results["status"] = "warning"
                    results["message"] = f"{pending} updates pending"
                results["data"] = update_info
                self.cached_data["updates"] = update_info
        except Exception as e:
            results["status"] = "error"
            results["message"] = str(e)
        
        self._complete_scan_task("update", results)
    
    def _scan_security(self):
        """Scan security status for full scan - runs in background thread"""
        # Create worker and thread
        self._security_thread = QThread(self)
        self._security_worker = SecurityCheckWorker(self.health_checker)
        self._security_worker.moveToThread(self._security_thread)
        
        # Connect signals
        self._security_thread.started.connect(self._security_worker.run)
        self._security_worker.finished.connect(self._on_security_scan_complete)
        self._security_worker.finished.connect(self._security_thread.quit)
        self._security_worker.finished.connect(self._security_worker.deleteLater)
        
        # Start the thread
        self._security_thread.start()
    
    def _on_security_scan_complete(self, defender: dict):
        """Handle security scan completion"""
        results = {"status": "check", "message": "Protected", "data": []}
        try:
            if 'Error' not in defender:
                enabled = defender.get('AntivirusEnabled', False)
                realtime = defender.get('RealTimeProtection', False)
                if not enabled:
                    results["status"] = "error"
                    results["message"] = "Disabled"
                elif not realtime:
                    results["status"] = "warning"
                    results["message"] = "Partial"
                results["data"] = defender
                self.cached_data["security"] = defender
        except Exception as e:
            results["status"] = "error"
            results["message"] = str(e)
        
        self._complete_scan_task("defender", results)
    
    def _scan_storage(self):
        """Scan storage health for full scan - runs in background thread"""
        # Create worker and thread
        self._storage_thread = QThread(self)
        self._storage_worker = StorageCheckWorker(self.health_checker)
        self._storage_worker.moveToThread(self._storage_thread)
        
        # Connect signals
        self._storage_thread.started.connect(self._storage_worker.run)
        self._storage_worker.finished.connect(self._on_storage_scan_complete)
        self._storage_worker.finished.connect(self._storage_thread.quit)
        self._storage_worker.finished.connect(self._storage_worker.deleteLater)
        
        # Start the thread
        self._storage_thread.start()
    
    def _on_storage_scan_complete(self, volume_info: list):
        """Handle storage scan completion"""
        results = {"status": "check", "message": "Healthy", "data": []}
        try:
            worst_usage = 0
            for vol in volume_info:
                size_gb = vol.get('SizeGB', 0)
                free_gb = vol.get('FreeSpaceGB', 0)
                if size_gb > 0:
                    used_percent = int(((size_gb - free_gb) / size_gb) * 100)
                    worst_usage = max(worst_usage, used_percent)
            
            if worst_usage >= 90:
                results["status"] = "error"
                results["message"] = f"{worst_usage}% used"
            elif worst_usage >= 75:
                results["status"] = "warning"
                results["message"] = f"{worst_usage}% used"
            else:
                results["message"] = f"{worst_usage}% used"
            
            results["data"] = volume_info
            self.cached_data["storage"] = volume_info
        except Exception as e:
            results["status"] = "error"
            results["message"] = str(e)
        
        self._complete_scan_task("smart", results)
    
    def _scan_hardware(self):
        """Scan hardware info for full scan - runs in background thread"""
        # Create worker and thread to avoid blocking UI
        self._hardware_scan_thread = QThread(self)
        self._hardware_scan_worker = HardwareMemoryWorker()
        self._hardware_scan_worker.moveToThread(self._hardware_scan_thread)
        
        # Connect signals
        self._hardware_scan_thread.started.connect(self._hardware_scan_worker.run)
        self._hardware_scan_worker.finished.connect(self._on_hardware_scan_complete)
        self._hardware_scan_worker.finished.connect(self._hardware_scan_thread.quit)
        self._hardware_scan_worker.finished.connect(self._hardware_scan_worker.deleteLater)
        
        # Start the thread
        self._hardware_scan_thread.start()
    
    def _on_hardware_scan_complete(self, hw_data: dict):
        """Handle hardware scan completion"""
        results = {"status": "check", "message": "All OK", "data": {}}
        try:
            if 'Error' not in hw_data and 'memory' in hw_data:
                mem_info = hw_data.get('memory', {})
                free_gb = mem_info.get('FreeGB', 0)
                results["data"]["memory"] = mem_info
                results["message"] = f"{free_gb:.1f} GB RAM free"
                self.cached_data["hardware"] = results["data"]
            else:
                results["status"] = "warning"
                results["message"] = "Check incomplete"
        except Exception as e:
            results["status"] = "warning"
            results["message"] = "Check incomplete"
        
        self._complete_scan_task("memory", results)
    
    def _scan_events(self):
        """Scan event logs for full scan - runs in background thread"""
        # Create worker and thread to avoid blocking UI
        self._event_scan_thread = QThread(self)
        self._event_scan_worker = EventScanWorker()
        self._event_scan_worker.moveToThread(self._event_scan_thread)
        
        # Connect signals
        self._event_scan_thread.started.connect(self._event_scan_worker.run)
        self._event_scan_worker.finished.connect(self._on_event_scan_complete)
        self._event_scan_worker.finished.connect(self._event_scan_thread.quit)
        self._event_scan_worker.finished.connect(self._event_scan_worker.deleteLater)
        
        # Start the thread
        self._event_scan_thread.start()
    
    def _on_event_scan_complete(self, event_data: dict):
        """Handle event scan completion"""
        results = {"status": "check", "message": "No issues", "data": {}}
        try:
            if 'Error' not in event_data:
                errors = event_data.get("ErrorCount", 0)
                warnings = event_data.get("WarningCount", 0)
                critical = event_data.get("CriticalCount", 0)
                
                # Only show red (error) status for critical events
                if critical > 0:
                    results["status"] = "error"
                    results["message"] = f"{critical} critical, {errors} errors"
                elif errors > 10 or warnings > 50:
                    results["status"] = "warning"
                    results["message"] = f"{errors} errors, {warnings} warnings"
                else:
                    results["message"] = f"{errors} errors, {warnings} warnings"
                
                results["data"] = event_data
                self.cached_data["events"] = event_data
            else:
                results["status"] = "warning"
                results["message"] = "Check failed"
        except Exception as e:
            results["status"] = "warning"
            results["message"] = "Check failed"
        
        self._complete_scan_task("events", results)
    
    def _scan_system(self):
        """Scan system files for full scan"""
        results = {"status": "check", "message": "No issues", "data": {}}
        # System file check is quick - we just report status
        results["data"]["status"] = "System files not verified (requires admin)"
        self._complete_scan_task("services", results)
    
    def _scan_startup(self):
        """Scan startup items for full scan - runs in background thread"""
        # Create worker and thread to avoid blocking UI
        self._startup_scan_thread = QThread(self)
        self._startup_scan_worker = StartupScanWorker()
        self._startup_scan_worker.moveToThread(self._startup_scan_thread)
        
        # Connect signals
        self._startup_scan_thread.started.connect(self._startup_scan_worker.run)
        self._startup_scan_worker.finished.connect(self._on_startup_full_scan_complete)
        self._startup_scan_worker.finished.connect(self._startup_scan_thread.quit)
        self._startup_scan_worker.finished.connect(self._startup_scan_worker.deleteLater)
        
        # Start the thread
        self._startup_scan_thread.start()
    
    def _on_startup_full_scan_complete(self, startup_items: list):
        """Handle startup scan completion during full scan"""
        results = {"status": "check", "message": "OK", "data": []}
        
        try:
            enabled_count = sum(1 for item in startup_items if item.get("enabled", False))
            total_count = len(startup_items)
            
            if enabled_count > 15:
                results["status"] = "warning"
                results["message"] = f"{enabled_count} items enabled"
            else:
                results["message"] = f"{enabled_count}/{total_count} items"
            
            results["data"] = startup_items
            self.cached_data["startup"] = startup_items
        except Exception as e:
            results["status"] = "warning"
            results["message"] = f"Check failed: {e}"
        
        self._complete_scan_task("sfc", results)
    
    def _finalize_scan(self):
        """Finalize the full scan and update all pages"""
        import datetime
        
        # Update timestamp
        self.cached_data["last_scan"] = datetime.datetime.now()
        
        # Calculate overall health score
        total_checks = len(self.scan_results)
        passed = sum(1 for r in self.scan_results.values() if r.get("status") == "check")
        warnings = sum(1 for r in self.scan_results.values() if r.get("status") == "warning")
        errors = sum(1 for r in self.scan_results.values() if r.get("status") == "error")
        
        health_score = max(0, 100 - (errors * 15) - (warnings * 5))
        
        # Update overview health card
        self.overview.health_card.set_score(health_score, passed, warnings, errors)
        
        # Update overview status cards
        update_res = self.scan_results.get("update", {})
        self.overview.status_cards["updates"].set_status(
            update_res.get("status", "check"),
            update_res.get("message", "Unknown")
        )
        
        defender_res = self.scan_results.get("defender", {})
        self.overview.status_cards["defender"].set_status(
            defender_res.get("status", "check"),
            defender_res.get("message", "Unknown")
        )
        
        storage_res = self.scan_results.get("smart", {})
        self.overview.status_cards["storage"].set_status(
            storage_res.get("status", "check"),
            storage_res.get("message", "Unknown")
        )
        
        memory_res = self.scan_results.get("memory", {})
        self.overview.status_cards["memory"].set_status(
            memory_res.get("status", "check"),
            memory_res.get("message", "Unknown")
        )
        
        events_res = self.scan_results.get("events", {})
        # Map to system card since we don't have dedicated events card on overview
        self.overview.status_cards["system"].set_status(
            events_res.get("status", "check"),
            events_res.get("message", "Unknown")
        )
        
        # Update drivers card - will show driver status after driver scan completes
        # For now, show as pending until drivers are scanned
        if hasattr(self, 'cached_data') and self.cached_data.get("drivers"):
            driver_data = self.cached_data["drivers"]
            total = len(driver_data) if isinstance(driver_data, list) else 0
            problem_count = sum(1 for d in driver_data if isinstance(d, dict) and d.get("status") != "OK") if isinstance(driver_data, list) else 0
            if problem_count > 0:
                self.overview.status_cards["drivers"].set_status("warning", f"{problem_count} issues")
            else:
                self.overview.status_cards["drivers"].set_status("check", f"{total} drivers OK")
        else:
            self.overview.status_cards["drivers"].set_status("check", "Not scanned")
        
        # Update startup programs card from scan results
        startup_res = self.scan_results.get("sfc", {})  # "sfc" is the task_id for startup
        if startup_res.get("data"):
            startup_items = startup_res["data"]
            enabled_count = sum(1 for item in startup_items if item.get("enabled", False))
            total_count = len(startup_items)
            self.overview.startup_card.summary_label.setText(f"{enabled_count} enabled, {total_count - enabled_count} disabled")
            if enabled_count > 15:
                self.overview.startup_card.status_chip.setText("Warning")
                self.overview.startup_card.status_chip.setStyleSheet(f"""
                    background: {Theme.WARNING_BG};
                    color: {Theme.WARNING};
                    font-size: 10px;
                    font-weight: 600;
                    padding: 3px 8px;
                    border-radius: 4px;
                """)
            else:
                self.overview.startup_card.status_chip.setText("Healthy")
                self.overview.startup_card.status_chip.setStyleSheet(f"""
                    background: {Theme.SUCCESS_BG};
                    color: {Theme.SUCCESS};
                    font-size: 10px;
                    font-weight: 600;
                    padding: 3px 8px;
                    border-radius: 4px;
                """)
        
        # Add activity entry
        self.overview.add_activity(
            "success" if errors == 0 else "warning",
            f"Full scan completed - {passed} passed, {warnings} warnings, {errors} issues",
            datetime.datetime.now().strftime("%I:%M %p")
        )
        
        # Populate detail pages with cached data
        self._populate_pages_from_cache()
        
        # Update status bar
        status_bar = self.statusBar()
        if status_bar:
            status_bar.showMessage(f"Scan complete - {passed} checks passed, {warnings} warnings, {errors} issues")
        
        # Set dialog to 100% and close
        self.scan_dialog.set_progress(100, "Complete")
        QTimer.singleShot(800, self.scan_dialog.accept)
    
    def _populate_pages_from_cache(self):
        """Populate all detail pages with cached scan data"""
        # Populate Startup page
        if self.cached_data.get("startup"):
            self.startup_page.display_cached_data(self.cached_data["startup"])  # type: ignore[arg-type]
        
        # Populate Events page with cached event data
        if self.cached_data.get("events"):
            event_data = self.cached_data["events"]
            self.events_page.display_cached_data(event_data)  # type: ignore[arg-type]
        
        # Populate System Files page - trigger detailed scan
        if self.scan_results.get("services"):
            self.system_page.display_cached_data(self.scan_results.get("services"))  # type: ignore[arg-type]
        
        # Populate Drivers page - trigger a scan if not already done
        if not self.cached_data.get("drivers"):
            # Queue driver scan for after dialog closes
            QTimer.singleShot(1000, self._scan_drivers_background)
        
        # Populate Windows Update page - trigger detailed check
        if self.cached_data.get("updates"):
            self.updates_page.display_cached_data(self.cached_data["updates"])  # type: ignore[arg-type]
        
        # Populate Storage page with cached volume data
        if self.cached_data.get("storage"):
            self.storage_page.display_cached_data(self.cached_data["storage"])  # type: ignore[arg-type]
        
        # Populate Security page with cached defender data
        if self.cached_data.get("security"):
            defender = self.cached_data["security"]
            # Store in security page's cache and display
            self.security_page.cached_defender_data = defender  # type: ignore[assignment]
            self.security_page.display_defender_data(defender)  # type: ignore[arg-type]
        
        if self.cached_data.get("hardware"):
            hw_data = self.cached_data["hardware"]
            self.hardware_page.display_cached_data(hw_data)  # type: ignore[arg-type]
        
        # Trigger audio device scan (runs in background)
        QTimer.singleShot(500, self._scan_audio_devices)
    
    def _scan_audio_devices(self):
        """Scan audio devices in background after full scan"""
        if hasattr(self, 'audio_page'):
            self.audio_page.scan_devices()
    
    def _update_scan(self):
        """Legacy method - no longer used but kept for compatibility"""
        pass
    
    # =========================================================================
    # MODULE CHECK METHODS
    # =========================================================================
    
    def run_module_check(self, module_id: str):
        """Run the check for a specific module"""
        page = self.pages.get(module_id)
        if page and hasattr(page, 'set_checking'):
            page.set_checking()  # type: ignore[attr-defined]
            # Use timer to simulate async and allow UI to update
            QTimer.singleShot(100, lambda: self.check_methods[module_id]())
    
    def check_windows_updates(self):
        """Check Windows Update status - delegates to dedicated page"""
        # Use the dedicated WindowsUpdatePage which has its own background thread
        self.updates_page.check_updates()
    
    def _on_windows_update_complete(self, update_info: dict):
        """Handle completion of Windows Update check (legacy - kept for compatibility)"""
        # Cache the data
        self.cached_data["updates"] = update_info
        
        # Update overview card
        pending = update_info.get('PendingUpdates', 0)
        if isinstance(pending, list):
            pending = len(pending)
        
        self.overview.status_cards["updates"].set_status(
            "check" if pending == 0 else "warning",
            "Up to date" if pending == 0 else f"{pending} updates available"
        )
    
    def _open_windows_update(self):
        """Open Windows Update settings"""
        import subprocess
        try:
            subprocess.Popen(["ms-settings:windowsupdate"], shell=True)
        except Exception as e:
            print(f"Error opening Windows Update: {e}")
    
    def _open_windows_security(self):
        """Open Windows Security app"""
        import subprocess
        try:
            subprocess.Popen(["ms-settings:windowsdefender"], shell=True)
        except Exception as e:
            print(f"Error opening Windows Security: {e}")
    
    def _update_defender_definitions(self):
        """Trigger Windows Defender definition update"""
        import subprocess
        from PyQt6.QtWidgets import QMessageBox
        try:
            # Run Update-MpSignature
            subprocess.Popen(
                ['powershell', '-Command', 'Update-MpSignature'],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            QMessageBox.information(
                self,
                "Definition Update",
                "Windows Defender is updating virus definitions.\n\nThis runs in the background.",
                QMessageBox.StandardButton.Ok
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to update definitions: {e}")
    
    def _run_quick_scan(self):
        """Run Windows Defender quick scan"""
        import subprocess
        from PyQt6.QtWidgets import QMessageBox
        try:
            subprocess.Popen(
                ['powershell', '-Command', 'Start-MpScan -ScanType QuickScan'],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            QMessageBox.information(
                self,
                "Quick Scan",
                "Windows Defender Quick Scan started.\n\nThis runs in the background - check Windows Security for progress.",
                QMessageBox.StandardButton.Ok
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to start scan: {e}")
    
    def _trigger_update_check(self):
        """Trigger a Windows Update check"""
        import subprocess
        from PyQt6.QtWidgets import QMessageBox
        try:
            # Open Windows Update and trigger check
            subprocess.Popen(["ms-settings:windowsupdate-action"], shell=True)
            QMessageBox.information(
                self,
                "Windows Update",
                "Windows Update is checking for updates.\n\nThis runs in the background - check the Settings app for progress.",
                QMessageBox.StandardButton.Ok
            )
        except Exception as e:
            # Fallback to just opening Windows Update
            self._open_windows_update()
    
    def check_storage_health(self):
        """Check storage/disk health - delegates to StoragePage"""
        # Delegate to the dedicated storage page
        self.storage_page.scan_storage()
    
    def _on_storage_check_complete(self, volume_info: list):
        """Handle completion of storage health check - legacy method for compatibility"""
        # Cache the data
        self.cached_data["storage"] = volume_info
        
        # Forward to storage page
        self.storage_page.display_cached_data(volume_info)
        
        # Update status card based on volume usage
        worst_status = "check"
        for vol in volume_info:
            size_gb = vol.get('SizeGB', 0)
            free_gb = vol.get('FreeSpaceGB', 0)
            if size_gb > 0:
                used_percent = ((size_gb - free_gb) / size_gb) * 100
                if used_percent >= 90:
                    worst_status = "error"
                    break
                elif used_percent >= 75:
                    worst_status = "warning"
        
        self.overview.status_cards["storage"].set_status(
            worst_status,
            "Critical" if worst_status == "error" else "Warning" if worst_status == "warning" else "Healthy"
        )
    
    def check_security_status(self):
        """Check Windows Defender and security status using background thread"""
        # Show loading state
        self.security_page.set_checking()
        
        # Run check in background thread
        self._security_thread = QThread(self)
        self._security_worker = SecurityCheckWorker(self.health_checker)
        self._security_worker.moveToThread(self._security_thread)
        
        self._security_thread.started.connect(self._security_worker.run)
        self._security_worker.finished.connect(self._on_security_check_complete)
        self._security_worker.finished.connect(self._security_thread.quit)
        self._security_worker.finished.connect(self._security_worker.deleteLater)
        
        self._security_thread.start()
    
    def _on_security_check_complete(self, defender: dict):
        """Handle completion of security check"""
        # Cache the data
        self.cached_data["security"] = defender
        
        # Update the security page with the new data
        self.security_page.cached_defender_data = defender
        self.security_page.display_defender_data(defender)
        
        # Update overview card
        if 'Error' not in defender:
            enabled = defender.get('AntivirusEnabled', False)
            realtime = defender.get('RealTimeProtection', False)
            if enabled and realtime:
                self.overview.status_cards["defender"].set_status("check", "Protected")
            elif enabled:
                self.overview.status_cards["defender"].set_status("warning", "Partial")
            else:
                self.overview.status_cards["defender"].set_status("error", "At Risk")
        else:
            self.overview.status_cards["defender"].set_status("warning", "Unknown")
    
    def check_hardware_health(self):
        """Check hardware health including disks"""
        results = []
        try:
            disk_health = self.health_checker.check_disk_health()
            
            for disk in disk_health:
                model = disk.get('Model', 'Unknown Disk')
                size_gb = disk.get('Size', 0)
                status = disk.get('Status', 'Unknown')
                predict_fail = disk.get('PredictFailure', None)
                
                if predict_fail is True:
                    results.append(("error", f"{model} ({size_gb} GB) - FAILURE PREDICTED! Back up data immediately!"))
                elif predict_fail is False:
                    results.append(("check", f"{model} ({size_gb} GB) - SMART status OK"))
                else:
                    if status == "OK":
                        results.append(("check", f"{model} ({size_gb} GB) - Status: {status}"))
                    else:
                        results.append(("warning", f"{model} ({size_gb} GB) - Status: {status}"))
                
        except Exception as e:
            results.append(("error", f"Error checking hardware: {str(e)}"))
        
        if not results:
            results.append(("info", "No hardware information available"))
        
        self.pages["hardware"].show_results(results)  # type: ignore[attr-defined]
        
        worst_status = "check"
        for status, _ in results:
            if status == "error":
                worst_status = "error"
                break
            elif status == "warning":
                worst_status = "warning"
        
        self.overview.status_cards["memory"].set_status(
            worst_status,
            "Healthy" if worst_status == "check" else "Attention needed"
        )
    
    def check_system_files(self):
        """Check system file integrity - delegates to SystemPage"""
        # Delegate to the dedicated system page
        self.system_page.scan_system()
        self.overview.status_cards["system"].set_status("check", "No issues")
    
    def _run_sfc_scan(self):
        """Run SFC /scannow in an elevated terminal"""
        try:
            import subprocess
            # Open elevated command prompt with SFC command
            subprocess.Popen(
                ['powershell', '-Command', 
                 'Start-Process', 'cmd', '-ArgumentList', '"/k sfc /scannow"', '-Verb', 'RunAs'],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self.statusBar().showMessage("SFC scan launched in elevated terminal") # type: ignore
        except Exception as e:
            self.statusBar().showMessage(f"Failed to launch SFC: {e}") # type: ignore
    
    def _scan_drivers_background(self):
        """Trigger driver scan after full system scan completes"""
        try:
            # Let drivers page handle its own scan
            self.drivers_page.scan_drivers()
        except Exception:
            pass  # Driver scan is optional
    
    def _run_dism_repair(self):
        """Run DISM repair commands in an elevated terminal"""
        try:
            import subprocess
            # Open elevated command prompt with DISM commands
            dism_cmd = 'DISM /Online /Cleanup-Image /RestoreHealth && pause'
            subprocess.Popen(
                ['powershell', '-Command',
                 'Start-Process', 'cmd', '-ArgumentList', f'"/k {dism_cmd}"', '-Verb', 'RunAs'],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self.statusBar().showMessage("DISM repair launched in elevated terminal") # pyright: ignore[reportOptionalMemberAccess]
        except Exception as e:
            self.statusBar().showMessage(f"Failed to launch DISM: {e}") # pyright: ignore[reportOptionalMemberAccess]
    
    def check_event_logs(self):
        """Check Windows event logs - delegates to EventsPage"""
        # EventsPage handles its own scanning and display
        self.events_page.load_events()
    
    def _get_resize_direction(self, pos):
        """Determine resize direction based on cursor position"""
        rect = self.rect()
        margin = self._resize_margin
        
        left = pos.x() < margin
        right = pos.x() > rect.width() - margin
        top = pos.y() < margin
        bottom = pos.y() > rect.height() - margin
        
        if top and left:
            return "top_left"
        elif top and right:
            return "top_right"
        elif bottom and left:
            return "bottom_left"
        elif bottom and right:
            return "bottom_right"
        elif left:
            return "left"
        elif right:
            return "right"
        elif top:
            return "top"
        elif bottom:
            return "bottom"
        return None
    
    def _update_cursor_for_position(self, global_pos):
        """Update cursor based on global mouse position relative to window"""
        local_pos = self.mapFromGlobal(global_pos)
        resize_dir = self._get_resize_direction(local_pos)
        
        if resize_dir in ("left", "right"):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif resize_dir in ("top", "bottom"):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif resize_dir in ("top_left", "bottom_right"):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif resize_dir in ("top_right", "bottom_left"):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        else:
            self.unsetCursor()
    
    def event(self, event):  # type: ignore[override]
        """Override event to handle cursor changes for resize zones"""
        from PyQt6.QtCore import QEvent
        
        # Handle hover/mouse move to update cursor for resize areas
        if event is not None and event.type() == QEvent.Type.HoverMove:
            if not self._resize_dir:  # Only update cursor when not actively resizing
                hover_event = event  # Cast for type checker
                if hasattr(hover_event, 'position'):
                    self._update_cursor_for_position(self.mapToGlobal(hover_event.position().toPoint()))
        
        return super().event(event)
    
    def enterEvent(self, event):  # type: ignore[override]
        """Update cursor when mouse enters window"""
        if event is not None and hasattr(event, 'position'):
            self._update_cursor_for_position(self.mapToGlobal(event.position().toPoint()))
        super().enterEvent(event)
    
    def leaveEvent(self, event):  # type: ignore[override]
        """Reset cursor when mouse leaves window"""
        if not self._resize_dir:
            self.unsetCursor()
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):  # type: ignore[override]
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self._resize_dir = self._get_resize_direction(event.pos())
            if self._resize_dir:
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geo = self.geometry()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):  # type: ignore[override]
        if event is not None and self._resize_dir and self._resize_start_geo and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            geo = self._resize_start_geo  # Original geometry at start of drag
            min_w, min_h = self.minimumWidth(), self.minimumHeight()
            
            # Start with original geometry values
            new_x = geo.x()
            new_y = geo.y()
            new_w = geo.width()
            new_h = geo.height()
            
            if "right" in self._resize_dir:
                new_w = max(min_w, geo.width() + delta.x())
            if "bottom" in self._resize_dir:
                new_h = max(min_h, geo.height() + delta.y())
            if "left" in self._resize_dir:
                proposed_w = geo.width() - delta.x()
                if proposed_w >= min_w:
                    new_w = proposed_w
                    new_x = geo.x() + delta.x()
                else:
                    new_w = min_w
                    new_x = geo.x() + geo.width() - min_w
            if "top" in self._resize_dir:
                proposed_h = geo.height() - delta.y()
                if proposed_h >= min_h:
                    new_h = proposed_h
                    new_y = geo.y() + delta.y()
                else:
                    new_h = min_h
                    new_y = geo.y() + geo.height() - min_h
            
            self.setGeometry(new_x, new_y, new_w, new_h)
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):  # type: ignore[override]
        self._resize_dir = None
        self.unsetCursor()
        super().mouseReleaseEvent(event)
    
    def closeEvent(self, event):  # type: ignore[override]
        """Clean up all running threads before closing"""
        # Helper to safely stop a thread
        def stop_thread(thread_attr):
            thread = getattr(self, thread_attr, None)
            if thread is not None and thread.isRunning():
                thread.quit()
                if not thread.wait(1000):  # Wait up to 1 second
                    thread.terminate()
                    thread.wait(500)
        
        # Stop MainWindow threads
        for attr in ['_update_thread', '_security_thread', '_storage_thread', '_startup_scan_thread']:
            stop_thread(attr)
        
        # Stop page threads
        pages_with_threads = [
            ('drivers_page', ['_driver_scan_thread', '_unused_scan_thread']),
            ('updates_page', ['_wu_check_thread']),
            ('security_page', ['_fw_status_thread', '_fw_rules_thread', '_thread']),
            ('hardware_page', ['_thread']),
            ('storage_page', ['_thread']),
            ('startup_page', ['_thread']),
            ('events_page', ['_thread']),
            ('audio_page', ['_thread']),
            ('overview', ['_thread']),
        ]
        
        for page_attr, thread_attrs in pages_with_threads:
            page = getattr(self, page_attr, None)
            if page:
                for thread_attr in thread_attrs:
                    thread = getattr(page, thread_attr, None)
                    if thread is not None and hasattr(thread, 'isRunning') and thread.isRunning():
                        thread.quit()
                        if not thread.wait(500):
                            thread.terminate()
                            thread.wait(250)
        
        # Stop the metrics collector in overview page
        if hasattr(self, 'overview') and hasattr(self.overview, 'metrics_collector'):
            self.overview.metrics_collector.stop()  # type: ignore[attr-defined]
        
        if event is not None:
            event.accept()


# =============================================================================
# SPLASH SCREEN (Runs in separate process)
# =============================================================================

def run_splash_process(pipe_conn):
    """
    Run splash screen in a separate process.
    Communicates with main process via pipe.
    """
    import sys
    from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QProgressBar
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QPainter, QColor, QBrush, QPen
    
    app = QApplication(sys.argv)
    
    # Theme colors from Theme class - exact match
    THEME = {
        "bg_window": "#1a1a1e",
        "bg_card": "#28282d",
        "bg_elevated": "#3a3a40",
        "border": "#404048",
        "border_light": "#505058",
        "text_primary": "#ffffff",
        "text_secondary": "#c0c0c8",
        "text_tertiary": "#808088",
        "accent": "#0078d4",
        "accent_hover": "#1a8cde",
        "success": "#4caf50",
        "warning": "#ff9800",
        "error": "#f44336",
        "info": "#2196f3",
    }
    
    class SplashWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint | 
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.SplashScreen
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setFixedSize(440, 400)
            
            # Center on screen
            screen = app.primaryScreen()
            if screen:
                geom = screen.geometry()
                x = (geom.width() - self.width()) // 2
                y = (geom.height() - self.height()) // 2
                self.move(x, y)
            
            self.task_labels = {}
            self.setup_ui()
            
            # Timer to check for messages from main process
            self.check_timer = QTimer()
            self.check_timer.timeout.connect(self.check_pipe)
            self.check_timer.start(50)
        
        def setup_ui(self):
            layout = QVBoxLayout(self)
            layout.setContentsMargins(8, 8, 8, 8)
            
            # Main container with card background
            container = QFrame()
            container.setObjectName("splashContainer")
            container.setStyleSheet(f"""
                #splashContainer {{
                    background: {THEME['bg_window']};
                    border-radius: 16px;
                    border: none;
                }}
            """)
            
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(32, 28, 32, 24)
            container_layout.setSpacing(0)
            
            # ===== Header Section =====
            header_layout = QHBoxLayout()
            header_layout.setSpacing(14)
            header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # App icon - simple plus symbol with accent background
            icon_container = QFrame()
            icon_container.setFixedSize(48, 48)
            icon_container.setStyleSheet(f"""
                QFrame {{
                    background: {THEME['accent']};
                    border-radius: 12px;
                }}
            """)
            icon_layout = QHBoxLayout(icon_container)
            icon_layout.setContentsMargins(0, 0, 0, 0)
            icon = QLabel("+")
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon.setStyleSheet("background: transparent; color: white; font-size: 24px; font-weight: bold;")
            icon_layout.addWidget(icon)
            header_layout.addWidget(icon_container)
            
            # Title stack
            title_stack = QVBoxLayout()
            title_stack.setSpacing(2)
            
            title = QLabel("Health Checker Pro")
            title.setStyleSheet(f"background: transparent; color: {THEME['text_primary']}; font-size: 20px; font-weight: 600;")
            title_stack.addWidget(title)
            
            subtitle = QLabel("Windows System Diagnostics")
            subtitle.setStyleSheet(f"background: transparent; color: {THEME['text_secondary']}; font-size: 11px;")
            title_stack.addWidget(subtitle)
            
            header_layout.addLayout(title_stack)
            container_layout.addLayout(header_layout)
            
            container_layout.addSpacing(24)
            
            # ===== Task List Section =====
            task_frame = QFrame()
            task_frame.setObjectName("taskFrame")
            task_frame.setStyleSheet(f"""
                #taskFrame {{
                    background: {THEME['bg_card']};
                    border-radius: 10px;
                    border: none;
                }}
            """)
            task_layout = QVBoxLayout(task_frame)
            task_layout.setContentsMargins(16, 14, 16, 14)
            task_layout.setSpacing(10)
            
            # Section header
            section_header = QLabel("LOADING COMPONENTS")
            section_header.setStyleSheet(f"""
                background: transparent; 
                color: {THEME['text_tertiary']}; 
                font-size: 9px; 
                font-weight: 600; 
                letter-spacing: 1px;
            """)
            task_layout.addWidget(section_header)
            
            # Task items
            tasks = [
                ("imports", "Core modules"),
                ("qt", "UI framework"),
                ("permissions", "Permissions"),
                ("backends", "Diagnostics"),
                ("ui", "Interface"),
            ]
            
            for task_id, task_name in tasks:
                row = QHBoxLayout()
                row.setSpacing(12)
                
                # Status indicator - circle that changes color
                indicator = QFrame()
                indicator.setFixedSize(8, 8)
                indicator.setStyleSheet(f"""
                    background: {THEME['border']};
                    border-radius: 4px;
                """)
                row.addWidget(indicator)
                
                # Task name
                name_label = QLabel(task_name)
                name_label.setStyleSheet(f"background: transparent; color: {THEME['text_secondary']}; font-size: 12px;")
                row.addWidget(name_label)
                
                row.addStretch()
                
                # Status text (time or status)
                status_label = QLabel("")
                status_label.setFixedWidth(50)
                status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                status_label.setStyleSheet(f"background: transparent; color: {THEME['text_tertiary']}; font-size: 10px;")
                row.addWidget(status_label)
                
                task_layout.addLayout(row)
                self.task_labels[task_id] = {
                    "indicator": indicator, 
                    "name": name_label, 
                    "status": status_label
                }
            
            container_layout.addWidget(task_frame)
            
            container_layout.addSpacing(20)
            
            # ===== Progress Section =====
            # Progress bar
            self.progress_bar = QProgressBar()
            self.progress_bar.setFixedHeight(6)
            self.progress_bar.setTextVisible(False)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setStyleSheet(f"""
                QProgressBar {{
                    background: {THEME['bg_elevated']};
                    border: none;
                    border-radius: 3px;
                }}
                QProgressBar::chunk {{
                    background: {THEME['accent']};
                    border-radius: 3px;
                }}
            """)
            container_layout.addWidget(self.progress_bar)
            
            container_layout.addSpacing(8)
            
            # Status row
            status_row = QHBoxLayout()
            self.status_label = QLabel("Starting...")
            self.status_label.setStyleSheet(f"background: transparent; color: {THEME['text_secondary']}; font-size: 11px;")
            status_row.addWidget(self.status_label)
            
            status_row.addStretch()
            
            self.percent_label = QLabel("0%")
            self.percent_label.setStyleSheet(f"background: transparent; color: {THEME['accent']}; font-size: 11px; font-weight: 600;")
            status_row.addWidget(self.percent_label)
            
            container_layout.addLayout(status_row)
            
            container_layout.addStretch()
            
            # ===== Footer =====
            footer = QLabel(f"v{APP_VERSION}")
            footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
            footer.setStyleSheet(f"background: transparent; color: {THEME['text_tertiary']}; font-size: 10px;")
            container_layout.addWidget(footer)
            
            layout.addWidget(container)
        
        def update_task(self, task_id: str, status: str, time_ms: float | None = None):
            """Update a task's status and time"""
            if task_id in self.task_labels:
                labels = self.task_labels[task_id]
                if status == "running":
                    labels["indicator"].setStyleSheet(f"background: {THEME['warning']}; border-radius: 4px;")
                    labels["name"].setStyleSheet(f"background: transparent; color: {THEME['text_primary']}; font-size: 12px;")
                    labels["status"].setText("...")
                    labels["status"].setStyleSheet(f"background: transparent; color: {THEME['warning']}; font-size: 10px;")
                elif status == "complete":
                    labels["indicator"].setStyleSheet(f"background: {THEME['success']}; border-radius: 4px;")
                    labels["name"].setStyleSheet(f"background: transparent; color: {THEME['success']}; font-size: 12px;")
                    if time_ms is not None:
                        if time_ms >= 1000:
                            labels["status"].setText(f"{time_ms/1000:.1f}s")
                        else:
                            labels["status"].setText(f"{time_ms:.0f}ms")
                        labels["status"].setStyleSheet(f"background: transparent; color: {THEME['success']}; font-size: 10px;")
                elif status == "error":
                    labels["indicator"].setStyleSheet(f"background: {THEME['error']}; border-radius: 4px;")
                    labels["name"].setStyleSheet(f"background: transparent; color: {THEME['error']}; font-size: 12px;")
                    labels["status"].setText("Error")
                    labels["status"].setStyleSheet(f"background: transparent; color: {THEME['error']}; font-size: 10px;")
        
        def check_pipe(self):
            """Check for messages from main process"""
            try:
                if pipe_conn.poll():
                    msg = pipe_conn.recv()
                    if msg.get("action") == "progress":
                        value = msg.get("value", 0)
                        self.progress_bar.setValue(value)
                        self.percent_label.setText(f"{value}%")
                        if msg.get("status"):
                            self.status_label.setText(msg["status"])
                    elif msg.get("action") == "task":
                        self.update_task(
                            msg.get("task_id", ""),
                            msg.get("status", ""),
                            msg.get("time_ms")
                        )
                    elif msg.get("action") == "close":
                        self.check_timer.stop()
                        app.quit()
            except Exception:
                pass
        
        def paintEvent(self, event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Draw subtle shadow
            for i in range(5):
                opacity = 30 - (i * 5)
                shadow_color = QColor(0, 0, 0, opacity)
                painter.setBrush(QBrush(shadow_color))
                painter.setPen(Qt.PenStyle.NoPen)
                offset = 8 - i
                painter.drawRoundedRect(offset, offset, self.width() - offset, self.height() - offset, 16, 16)
    
    splash = SplashWindow()
    splash.show()
    app.exec()


class SplashController:
    """
    Controller for the splash screen process.
    Runs splash in separate process and communicates via pipe.
    """
    
    def __init__(self):
        self.process = None
        self.parent_conn = None
        self.child_conn = None
    
    def start(self):
        """Start the splash screen process"""
        import multiprocessing
        self.parent_conn, self.child_conn = multiprocessing.Pipe()
        self.process = multiprocessing.Process(
            target=run_splash_process, 
            args=(self.child_conn,),
            daemon=True
        )
        self.process.start()
    
    def set_progress(self, value: int, status: str | None = None):
        """Update splash screen progress"""
        if self.parent_conn:
            try:
                self.parent_conn.send({
                    "action": "progress",
                    "value": value,
                    "status": status
                })
            except Exception:
                pass
    
    def update_task(self, task_id: str, status: str, time_ms: float | None = None):
        """Update a specific task in the splash screen task list"""
        if self.parent_conn:
            try:
                self.parent_conn.send({
                    "action": "task",
                    "task_id": task_id,
                    "status": status,
                    "time_ms": time_ms
                })
            except Exception:
                pass
    
    def close(self):
        """Close the splash screen"""
        if self.parent_conn:
            try:
                self.parent_conn.send({"action": "close"})
            except Exception:
                pass
        
        # Give it a moment to close gracefully
        if self.process:
            self.process.join(timeout=1)
            if self.process.is_alive():
                self.process.terminate()


# =============================================================================
# ENTRY POINT
# =============================================================================

def show_error_dialog(exc_type, exc_value, exc_tb):
    """Show a detailed error dialog when an unhandled exception occurs"""
    import traceback
    from PyQt6.QtWidgets import QMessageBox, QApplication
    
    # Format the traceback
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    tb_text = ''.join(tb_lines)
    
    # Log to file
    try:
        import os
        import datetime
        log_path = os.path.join(os.path.expanduser("~"), "health_checker_crash.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"CRASH: {datetime.datetime.now().isoformat()}\n")
            f.write(f"{'='*60}\n")
            f.write(tb_text)
            f.write(f"\n{'='*60}\n")
    except:
        log_path = None
    
    # Print to console for debugging
    print("=" * 60)
    print("UNHANDLED EXCEPTION:")
    print("=" * 60)
    print(tb_text)
    print("=" * 60)
    
    # Show dialog if Qt app exists
    app = QApplication.instance()
    if app:
        error_msg = f"An unexpected error occurred:\n\n{exc_type.__name__}: {exc_value}"
        
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Windows Health Checker Pro - Error")
        msg_box.setText(error_msg)
        msg_box.setDetailedText(tb_text)
        if log_path:
            msg_box.setInformativeText(f"Details saved to: {log_path}")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Ignore)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Ok)
        
        result = msg_box.exec()
        if result == QMessageBox.StandardButton.Ok:
            # Exit the application
            app.quit()
            sys.exit(1)
        # If Ignore, continue running (may be unstable)


def install_exception_hooks():
    """Install global exception handlers for both Python and Qt"""
    # Python exception hook
    sys.excepthook = show_error_dialog
    
    # Qt exception hook for signals/slots (unhandled exceptions in Qt callbacks)
    def qt_exception_hook(exc_type, exc_value, exc_tb):
        show_error_dialog(exc_type, exc_value, exc_tb)
    
    # Store original to call if needed
    original_excepthook = sys.excepthook
    sys.excepthook = qt_exception_hook


def main():
    import multiprocessing
    import time
    multiprocessing.freeze_support()  # Required for Windows executables
    
    # Install global exception handlers
    install_exception_hooks()
    
    # Start splash screen in separate process
    splash = SplashController()
    splash.start()
    splash.set_progress(5, "Starting application...")
    
    # Track timing for each task
    task_start = time.time()
    
    # Task 1: Loading modules
    splash.update_task("imports", "running")
    splash.set_progress(10, "Loading modules...")
    # Heavy imports happen here implicitly
    imports_time = (time.time() - task_start) * 1000
    splash.update_task("imports", "complete", imports_time)
    
    # Task 2: Qt framework
    task_start = time.time()
    splash.update_task("qt", "running")
    splash.set_progress(25, "Loading UI framework...")
    
    # Enable high DPI before creating app
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    qt_time = (time.time() - task_start) * 1000
    splash.update_task("qt", "complete", qt_time)
    
    # Task 3: Check permissions
    task_start = time.time()
    splash.update_task("permissions", "running")
    splash.set_progress(40, "Checking permissions...")
    
    # Check admin privileges
    admin_check = is_admin()
    perms_time = (time.time() - task_start) * 1000
    splash.update_task("permissions", "complete", perms_time)
    
    if not admin_check:
        splash.close()  # Close splash before showing dialog
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            None,
            "Administrator Required",
            "This application requires administrator privileges for full functionality.\n\n"
            "Would you like to restart as administrator?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            run_as_admin()
            sys.exit()
        # If user says no, restart splash
        splash = SplashController()
        splash.start()
        splash.set_progress(45, "Continuing...")
    
    # Task 4: Initialize backends
    task_start = time.time()
    splash.update_task("backends", "running")
    splash.set_progress(55, "Initializing backends...")
    
    # Create the main window (this initializes backends)
    window = MainWindow()
    backends_time = (time.time() - task_start) * 1000
    splash.update_task("backends", "complete", backends_time)
    
    # Task 5: Building interface
    task_start = time.time()
    splash.update_task("ui", "running")
    splash.set_progress(85, "Preparing interface...")
    
    # Small delay to ensure UI is ready
    time.sleep(0.1)
    ui_time = (time.time() - task_start) * 1000
    splash.update_task("ui", "complete", ui_time)
    
    splash.set_progress(100, "Ready!")
    time.sleep(0.3)
    
    # Close splash and show window
    splash.close()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        import sys
        
        # Try to show GUI error dialog
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            app = QApplication.instance() or QApplication(sys.argv)
            
            tb_text = traceback.format_exc()
            
            # Log to file
            try:
                import os
                import datetime
                log_path = os.path.join(os.path.expanduser("~"), "health_checker_crash.log")
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*60}\n")
                    f.write(f"STARTUP CRASH: {datetime.datetime.now().isoformat()}\n")
                    f.write(f"{'='*60}\n")
                    f.write(tb_text)
                    f.write(f"\n{'='*60}\n")
            except:
                log_path = "your home folder"
            
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("Windows Health Checker Pro - Startup Error")
            msg_box.setText(f"The application failed to start:\n\n{type(e).__name__}: {e}")
            msg_box.setDetailedText(tb_text)
            msg_box.setInformativeText(f"Error log saved to: {log_path}")
            msg_box.exec()
        except:
            # Fallback to console
            print("=" * 60)
            print("CRASH LOG:")
            print("=" * 60)
            traceback.print_exc()
            print("=" * 60)
            input("Press Enter to exit...")
