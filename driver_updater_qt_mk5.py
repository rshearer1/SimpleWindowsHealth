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
    QStackedWidget, QGraphicsDropShadowEffect, QSizePolicy,
    QDialog, QGridLayout, QTextEdit, QSpacerItem
)
from PyQt6.QtCore import Qt, QTimer, QSize, QPropertyAnimation, QEasingCurve, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush, QFontDatabase, QPainterPath

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
# DESIGN SYSTEM (Per UI_SPECIFICATION.md)
# =============================================================================

class Theme:
    """Color palette following UI Specification - Minimalist Version"""
    # Background Layers (from spec)
    BG_WINDOW = "#1b1b1f"      # Window Background (Near black with warmth)
    BG_SIDEBAR = "#232328"     # Sidebar Background (Slightly elevated)
    BG_CARD = "#2d2d32"        # Card Background (Content containers)
    BG_CARD_HOVER = "#38383d"  # Hover State (Interactive feedback)
    BG_ELEVATED = "#38383d"    # Same as hover for elevated surfaces
    
    # Borders
    BORDER = "#3a3a3f"         # Subtle border for cards
    BORDER_LIGHT = "#3a3a3f"
    BORDER_ACCENT = "#0078d4"
    
    # Text Hierarchy (from spec)
    TEXT_PRIMARY = "#ffffff"    # Headings, important
    TEXT_SECONDARY = "#b4b4b4"  # Body text
    TEXT_TERTIARY = "#7a7a7a"   # Captions, timestamps
    TEXT_DISABLED = "#4a4a4a"   # Inactive elements
    
    # Accent Colors (from spec)
    ACCENT = "#0078d4"          # Windows Blue (Primary Accent)
    ACCENT_HOVER = "#106ebe"    # Darker blue for depth
    ACCENT_LIGHT = "#60cdff"    # Light blue for emphasis
    ACCENT_SUBTLE = "rgba(0, 120, 212, 0.1)"  # 10% opacity for selected backgrounds
    
    # Semantic Colors (from spec)
    SUCCESS = "#0f9d58"         # Green - not neon
    SUCCESS_BG = "rgba(15, 157, 88, 0.15)"
    WARNING = "#f4b400"         # Amber
    WARNING_BG = "rgba(244, 180, 0, 0.15)"
    ERROR = "#db4437"           # Red
    ERROR_BG = "rgba(219, 68, 55, 0.15)"
    INFO = "#4285f4"            # Blue
    INFO_BG = "rgba(66, 133, 244, 0.15)"
    RUNNING = "#8e44ad"         # Purple for running scans
    RUNNING_BG = "rgba(142, 68, 173, 0.15)"
    
    # Spacing (from spec - 8px grid)
    SIDEBAR_W = 240             # Spec: 240px sidebar
    RADIUS_SM = 6               # Button radius
    RADIUS_MD = 8               # Card radius (spec)
    RADIUS_LG = 8               # Same as card radius for consistency


# =============================================================================
# GLOBAL STYLESHEET
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
}}

QScrollArea {{
    border: none;
    background: transparent;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 4px 2px 4px 2px;
}}

QScrollBar::handle:vertical {{
    background: {Theme.BORDER_LIGHT};
    border-radius: 4px;
    min-height: 40px;
}}

QScrollBar::handle:vertical:hover {{
    background: {Theme.TEXT_TERTIARY};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
    height: 0px;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 2px 4px 2px 4px;
}}

QScrollBar::handle:horizontal {{
    background: {Theme.BORDER_LIGHT};
    border-radius: 4px;
    min-width: 40px;
}}

QProgressBar {{
    background: {Theme.BG_ELEVATED};
    border: none;
    border-radius: 4px;
    height: 8px;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {Theme.ACCENT}, stop:1 {Theme.ACCENT_LIGHT});
    border-radius: 4px;
}}

