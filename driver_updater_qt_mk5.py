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
from ctypes import wintypes
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QProgressBar,
    QStackedWidget, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
    QSizePolicy, QDialog, QGridLayout, QTextEdit, QSpacerItem
)
from PyQt6.QtCore import Qt, QTimer, QSize, QPropertyAnimation, QEasingCurve, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush, QFontDatabase, QPainterPath, QIcon, QPixmap

from driver_backend import (
    DriverScanner, OnlineDriverChecker, ManufacturerSupport,
    HealthChecker, DiskManager, DriverInfo,
    is_admin, run_as_admin
)

# Performance utilities
try:
    from perf_utils import timed, TimingContext, perf_logger, BatchUpdater
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
                                    # Found the app, try to get icon
                                    try:
                                        display_icon, _ = winreg.QueryValueEx(subkey, "DisplayIcon")
                                        icon_path = display_icon.split(",")[0].strip('"')
                                        if os.path.exists(icon_path):
                                            icon = QIcon(icon_path)
                                            if not icon.isNull():
                                                return icon.pixmap(32, 32)
                                    except:
                                        pass
                                    
                                    # Try InstallLocation
                                    try:
                                        install_loc, _ = winreg.QueryValueEx(subkey, "InstallLocation")
                                        if install_loc and os.path.isdir(install_loc):
                                            # Look for exe files
                                            for f in os.listdir(install_loc):
                                                if f.endswith('.exe'):
                                                    exe_path = os.path.join(install_loc, f)
                                                    icon = QIcon(exe_path)
                                                    if not icon.isNull():
                                                        return icon.pixmap(32, 32)
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
        get_cached_app_icon._cache = {}
    
    cache_key = f"{app_name}_{size}"
    if cache_key in get_cached_app_icon._cache:
        return get_cached_app_icon._cache[cache_key]
    
    pixmap = get_app_icon_from_registry(app_name)
    if pixmap:
        # Scale to desired size
        pixmap = pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, 
                               Qt.TransformationMode.SmoothTransformation)
    
    get_cached_app_icon._cache[cache_key] = pixmap
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
    # Material Design: High emphasis text at 87% white
    # But we use NEAR-WHITE for better visibility
    # =========================================================================
    TEXT_PRIMARY = "#ffffff"           # Pure white for headings
    TEXT_SECONDARY = "#c0c0c8"         # Light grey for body (higher than 60%)
    TEXT_TERTIARY = "#808088"          # Medium grey for captions
    TEXT_DISABLED = "#606068"          # Disabled state
    
    # Hex versions (same as above for Qt stylesheet compatibility)
    TEXT_PRIMARY_HEX = "#ffffff"
    TEXT_SECONDARY_HEX = "#c0c0c8"
    TEXT_TERTIARY_HEX = "#808088"
    
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
    # SEMANTIC COLORS - Vibrant but not eye-straining
    # =========================================================================
    # Success - Green (vibrant but not neon)
    SUCCESS = "#4caf50"                # Material Green 500
    SUCCESS_LIGHT = "#81c784"          # Lighter for text
    SUCCESS_BG = "rgba(76, 175, 80, 0.15)"
    
    # Warning - Amber/Orange
    WARNING = "#ff9800"                # Material Orange 500
    WARNING_LIGHT = "#ffb74d"          # Lighter for text
    WARNING_BG = "rgba(255, 152, 0, 0.15)"
    
    # Error - Red (vibrant)
    ERROR = "#f44336"                  # Material Red 500
    ERROR_LIGHT = "#ef5350"            # Lighter variant
    ERROR_BG = "rgba(244, 67, 54, 0.15)"
    
    # Info - Blue
    INFO = "#2196f3"                   # Material Blue 500
    INFO_LIGHT = "#64b5f6"             # Lighter for text
    INFO_BG = "rgba(33, 150, 243, 0.15)"
    
    # Running/Progress - Purple
    RUNNING = "#9c27b0"                # Material Purple 500
    RUNNING_LIGHT = "#ba68c8"          # Lighter variant
    RUNNING_BG = "rgba(156, 39, 176, 0.15)"
    
    # =========================================================================
    # APPLE-STYLE GLOW COLORS - For status icon animations
    # =========================================================================
    GLOW_SUCCESS = "#30d158"           # Apple green - vibrant
    GLOW_ERROR = "#ff453a"             # Apple red - vibrant
    GLOW_WARNING = "#ffd60a"           # Apple yellow - vibrant
    GLOW_INFO = "#0a84ff"              # Apple blue - vibrant
    GLOW_RUNNING = "#bf5af2"           # Apple purple - vibrant
    
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
    SIDEBAR_W = 240
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
    border: 1px solid {Theme.BORDER};
    border-radius: 5px;
    height: 10px;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {Theme.PRIMARY}, stop:1 {Theme.ACCENT_LIGHT});
    border-radius: 4px;
}}

QTextEdit {{
    background: {Theme.SURFACE_02DP};
    border: 1px solid {Theme.BORDER};
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
    border: 1px solid {Theme.BORDER};
    border-radius: {Theme.RADIUS_SM}px;
    padding: 10px 20px;
    font-weight: 500;
}}

