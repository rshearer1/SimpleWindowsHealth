"""
Windows Health Checker Pro - MK4
Professional UI based on comprehensive design specification
Inspired by Microsoft PowerToys, Windows Security, and Windows Terminal
"""

import sys
import uuid
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QProgressBar,
    QStackedWidget, QGraphicsDropShadowEffect, QSizePolicy,
    QDialog, QCheckBox, QSpacerItem, QGridLayout, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtGui import QFont, QColor, QPainter, QPainterPath, QLinearGradient

from driver_backend import (
    DriverScanner, OnlineDriverChecker, ManufacturerSupport,
    HealthChecker, DiskManager, DriverInfo,
    is_admin, run_as_admin, open_url
)


# =============================================================================
# DESIGN TOKENS (from UI Specification)
# =============================================================================

class Colors:
    """Color palette - Minimalist dark theme"""
    # Background layers
    WINDOW_BG = "#1b1b1f"
    SIDEBAR_BG = "#232328"
    CARD_BG = "#2d2d32"
    HOVER = "#38383d"
    ACTIVE = "#0078d4"
    
    # Text hierarchy
    TEXT_PRIMARY = "#ffffff"
    TEXT_SECONDARY = "#b4b4b4"
    TEXT_TERTIARY = "#7a7a7a"
    TEXT_DISABLED = "#4a4a4a"
    
    # Semantic colors
    SUCCESS = "#0f9d58"
    WARNING = "#f4b400"
    ERROR = "#db4437"
    INFO = "#4285f4"
    RUNNING = "#8e44ad"
    
    # Accent colors
    ACCENT = "#0078d4"
    ACCENT_DARK = "#106ebe"
    ACCENT_LIGHT = "#60cdff"
    
    # Borders
    BORDER = "#3a3a3f"
    BORDER_LIGHT = "rgba(255,255,255,0.06)"


class Spacing:
    """Spacing system - 8px grid"""
    XS = 4
    SM = 8
    MD = 16
    LG = 24
    XL = 32
    XXL = 48
    
    CARD_PADDING = 20
    SIDEBAR_WIDTH = 240
    SIDEBAR_COLLAPSED = 48


class Typography:
    """Typography system"""
    FONT_FAMILY = "Segoe UI Variable, Segoe UI, system-ui, sans-serif"
    FONT_MONO = "Cascadia Code, Consolas, monospace"
    
    # Sizes
    PAGE_TITLE = 28
    SECTION_HEADER = 18
    CARD_TITLE = 14
    BODY = 13
    CAPTION = 11
    BUTTON = 13


# =============================================================================
# STYLESHEET
# =============================================================================

STYLESHEET = f"""
QMainWindow {{
    background: {Colors.WINDOW_BG};
}}

QWidget {{
    background: transparent;
    color: {Colors.TEXT_PRIMARY};
    font-family: {Typography.FONT_FAMILY};
    font-size: {Typography.BODY}px;
}}

QScrollArea {{
    border: none;
    background: transparent;
}}

QScrollBar:vertical {{
    background: {Colors.SIDEBAR_BG};
    width: 10px;
    border-radius: 5px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: {Colors.HOVER};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: {Colors.TEXT_TERTIARY};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background: {Colors.SIDEBAR_BG};
    height: 10px;
    border-radius: 5px;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background: {Colors.HOVER};
    border-radius: 4px;
    min-width: 30px;
}}

QProgressBar {{
    background: {Colors.HOVER};
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {Colors.ACCENT}, stop:1 {Colors.ACCENT_LIGHT});
    border-radius: 3px;
}}

QTextEdit {{
    background: {Colors.SIDEBAR_BG};
    border: 1px solid {Colors.BORDER};
    border-radius: 8px;
    padding: 12px;
    color: {Colors.TEXT_PRIMARY};
    font-family: {Typography.FONT_MONO};
    font-size: 12px;
}}

QTableWidget {{
    background: {Colors.SIDEBAR_BG};
    alternate-background-color: {Colors.CARD_BG};
    border: 1px solid {Colors.BORDER};
    border-radius: 8px;
    gridline-color: transparent;
}}

QTableWidget::item {{
    padding: 8px;
    border: none;
}}

QTableWidget::item:selected {{
    background: {Colors.HOVER};
}}

QHeaderView::section {{
    background: {Colors.SIDEBAR_BG};
    color: {Colors.TEXT_SECONDARY};
    padding: 10px;
    border: none;
    border-bottom: 1px solid {Colors.BORDER};
    font-weight: 600;
}}

QDialog {{
    background: {Colors.CARD_BG};
}}
"""