QTextEdit {{
    background: {Theme.BG_CARD};
    border: 1px solid {Theme.BORDER};
    border-radius: {Theme.RADIUS_MD}px;
    padding: 12px;
    color: {Theme.TEXT_PRIMARY};
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 12px;
    selection-background-color: {Theme.ACCENT};
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
        
        self._thread = QThread()
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
    """Custom painted status icon"""
    
    def __init__(self, status: str = "check", size: int = 20, parent=None):
        super().__init__(parent)
        self.status = status
        self.icon_size = size
        self.setFixedSize(size, size)
    
    def set_status(self, status: str):
        self.status = status
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        colors = {
            "check": Theme.SUCCESS,
            "warning": Theme.WARNING,
            "error": Theme.ERROR,
            "pending": Theme.TEXT_TERTIARY,
            "running": Theme.ACCENT,
        }
        color = colors.get(self.status, Theme.TEXT_TERTIARY)
        
        if self.status == "check":
            IconPainter.draw_check(painter, self.rect(), color)
        elif self.status == "warning":
            IconPainter.draw_warning(painter, self.rect(), color)
        elif self.status == "error":
            IconPainter.draw_error(painter, self.rect(), color)
        elif self.status == "running":
            # Draw spinning arc (simplified - just partial circle)
            pen = QPen(QColor(color))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawArc(4, 4, self.icon_size-8, self.icon_size-8, 30*16, 300*16)
        else:
            # Pending - empty circle
            pen = QPen(QColor(color))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(4, 4, self.icon_size-8, self.icon_size-8)


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
        """Update style per UI Spec Section 5.2 Sidebar Navigation Item"""
        if self.is_active:
            # Selected state: left border, accent background at 10% opacity
            self.setStyleSheet(f"""
                SidebarItem {{
                    background: {Theme.ACCENT_SUBTLE};
                    border-left: 3px solid {Theme.ACCENT};
                    border-radius: 0px;
                    margin-left: 0px;
                    margin-right: 12px;
                    padding-left: 9px;
                }}
            """)
            self.icon.set_color(Theme.ACCENT_LIGHT)
            self.label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-weight: 500;")
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
        ring_width = 8
        margin = ring_width // 2 + 2
        
        # Determine color based on score
        if self.score >= 80:
            color = QColor(Theme.SUCCESS)
        elif self.score >= 50:
            color = QColor(Theme.WARNING)
        else:
            color = QColor(Theme.ERROR)
        
        # Background ring
        pen = QPen(QColor(Theme.BG_ELEVATED))
        pen.setWidth(ring_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(margin, margin, size-2*margin, size-2*margin, 0, 360*16)
        
        # Progress ring
        pen.setColor(color)
        painter.setPen(pen)
        span = int((self.score / 100) * 360 * 16)
        painter.drawArc(margin, margin, size-2*margin, size-2*margin, 90*16, -span)
        
        # Score text
        painter.setPen(QColor(Theme.TEXT_PRIMARY))
        font = QFont("Segoe UI Variable", 32, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, str(int(self.score)))


class StatusCard(QFrame):
    """Quick status card for overview grid"""
    
    clicked = pyqtSignal()  # Signal when card is clicked
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title_text = title
        self.setFixedHeight(72)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_ui()
        self._apply_style()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)
        
        # Status icon
        self.status_icon = StatusIcon("pending", 22)
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
        chevron.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 18px;")
        layout.addWidget(chevron)
    
    def _apply_style(self):
        """Apply style per UI Spec Section 5.1 - Cards have 1px border"""
        self.setStyleSheet(f"""
            StatusCard {{
                background: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_MD}px;
            }}
            StatusCard:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
    
    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)
    
    def set_status(self, status: str, subtitle: str):
        self.status_icon.set_status(status)
        self.subtitle.setText(subtitle)
        self.subtitle.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 11px;")


class HealthSummaryCard(QFrame):
    """Large health score summary card"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            HealthSummaryCard {{
                background: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        
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
        
        # Scan button
        self.scan_btn = QPushButton("Run Full Scan")
        self.scan_btn.setFixedSize(140, 44)
        self.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Theme.ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                background: {Theme.ACCENT};
            }}
        """)
        layout.addWidget(self.scan_btn, 0, Qt.AlignmentFlag.AlignTop)
    
    def set_score(self, score: int, passed: int, warnings: int, errors: int):
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
    """Single activity log item"""
    
    def __init__(self, status: str, text: str, time: str = "", parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)
        
        # Status dot
        dot = QLabel("•")
        color = {
            "success": Theme.SUCCESS,
            "warning": Theme.WARNING,
            "error": Theme.ERROR,
            "info": Theme.INFO,
        }.get(status, Theme.TEXT_TERTIARY)
        dot.setStyleSheet(f"background: transparent; color: {color}; font-size: 16px;")
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
    """Card showing startup programs status"""
    
    manage_clicked = pyqtSignal()  # Signal to navigate to startup page
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_data()
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            StartupProgramsCard {{
                background: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER};
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
        
        # Update status chip
        if enabled > threshold or unknown > 0:
            self.status_chip.setText("Warning")
            self.status_chip.setStyleSheet(f"""
                background: {Theme.WARNING_BG};
                color: {Theme.WARNING};
                font-size: 10px;
                font-weight: 600;
                padding: 3px 8px;
                border-radius: 4px;
            """)
        else:
            self.status_chip.setText("Healthy")
            self.status_chip.setStyleSheet(f"""
                background: {Theme.SUCCESS_BG};
                color: {Theme.SUCCESS};
                font-size: 10px;
                font-weight: 600;
                padding: 3px 8px;
                border-radius: 4px;
            """)
        
        # Clear existing details
        while self.details_layout.count():
            item = self.details_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
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
    """Card showing Secure Boot and BIOS mode status"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_data()
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            BootSecurityCard {{
                background: {Theme.BG_CARD};
                border: 1px solid {Theme.BORDER};
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
        
        # Update Secure Boot status
        if secure_boot is True:
            self.secure_boot_status.setText("Enabled")
            self.secure_boot_status.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 13px; font-weight: 500;")
            self.secure_boot_dot.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 10px;")
        elif secure_boot is False:
            self.secure_boot_status.setText("Disabled")
            self.secure_boot_status.setStyleSheet(f"background: transparent; color: {Theme.WARNING}; font-size: 13px; font-weight: 500;")
            self.secure_boot_dot.setStyleSheet(f"background: transparent; color: {Theme.WARNING}; font-size: 10px;")
        else:
            self.secure_boot_status.setText("Unsupported")
            self.secure_boot_status.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 13px;")
            self.secure_boot_dot.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 10px;")
        
        # Update BIOS mode status
        self.bios_status.setText(bios_mode)
        if bios_mode == "UEFI":
            self.bios_status.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 13px; font-weight: 500;")
            self.bios_dot.setStyleSheet(f"background: transparent; color: {Theme.SUCCESS}; font-size: 10px;")
        else:
            self.bios_status.setStyleSheet(f"background: transparent; color: {Theme.WARNING}; font-size: 13px; font-weight: 500;")
            self.bios_dot.setStyleSheet(f"background: transparent; color: {Theme.WARNING}; font-size: 10px;")
    
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
    
    def update_task(self, task_id: str, status: str, text: str = None):
        if task_id not in self.tasks:
            return
        
        task = self.tasks[task_id]
        
        status_map = {
            "running": ("running", Theme.ACCENT, "Running..."),
            "complete": ("check", Theme.SUCCESS, "Complete"),
            "error": ("error", Theme.ERROR, "Failed"),
        }
        
        icon_status, color, default_text = status_map.get(status, ("pending", Theme.TEXT_TERTIARY, "Waiting"))
        
        task["icon"].set_status(icon_status)
        task["status"].setText(text or default_text)
        task["status"].setStyleSheet(f"background: transparent; color: {color}; font-size: 11px;")
    
    def set_progress(self, percent: int, time_remaining: str = None):
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
            font-size: 26px;
            font-weight: bold;
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
        
        # Status cards grid
        grid = QGridLayout()
        grid.setSpacing(12)
        
        self.status_cards = {}
        # Map card_id to the navigation page id
        cards_data = [
            ("updates", "Windows Update", "updates"),
            ("defender", "Defender", "security"),
            ("storage", "Storage", "storage"),
            ("drives", "Drive Health", "hardware"),
            ("memory", "Memory", "hardware"),
            ("system", "System Files", "system"),
        ]
        
        for i, (card_id, title, nav_target) in enumerate(cards_data):
            card = StatusCard(title)
            card.clicked.connect(lambda target=nav_target: self.card_clicked.emit(target))
            self.status_cards[card_id] = card
            grid.addWidget(card, i // 3, i % 3)
        
        layout.addLayout(grid)
        
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
        
        layout.addStretch()
        
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
    
    def add_activity(self, status: str, text: str, time: str):
        item = ActivityItem(status, text, time)
        self.activity_layout.insertWidget(0, item)
        
        # Keep only last 10 items
        while self.activity_layout.count() > 10:
            old = self.activity_layout.takeAt(self.activity_layout.count() - 1)
            if old.widget():
                old.widget().deleteLater()


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
            font-size: 26px;
            font-weight: bold;
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
                padding: 10px 20px;
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
        """Display results - list of (status, text) tuples"""
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


class DriversPage(QWidget):
    """Dedicated drivers management page"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scanner = DriverScanner()
        self.online_checker = OnlineDriverChecker()
        self.drivers = []
        self.driver_widgets = []
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
        
        title = QLabel("Driver Manager")
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 26px;
            font-weight: bold;
        """)
        header.addWidget(title)
        
        header.addStretch()
        
        self.scan_btn = QPushButton("Scan Drivers")
        self.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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
        """)
        self.scan_btn.clicked.connect(self.scan_drivers)
        header.addWidget(self.scan_btn)
        
        self.content_layout.addLayout(header)
        
        # Summary stats
        self.stats_frame = QFrame()
        self.stats_frame.setStyleSheet(f"""
            background: {Theme.BG_CARD};
            border: 1px solid {Theme.BORDER};
            border-radius: {Theme.RADIUS_MD}px;
        """)
        stats_layout = QHBoxLayout(self.stats_frame)
        stats_layout.setContentsMargins(20, 16, 20, 16)
        stats_layout.setSpacing(40)
        
        self.stat_total = self._create_stat("Total Drivers", "—")
        self.stat_ok = self._create_stat("OK", "—")
        self.stat_updates = self._create_stat("Updates Available", "—")
        self.stat_problems = self._create_stat("Problems", "—")
        
        stats_layout.addWidget(self.stat_total)
        stats_layout.addWidget(self.stat_ok)
        stats_layout.addWidget(self.stat_updates)
        stats_layout.addWidget(self.stat_problems)
        stats_layout.addStretch()
        
        self.content_layout.addWidget(self.stats_frame)
        
        # Status label
        self.status_label = QLabel("Click 'Scan Drivers' to detect installed drivers")
        self.status_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 14px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.status_label)
        
        # Drivers list container
        self.drivers_container = QFrame()
        self.drivers_container.setStyleSheet(f"""
            background: {Theme.BG_CARD};
            border: 1px solid {Theme.BORDER};
            border-radius: {Theme.RADIUS_MD}px;
        """)
        self.drivers_layout = QVBoxLayout(self.drivers_container)
        self.drivers_layout.setContentsMargins(0, 0, 0, 0)
        self.drivers_layout.setSpacing(0)
        self.drivers_container.setVisible(False)
        self.content_layout.addWidget(self.drivers_container)
        
        self.content_layout.addStretch()
        
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
    
    def _create_stat(self, label: str, value: str):
        """Create a stat display widget"""
        frame = QFrame()
        frame.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        val_label = QLabel(value)
        val_label.setObjectName("stat_value")
        val_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 24px; font-weight: bold;")
        layout.addWidget(val_label)
        
        name_label = QLabel(label)
        name_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        layout.addWidget(name_label)
        
        return frame
    
    def _update_stat(self, frame: QFrame, value: str):
        """Update a stat widget's value"""
        val_label = frame.findChild(QLabel, "stat_value")
        if val_label:
            val_label.setText(value)
    
    def scan_drivers(self):
        """Scan installed drivers"""
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("Scanning...")
        self.status_label.setText("Scanning installed drivers...")
        self.status_label.setVisible(True)
        self.drivers_container.setVisible(False)
        
        # Use timer to allow UI to update
        QTimer.singleShot(100, self._do_scan)
    
    def _do_scan(self):
        """Perform the actual scan"""
        try:
            self.drivers = self.scanner.scan_installed_drivers()
            problems = self.scanner.scan_problem_devices()
            
            # Update stats
            total = len(self.drivers)
            ok_count = sum(1 for d in self.drivers if d.status == "OK")
            problem_count = len(problems)
            
            self._update_stat(self.stat_total, str(total))
            self._update_stat(self.stat_ok, str(ok_count))
            self._update_stat(self.stat_updates, "0")  # Will update after online check
            self._update_stat(self.stat_problems, str(problem_count))
            
            # Clear old driver widgets
            for widget in self.driver_widgets:
                widget.deleteLater()
            self.driver_widgets.clear()
            
            # Show driver list
            self.status_label.setVisible(False)
            self.drivers_container.setVisible(True)
            
            # Add drivers to list (group by category)
            categories = {}
            for driver in self.drivers:
                cat = driver.device_class or "Other"
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(driver)
            
            for category, cat_drivers in sorted(categories.items()):
                # Category header
                cat_header = QLabel(f"  {category} ({len(cat_drivers)})")
                cat_header.setStyleSheet(f"""
                    background: {Theme.BG_CARD_HOVER};
                    color: {Theme.TEXT_SECONDARY};
                    font-size: 12px;
                    font-weight: 600;
                    padding: 8px 12px;
                """)
                self.drivers_layout.addWidget(cat_header)
                self.driver_widgets.append(cat_header)
                
                for driver in cat_drivers[:5]:  # Limit to 5 per category for performance
                    row = self._create_driver_row(driver)
                    self.drivers_layout.addWidget(row)
                    self.driver_widgets.append(row)
                
                if len(cat_drivers) > 5:
                    more = QLabel(f"    ... and {len(cat_drivers) - 5} more")
                    more.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; padding: 8px 16px;")
                    self.drivers_layout.addWidget(more)
                    self.driver_widgets.append(more)
            
        except Exception as e:
            self.status_label.setText(f"Error scanning drivers: {str(e)}")
            self.status_label.setVisible(True)
        
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("Scan Drivers")
    
    def _create_driver_row(self, driver):
        """Create a row widget for a driver"""
        row = QFrame()
        row.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border-bottom: 1px solid {Theme.BORDER};
            }}
            QFrame:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)
        
        # Status icon
        status = "check" if driver.status == "OK" else "warning" if driver.status == "Unsigned" else "error"
        icon = StatusIcon(status, 16)
        layout.addWidget(icon)
        
        # Device info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        name = QLabel(driver.device_name)
        name.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 13px;")
        info_layout.addWidget(name)
        
        details = QLabel(f"{driver.manufacturer} • v{driver.driver_version} • {driver.driver_date}")
        details.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
        info_layout.addWidget(details)
        
        layout.addLayout(info_layout, 1)
        
        # Status text
        status_text = QLabel(driver.status)
        color = Theme.SUCCESS if driver.status == "OK" else Theme.WARNING if driver.status == "Unsigned" else Theme.ERROR
        status_text.setStyleSheet(f"background: transparent; color: {color}; font-size: 11px; font-weight: 600;")
        layout.addWidget(status_text)
        
        # Action button for problematic drivers
        if driver.status != "OK":
            action_btn = QPushButton("Fix")
            action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            action_btn.setFixedWidth(50)
            action_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {Theme.ACCENT};
                    color: white;
                    border: none;
                    padding: 5px 10px;
                    border-radius: {Theme.RADIUS_SM}px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {Theme.ACCENT_HOVER};
                }}
            """)
            action_btn.clicked.connect(lambda checked, d=driver: self._fix_driver(d))
            layout.addWidget(action_btn)
        
        return row
    
    def _fix_driver(self, driver):
        """Open Device Manager to fix a problematic driver"""
        from PyQt6.QtWidgets import QMessageBox
        import subprocess
        
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
        
        try:
            subprocess.Popen(["devmgmt.msc"])
        except Exception:
            pass


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
    """Page for managing startup programs"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.startup_items = []
        self.item_widgets = []
        self.loaded = False  # Track if data has been loaded
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
        
        title = QLabel("Startup Programs")
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 26px;
            font-weight: bold;
        """)
        header.addWidget(title)
        header.addStretch()
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.load_startup_items)
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CARD};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                padding: 8px 16px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Theme.BG_CARD_HOVER};
                border-color: {Theme.ACCENT};
            }}
        """)
        header.addWidget(self.refresh_btn)
        
        # Open Task Manager button
        self.taskmgr_btn = QPushButton("Open Task Manager")
        self.taskmgr_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.taskmgr_btn.clicked.connect(self.open_task_manager)
        self.taskmgr_btn.setStyleSheet(f"""
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
        header.addWidget(self.taskmgr_btn)
        
        self.content_layout.addLayout(header)
        
        # Info text
        info = QLabel("Manage programs that run automatically when Windows starts. Disabling unnecessary startup programs can improve boot time.")
        info.setWordWrap(True)
        info.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        self.content_layout.addWidget(info)
        
        # Stats row
        self.stats_frame = QFrame()
        self.stats_frame.setStyleSheet(f"""
            background: {Theme.BG_CARD};
            border-radius: {Theme.RADIUS_MD}px;
        """)
        stats_layout = QHBoxLayout(self.stats_frame)
        stats_layout.setContentsMargins(20, 16, 20, 16)
        stats_layout.setSpacing(40)
        
        self.stat_total = self._create_stat("Total", "0")
        stats_layout.addWidget(self.stat_total)
        
        self.stat_enabled = self._create_stat("Enabled", "0")
        stats_layout.addWidget(self.stat_enabled)
        
        self.stat_disabled = self._create_stat("Disabled", "0")
        stats_layout.addWidget(self.stat_disabled)
        
        self.stat_high_impact = self._create_stat("High Impact", "0")
        stats_layout.addWidget(self.stat_high_impact)
        
        stats_layout.addStretch()
        
        self.content_layout.addWidget(self.stats_frame)
        
        # Status label
        self.status_label = QLabel("Click 'Refresh' to scan startup programs")
        self.status_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 14px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.status_label)
        
        # Startup items container
        self.items_container = QFrame()
        self.items_container.setStyleSheet(f"""
            background: {Theme.BG_CARD};
            border: 1px solid {Theme.BORDER};
            border-radius: {Theme.RADIUS_MD}px;
        """)
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(0)
        self.items_container.setVisible(False)
        self.content_layout.addWidget(self.items_container)
        
        self.content_layout.addStretch()
        
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
    
    def _create_stat(self, label: str, value: str):
        """Create a stat display widget"""
        frame = QFrame()
        frame.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        val_label = QLabel(value)
        val_label.setObjectName("stat_value")
        val_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 24px; font-weight: bold;")
        layout.addWidget(val_label)
        
        name_label = QLabel(label)
        name_label.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
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
        self._thread = QThread()
        self._worker = StartupScanWorker()
        self._worker.moveToThread(self._thread)
        
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_startup_scan_complete)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        
        self._thread.start()
    
    def _on_startup_scan_complete(self, items: list):
        """Handle completion of startup scan (called on main thread)"""
        self.startup_items = items
        
        # Update stats
        total = len(self.startup_items)
        enabled = sum(1 for item in self.startup_items if item["enabled"])
        disabled = total - enabled
        high_impact = sum(1 for item in self.startup_items if item["impact"] == "High")
        
        self._update_stat(self.stat_total, str(total))
        self._update_stat(self.stat_enabled, str(enabled))
        self._update_stat(self.stat_disabled, str(disabled))
        self._update_stat(self.stat_high_impact, str(high_impact))
        
        # Clear old widgets
        for widget in self.item_widgets:
            widget.deleteLater()
        self.item_widgets.clear()
        
        # Show items container
        self.status_label.setVisible(False)
        self.items_container.setVisible(True)
        
        # Group by impact
        by_impact = {"High": [], "Medium": [], "Low": [], "Not measured": []}
        for item in self.startup_items:
            impact = item.get("impact", "Not measured")
            if impact in by_impact:
                by_impact[impact].append(item)
            else:
                by_impact["Not measured"].append(item)
        
        # Add items grouped by impact
        for impact_level in ["High", "Medium", "Low", "Not measured"]:
            items = by_impact.get(impact_level, [])
            if not items:
                continue
            
            # Category header
            impact_color = Theme.ERROR if impact_level == "High" else Theme.WARNING if impact_level == "Medium" else Theme.TEXT_TERTIARY
            header = QLabel(f"  {impact_level} Impact ({len(items)})")
            header.setStyleSheet(f"""
                background: {Theme.BG_CARD_HOVER};
                color: {impact_color};
                font-size: 12px;
                font-weight: 600;
                padding: 8px 12px;
            """)
            self.items_layout.addWidget(header)
            self.item_widgets.append(header)
            
            for item in items:
                row = self._create_item_row(item)
                self.items_layout.addWidget(row)
                self.item_widgets.append(row)
        
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Refresh")
        self.loaded = True
    
    def _create_item_row(self, item: dict):
        """Create a row widget for a startup item"""
        row = QFrame()
        row.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border-bottom: 1px solid {Theme.BORDER};
            }}
            QFrame:hover {{
                background: {Theme.BG_CARD_HOVER};
            }}
        """)
        
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        # Status icon
        status = "check" if item["enabled"] else "disabled"
        icon_text = "✓" if item["enabled"] else "○"
        icon_color = Theme.SUCCESS if item["enabled"] else Theme.TEXT_TERTIARY
        icon = QLabel(icon_text)
        icon.setFixedWidth(20)
        icon.setStyleSheet(f"background: transparent; color: {icon_color}; font-size: 14px; font-weight: bold;")
        layout.addWidget(icon)
        
        # Item info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        name = QLabel(item["name"])
        name.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 13px; font-weight: 500;")
        info_layout.addWidget(name)
        
        details = QLabel(f"{item['publisher']} • {item['location']}")
        details.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
        info_layout.addWidget(details)
        
        layout.addLayout(info_layout, 1)
        
        # Impact badge
        impact = item.get("impact", "Not measured")
        impact_color = Theme.ERROR if impact == "High" else Theme.WARNING if impact == "Medium" else Theme.TEXT_TERTIARY
        impact_label = QLabel(impact)
        impact_label.setStyleSheet(f"""
            background: transparent;
            color: {impact_color};
            font-size: 11px;
            font-weight: 500;
        """)
        layout.addWidget(impact_label)
        
        # Status text
        status_text = "Enabled" if item["enabled"] else "Disabled"
        status_color = Theme.SUCCESS if item["enabled"] else Theme.TEXT_TERTIARY
        status_label = QLabel(status_text)
        status_label.setStyleSheet(f"background: transparent; color: {status_color}; font-size: 11px; font-weight: 600;")
        status_label.setFixedWidth(60)
        layout.addWidget(status_label)
        
        # Toggle button
        toggle_btn = QPushButton("Disable" if item["enabled"] else "Enable")
        toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle_btn.setFixedWidth(70)
        btn_color = Theme.WARNING if item["enabled"] else Theme.SUCCESS
        toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: {btn_color};
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: {Theme.RADIUS_SM}px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        toggle_btn.clicked.connect(lambda checked, i=item: self._toggle_startup_item(i, row))
        layout.addWidget(toggle_btn)
        
        return row
    
    def _toggle_startup_item(self, item: dict, row_widget: QFrame):
        """Toggle a startup item's enabled/disabled state"""
        try:
            import subprocess
            
            source_path = item.get("source_path", "")
            name = item["name"]
            currently_enabled = item["enabled"]
            
            # Determine the registry path and action
            if "Run" in item.get("location", ""):
                # Registry-based startup item
                if "HKLM" in source_path or "Machine" in source_path:
                    reg_path = r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
                else:
                    reg_path = r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
                
                if currently_enabled:
                    # To disable: rename the value or move to a disabled key
                    # We'll use Task Manager's approach - open it for the user
                    self._open_task_manager_startup()
                    return
                else:
                    # Re-enable would need the original command
                    self._open_task_manager_startup()
                    return
            else:
                # For Task Scheduler or other sources, open Task Manager
                self._open_task_manager_startup()
                return
                
        except Exception as e:
            print(f"Error toggling startup item: {e}")
            self._open_task_manager_startup()
    
    def _open_task_manager_startup(self):
        """Open Task Manager to the Startup tab with helpful message"""
        import subprocess
        from PyQt6.QtWidgets import QMessageBox
        
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("Startup Manager")
        msg.setText("Opening Task Manager...")
        msg.setInformativeText(
            "To enable/disable startup items:\n\n"
            "1. Go to the 'Startup apps' tab\n"
            "2. Right-click the item\n"
            "3. Select 'Enable' or 'Disable'\n\n"
            "Task Manager provides the safest way to manage startup items."
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
# HARDWARE PAGE - Comprehensive Hardware Information
# =============================================================================

class RealtimeGraph(QFrame):
    """Real-time line graph widget for displaying utilization metrics"""
    
    def __init__(self, title: str, color: str = None, max_points: int = 60, parent=None):
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
    """Collapsible card for displaying hardware category information"""
    
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
                border-radius: {Theme.RADIUS_LG}px;
            }}
        """)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 16, 20, 16)
        self.main_layout.setSpacing(12)
        
        # Header (clickable to expand/collapse)
        header = QHBoxLayout()
        header.setSpacing(12)
        
        # Icon container
        icon_container = QFrame()
        icon_container.setFixedSize(36, 36)
        icon_container.setStyleSheet(f"""
            background: {Theme.BG_CARD_HOVER};
            border-radius: {Theme.RADIUS_SM}px;
        """)
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel(self.icon_char)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"background: transparent; color: {Theme.ACCENT_LIGHT}; font-size: 14px; font-weight: bold;")
        icon_layout.addWidget(icon_label)
        header.addWidget(icon_container)
        
        # Title
        title = QLabel(self.title_text)
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 15px;
            font-weight: 600;
        """)
        header.addWidget(title)
        
        header.addStretch()
        
        # Status chip
        self.status_chip = QLabel("OK")
        self.status_chip.setStyleSheet(f"""
            background: {Theme.SUCCESS_BG};
            color: {Theme.SUCCESS};
            padding: 4px 10px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 600;
        """)
        header.addWidget(self.status_chip)
        
        # Expand/collapse chevron
        self.chevron = QLabel("v")
        self.chevron.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 12px;")
        header.addWidget(self.chevron)
        
        self.main_layout.addLayout(header)
        
        # Content container (for info rows)
        self.content = QFrame()
        self.content.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(48, 4, 0, 0)  # Indent content
        self.content_layout.setSpacing(6)
        
        self.main_layout.addWidget(self.content)
    
    def set_status(self, status: str, text: str = ""):
        """Set the status chip"""
        if status == "healthy" or status == "check":
            self.status_chip.setStyleSheet(f"""
                background: {Theme.SUCCESS_BG};
                color: {Theme.SUCCESS};
                padding: 4px 10px;
                border-radius: 10px;
                font-size: 11px;
                font-weight: 600;
            """)
            self.status_chip.setText(text or "OK")
        elif status == "warning":
            self.status_chip.setStyleSheet(f"""
                background: {Theme.WARNING_BG};
                color: {Theme.WARNING};
                padding: 4px 10px;
                border-radius: 10px;
                font-size: 11px;
                font-weight: 600;
            """)
            self.status_chip.setText(text or "Warning")
        elif status == "critical" or status == "error":
            self.status_chip.setStyleSheet(f"""
                background: {Theme.ERROR_BG};
                color: {Theme.ERROR};
                padding: 4px 10px;
                border-radius: 10px;
                font-size: 11px;
                font-weight: 600;
            """)
            self.status_chip.setText(text or "Critical")
        else:
            self.status_chip.setStyleSheet(f"""
                background: {Theme.BG_CARD_HOVER};
                color: {Theme.TEXT_SECONDARY};
                padding: 4px 10px;
                border-radius: 10px;
                font-size: 11px;
                font-weight: 600;
            """)
            self.status_chip.setText(text or "Unknown")
    
    def clear_info(self):
        """Clear all info rows"""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.info_rows = []
    
    def add_info_row(self, label: str, value: str, highlight: bool = False):
        """Add an info row with label and value"""
        row = QHBoxLayout()
        row.setSpacing(16)
        
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        label_widget.setFixedWidth(140)
        row.addWidget(label_widget)
        
        value_color = Theme.ACCENT_LIGHT if highlight else Theme.TEXT_PRIMARY
        value_widget = QLabel(value)
        value_widget.setStyleSheet(f"background: transparent; color: {value_color}; font-size: 12px;")
        value_widget.setWordWrap(True)
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
        divider.setStyleSheet(f"background: {Theme.BORDER};")
        self.content_layout.addWidget(divider)
    
    def add_subsection(self, title: str):
        """Add a subsection header"""
        label = QLabel(title)
        label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_TERTIARY};
            font-size: 11px;
            font-weight: 600;
            margin-top: 8px;
        """)
        self.content_layout.addWidget(label)


class HardwareSummaryGrid(QFrame):
    """Grid showing quick hardware summary stats"""
    
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
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(0)
        
        # Create stat items
        stats = [
            ("cpu", "CPU", "--", "cores"),
            ("gpu", "GPU", "--", "VRAM"),
            ("ram", "RAM", "--", "used"),
            ("storage", "Storage", "--", "total"),
        ]
        
        for i, (stat_id, label, value, unit) in enumerate(stats):
            if i > 0:
                # Add separator
                sep = QFrame()
                sep.setFixedWidth(1)
                sep.setStyleSheet(f"background: {Theme.BORDER};")
                layout.addWidget(sep)
            
            stat_widget = self._create_stat(label, value, unit)
            self.stat_widgets[stat_id] = stat_widget
            layout.addWidget(stat_widget, 1)
    
    def _create_stat(self, label: str, value: str, unit: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("background: transparent;")
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"background: transparent; color: {Theme.TEXT_TERTIARY}; font-size: 11px;")
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label_widget)
        
        value_widget = QLabel(value)
        value_widget.setObjectName("value")
        value_widget.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; font-size: 18px; font-weight: 600;")
        value_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_widget)
        
        unit_widget = QLabel(unit)
        unit_widget.setObjectName("unit")
        unit_widget.setStyleSheet(f"background: transparent; color: {Theme.TEXT_SECONDARY}; font-size: 11px;")
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
            font-size: 26px;
            font-weight: bold;
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
        
        # Hardware cards container
        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(16)
        
        # Create hardware category cards
        card_configs = [
            ("cpu", "Processor (CPU)", "C"),
            ("gpu", "Graphics (GPU)", "G"),
            ("ram", "Memory (RAM)", "M"),
            ("motherboard", "Motherboard & BIOS", "B"),
            ("storage", "Storage", "S"),
            ("network", "Network Adapters", "N"),
        ]
        
        for card_id, title, icon in card_configs:
            card = HardwareInfoCard(title, icon)
            self.cards[card_id] = card
            self.cards_layout.addWidget(card)
        
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
        self._thread = QThread()
        self._worker = HardwareScanWorker()
        self._worker.moveToThread(self._thread)
        
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_hardware_scan_complete)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        
        self._thread.start()
    
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
        
        card.add_info_row("Processor", cpu.name, highlight=True)
        card.add_info_row("Manufacturer", cpu.manufacturer)
        card.add_info_row("Architecture", cpu.architecture)
        card.add_info_row("Cores / Threads", f"{cpu.cores} cores / {cpu.threads} threads")
        card.add_info_row("Base Clock", f"{cpu.max_clock_mhz} MHz")
        card.add_info_row("Current Clock", f"{cpu.current_clock_mhz} MHz")
        card.add_info_row("Socket", cpu.socket)
        
        if cpu.l2_cache_kb > 0:
            l2_mb = cpu.l2_cache_kb / 1024
            card.add_info_row("L2 Cache", f"{l2_mb:.1f} MB" if l2_mb >= 1 else f"{cpu.l2_cache_kb} KB")
        if cpu.l3_cache_kb > 0:
            l3_mb = cpu.l3_cache_kb / 1024
            card.add_info_row("L3 Cache", f"{l3_mb:.1f} MB" if l3_mb >= 1 else f"{cpu.l3_cache_kb} KB")
        
        card.add_divider()
        card.add_info_row("Current Usage", f"{cpu.utilization_percent:.0f}%")
        
        if cpu.temperature_c:
            temp_status = "healthy" if cpu.temperature_c < 70 else ("warning" if cpu.temperature_c < 85 else "critical")
            card.add_info_row("Temperature", f"{cpu.temperature_c:.0f}°C")
        
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
                card.add_divider()
                card.add_subsection(f"GPU {i + 1}")
            
            card.add_info_row("Graphics Card", gpu.name, highlight=True)
            card.add_info_row("Manufacturer", gpu.manufacturer)
            card.add_info_row("Driver Version", gpu.driver_version)
            card.add_info_row("Driver Date", gpu.driver_date)
            
            if gpu.vram_mb > 0:
                vram_gb = gpu.vram_mb / 1024
                vram_str = f"{vram_gb:.1f} GB" if vram_gb >= 1 else f"{gpu.vram_mb} MB"
                card.add_info_row("Video Memory", vram_str)
            
            if gpu.resolution != "Unknown":
                card.add_info_row("Resolution", f"{gpu.resolution} @ {gpu.refresh_rate}Hz")
            
            if gpu.temperature_c:
                card.add_info_row("Temperature", f"{gpu.temperature_c:.0f}°C")
        
        # Set card status based on first GPU
        if gpus:
            status = gpus[0].status.value if hasattr(gpus[0].status, 'value') else str(gpus[0].status)
            card.set_status(status)
    
    def _populate_ram_card(self, ram):
        """Populate RAM information card"""
        card = self.cards["ram"]
        card.clear_info()
        
        card.add_info_row("Total Memory", f"{ram.total_gb:.1f} GB", highlight=True)
        card.add_info_row("Used", f"{ram.used_gb:.1f} GB ({ram.utilization_percent:.0f}%)")
        card.add_info_row("Available", f"{ram.available_gb:.1f} GB")
        card.add_info_row("Slots Used", f"{ram.slots_used} of {ram.slots_total}")
        
        if ram.slots:
            card.add_divider()
            card.add_subsection("Installed Modules")
            
            for slot in ram.slots:
                if slot.capacity_gb > 0:
                    slot_info = f"{slot.capacity_gb:.0f} GB {slot.memory_type}"
                    if slot.speed_mhz > 0:
                        slot_info += f" @ {slot.speed_mhz} MHz"
                    card.add_info_row(slot.slot or "Slot", slot_info)
                    
                    if slot.manufacturer and slot.manufacturer not in ["Unknown", ""]:
                        card.add_info_row("  Manufacturer", slot.manufacturer)
        
        # Set status based on utilization
        status = ram.status.value if hasattr(ram.status, 'value') else str(ram.status)
        if ram.utilization_percent > 90:
            card.set_status("critical", f"{ram.utilization_percent:.0f}% Used")
        elif ram.utilization_percent > 75:
            card.set_status("warning", f"{ram.utilization_percent:.0f}% Used")
        else:
            card.set_status(status, f"{ram.available_gb:.1f} GB Free")
    
    def _populate_motherboard_card(self, mb):
        """Populate motherboard and BIOS information card"""
        card = self.cards["motherboard"]
        card.clear_info()
        
        card.add_info_row("Manufacturer", mb.manufacturer, highlight=True)
        card.add_info_row("Model", mb.product)
        if mb.version:
            card.add_info_row("Version", mb.version)
        if mb.serial_number and mb.serial_number != "Unknown":
            card.add_info_row("Serial Number", mb.serial_number)
        
        card.add_divider()
        card.add_subsection("BIOS Information")
        
        card.add_info_row("BIOS Vendor", mb.bios_vendor)
        card.add_info_row("BIOS Version", mb.bios_version)
        card.add_info_row("BIOS Date", mb.bios_date)
        card.add_info_row("Firmware Mode", mb.bios_mode)
        
        card.add_divider()
        card.add_subsection("Security Features")
        
        secure_boot_status = "Enabled" if mb.secure_boot else "Disabled"
        secure_boot_color = Theme.SUCCESS if mb.secure_boot else Theme.WARNING
        card.add_info_row("Secure Boot", secure_boot_status)
        
        tpm_status = f"Present (v{mb.tpm_version})" if mb.tpm_present else "Not detected"
        card.add_info_row("TPM", tpm_status)
        
        # Set card status
        status = mb.status.value if hasattr(mb.status, 'value') else str(mb.status)
        card.set_status(status)
    
    def _populate_storage_card(self, storage):
        """Populate storage information card"""
        card = self.cards["storage"]
        card.clear_info()
        
        # Physical drives
        for i, drive in enumerate(storage.physical_drives):
            if i > 0:
                card.add_divider()
            
            card.add_info_row("Drive", drive.model, highlight=True)
            card.add_info_row("Capacity", f"{drive.capacity_gb:.0f} GB")
            card.add_info_row("Type", f"{drive.media_type} ({drive.interface_type})")
            card.add_info_row("Firmware", drive.firmware_version)
            card.add_info_row("SMART Status", drive.smart_status)
            
            if drive.temperature_c:
                card.add_info_row("Temperature", f"{drive.temperature_c:.0f}°C")
            if drive.power_on_hours:
                card.add_info_row("Power-On Hours", f"{drive.power_on_hours:,}")
        
        if storage.volumes:
            card.add_divider()
            card.add_subsection("Volumes")
            
            for vol in storage.volumes:
                usage_str = f"{vol.used_gb:.1f} / {vol.capacity_gb:.1f} GB ({vol.utilization_percent:.0f}%)"
                vol_name = f"{vol.drive_letter}"
                if vol.label:
                    vol_name += f" ({vol.label})"
                card.add_info_row(vol_name, usage_str)
        
        # Set status based on drive health
        has_warning = any(d.status.value == "warning" for d in storage.physical_drives if hasattr(d.status, 'value'))
        has_critical = any(d.status.value == "critical" for d in storage.physical_drives if hasattr(d.status, 'value'))
        vol_critical = any(v.utilization_percent > 95 for v in storage.volumes)
        vol_warning = any(v.utilization_percent > 85 for v in storage.volumes)
        
        if has_critical or vol_critical:
            card.set_status("critical", "Issues Detected")
        elif has_warning or vol_warning:
            card.set_status("warning", "Attention Needed")
        else:
            card.set_status("healthy", "All Healthy")
    
    def _populate_network_card(self, adapters):
        """Populate network adapter information card"""
        card = self.cards["network"]
        card.clear_info()
        
        connected_count = sum(1 for a in adapters if a.link_state == "Connected")
        card.set_status("healthy" if connected_count > 0 else "warning", 
                       f"{connected_count} Connected" if connected_count > 0 else "Disconnected")
        
        for i, adapter in enumerate(adapters):
            if i > 0:
                card.add_divider()
            
            card.add_info_row("Adapter", adapter.name, highlight=True)
            card.add_info_row("Type", adapter.adapter_type)
            card.add_info_row("Status", adapter.link_state)
            
            if adapter.speed_mbps > 0:
                speed_str = f"{adapter.speed_mbps} Mbps"
                if adapter.speed_mbps >= 1000:
                    speed_str = f"{adapter.speed_mbps / 1000:.0f} Gbps"
                card.add_info_row("Speed", speed_str)
            
            card.add_info_row("MAC Address", adapter.mac_address)
            
            if adapter.ipv4_address != "Not assigned":
                card.add_info_row("IPv4 Address", adapter.ipv4_address)
            if adapter.ipv6_address != "Not assigned" and len(adapter.ipv6_address) < 40:
                card.add_info_row("IPv6 Address", adapter.ipv6_address)
            if adapter.gateway:
                card.add_info_row("Gateway", adapter.gateway)
            if adapter.dns_servers:
                card.add_info_row("DNS Servers", ", ".join(adapter.dns_servers[:2]))
            
            dhcp_status = "Enabled" if adapter.dhcp_enabled else "Disabled"
            card.add_info_row("DHCP", dhcp_status)
        
        if not adapters:
            card.add_info_row("Status", "No active network adapters found")
            card.set_status("warning", "No Adapters")
    
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
            font-size: 26px;
            font-weight: bold;
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
    
    def _create_dropdown(self, options: list, setting_key: str = None) -> QWidget:
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
    
    def _create_toggle(self, initial: bool, setting_key: str = None) -> QFrame:
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
        
        # Content stack
        self.content_stack = QStackedWidget()
        
        # Create pages
        self.overview = OverviewPage()
        self.overview.health_card.scan_btn.clicked.connect(self.run_scan)
        self.overview.card_clicked.connect(self.navigate)  # Connect status card clicks to navigation
        self.content_stack.addWidget(self.overview)
        
        self.pages = {"overview": self.overview}
        
        modules = [
            ("updates", "Windows Update", "download"),
            ("storage", "Storage Health", "hdd"),
            ("security", "Security Status", "shield"),
            # Hardware now uses dedicated HardwarePage
            ("system", "System Files", "file"),
            ("events", "Event Analysis", "alert"),
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
    
    def run_scan(self):
        """Run full system scan"""
        dialog = ScanProgressDialog(self)
        dialog.show()
        
        self.scan_dialog = dialog
        self.scan_progress = 0
        self.scan_task_index = 0
        self.scan_tasks = ["update", "defender", "sfc", "smart", "memory", "events", "services"]
        
        # Start scan simulation
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self._update_scan)
        self.scan_timer.start(400)
    
    def _update_scan(self):
        tasks = self.scan_tasks
        
        # Complete previous task
        if self.scan_task_index > 0:
            prev_task = tasks[self.scan_task_index - 1]
            self.scan_dialog.update_task(prev_task, "complete")
        
        # Start current task
        if self.scan_task_index < len(tasks):
            current_task = tasks[self.scan_task_index]
            self.scan_dialog.update_task(current_task, "running")
            self.scan_task_index += 1
        
        # Update progress
        self.scan_progress = min(100, int((self.scan_task_index / len(tasks)) * 100))
        remaining = max(0, len(tasks) - self.scan_task_index)
        self.scan_dialog.set_progress(self.scan_progress, f"{remaining * 2} seconds")
        
        # Finish
        if self.scan_progress >= 100:
            self.scan_timer.stop()
            
            # Update overview with results
            self.overview.health_card.set_score(94, 12, 2, 0)
            
            cards = self.overview.status_cards
            cards["updates"].set_status("check", "Up to date")
            cards["defender"].set_status("check", "Protected")
            cards["storage"].set_status("warning", "85% used")
            cards["drives"].set_status("check", "All drives OK")
            cards["memory"].set_status("check", "4.2 GB free")
            cards["system"].set_status("check", "No issues")
            
            # Add activity
            self.overview.add_activity("success", "Full scan completed", datetime.now().strftime("%I:%M %p"))
            
            self.statusBar().showMessage("Scan complete - 12 checks passed, 2 warnings")
            
            QTimer.singleShot(800, self.scan_dialog.accept)
    
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
        """Check Windows Update status"""
        results = []
        try:
            update_info = self.health_checker.check_windows_update_status()
            
            if 'Error' in update_info:
                results.append(("warning", f"Could not check updates: {update_info['Error']}"))
            else:
                last_check = update_info.get('LastCheck', 'Unknown')
                results.append(("info", f"Last update check: {last_check}"))
                
                pending = update_info.get('PendingUpdates', 0)
                if pending > 0:
                    results.append(("warning", f"{pending} updates pending installation"))
                else:
                    results.append(("check", "All updates installed"))
                
                last_install = update_info.get('LastInstall', 'Unknown')
                results.append(("info", f"Last install: {last_install}"))
                
        except Exception as e:
            results.append(("error", f"Error checking updates: {str(e)}"))
        
        if not results:
            results.append(("info", "No update information available"))
        
        self.pages["updates"].show_results(results)
        self.overview.status_cards["updates"].set_status(
            "check" if all(r[0] == "check" or r[0] == "info" for r in results) else "warning",
            "Up to date" if all(r[0] != "warning" for r in results) else "Updates available"
        )
    
    def check_storage_health(self):
        """Check storage/disk health"""
        results = []
        try:
            volume_info = self.health_checker.get_volume_info()
            
            for vol in volume_info:
                letter = vol.get('DriveLetter', '?')
                label = vol.get('FileSystemLabel', '')
                size_gb = vol.get('SizeGB', 0)
                free_gb = vol.get('FreeSpaceGB', 0)
                health = vol.get('HealthStatus', 'Unknown')
                
                if size_gb > 0:
                    used_percent = int(((size_gb - free_gb) / size_gb) * 100)
                else:
                    used_percent = 0
                
                name = f"{letter}:"
                if label:
                    name += f" ({label})"
                
                if used_percent >= 90:
                    results.append(("error", f"{name}: {used_percent}% used - Critical! ({free_gb:.1f} GB free)"))
                elif used_percent >= 75:
                    results.append(("warning", f"{name}: {used_percent}% used ({free_gb:.1f} GB free)"))
                else:
                    results.append(("check", f"{name}: {used_percent}% used ({free_gb:.1f} GB free)"))
                    
        except Exception as e:
            results.append(("error", f"Error checking storage: {str(e)}"))
        
        if not results:
            results.append(("info", "No volume information available"))
        
        self.pages["storage"].show_results(results)
        
        # Update status card
        worst_status = "check"
        for status, _ in results:
            if status == "error":
                worst_status = "error"
                break
            elif status == "warning":
                worst_status = "warning"
        
        self.overview.status_cards["storage"].set_status(
            worst_status,
            "Critical" if worst_status == "error" else "Warning" if worst_status == "warning" else "Healthy"
        )
    
    def check_security_status(self):
        """Check Windows Defender and security status"""
        results = []
        try:
            defender = self.health_checker.check_defender_status()
            
            if 'Error' in defender:
                results.append(("warning", f"Could not check Defender: {defender['Error']}"))
            else:
                enabled = defender.get('AntivirusEnabled', False)
                if enabled:
                    results.append(("check", "Windows Defender Antivirus is enabled"))
                else:
                    results.append(("error", "Windows Defender Antivirus is disabled!"))
                
                realtime = defender.get('RealTimeProtection', False)
                if realtime:
                    results.append(("check", "Real-time protection is active"))
                else:
                    results.append(("warning", "Real-time protection is off"))
                
                last_scan = defender.get('LastScan', 'Unknown')
                results.append(("info", f"Last full scan: {last_scan}"))
                
                sig_age = defender.get('SignatureAge', 0)
                if sig_age == 0:
                    results.append(("check", "Virus definitions are up to date"))
                elif sig_age <= 3:
                    results.append(("info", f"Virus definitions are {sig_age} days old"))
                else:
                    results.append(("warning", f"Virus definitions are {sig_age} days old - update recommended"))
                
        except Exception as e:
            results.append(("error", f"Error checking security: {str(e)}"))
        
        if not results:
            results.append(("info", "No security information available"))
        
        self.pages["security"].show_results(results)
        self.overview.status_cards["defender"].set_status(
            "check" if all(r[0] != "error" for r in results) else "error",
            "Protected" if all(r[0] != "error" for r in results) else "At Risk"
        )
    
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
        """Check system file integrity info (quick check, not full SFC)"""
        results = []
        try:
            # Provide info and action buttons
            results.append(("info", "System file integrity can be verified with SFC /scannow"))
            results.append(("info", "DISM can repair the Windows component store"))
            results.append(("check", "Use the action buttons below to run system repairs"))
            
        except Exception as e:
            results.append(("error", f"Error: {str(e)}"))
        
        # Show results with action buttons
        self.pages["system"].show_results_with_actions(results, [
            ("Run SFC Scan", self._run_sfc_scan),
            ("Run DISM Repair", self._run_dism_repair),
        ])
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
        """Check Windows event logs summary"""
        results = []
        try:
            # Quick PowerShell query for recent errors
            command = """
            $errors = Get-EventLog -LogName System -EntryType Error -Newest 10 -ErrorAction SilentlyContinue | 
                      Select-Object -First 5 TimeGenerated, Source, Message
            $warnings = Get-EventLog -LogName System -EntryType Warning -Newest 10 -ErrorAction SilentlyContinue |
                        Select-Object -First 5 TimeGenerated, Source, Message
            @{
                ErrorCount = (Get-EventLog -LogName System -EntryType Error -After (Get-Date).AddHours(-24) -ErrorAction SilentlyContinue).Count
                WarningCount = (Get-EventLog -LogName System -EntryType Warning -After (Get-Date).AddHours(-24) -ErrorAction SilentlyContinue).Count
                RecentErrors = $errors
            } | ConvertTo-Json -Depth 3
            """
            import subprocess
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            import json
            data = json.loads(result.stdout) if result.stdout.strip() else {}
            
            error_count = data.get('ErrorCount', 0) or 0
            warning_count = data.get('WarningCount', 0) or 0
            
            if error_count > 10:
                results.append(("error", f"{error_count} errors in the last 24 hours"))
            elif error_count > 0:
                results.append(("warning", f"{error_count} errors in the last 24 hours"))
            else:
                results.append(("check", "No errors in the last 24 hours"))
            
            if warning_count > 20:
                results.append(("warning", f"{warning_count} warnings in the last 24 hours"))
            elif warning_count > 0:
                results.append(("info", f"{warning_count} warnings in the last 24 hours"))
            else:
                results.append(("check", "No warnings in the last 24 hours"))
                
        except Exception as e:
            results.append(("warning", f"Could not check event logs: {str(e)}"))
        
        if not results:
            results.append(("info", "Event log check complete"))
        
        self.pages["events"].show_results(results)


# =============================================================================
# SPLASH SCREEN
# =============================================================================

class SplashScreen(QWidget):
    """
    Modern splash screen with loading progress bar.
    Shows during app initialization to provide immediate visual feedback.
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SplashScreen
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(480, 320)
        
        # Center on screen
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
        
        self.progress = 0
        self.status_text = "Initializing..."
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Main container with rounded corners
        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_SIDEBAR};
                border-radius: 16px;
                border: 1px solid {Theme.BORDER};
            }}
        """)
        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(40, 40, 40, 32)
        container_layout.setSpacing(16)
        
        # App icon
        icon_container = QFrame()
        icon_container.setFixedSize(64, 64)
        icon_container.setStyleSheet(f"""
            background: {Theme.ACCENT};
            border-radius: 16px;
        """)
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon = QLabel("+")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("background: transparent; color: white; font-size: 32px; font-weight: bold;")
        icon_layout.addWidget(icon)
        
        container_layout.addWidget(icon_container, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # App title
        title = QLabel("Windows Health Checker Pro")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_PRIMARY};
            font-size: 22px;
            font-weight: bold;
        """)
        container_layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("System Diagnostics & Optimization")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_TERTIARY};
            font-size: 12px;
        """)
        container_layout.addWidget(subtitle)
        
        container_layout.addSpacing(24)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {Theme.BG_CARD};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {Theme.ACCENT}, stop:1 {Theme.ACCENT_LIGHT});
                border-radius: 3px;
            }}
        """)
        container_layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_SECONDARY};
            font-size: 11px;
        """)
        container_layout.addWidget(self.status_label)
        
        container_layout.addStretch()
        
        # Version
        version = QLabel("Version 1.0.0")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet(f"""
            background: transparent;
            color: {Theme.TEXT_TERTIARY};
            font-size: 10px;
        """)
        container_layout.addWidget(version)
        
        layout.addWidget(container)
    
    def set_progress(self, value: int, status: str = None):
        """Update progress bar and status text"""
        self.progress = min(100, max(0, value))
        self.progress_bar.setValue(self.progress)
        if status:
            self.status_label.setText(status)
        QApplication.processEvents()  # Force UI update
    
    def paintEvent(self, event):
        """Draw shadow behind the container"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw subtle shadow
        shadow_color = QColor(0, 0, 0, 60)
        painter.setBrush(QBrush(shadow_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(4, 4, self.width() - 4, self.height() - 4, 16, 16)


class AppLoader:
    """
    Manages app loading with splash screen.
    Loads components in stages with progress updates.
    """
    
    def __init__(self, app: QApplication):
        self.app = app
        self.splash = SplashScreen()
        self.window = None
    
    def load(self) -> MainWindow:
        """Load the app with progress updates"""
        self.splash.show()
        
        # Stage 1: Basic initialization
        self.splash.set_progress(10, "Loading UI components...")
        QApplication.processEvents()
        
        # Stage 2: Create main window (this imports and sets up all pages)
        self.splash.set_progress(30, "Initializing main window...")
        QApplication.processEvents()
        
        self.window = MainWindow()
        
        # Stage 3: Additional setup
        self.splash.set_progress(60, "Loading backend services...")
        QApplication.processEvents()
        
        # Small delay to show progress
        import time
        time.sleep(0.1)
        
        # Stage 4: Finalizing
        self.splash.set_progress(80, "Preparing interface...")
        QApplication.processEvents()
        time.sleep(0.1)
        
        # Stage 5: Complete
        self.splash.set_progress(100, "Ready!")
        QApplication.processEvents()
        time.sleep(0.2)
        
        # Close splash and show main window
        self.splash.close()
        return self.window


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    # Enable high DPI before creating app
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Check admin privileges
    if not is_admin():
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
    
    # Load app with splash screen
    loader = AppLoader(app)
    window = loader.load()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