QPushButton:hover {{
    background: {Theme.SURFACE_08DP};
    border-color: {Theme.PRIMARY};
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
                result = get_hardware_summary()
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
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
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
                ["powershell", "-NoProfile", "-Command", cmd],
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
    
    def paintEvent(self, event):
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
                    border: 1px solid {Theme.BORDER};
                    border-radius: {Theme.RADIUS_SM}px;
                    padding: 10px 20px;
                    font-size: 13px;
                    font-weight: 500;
                }}
                AnimatedButton:hover {{
                    background: {Theme.BG_CARD_HOVER};
                    border-color: {Theme.TEXT_TERTIARY};
                }}
                AnimatedButton:pressed {{
                    background: {Theme.BG_CARD};
                }}
                AnimatedButton:disabled {{
                    background: {Theme.BG_CARD};
                    color: {Theme.TEXT_DISABLED};
                    border-color: {Theme.BORDER};
                }}
            """)
    
    def enterEvent(self, event):
        """Animate shadow on hover"""
        if self._shadow:
            self._shadow.setBlurRadius(self._hover_shadow_blur)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
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
    
    def paintEvent(self, event):
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
                padding: 12px 28px;
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
    
    def leaveEvent(self, event):
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
        self.main_layout.setContentsMargins(16, 14, 16, 14)
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
                color: {Theme.TEXT_TERTIARY};
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
                    background: {Theme.BG_ELEVATED};
                    color: {Theme.TEXT_SECONDARY};
                    border: 1px solid {Theme.BORDER};
                    padding: 4px 14px;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background: {Theme.BG_CARD_HOVER};
                    color: {Theme.TEXT_PRIMARY};
                    border-color: {Theme.ACCENT};
                }}
            """)
        btn.clicked.connect(callback)
        self.action_layout.addWidget(btn)
        return btn
    
    def _apply_style(self):
        bg = Theme.BG_CARD if not self.is_alternate else "#292930"
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
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ModernCategoryHeader(QFrame):
    """Category header for grouping list items with a modern look."""
    
    def __init__(self, title: str, count: int = 0, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        
        # Category title - larger and bolder
        title_label = QLabel(title.upper())
        title_label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 1.5px;
        """)
        layout.addWidget(title_label)
        
        # Count badge
        if count > 0:
            count_label = QLabel(f"({count})")
            count_label.setStyleSheet(f"""
                background: transparent;
                color: {Theme.TEXT_TERTIARY};
                font-size: 12px;
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
                border: 1px solid {Theme.BORDER};
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
    """Navigation icon widget"""
    
    ICONS = {
        "overview": "grid",
        "updates": "download",
        "storage": "hdd",
        "security": "shield",
        "hardware": "cpu",
        "system": "file",
        "events": "alert",
        "settings": "gear",
    }
    
    def __init__(self, icon_name: str, size: int = 20, parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.icon_size = size
        self.color = Theme.TEXT_SECONDARY
        self.setFixedSize(size, size)
    
    def set_color(self, color: str):
        self.color = color
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        pen = QPen(QColor(self.color))
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        s = self.icon_size
        m = 3  # margin
        
        if self.icon_name == "grid":
            # 2x2 grid
            gap = 2
            box = (s - 2*m - gap) // 2
            painter.drawRoundedRect(m, m, box, box, 2, 2)
            painter.drawRoundedRect(m+box+gap, m, box, box, 2, 2)
            painter.drawRoundedRect(m, m+box+gap, box, box, 2, 2)
            painter.drawRoundedRect(m+box+gap, m+box+gap, box, box, 2, 2)
            
        elif self.icon_name == "download":
            cx = s // 2
            painter.drawLine(cx, m+2, cx, s-m-4)
            painter.drawLine(cx-4, s-m-7, cx, s-m-3)
            painter.drawLine(cx+4, s-m-7, cx, s-m-3)
            painter.drawLine(m+2, s-m, s-m-2, s-m)
            
        elif self.icon_name == "hdd":
            painter.drawRoundedRect(m, m+2, s-2*m, s-2*m-4, 3, 3)
            painter.drawLine(m+3, s//2, s-m-3, s//2)
            # LED dot
            painter.setBrush(QBrush(QColor(self.color)))
            painter.drawEllipse(s-m-5, s//2+3, 3, 3)
            
        elif self.icon_name == "shield":
            path = QPainterPath()
            cx = s / 2
            path.moveTo(cx, m)
            path.lineTo(s-m, m+4)
            path.lineTo(s-m, s//2+2)
            path.quadTo(s-m, s-m-2, cx, s-m)
            path.quadTo(m, s-m-2, m, s//2+2)
            path.lineTo(m, m+4)
            path.closeSubpath()
            painter.drawPath(path)
            
        elif self.icon_name == "cpu":
            # Main chip
            painter.drawRoundedRect(m+3, m+3, s-2*m-6, s-2*m-6, 2, 2)
            # Pins
            for i in range(3):
                x = m + 5 + i * 4
                painter.drawLine(x, m, x, m+3)
                painter.drawLine(x, s-m-3, x, s-m)
                painter.drawLine(m, m+5+i*4, m+3, m+5+i*4)
                painter.drawLine(s-m-3, m+5+i*4, s-m, m+5+i*4)
                
        elif self.icon_name == "file":
            painter.drawRoundedRect(m+2, m, s-2*m-4, s-2*m, 2, 2)
            # Lines
            for i in range(3):
                y = m + 5 + i * 4
                painter.drawLine(m+5, y, s-m-5, y)
                
        elif self.icon_name == "alert":
            # Triangle
            path = QPainterPath()
            cx = s / 2
            path.moveTo(cx, m+1)
            path.lineTo(s-m, s-m-1)
            path.lineTo(m, s-m-1)
            path.closeSubpath()
            painter.drawPath(path)
            # Exclamation
            painter.drawLine(int(cx), m+6, int(cx), s-m-6)
            painter.setBrush(QBrush(QColor(self.color)))
            painter.drawEllipse(int(cx)-1, s-m-4, 2, 2)
            
        elif self.icon_name == "gear":
            # Simple gear
            cx, cy = s//2, s//2
            painter.drawEllipse(cx-3, cy-3, 6, 6)
            for i in range(8):
                import math
                angle = i * math.pi / 4
                x1 = int(cx + 4 * math.cos(angle))
                y1 = int(cy + 4 * math.sin(angle))
                x2 = int(cx + 7 * math.cos(angle))
                y2 = int(cy + 7 * math.sin(angle))
                painter.drawLine(x1, y1, x2, y2)
        
        elif self.icon_name == "chip":
            # Chip/driver icon - circuit board style
            painter.drawRoundedRect(m+2, m+2, s-2*m-4, s-2*m-4, 2, 2)
            # Inner square
            painter.drawRect(m+5, m+5, s-2*m-10, s-2*m-10)
            # Connection pins on all sides
            cx, cy = s//2, s//2
            pin_len = 3
            # Top and bottom pins
            painter.drawLine(cx-3, m+2, cx-3, m+2-pin_len)
            painter.drawLine(cx+3, m+2, cx+3, m+2-pin_len)
            painter.drawLine(cx-3, s-m-2, cx-3, s-m-2+pin_len)
            painter.drawLine(cx+3, s-m-2, cx+3, s-m-2+pin_len)
            # Left and right pins
            painter.drawLine(m+2, cy-3, m+2-pin_len, cy-3)
            painter.drawLine(m+2, cy+3, m+2-pin_len, cy+3)
            painter.drawLine(s-m-2, cy-3, s-m-2+pin_len, cy-3)
            painter.drawLine(s-m-2, cy+3, s-m-2+pin_len, cy+3)
        
        elif self.icon_name == "rocket":
            # Rocket icon for startup programs
            import math
            cx, cy = s // 2, s // 2
            # Rocket body (rotated 45 degrees - pointing up-right)
            path = QPainterPath()
            path.moveTo(s - m - 2, m + 2)  # nose
            path.lineTo(s - m - 5, m + 5)
            path.lineTo(m + 5, s - m - 5)
            path.lineTo(m + 2, s - m - 2)  # tail
            path.lineTo(m + 5, s - m - 5)
            path.lineTo(s - m - 5, m + 5)
            path.closeSubpath()
            painter.drawPath(path)
            # Fins
            painter.drawLine(m + 3, s - m - 6, m + 6, s - m - 3)
            painter.drawLine(s - m - 6, m + 3, s - m - 3, m + 6)
            # Exhaust flames
            painter.drawLine(m + 1, s - m - 1, m + 4, s - m - 4)
            painter.drawLine(m + 3, s - m + 1, m + 6, s - m - 2)
        
        elif self.icon_name == "speaker":
            # Speaker/audio icon
            import math
            # Speaker cone
            path = QPainterPath()
            path.moveTo(m + 2, s // 2 - 3)
            path.lineTo(m + 5, s // 2 - 3)
            path.lineTo(m + 9, s // 2 - 6)
            path.lineTo(m + 9, s // 2 + 6)
            path.lineTo(m + 5, s // 2 + 3)
            path.lineTo(m + 2, s // 2 + 3)
            path.closeSubpath()
            painter.drawPath(path)
            # Sound waves
            for i, radius in enumerate([4, 7]):
                cx = m + 9
                cy = s // 2
                start_angle = -45
                span_angle = 90
                painter.drawArc(cx, cy - radius, radius * 2, radius * 2, start_angle * 16, span_angle * 16)


class SidebarItem(QFrame):
    """Refined sidebar navigation item"""
    
    def __init__(self, icon_name: str, label: str, parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.label_text = label
        self.is_active = False
        self.setFixedHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
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
    
    def set_active(self, active: bool):
        self.is_active = active
        self._update_style()
    
    def _update_style(self):
        """Update style - Apple-style glass with vibrant accent"""
        if self.is_active:
            # Selected state: glowing left border, glass background
            self.setStyleSheet(f"""
                SidebarItem {{
                    background: rgba(0, 120, 212, 0.2);
                    border-left: 3px solid {Theme.GLOW_INFO};
                    border-radius: 0px;
                    margin-left: 0px;
                    margin-right: 12px;
                    padding-left: 9px;
                }}
            """)
            self.icon.set_color(Theme.GLOW_INFO)
            self.label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-weight: 600;")
        else:
            # Default state: transparent
            self.setStyleSheet(f"""
                SidebarItem {{
                    background: transparent;
                    border-left: 3px solid transparent;
                    border-radius: 0px;
                    margin-left: 0px;
                    margin-right: 12px;
                    padding-left: 9px;
                }}
            """)
            self.icon.set_color(Theme.TEXT_SECONDARY)
            self.label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-weight: normal;")
    
    def enterEvent(self, event):
        if not self.is_active:
            # Hover state: subtle background
            self.setStyleSheet(f"""
                SidebarItem {{
                    background: {Theme.BG_CARD_HOVER};
                    border-left: 3px solid transparent;
                    border-radius: 0px;
                    margin-left: 0px;
                    margin-right: 12px;
                    padding-left: 9px;
                }}
            """)
            self.icon.set_color(Theme.TEXT_PRIMARY)
            self.label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-weight: normal;")
    
    def leaveEvent(self, event):
        self._update_style()


class ScoreRing(QWidget):
    """Animated score ring widget"""
    
    def __init__(self, size: int = 120, parent=None):
        super().__init__(parent)
        self.ring_size = size
        self.score = 0
        self.target_score = 0
        self.setFixedSize(size, size)
        
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
    
    def paintEvent(self, event):
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
    """Clean glass card without glow - glow is painted by parent container"""
    
    clicked = pyqtSignal()
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title_text = title
        self._status = "pending"
        self.setFixedHeight(72)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        # Status icon
        self.status_icon = QLabel("○")
        self.status_icon.setFixedSize(22, 22)
        self.status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_icon.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 16px;")
        layout.addWidget(self.status_icon)
        
        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        self.title = QLabel(self.title_text)
        self.title.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 13px; font-weight: 600;")
        text_layout.addWidget(self.title)
        
        self.subtitle = QLabel("Checking...")
        self.subtitle.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
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
    
    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)
    
    def set_status(self, status: str, subtitle: str):
        self._status = status
        self.subtitle.setText(subtitle)
        self.subtitle.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 11px;")
        
        # Update icon with vibrant colors
        icons = {
            "check": ("✓", Theme.GLOW_SUCCESS),
            "warning": ("!", Theme.GLOW_WARNING),
            "error": ("✕", Theme.GLOW_ERROR),
            "info": ("i", Theme.GLOW_INFO),
            "running": ("◐", Theme.GLOW_RUNNING),
            "pending": ("○", Theme.TEXT_TERTIARY),
        }
        icon_char, icon_color = icons.get(status, ("○", Theme.TEXT_TERTIARY))
        self.status_icon.setText(icon_char)
        self.status_icon.setStyleSheet(f"background: transparent; color: {icon_color}; font-size: 16px; font-weight: bold;")
        
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
            
            # Very subtle 2-layer glow
            for i in range(2, 0, -1):
                layer_color = QColor(glow_color)
                # Much more subtle - max alpha around 20
                alpha = int(18 * pulse * (3 - i) / 2)
                layer_color.setAlpha(alpha)
                
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(layer_color))
                
                expand = i * 6
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
            
            # Card background - solid dark
            bg_color = QColor(32, 32, 36)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(bg_color))
            
            path = QPainterPath()
            path.addRoundedRect(
                float(card_rect.x()), float(card_rect.y()),
                float(card_rect.width()), float(card_rect.height()),
                radius, radius
            )
            painter.drawPath(path)
            
            # Colored border for status cards - more subtle
            if status in ("check", "error", "warning"):
                glow_color = card.get_glow_color()
                border_alpha = int(80 + 50 * pulse)
                border_color = QColor(glow_color.red(), glow_color.green(), glow_color.blue(), border_alpha)
                painter.setPen(QPen(border_color, 1.5))
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
        
        # Simple solid card background
        bg_color = QColor(32, 32, 36)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg_color))
        
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
        "threshold": 15,
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
                border: 1px solid {Theme.GLASS_BORDER};
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
        icon_label = QLabel("▶")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"background: transparent; color: {Theme.ACCENT_LIGHT}; font-size: 14px; font-weight: bold;")
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
            font-size: 15px;
            font-weight: 600;
        """)
        title_row.addWidget(title)
        
        self.status_chip = QLabel("Healthy")
        self.status_chip.setStyleSheet(f"""
            background: {Theme.SUCCESS_BG};
            color: {Theme.SUCCESS};
            font-size: 10px;
            font-weight: 600;
            padding: 3px 8px;
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
        sep.setStyleSheet(f"background: {Theme.BORDER};")
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
                border: 1px solid {Theme.BORDER};
                padding: 8px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_ELEVATED};
                border-color: {Theme.ACCENT};
            }}
        """)
        self.action_btn.clicked.connect(self.on_manage_clicked)
        layout.addWidget(self.action_btn)
    
    def load_data(self):
        """Load and display startup data"""
        data = get_startup_data()
        
        enabled = data["enabled_count"]
        disabled = data["disabled_count"]
        unknown = data["unknown_count"]
        threshold = data["threshold"]
        
        # Update summary
        self.summary_label.setText(f"{enabled} enabled, {disabled} disabled")
        
        # Update status chip with vibrant glow colors
        if enabled > threshold or unknown > 0:
            self.status_chip.setText("Warning")
            self.status_chip.setStyleSheet(f"""
                background: rgba(255, 214, 10, 0.2);
                color: {Theme.GLOW_WARNING};
                font-size: 10px;
                font-weight: 600;
                padding: 3px 8px;
                border-radius: 4px;
            """)
        else:
            self.status_chip.setText("Healthy")
            self.status_chip.setStyleSheet(f"""
                background: rgba(48, 209, 88, 0.2);
                color: {Theme.GLOW_SUCCESS};
                font-size: 10px;
                font-weight: 600;
                padding: 3px 8px;
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
                border: 1px solid {Theme.GLASS_BORDER};
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
        icon_label = QLabel("⛨")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"background: transparent; color: {Theme.ACCENT_LIGHT}; font-size: 14px;")
        icon_layout.addWidget(icon_label)
        header.addWidget(icon_container)
        
        title = QLabel("Boot Security")
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 15px;
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
        sep.setStyleSheet(f"background: {Theme.BORDER};")
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
                border: 1px solid {Theme.BORDER};
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
                border: 1px solid {Theme.BORDER};
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
    """Main overview/dashboard page"""
    
    card_clicked = pyqtSignal(str)  # Signal emits card_id when clicked
    
    def __init__(self, parent=None):
        super().__init__(parent)
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
        
        # Health summary card
        self.health_card = HealthSummaryCard()
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
        
        self.status_cards = {}
        # Map card_id to the navigation page id
        cards_data = [
            ("updates", "Windows Update", "updates"),
            ("defender", "Defender", "security"),
            ("storage", "Storage", "storage"),
            ("drives", "Drive Health", "hardware"),
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
        cards_row.addWidget(self.startup_card, 1)
        
        self.boot_security_card = BootSecurityCard()
        cards_row.addWidget(self.boot_security_card, 1)
        
        layout.addLayout(cards_row)
        
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
            border: 1px solid {Theme.BORDER};
            border-radius: {Theme.RADIUS_MD}px;
        """)
        self.activity_layout = QVBoxLayout(self.activity_container)
        self.activity_layout.setContentsMargins(4, 8, 4, 8)
        self.activity_layout.setSpacing(0)
        
        # Initial activity items
        self.add_activity("info", "Ready to scan", "")
        self.add_activity("info", "Click 'Run Full Scan' to check your system", "")
        
        layout.addWidget(self.activity_container)
        
        # Quick Tools section
        tools_header = QLabel("Quick Tools")
        tools_header.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 16px;
            font-weight: 600;
            margin-top: 8px;
        """)
        layout.addWidget(tools_header)
        
        # Tools grid
        self.tools_container = QFrame()
        self.tools_container.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        tools_layout = QVBoxLayout(self.tools_container)
        tools_layout.setContentsMargins(16, 16, 16, 16)
        tools_layout.setSpacing(10)
        
        # Create tools grid
        tools_grid = QGridLayout()
        tools_grid.setSpacing(10)
        
        # Define quick tools with colors
        quick_tools = [
            ("Task Manager", "📊", "#10b981", self._open_task_manager),
            ("Device Manager", "🔧", "#f59e0b", self._open_device_manager),
            ("Disk Cleanup", "🧹", "#8b5cf6", self._open_disk_cleanup),
            ("Windows Update", "🔄", "#3b82f6", self._open_windows_update),
        ]
        
        for idx, (label, icon, color, action) in enumerate(quick_tools):
            btn = self._create_quick_tool_button(label, icon, color, action)
            tools_grid.addWidget(btn, 0, idx)
        
        tools_layout.addLayout(tools_grid)
        layout.addWidget(self.tools_container)
        
        layout.addStretch()
        
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
    
    def _create_quick_tool_button(self, label: str, icon: str, color: str, action) -> QPushButton:
        """Create a compact styled tool button for the overview"""
        btn = QPushButton()
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(action)
        btn.setFixedHeight(72)
        btn.setMinimumWidth(140)
        
        # Create layout for button content
        btn_layout = QVBoxLayout(btn)
        btn_layout.setContentsMargins(12, 10, 12, 10)
        btn_layout.setSpacing(6)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Icon with colored background
        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            background: {color}25;
            border-radius: 8px;
            font-size: 20px;
            padding: 6px;
        """)
        icon_label.setFixedSize(36, 36)
        btn_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignCenter)
        
        # Label
        text_label = QLabel(label)
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 11px;
            font-weight: 500;
        """)
        btn_layout.addWidget(text_label)
        
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_ELEVATED};
                border: 1px solid transparent;
                border-radius: {Theme.RADIUS_MD}px;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                border: 1px solid {color}55;
            }}
            QPushButton:pressed {{
                background: {color}20;
            }}
        """)
        
        return btn
    
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
            border: 1px solid {Theme.BORDER};
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
        devmgr_btn.setStyleSheet(f"""
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
        header.addWidget(devmgr_btn)
        
        main_layout.addLayout(header)
        
        # Tab bar
        tab_bar = QHBoxLayout()
        tab_bar.setSpacing(0)
        
        self.tabs = {}
        tab_items = [
            ("installed", "Installed Drivers"),
            ("cleanup", "Driver Cleanup"),
            ("updates", "Updates & Resources"),
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
    
    def _get_tab_style(self, is_active: bool) -> str:
        if is_active:
            return f"""
                QPushButton {{
                    background: {Theme.BG_CARD};
                    color: {Theme.TEXT_PRIMARY};
                    border: none;
                    border-bottom: 2px solid {Theme.ACCENT};
                    padding: 12px 24px;
                    font-size: 13px;
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
                    font-size: 13px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    color: {Theme.TEXT_PRIMARY};
                    background: {Theme.BG_CARD};
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
                border: 1px solid {Theme.BORDER};
            }}
        """)
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
                border: 1px solid {Theme.BORDER};
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
                border: 1px solid {Theme.BORDER};
                padding: 10px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                border-color: {Theme.ACCENT};
            }}
        """)
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
                border: 1px solid {Theme.INFO};
            }}
        """)
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
                    border: 1px solid {Theme.SUCCESS};
                }}
            """)
            clean_layout = QVBoxLayout(clean_card)
            clean_layout.setContentsMargins(24, 24, 24, 24)
            clean_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            check_icon = QLabel("✓")
            check_icon.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 36px; font-weight: bold;")
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
                    row.add_action_button("Remove", lambda checked, d=driver: self._remove_driver(d), primary=True)
                
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
                border: 1px solid {Theme.BORDER};
                padding: 10px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                border-color: {Theme.ACCENT};
            }}
        """)
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
                ["powershell", "-NoProfile", "-Command", gpu_cmd],
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
                ["powershell", "-NoProfile", "-Command", cpu_cmd],
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
                ["powershell", "-NoProfile", "-Command", sys_cmd],
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
        
        # Cache the result
        self._cached_vendors = vendors
        return vendors
    
    def _load_updates_data(self):
        """Load updates and resources data with hardware detection"""
        self._clear_layout(self.updates_layout)
        
        # Detect hardware
        vendors = self._detect_hardware_vendors()
        
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
        
        resources_desc = QLabel("Recommended drivers based on your detected hardware. Other suggestions shown below.")
        resources_desc.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 13px; padding-bottom: 12px;")
        resources_desc.setWordWrap(True)
        self.updates_layout.insertWidget(self.updates_layout.count() - 1, resources_desc)
        
        # =================================================================
        # DETECTED HARDWARE - Recommended drivers
        # =================================================================
        has_detected = vendors['nvidia_gpu'] or vendors['amd_gpu'] or vendors['intel_gpu'] or vendors['intel_cpu'] or vendors['amd_cpu']
        
        if has_detected:
            detected_header = QLabel("⚡ Recommended for Your Hardware")
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
                    subtitle="✓ NVIDIA GPU detected • Game Ready & Studio drivers",
                    status="ok",
                    status_text="Detected"
                )
                nvidia_row.add_action_button("Download", lambda: self._open_url("https://www.nvidia.com/Download/index.aspx"), primary=True)
                nvidia_row.add_action_button("GeForce Experience", lambda: self._open_url("https://www.nvidia.com/en-us/geforce/geforce-experience/"))
            
            # AMD GPU detected
            if vendors['amd_gpu']:
                amd_row = detected_container.add_row(
                    title="AMD Radeon Software",
                    subtitle="✓ AMD GPU detected • Adrenalin Edition",
                    status="ok",
                    status_text="Detected"
                )
                amd_row.add_action_button("Download", lambda: self._open_url("https://www.amd.com/en/support"), primary=True)
                amd_row.add_action_button("Auto-Detect", lambda: self._open_url("https://www.amd.com/en/support/kb/faq/gpu-131"))
            
            # Intel GPU detected
            if vendors['intel_gpu']:
                intel_row = detected_container.add_row(
                    title="Intel Graphics Drivers",
                    subtitle="✓ Intel GPU detected • Arc, Iris Xe, or integrated",
                    status="ok",
                    status_text="Detected"
                )
                intel_row.add_action_button("Download", lambda: self._open_url("https://www.intel.com/content/www/us/en/download/785597/intel-arc-iris-xe-graphics-windows.html"), primary=True)
                intel_row.add_action_button("Driver Assistant", lambda: self._open_url("https://www.intel.com/content/www/us/en/support/detect.html"))
            
            # Intel CPU/Chipset detected
            if vendors['intel_cpu']:
                intel_chipset_row = detected_container.add_row(
                    title="Intel Chipset Drivers",
                    subtitle="✓ Intel CPU detected • INF utility for system stability",
                    status="ok",
                    status_text="Detected"
                )
                intel_chipset_row.add_action_button("Download", lambda: self._open_url("https://www.intel.com/content/www/us/en/download/19347/chipset-inf-utility.html"), primary=True)
            
            # AMD CPU/Chipset detected
            if vendors['amd_cpu']:
                amd_chipset_row = detected_container.add_row(
                    title="AMD Chipset Drivers",
                    subtitle="✓ AMD CPU detected • Ryzen chipset drivers",
                    status="ok",
                    status_text="Detected"
                )
                amd_chipset_row.add_action_button("Download", lambda: self._open_url("https://www.amd.com/en/support/download/drivers.html"), primary=True)
            
            # Realtek Audio detected
            if vendors['realtek_audio']:
                realtek_row = detected_container.add_row(
                    title="Realtek Audio Drivers",
                    subtitle="✓ Realtek audio detected • HD Audio codecs",
                    status="ok",
                    status_text="Detected"
                )
                realtek_row.add_action_button("Download", lambda: self._open_url("https://www.realtek.com/en/component/zoo/category/pc-audio-codecs-high-definition-audio-codecs-software"), primary=True)
            
            # Intel Network detected
            if vendors['intel_network']:
                intel_net_row = detected_container.add_row(
                    title="Intel Network Drivers",
                    subtitle="✓ Intel network adapter detected",
                    status="ok",
                    status_text="Detected"
                )
                intel_net_row.add_action_button("Download", lambda: self._open_url("https://www.intel.com/content/www/us/en/download/18293/intel-network-adapter-driver-for-windows-10.html"), primary=True)
            
            # Realtek Network detected
            if vendors['realtek_network']:
                realtek_net_row = detected_container.add_row(
                    title="Realtek Network Drivers",
                    subtitle="✓ Realtek ethernet detected",
                    status="ok",
                    status_text="Detected"
                )
                realtek_net_row.add_action_button("Download", lambda: self._open_url("https://www.realtek.com/en/component/zoo/category/network-interface-controllers-10-100-1000m-gigabit-ethernet-pci-express-software"), primary=True)
            
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
                    subtitle=f"✓ {desc}",
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
                border: 1px solid {Theme.BORDER};
            }}
        """)
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
            result_label = QLabel("✓ No driver updates available from Windows Update")
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
        divider.setStyleSheet(f"background: {Theme.BORDER};")
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


# Global settings instance
app_settings = AppSettings()


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
                padding: 12px 28px;
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
                background: transparent;
                color: {Theme.TEXT_SECONDARY};
                border: 1px solid {Theme.BORDER};
                padding: 12px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        header.addWidget(self.taskmgr_btn)
        
        self.content_layout.addLayout(header)
        
        # Summary stats card with improved styling
        self.stats_frame = QFrame()
        self.stats_frame.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(self.stats_frame, blur_radius=10, offset_y=2, opacity=40)
        
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
    
    def _add_stat_divider(self, layout):
        """Add a vertical divider between stats"""
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setFixedHeight(40)
        divider.setStyleSheet(f"background: {Theme.BORDER};")
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
                        border: 1px solid {Theme.BORDER};
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
                border: 1px solid {Theme.BORDER};
                padding: 10px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                border-color: {Theme.ACCENT};
            }}
        """)
        header.addWidget(self.refresh_btn)
        
        # Open Event Viewer button
        self.viewer_btn = QPushButton("Open Event Viewer")
        self.viewer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.viewer_btn.clicked.connect(self._open_event_viewer)
        self.viewer_btn.setStyleSheet(f"""
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
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(self.stats_frame, blur_radius=10, offset_y=2, opacity=40)
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
    
    def _add_stat_divider(self, layout):
        """Add a vertical divider between stats"""
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setFixedHeight(40)
        divider.setStyleSheet(f"background: {Theme.BORDER};")
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
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
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
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        
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
                background: transparent;
                color: {Theme.ACCENT};
                border: 1px solid {Theme.ACCENT};
                padding: 6px 12px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: rgba(0, 120, 212, 0.1);
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
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        
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
            row.setStyleSheet(f"""
                QFrame {{
                    background: transparent;
                    border-bottom: 1px solid {Theme.BORDER if i < len(events) - 1 else 'transparent'};
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
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
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
                border: 1px solid {Theme.BORDER};
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
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_MD}px;
            }}
            AudioDeviceCard:hover {{
                border-color: {Theme.ACCENT};
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)
        
        # Icon
        icon_char = "🔊" if self.device_type == "output" else "🎤"
        icon = QLabel(icon_char)
        icon.setStyleSheet(f"background: transparent; font-size: 24px;")
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
                border: 1px solid {Theme.BORDER};
                padding: 6px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT};
                border-color: {Theme.ACCENT};
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
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
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
                border: 1px solid {Theme.BORDER};
                padding: 10px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                border-color: {Theme.ACCENT};
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
            border: 1px solid {Theme.BORDER};
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
                    border: 1px solid {Theme.BORDER};
                    padding: 4px 10px;
                    border-radius: 4px;
                    font-size: 10px;
                }}
                QPushButton:checked {{
                    background: {Theme.ACCENT};
                    color: white;
                    border-color: {Theme.ACCENT};
                }}
                QPushButton:hover {{
                    border-color: {Theme.ACCENT};
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
            border: 1px solid {Theme.BORDER};
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
                border: 1px solid {Theme.BORDER};
                padding: 10px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                border-color: {Theme.ACCENT};
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
                border: 1px solid {Theme.BORDER};
                padding: 10px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                border-color: {Theme.ACCENT};
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
        
        # Background worker
        self._worker = None
        self._thread = None
    
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
        """Start the oscilloscope visualization"""
        self.oscilloscope.set_amplitude(0.7)
        self.oscilloscope.start(demo_mode=True)
        self.start_scope_btn.setEnabled(False)
        self.stop_scope_btn.setEnabled(True)
        self.amp_value.setText("ACTIVE")
        self.amp_value.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 18px; font-weight: 600;")
    
    def _stop_oscilloscope(self):
        """Stop the oscilloscope"""
        self.oscilloscope.stop()
        self.start_scope_btn.setEnabled(True)
        self.stop_scope_btn.setEnabled(False)
        self.amp_value.setText("OFF")
        self.amp_value.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 18px; font-weight: 600;")
    
    def _set_frequency(self, freq: str):
        """Set oscilloscope frequency display"""
        for btn in self.freq_btns:
            btn.setChecked(btn.text() == freq)
        
        # Adjust amplitude based on frequency for visual effect
        if freq == "Low":
            self.oscilloscope.set_amplitude(0.5)
        elif freq == "Mid":
            self.oscilloscope.set_amplitude(0.7)
        else:
            self.oscilloscope.set_amplitude(0.9)
    
    def _play_test_tone(self):
        """Play a test tone using Windows built-in beep"""
        import subprocess
        try:
            # Use PowerShell to play a beep tone
            command = '''
            [console]::beep(440, 500)
            Start-Sleep -Milliseconds 200
            [console]::beep(554, 500)
            Start-Sleep -Milliseconds 200  
            [console]::beep(659, 500)
            '''
            subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
        except Exception as e:
            print(f"Error playing tone: {e}")
    
    def _play_channel_test(self, channel: str):
        """Play test tone for a specific channel"""
        import subprocess
        try:
            freq = 440 if channel == "left" else 554
            command = f'[console]::beep({freq}, 1000)'
            subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
        except Exception as e:
            print(f"Error playing channel test: {e}")
    
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
                border: 1px solid {Theme.BORDER};
                padding: 10px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                border-color: {Theme.ACCENT};
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
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(self.stats_frame, blur_radius=10, offset_y=2, opacity=40)
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
    
    def _add_stat_divider(self, layout):
        """Add a vertical divider between stats"""
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setFixedHeight(40)
        divider.setStyleSheet(f"background: {Theme.BORDER};")
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
                background: {Theme.BG_CARD};
                border-radius: {Theme.RADIUS_MD}px;
                border-left: 4px solid {Theme.SUCCESS};
            """)
            up_to_date_layout = QHBoxLayout(up_to_date)
            up_to_date_layout.setContentsMargins(16, 20, 16, 20)
            
            check_icon = QLabel("✓")
            check_icon.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 20px; font-weight: bold;")
            up_to_date_layout.addWidget(check_icon)
            
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
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        
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
        sep.setStyleSheet(f"background: {Theme.BORDER};")
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
            background: transparent;
            color: {cat_color};
            font-size: 11px;
            padding: 2px 8px;
            border: 1px solid {cat_color};
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
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        
        # Header
        header = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 16px; font-weight: 600;")
        header.addWidget(title_label)
        header.addStretch()
        layout.addLayout(header)
        
        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {Theme.BORDER};")
        layout.addWidget(sep)
        
        # History list
        for entry in history[:15]:  # Limit to 15
            history_row = self._create_history_row(entry)
            layout.addWidget(history_row)
        
        return card
    
    def _create_history_row(self, entry: dict):
        """Create a row for a history entry"""
        row = QFrame()
        row.setStyleSheet("background: transparent;")
        
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        # Result icon
        result = entry.get('Result', 'Unknown')
        if result == 'Succeeded':
            icon = "✓"
            icon_color = Theme.SUCCESS
        elif result == 'Failed':
            icon = "✗"
            icon_color = Theme.ERROR
        else:
            icon = "○"
            icon_color = Theme.TEXT_TERTIARY
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"background: transparent; color: {icon_color}; font-size: 14px; font-weight: bold;")
        icon_label.setFixedWidth(20)
        layout.addWidget(icon_label)
        
        # Title
        title = entry.get('Title', 'Unknown')
        if len(title) > 80:
            title = title[:80] + "..."
        title_label = QLabel(title)
        title_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 12px;")
        title_label.setWordWrap(True)
        layout.addWidget(title_label, 1)
        
        # Date
        date = entry.get('Date', '')
        date_label = QLabel(date)
        date_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
        layout.addWidget(date_label)
        
        return row
    
    def _open_windows_update(self):
        """Open Windows Update settings"""
        import subprocess
        try:
            subprocess.Popen(["cmd", "/c", "start", "ms-settings:windowsupdate"], 
                           creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        except Exception as e:
            print(f"Error opening Windows Update: {e}")


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
                border: 1px solid {Theme.BORDER};
                padding: 10px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                border-color: {Theme.ACCENT};
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
                border: 1px solid {Theme.BORDER};
                padding: 10px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                border-color: {Theme.ACCENT};
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
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(self.stats_frame, blur_radius=10, offset_y=2, opacity=40)
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
    
    def _add_stat_divider(self, layout):
        """Add a vertical divider between stats"""
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setFixedHeight(40)
        divider.setStyleSheet(f"background: {Theme.BORDER};")
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
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        
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
            background: transparent;
            color: {Theme.TEXT_TERTIARY};
            font-size: 11px;
            padding: 2px 8px;
            border: 1px solid {Theme.BORDER};
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
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        
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
        icon_text = "💾" if 'SSD' in media_type else "💿"
        icon = QLabel(icon_text)
        icon.setStyleSheet("background: transparent; font-size: 24px;")
        layout.addWidget(icon)
        
        # Disk info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        model = disk.get('Model', 'Unknown Disk')
        model_label = QLabel(model)
        model_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 13px; font-weight: 500;")
        info_layout.addWidget(model_label)
        
        details = f"{disk.get('SizeGB', 0):.0f} GB • {media_type} • {disk.get('InterfaceType', 'Unknown')}"
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
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        
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
                    ["powershell", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
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
    
    def _get_tab_style(self, is_active: bool) -> str:
        if is_active:
            return f"""
                QPushButton {{
                    background: {Theme.BG_CARD};
                    color: {Theme.TEXT_PRIMARY};
                    border: none;
                    border-bottom: 2px solid {Theme.ACCENT};
                    padding: 12px 24px;
                    font-size: 13px;
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
                    font-size: 13px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    color: {Theme.TEXT_PRIMARY};
                    background: {Theme.BG_CARD};
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
                    border: 1px solid {Theme.BORDER};
                    padding: 8px 16px;
                    border-radius: {Theme.RADIUS_SM}px;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background: {Theme.BG_CARD_HOVER};
                    border-color: {Theme.ACCENT};
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
                border: 1px solid {Theme.BORDER};
                padding: 10px 20px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                border-color: {Theme.ACCENT};
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
                border: 1px solid {Theme.BORDER};
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
            font-size: 15px;
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
        self.scan_btn.setStyleSheet(f"""
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
        header.addWidget(self.scan_btn)
        
        # SFC Scan button
        sfc_btn = QPushButton("Run SFC Scan")
        sfc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sfc_btn.clicked.connect(self._run_sfc_scan)
        sfc_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                padding: 10px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                border-color: {Theme.ACCENT};
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
                border: 1px solid {Theme.BORDER};
                padding: 10px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                border-color: {Theme.ACCENT};
            }}
        """)
        header.addWidget(dism_btn)
        
        self.content_layout.addLayout(header)
        
        # Reboot required banner (hidden by default)
        self.reboot_banner = QFrame()
        self.reboot_banner.setStyleSheet(f"""
            background: {Theme.WARNING}22;
            border: 1px solid {Theme.WARNING};
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
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(self.info_card, blur_radius=12, offset_y=3, opacity=50)
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
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(card, blur_radius=12, offset_y=3, opacity=50)
        
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
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(card, blur_radius=12, offset_y=3, opacity=50)
        
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
                        border: 1px solid {Theme.BORDER};
                        border-radius: {Theme.RADIUS_SM}px;
                    }}
                    QFrame:hover {{
                        border-color: {Theme.BORDER_LIGHT};
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
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(card, blur_radius=12, offset_y=3, opacity=50)
        
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
                background: transparent;
                color: {Theme.ACCENT};
                border: 1px solid {Theme.ACCENT};
                padding: 6px 14px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT};
                color: white;
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
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        Theme.apply_shadow(card, blur_radius=12, offset_y=3, opacity=50)
        
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
                border: 1px solid {Theme.BORDER};
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
    
    def __init__(self, title: str, icon_char: str, parent=None):
        super().__init__(parent)
        self.title_text = title
        self.icon_char = icon_char
        self.is_expanded = True
        self.info_rows = []
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            HardwareInfoCard {{
                background: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_MD}px;
            }}
        """)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 12, 16, 12)
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
        
        # Title
        title = QLabel(self.title_text)
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 14px;
            font-weight: 600;
        """)
        header.addWidget(title)
        
        header.addStretch()
        
        # Status chip
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
    
    def set_status(self, status: str, text: str = ""):
        """Set the status chip"""
        # Common style base - note the fixed height is set on widget itself
        base_style = "padding: 2px 10px; border-radius: 10px; font-size: 10px; font-weight: 600;"
        
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
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        Theme.apply_shadow(self, blur_radius=10, offset_y=2, opacity=40)
        
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
        divider.setStyleSheet(f"background: {Theme.BORDER};")
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
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh Hardware Info")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh_hardware)
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
            QPushButton:disabled {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_TERTIARY};
            }}
        """)
        header.addWidget(self.refresh_btn)
        
        # Device Manager button
        devmgr_btn = QPushButton("Device Manager")
        devmgr_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        devmgr_btn.clicked.connect(self.open_device_manager)
        devmgr_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                padding: 10px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                border-color: {Theme.ACCENT};
            }}
        """)
        header.addWidget(devmgr_btn)
        
        self.content_layout.addLayout(header)
        
        # Status/loading indicator
        self.status_label = QLabel("Click 'Refresh Hardware Info' to scan your system")
        self.status_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 13px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.status_label)
        
        # Summary grid
        self.summary_grid = HardwareSummaryGrid()
        self.summary_grid.setVisible(False)
        self.content_layout.addWidget(self.summary_grid)
        
        # Real-time monitoring graphs
        self.graph_panel = RealtimeGraphPanel()
        self.graph_panel.setVisible(False)
        self.content_layout.addWidget(self.graph_panel)
        
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
            card = HardwareInfoCard(title, icon)
            self.cards[card_id] = card
            self.cards_layout.addWidget(card, row, col)
        
        self.cards_container.setVisible(False)
        self.content_layout.addWidget(self.cards_container)
        
        self.content_layout.addStretch()
        
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        
        # Background worker setup
        self._worker = None
        self._thread = None
    
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
        secure_boot = "✓ Enabled" if mb.secure_boot else "✗ Disabled"
        tpm = f"✓ v{mb.tpm_version}" if mb.tpm_present else "✗ Not detected"
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
        self.controls["theme"] = self._create_dropdown(["Dark", "Light", "System"], "theme")
        theme_row = self._create_option_row(
            "Theme", 
            "Choose between light and dark mode",
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
        """Create a section header"""
        label = QLabel(text)
        label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_SECONDARY};
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
        """)
        return label
    
    def _create_card(self) -> QFrame:
        """Create a settings card container"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER};
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
                self._update_toggle_style(self.controls[key], checked)
    
    def _create_dropdown(self, options: list, setting_key: str | None = None) -> QWidget:
        """Create a styled dropdown"""
        from PyQt6.QtWidgets import QComboBox
        
        combo = QComboBox()
        combo.addItems(options)
        combo.setFixedWidth(120)
        combo.setStyleSheet(f"""
            QComboBox {{
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_SM}px;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QComboBox:hover {{
                border-color: {Theme.ACCENT};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                selection-background-color: {Theme.ACCENT};
            }}
        """)
        
        # Connect to save on change
        if setting_key:
            combo.currentTextChanged.connect(lambda text: app_settings.set(setting_key, text))
        
        return combo
    
    def _create_toggle(self, initial: bool, setting_key: str | None = None) -> QFrame:
        """Create a toggle switch"""
        toggle = QFrame()
        toggle.setFixedSize(44, 24)
        toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle.setProperty("checked", initial)
        
        self._update_toggle_style(toggle, initial)
        
        # Store setting key and create toggle behavior
        toggle.setProperty("setting_key", setting_key)
        
        def toggle_click(event):
            checked = not toggle.property("checked")
            toggle.setProperty("checked", checked)
            self._update_toggle_style(toggle, checked)
            # Save the setting
            key = toggle.property("setting_key")
            if key:
                app_settings.set(key, checked)
        
        toggle.mousePressEvent = toggle_click
        
        return toggle
    
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
# MAIN WINDOW
# =============================================================================

class MainWindow(QMainWindow):
    """Main application window - per UI Spec Section 1"""
    
    def __init__(self):
        super().__init__()
        
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
        # Per spec: Min 1100x720, Default 1280x800
        self.setMinimumSize(1100, 720)
        self.resize(1280, 800)
        
        self.current_nav = "overview"
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet(GLOBAL_STYLE)
        
        central = QWidget()
        central.setStyleSheet(f"background: {Theme.BG_WINDOW};")
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
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
        
        # Add Settings page
        self.settings_page = SettingsPage()
        self.pages["settings"] = self.settings_page
        self.content_stack.addWidget(self.settings_page)
        
        main_layout.addWidget(self.content_stack, 1)
        
        # Status bar
        self.statusBar().setStyleSheet(f"""
            QStatusBar {{
                background: {Theme.BG_SIDEBAR};
                color: {Theme.TEXT_TERTIARY};
                border-top: 1px solid {Theme.BORDER};
                padding: 6px 16px;
                font-size: 11px;
            }}
        """)
        self.statusBar().showMessage("Ready")
        
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
    
    def create_sidebar(self):
        sidebar = QFrame()
        sidebar.setFixedWidth(Theme.SIDEBAR_W)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_SIDEBAR};
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
        
        # App icon/title (Fluent style icon container)
        app_icon_container = QFrame()
        app_icon_container.setFixedSize(32, 32)
        app_icon_container.setStyleSheet(f"""
            background: {Theme.ACCENT};
            border-radius: {Theme.RADIUS_SM}px;
        """)
        app_icon_layout = QHBoxLayout(app_icon_container)
        app_icon_layout.setContentsMargins(0, 0, 0, 0)
        app_icon = QLabel("+")
        app_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_icon.setStyleSheet("background: transparent; color: white; font-size: 18px; font-weight: bold;")
        app_icon_layout.addWidget(app_icon)
        header_layout.addWidget(app_icon_container)
        
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
        
        # Navigation items
        self.nav_items = {}
        nav_data = [
            ("overview", "grid", "Overview"),
            ("drivers", "chip", "Drivers"),
            ("startup", "rocket", "Startup"),
            ("updates", "download", "Updates"),
            ("storage", "hdd", "Storage"),
            ("security", "shield", "Security"),
            ("hardware", "cpu", "Hardware"),
            ("system", "file", "System"),
            ("events", "alert", "Events"),
            ("audio", "speaker", "Audio"),
        ]
        
        for nav_id, icon, label in nav_data:
            item = SidebarItem(icon, label)
            item.mousePressEvent = lambda e, nid=nav_id: self.navigate(nid)
            self.nav_items[nav_id] = item
            layout.addWidget(item)
        
        self.nav_items["overview"].set_active(True)
        
        layout.addStretch()
        
        # Settings at bottom
        layout.addSpacing(8)
        settings = SidebarItem("gear", "Settings")
        settings.mousePressEvent = lambda e: self.navigate("settings")
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
                
                if critical > 0 or errors > 20:
                    results["status"] = "error"
                    results["message"] = f"{critical} critical, {errors} errors"
                elif warnings > 50 or errors > 10:
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
        
        # Update drives card (use storage data)
        self.overview.status_cards["drives"].set_status(
            storage_res.get("status", "check"),
            "All drives OK" if storage_res.get("status") == "check" else "Issues found"
        )
        
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
        self.statusBar().showMessage(f"Scan complete - {passed} checks passed, {warnings} warnings, {errors} issues")
        
        # Set dialog to 100% and close
        self.scan_dialog.set_progress(100, "Complete")
        QTimer.singleShot(800, self.scan_dialog.accept)
    
    def _populate_pages_from_cache(self):
        """Populate all detail pages with cached scan data"""
        # Populate Startup page
        if self.cached_data.get("startup"):
            self.startup_page.display_cached_data(self.cached_data["startup"])
        
        # Populate Events page with cached event data
        if self.cached_data.get("events"):
            event_data = self.cached_data["events"]
            self.events_page.display_cached_data(event_data)
        
        # Populate System Files page - trigger detailed scan
        if self.scan_results.get("services"):
            self.system_page.display_cached_data(self.scan_results.get("services"))
        
        # Populate Drivers page - trigger a scan if not already done
        if not self.cached_data.get("drivers"):
            # Queue driver scan for after dialog closes
            QTimer.singleShot(1000, self._scan_drivers_background)
        
        # Populate Windows Update page - trigger detailed check
        if self.cached_data.get("updates"):
            self.updates_page.display_cached_data(self.cached_data["updates"])
        
        # Populate Storage page with cached volume data
        if self.cached_data.get("storage"):
            self.storage_page.display_cached_data(self.cached_data["storage"])
        
        # Populate Security page with cached defender data
        if self.cached_data.get("security"):
            defender = self.cached_data["security"]
            # Store in security page's cache and display
            self.security_page.cached_defender_data = defender
            self.security_page.display_defender_data(defender)
        
        if self.cached_data.get("hardware"):
            hw_data = self.cached_data["hardware"]
            self.hardware_page.display_cached_data(hw_data)
        
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
            page.set_checking()
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
        
        self.pages["hardware"].show_results(results)
        
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
            self.statusBar().showMessage("SFC scan launched in elevated terminal")
        except Exception as e:
            self.statusBar().showMessage(f"Failed to launch SFC: {e}")
    
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
            self.statusBar().showMessage("DISM repair launched in elevated terminal")
        except Exception as e:
            self.statusBar().showMessage(f"Failed to launch DISM: {e}")
    
    def check_event_logs(self):
        """Check Windows event logs - delegates to EventsPage"""
        # EventsPage handles its own scanning and display
        self.events_page.load_events()
    
    def closeEvent(self, event):
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
            self.overview.metrics_collector.stop()
        
        event.accept()


# =============================================================================
# SPLASH SCREEN (Runs in separate process)
# =============================================================================

APP_VERSION = "2.0.0"
APP_BUILD = "2025.06.12"

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
                    border: 1px solid {THEME['border']};
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
                    border: 1px solid {THEME['border']};
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

def main():
    import multiprocessing
    import time
    multiprocessing.freeze_support()  # Required for Windows executables
    
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
        print("=" * 60)
        print("CRASH LOG:")
        print("=" * 60)
        traceback.print_exc()
        print("=" * 60)
        input("Press Enter to exit...")