# =============================================================================
# CUSTOM WIDGETS
# =============================================================================

class NavItem(QFrame):
    """Sidebar navigation item"""
    clicked = pyqtSignal()
    
    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self.icon_text = icon
        self.label_text = label
        self.is_selected = False
        self.setFixedHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)
        
        self.icon = QLabel(self.icon_text)
        self.icon.setStyleSheet(f"font-size: 18px; color: {Colors.TEXT_SECONDARY};")
        layout.addWidget(self.icon)
        
        self.label = QLabel(self.label_text)
        self.label.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_SECONDARY}; font-weight: 500;")
        layout.addWidget(self.label)
        
        layout.addStretch()
        self.update_style()
    
    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.update_style()
    
    def update_style(self):
        if self.is_selected:
            self.setStyleSheet(f"""
                NavItem {{
                    background: rgba(0, 120, 212, 0.1);
                    border-left: 3px solid {Colors.ACCENT};
                    border-radius: 0;
                }}
            """)
            self.icon.setStyleSheet(f"font-size: 18px; color: {Colors.ACCENT_LIGHT};")
            self.label.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_PRIMARY}; font-weight: 500;")
        else:
            self.setStyleSheet(f"""
                NavItem {{
                    background: transparent;
                    border-left: 3px solid transparent;
                }}
                NavItem:hover {{
                    background: {Colors.HOVER};
                }}
            """)
            self.icon.setStyleSheet(f"font-size: 18px; color: {Colors.TEXT_SECONDARY};")
            self.label.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_SECONDARY}; font-weight: 500;")
    
    def enterEvent(self, event):
        if not self.is_selected:
            self.setStyleSheet(f"""
                NavItem {{
                    background: {Colors.HOVER};
                    border-left: 3px solid transparent;
                }}
            """)
    
    def leaveEvent(self, event):
        self.update_style()
    
    def mousePressEvent(self, event):
        self.clicked.emit()


class StatusChip(QFrame):
    """Status indicator chip"""
    
    def __init__(self, status: str = "healthy", text: str = "Healthy", parent=None):
        super().__init__(parent)
        self.setup_ui(status, text)
    
    def setup_ui(self, status: str, text: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)
        
        # Status dot
        self.dot = QLabel("●")
        
        # Text
        self.text = QLabel(text)
        self.text.setStyleSheet("font-size: 12px; font-weight: 500;")
        
        layout.addWidget(self.dot)
        layout.addWidget(self.text)
        
        self.set_status(status)
    
    def set_status(self, status: str, text: str = None):
        colors = {
            "healthy": (Colors.SUCCESS, "rgba(15,157,88,0.15)", "rgba(15,157,88,0.3)"),
            "warning": (Colors.WARNING, "rgba(244,180,0,0.15)", "rgba(244,180,0,0.3)"),
            "error": (Colors.ERROR, "rgba(219,68,55,0.15)", "rgba(219,68,55,0.3)"),
            "running": (Colors.RUNNING, "rgba(142,68,173,0.15)", "rgba(142,68,173,0.3)"),
            "info": (Colors.INFO, "rgba(66,133,244,0.15)", "rgba(66,133,244,0.3)"),
        }
        
        color, bg, border = colors.get(status, colors["info"])
        
        self.setStyleSheet(f"""
            StatusChip {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 12px;
            }}
        """)
        self.dot.setStyleSheet(f"color: {color}; font-size: 8px;")
        self.text.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 500;")
        
        if text:
            self.text.setText(text)


class HealthCard(QFrame):
    """Health status card component"""
    
    action_clicked = pyqtSignal(str)
    
    def __init__(self, icon: str, title: str, parent=None):
        super().__init__(parent)
        self.icon_text = icon
        self.title_text = title
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            HealthCard {{
                background: {Colors.CARD_BG};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.CARD_PADDING, Spacing.CARD_PADDING, 
                                   Spacing.CARD_PADDING, Spacing.CARD_PADDING)
        layout.setSpacing(Spacing.MD)
        
        # Header row
        header = QHBoxLayout()
        header.setSpacing(Spacing.SM)
        
        # Icon container
        icon_container = QFrame()
        icon_container.setFixedSize(40, 40)
        icon_container.setStyleSheet(f"""
            background: {Colors.HOVER};
            border-radius: 8px;
        """)
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel(self.icon_text)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 20px;")
        icon_layout.addWidget(icon_label)
        header.addWidget(icon_container)
        
        # Title
        self.title_label = QLabel(self.title_text)
        self.title_label.setStyleSheet(f"""
            font-size: {Typography.CARD_TITLE}px;
            font-weight: 600;
            color: {Colors.TEXT_PRIMARY};
        """)
        header.addWidget(self.title_label)
        
        header.addStretch()
        
        # Status chip
        self.status_chip = StatusChip("info", "Unknown")
        header.addWidget(self.status_chip)
        
        layout.addLayout(header)
        
        # Description
        self.description = QLabel("Checking status...")
        self.description.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 12px;")
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        
        # Details area (optional)
        self.details_frame = QFrame()
        self.details_frame.setStyleSheet(f"""
            background: {Colors.SIDEBAR_BG};
            border-radius: 6px;
            padding: 8px;
        """)
        self.details_frame.setVisible(False)
        self.details_layout = QVBoxLayout(self.details_frame)
        self.details_layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(self.details_frame)
        
        # Action buttons
        self.actions_layout = QHBoxLayout()
        self.actions_layout.setSpacing(Spacing.SM)
        layout.addLayout(self.actions_layout)
    
    def set_status(self, status: str, status_text: str, description: str):
        self.status_chip.set_status(status, status_text)
        self.description.setText(description)
    
    def add_action(self, text: str, primary: bool = False, action_id: str = None):
        btn = QPushButton(text)
        if primary:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {Colors.ACCENT};
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-weight: 600;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background: {Colors.ACCENT_DARK};
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {Colors.TEXT_PRIMARY};
                    border: 1px solid {Colors.BORDER};
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-weight: 500;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background: {Colors.HOVER};
                }}
            """)
        btn.clicked.connect(lambda: self.action_clicked.emit(action_id or text))
        self.actions_layout.addWidget(btn)
    
    def add_detail(self, label: str, value: str):
        self.details_frame.setVisible(True)
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 12px;")
        val = QLabel(value)
        val.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 12px;")
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(val)
        self.details_layout.addLayout(row)


class QuickStatusCard(QFrame):
    """Small status card for overview grid"""
    
    clicked = pyqtSignal()
    
    def __init__(self, icon: str, title: str, parent=None):
        super().__init__(parent)
        self.icon_text = icon
        self.title_text = title
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(80)
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            QuickStatusCard {{
                background: {Colors.CARD_BG};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
            }}
            QuickStatusCard:hover {{
                border-color: {Colors.ACCENT};
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        # Status indicator
        self.status_dot = QLabel("✓")
        self.status_dot.setStyleSheet(f"font-size: 18px; color: {Colors.SUCCESS};")
        layout.addWidget(self.status_dot)
        
        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        self.title_label = QLabel(self.title_text)
        self.title_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {Colors.TEXT_PRIMARY};")
        text_layout.addWidget(self.title_label)
        
        self.subtitle = QLabel("Checking...")
        self.subtitle.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_TERTIARY};")
        text_layout.addWidget(self.subtitle)
        
        layout.addLayout(text_layout)
        layout.addStretch()
    
    def set_status(self, status: str, subtitle: str):
        icons = {
            "healthy": ("✓", Colors.SUCCESS),
            "warning": ("⚠", Colors.WARNING),
            "error": ("✗", Colors.ERROR),
            "running": ("◐", Colors.RUNNING),
        }
        icon, color = icons.get(status, ("?", Colors.TEXT_TERTIARY))
        self.status_dot.setText(icon)
        self.status_dot.setStyleSheet(f"font-size: 18px; color: {color};")
        self.subtitle.setText(subtitle)
    
    def mousePressEvent(self, event):
        self.clicked.emit()


class HealthScoreWidget(QFrame):
    """Large health score display"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.score = 0
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            HealthScoreWidget {{
                background: {Colors.CARD_BG};
                border: 1px solid {Colors.BORDER};
                border-radius: 12px;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.XL)
        
        # Score circle (simplified - just number)
        score_container = QVBoxLayout()
        score_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.score_label = QLabel("--")
        self.score_label.setStyleSheet(f"""
            font-size: 64px;
            font-weight: bold;
            color: {Colors.SUCCESS};
        """)
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_container.addWidget(self.score_label)
        
        score_subtitle = QLabel("/ 100")
        score_subtitle.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 18px;")
        score_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_container.addWidget(score_subtitle)
        
        layout.addLayout(score_container)
        
        # Status text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(Spacing.SM)
        
        self.status_text = QLabel("Analyzing system...")
        self.status_text.setStyleSheet(f"""
            font-size: 20px;
            font-weight: 600;
            color: {Colors.TEXT_PRIMARY};
        """)
        text_layout.addWidget(self.status_text)
        
        self.details_text = QLabel("Running initial checks...")
        self.details_text.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 13px;")
        self.details_text.setWordWrap(True)
        text_layout.addWidget(self.details_text)
        
        text_layout.addStretch()
        
        # Last scan time
        self.last_scan = QLabel("Last scan: Never")
        self.last_scan.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 11px;")
        text_layout.addWidget(self.last_scan)
        
        layout.addLayout(text_layout, 1)
        
        # Action button
        self.scan_btn = QPushButton("Run Full Scan")
        self.scan_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Colors.ACCENT};
                color: white;
                border: none;
                padding: 14px 28px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: {Colors.ACCENT_DARK};
            }}
        """)
        layout.addWidget(self.scan_btn, 0, Qt.AlignmentFlag.AlignTop)
    
    def set_score(self, score: int, passed: int, warnings: int, errors: int):
        self.score = score
        self.score_label.setText(str(score))
        
        # Color based on score
        if score >= 90:
            color = Colors.SUCCESS
            status = "Your system is healthy"
        elif score >= 70:
            color = Colors.WARNING
            status = "Some attention needed"
        else:
            color = Colors.ERROR
            status = "Issues detected"
        
        self.score_label.setStyleSheet(f"font-size: 64px; font-weight: bold; color: {color};")
        self.status_text.setText(status)
        self.details_text.setText(f"{passed} checks passed  •  {warnings} warnings  •  {errors} errors")
        self.last_scan.setText(f"Last scan: {datetime.now().strftime('%I:%M %p')}")


class ScanProgressModal(QDialog):
    """Modal dialog for running all checks"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Running System Health Check")
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setFixedSize(500, 450)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet(f"background: {Colors.CARD_BG};")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.MD)
        
        # Title
        title = QLabel("Running System Health Check")
        title.setStyleSheet(f"font-size: 18px; font-weight: 600; color: {Colors.TEXT_PRIMARY};")
        layout.addWidget(title)
        
        # Task list
        self.task_frame = QFrame()
        self.task_frame.setStyleSheet(f"""
            background: {Colors.SIDEBAR_BG};
            border-radius: 8px;
        """)
        self.task_layout = QVBoxLayout(self.task_frame)
        self.task_layout.setContentsMargins(12, 12, 12, 12)
        self.task_layout.setSpacing(8)
        
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
            row = QHBoxLayout()
            
            status_icon = QLabel("○")
            status_icon.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 14px;")
            status_icon.setFixedWidth(20)
            row.addWidget(status_icon)
            
            name = QLabel(task_name)
            name.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 13px;")
            row.addWidget(name)
            
            row.addStretch()
            
            status_text = QLabel("Pending")
            status_text.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 12px;")
            row.addWidget(status_text)
            
            self.tasks[task_id] = {
                "icon": status_icon,
                "name": name,
                "status": status_text
            }
            
            self.task_layout.addLayout(row)
        
        layout.addWidget(self.task_frame)
        
        # Overall progress
        progress_label = QLabel("Overall Progress")
        progress_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(progress_label)
        
        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_row.addWidget(self.progress_bar)
        
        self.progress_percent = QLabel("0%")
        self.progress_percent.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 13px; font-weight: 600;")
        self.progress_percent.setFixedWidth(40)
        progress_row.addWidget(self.progress_percent)
        
        layout.addLayout(progress_row)
        
        # Time estimate
        self.time_label = QLabel("Estimated time remaining: Calculating...")
        self.time_label.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 11px;")
        layout.addWidget(self.time_label)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.bg_btn = QPushButton("Run in Background")
        self.bg_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {Colors.HOVER};
            }}
        """)
        self.bg_btn.setEnabled(False)  # Disable until real background behavior is implemented
        btn_layout.addWidget(self.bg_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Colors.TEXT_SECONDARY};
                border: none;
                padding: 10px 16px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def update_task(self, task_id: str, status: str, status_text: str = None):
        if task_id not in self.tasks:
            return
        
        task = self.tasks[task_id]
        
        if status == "running":
            task["icon"].setText("◐")
            task["icon"].setStyleSheet(f"color: {Colors.RUNNING}; font-size: 14px;")
            task["status"].setText(status_text or "Running...")
            task["status"].setStyleSheet(f"color: {Colors.RUNNING}; font-size: 12px;")
        elif status == "complete":
            task["icon"].setText("✓")
            task["icon"].setStyleSheet(f"color: {Colors.SUCCESS}; font-size: 14px;")
            task["status"].setText(status_text or "Complete")
            task["status"].setStyleSheet(f"color: {Colors.SUCCESS}; font-size: 12px;")
        elif status == "error":
            task["icon"].setText("✗")
            task["icon"].setStyleSheet(f"color: {Colors.ERROR}; font-size: 14px;")
            task["status"].setText(status_text or "Failed")
            task["status"].setStyleSheet(f"color: {Colors.ERROR}; font-size: 12px;")
    
    def set_progress(self, percent: int, time_remaining: str = None):
        self.progress_bar.setValue(percent)
        self.progress_percent.setText(f"{percent}%")
        if time_remaining:
            self.time_label.setText(f"Estimated time remaining: {time_remaining}")


# =============================================================================
# MODULE VIEWS
# =============================================================================

class OverviewPage(QWidget):
    """Overview dashboard page"""
    
    navigate_to = pyqtSignal(str)  # Emit module name to navigate
    run_all_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.LG)
        
        # Page title
        title = QLabel("System Health")
        title.setStyleSheet(f"""
            font-size: {Typography.PAGE_TITLE}px;
            font-weight: bold;
            color: {Colors.TEXT_PRIMARY};
        """)
        layout.addWidget(title)
        
        # Health score widget
        self.score_widget = HealthScoreWidget()
        self.score_widget.scan_btn.clicked.connect(self.run_all_clicked.emit)
        layout.addWidget(self.score_widget)
        
        # Quick status section
        section_label = QLabel("Quick Status")
        section_label.setStyleSheet(f"""
            font-size: {Typography.SECTION_HEADER}px;
            font-weight: 600;
            color: {Colors.TEXT_PRIMARY};
        """)
        layout.addWidget(section_label)
        
        # Status grid
        grid = QGridLayout()
        grid.setSpacing(Spacing.MD)
        
        self.quick_cards = {}
        # Map card IDs to sidebar module IDs for navigation
        cards_data = [
            ("updates", "updates", "📥", "Windows Update"),
            ("defender", "security", "🛡️", "Defender"),
            ("storage", "storage", "💾", "Storage"),
            ("drives", "hardware", "🔧", "Drive Health"),
            ("memory", "hardware", "🧠", "Memory"),
            ("system", "system", "📄", "System Files"),
        ]
        
        for i, (card_id, nav_id, icon, title) in enumerate(cards_data):
            card = QuickStatusCard(icon, title)
            card.clicked.connect(lambda nid=nav_id: self.navigate_to.emit(nid))
            self.quick_cards[card_id] = card
            grid.addWidget(card, i // 3, i % 3)
        
        layout.addLayout(grid)
        
        # Recent activity
        activity_label = QLabel("Recent Activity")
        activity_label.setStyleSheet(f"""
            font-size: {Typography.SECTION_HEADER}px;
            font-weight: 600;
            color: {Colors.TEXT_PRIMARY};
        """)
        layout.addWidget(activity_label)
        
        self.activity_list = QFrame()
        self.activity_list.setStyleSheet(f"""
            background: {Colors.CARD_BG};
            border: 1px solid {Colors.BORDER};
            border-radius: 8px;
        """)
        activity_layout = QVBoxLayout(self.activity_list)
        activity_layout.setContentsMargins(16, 12, 16, 12)
        activity_layout.setSpacing(8)
        
        # Placeholder activities
        for text in [
            "● Ready to scan",
            "  Click 'Run Full Scan' to begin",
        ]:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 12px;")
            activity_layout.addWidget(lbl)
        
        layout.addWidget(self.activity_list)
        layout.addStretch()


class ModulePage(QWidget):
    """Generic module detail page"""
    
    def __init__(self, title: str, icon: str, parent=None):
        super().__init__(parent)
        self.title_text = title
        self.icon_text = icon
        self.cards = []
        self.setup_ui()
    
    def setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        
        content = QWidget()
        self.layout = QVBoxLayout(content)
        self.layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        self.layout.setSpacing(Spacing.LG)
        
        # Header
        header = QHBoxLayout()
        
        title = QLabel(f"{self.icon_text}  {self.title_text}")
        title.setStyleSheet(f"""
            font-size: {Typography.PAGE_TITLE}px;
            font-weight: bold;
            color: {Colors.TEXT_PRIMARY};
        """)
        header.addWidget(title)
        
        header.addStretch()
        
        self.check_btn = QPushButton("Run Check")
        self.check_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Colors.ACCENT};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Colors.ACCENT_DARK};
            }}
        """)
        header.addWidget(self.check_btn)
        
        self.layout.addLayout(header)
        
        # Cards container
        self.cards_layout = QVBoxLayout()
        self.cards_layout.setSpacing(Spacing.MD)
        self.layout.addLayout(self.cards_layout)
        
        self.layout.addStretch()
        
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
    
    def add_card(self, card: HealthCard):
        self.cards.append(card)
        self.cards_layout.addWidget(card)


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class HealthCheckerApp(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        # Check admin
        if not is_admin():
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self,
                "Administrator Required",
                "This application requires administrator privileges.\n\n"
                "Would you like to restart as administrator?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                run_as_admin()
            else:
                sys.exit()
        
        # Initialize backends
        self.scanner = DriverScanner()
        self.health_checker = HealthChecker()
        self.disk_manager = DiskManager()
        
        self.setWindowTitle("Windows Health Checker Pro")
        self.setMinimumSize(1100, 720)
        self.resize(1280, 800)
        
        self.setup_ui()
        
        # Initial data load
        QTimer.singleShot(500, self.initial_load)
    
    def setup_ui(self):
        self.setStyleSheet(STYLESHEET)
        
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar)
        
        # Content area
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet(f"background: {Colors.WINDOW_BG};")
        
        # Create pages
        self.overview_page = OverviewPage()
        self.overview_page.run_all_clicked.connect(self.run_all_checks)
        self.overview_page.navigate_to.connect(self.navigate_to_module)
        self.content_stack.addWidget(self.overview_page)
        
        # Module pages
        self.pages = {"overview": self.overview_page}
        
        modules = [
            ("updates", "Windows Update", "📥"),
            ("storage", "Storage Health", "💾"),
            ("security", "Security Status", "🛡️"),
            ("hardware", "Hardware Health", "🔧"),
            ("system", "System Files", "📄"),
            ("events", "Event Analysis", "⚠️"),
        ]
        
        for module_id, title, icon in modules:
            page = ModulePage(title, icon)
            self.pages[module_id] = page
            self.content_stack.addWidget(page)
        
        main_layout.addWidget(self.content_stack, 1)
        
        # Status bar
        self.statusBar().setStyleSheet(f"""
            QStatusBar {{
                background: {Colors.SIDEBAR_BG};
                color: {Colors.TEXT_TERTIARY};
                border-top: 1px solid {Colors.BORDER};
                padding: 4px 16px;
            }}
        """)
        self.statusBar().showMessage("Ready")
    
    def create_sidebar(self):
        sidebar = QFrame()
        sidebar.setFixedWidth(Spacing.SIDEBAR_WIDTH)
        sidebar.setStyleSheet(f"background: {Colors.SIDEBAR_BG};")
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Logo/Header
        header = QFrame()
        header.setFixedHeight(64)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)
        
        logo = QLabel("🏥")
        logo.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(logo)
        
        title = QLabel("Health Checker")
        title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {Colors.TEXT_PRIMARY};")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        layout.addWidget(header)
        
        # Navigation items
        self.nav_items = {}
        nav_data = [
            ("overview", "📊", "Overview"),
            ("updates", "📥", "Updates"),
            ("storage", "💾", "Storage"),
            ("security", "🛡️", "Security"),
            ("hardware", "🔧", "Hardware"),
            ("system", "📄", "System"),
            ("events", "⚠️", "Events"),
        ]
        
        for nav_id, icon, label in nav_data:
            item = NavItem(icon, label)
            item.clicked.connect(lambda nid=nav_id: self.navigate_to_module(nid))
            self.nav_items[nav_id] = item
            layout.addWidget(item)
        
        # Select overview by default
        self.nav_items["overview"].set_selected(True)
        self.current_nav = "overview"
        
        layout.addStretch()
        
        # Settings button at bottom
        settings_btn = NavItem("⚙️", "Settings")
        layout.addWidget(settings_btn)
        
        return sidebar
    
    def navigate_to_module(self, module_id: str):
        if module_id in self.nav_items:
            # Update nav selection
            if self.current_nav in self.nav_items:
                self.nav_items[self.current_nav].set_selected(False)
            self.nav_items[module_id].set_selected(True)
            self.current_nav = module_id
            
            # Switch page
            if module_id in self.pages:
                self.content_stack.setCurrentWidget(self.pages[module_id])
    
    def initial_load(self):
        """Load initial data"""
        self.statusBar().showMessage("Loading system information...")
        
        # Update quick status cards with placeholder
        for card_id, card in self.overview_page.quick_cards.items():
            card.set_status("info", "Click to scan")
        
        self.overview_page.score_widget.set_score(0, 0, 0, 0)
        self.statusBar().showMessage("Ready - Click 'Run Full Scan' to begin")
    
    def run_all_checks(self):
        """Run all health checks"""
        # Prevent multiple scans from running
        if hasattr(self, 'scan_timer') and self.scan_timer.isActive():
            self.statusBar().showMessage("Scan already in progress")
            return
        
        dialog = ScanProgressModal(self)
        
        # Connect cancel/close handlers
        dialog.rejected.connect(self.cancel_scan)
        
        # Simulate progress (in real app, connect to actual scanners)
        self.current_progress = 0
        self.dialog = dialog
        
        # Start simulated scan
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.update_scan_progress)
        self.scan_timer.start(500)
        
        # Show as modal and wait
        result = dialog.exec()
        
        # Clean up if dialog was closed without completion
        if result == QDialog.DialogCode.Rejected:
            self.cancel_scan()
    
    def cancel_scan(self):
        """Cancel the ongoing scan"""
        # Stop the timer if it exists and is active
        if hasattr(self, 'scan_timer') and self.scan_timer is not None:
            if self.scan_timer.isActive():
                self.scan_timer.stop()
            self.scan_timer = None
        
        # Clear dialog reference
        if hasattr(self, 'dialog'):
            self.dialog = None
        
        # Reset progress
        self.current_progress = 0
        
        self.statusBar().showMessage("Scan cancelled")
    
    def update_scan_progress(self):
        """Update scan progress (simulation)"""
        # Safety check: ensure dialog still exists
        if not hasattr(self, 'dialog') or self.dialog is None:
            if hasattr(self, 'scan_timer') and self.scan_timer is not None:
                self.scan_timer.stop()
            return
        
        tasks = ["update", "defender", "sfc", "smart", "memory", "events", "services"]

        task_index = self.current_progress // 15

        if task_index > 0 and task_index <= len(tasks):
            self.dialog.update_task(tasks[task_index - 1], "complete")

        if task_index < len(tasks):
            self.dialog.update_task(tasks[task_index], "running", "Checking...")

        self.current_progress += 5
        self.dialog.set_progress(min(self.current_progress, 100),
                                  f"{max(0, (100 - self.current_progress) // 10)} seconds")

        if self.current_progress >= 100:
            self.scan_timer.stop()
            self.dialog.update_task(tasks[-1], "complete")

            # Update UI with results
            self.overview_page.score_widget.set_score(94, 12, 2, 0)

            cards = self.overview_page.quick_cards
            cards["updates"].set_status("healthy", "Up to date")
            cards["defender"].set_status("healthy", "Protected")
            cards["storage"].set_status("warning", "85% used")
            cards["drives"].set_status("healthy", "All drives OK")
            cards["memory"].set_status("healthy", "4.2 GB free")
            cards["system"].set_status("healthy", "No issues")

            self.statusBar().showMessage("Scan complete - 12 checks passed, 2 warnings")

            # Close dialog and clean up
            QTimer.singleShot(1000, lambda: self.complete_scan())
    
    def complete_scan(self):
        """Complete the scan and close the dialog"""
        if hasattr(self, 'dialog') and self.dialog is not None:
            self.dialog.accept()
            self.dialog = None
        
        if hasattr(self, 'scan_timer') and self.scan_timer is not None:
            if self.scan_timer.isActive():
                self.scan_timer.stop()
            self.scan_timer = None


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = HealthCheckerApp()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
