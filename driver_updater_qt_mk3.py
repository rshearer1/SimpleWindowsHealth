"""
Driver Update Scanner & Installer - PyQt6 UI MK3
Multi-scan architecture with process tree dashboard
"""

import sys
import uuid
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QTextEdit, QProgressBar, QMessageBox, QHeaderView, QFrame,
    QSplitter, QTreeWidget, QTreeWidgetItem, QGroupBox, QScrollArea,
    QStatusBar, QToolBar, QMenu, QStyle, QComboBox, QStackedWidget,
    QListWidget, QListWidgetItem, QDialog, QDialogButtonBox, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject
from PyQt6.QtGui import QFont, QColor, QPalette, QAction, QIcon

from driver_backend import (
    DriverScanner, OnlineDriverChecker, ManufacturerSupport,
    HealthChecker, DiskManager, DriverInfo,
    is_admin, run_as_admin, open_url
)


# Dracula Theme
DARK_STYLE = """
QMainWindow {
    background: #282a36;
}
QWidget {
    background: transparent;
    color: #f8f8f2;
    font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
    font-size: 10pt;
}
QTabWidget {
    background: #282a36;
}
QTabWidget::pane {
    border: none;
    background: #282a36;
    border-top: none;
    margin: 0px;
    padding: 0px;
}
QTabBar {
    background: #282a36;
    qproperty-drawBase: 0;
}
QTabBar::tab {
    background: #282a36;
    color: #6272a4;
    padding: 12px 24px;
    margin-right: 2px;
    border: none;
    border-bottom: 2px solid transparent;
    font-weight: 500;
    min-width: 80px;
}
QTabBar::tab:selected {
    background: #282a36;
    color: #ff79c6;
    border-bottom: 2px solid #ff79c6;
}
QTabBar::tab:hover:!selected {
    background: #44475a;
    color: #f8f8f2;
}
QPushButton {
    background: #44475a;
    color: #f8f8f2;
    border: 1px solid #6272a4;
    padding: 10px 20px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 10pt;
}
QPushButton:hover {
    background: #6272a4;
    border-color: #bd93f9;
}
QPushButton:pressed {
    background: #3d3f50;
}
QPushButton:disabled {
    background: #21222c;
    color: #44475a;
    border-color: #44475a;
}
QPushButton#dangerButton {
    background: #44475a;
    border-color: #ff5555;
    color: #ff5555;
}
QPushButton#dangerButton:hover {
    background: #ff5555;
    color: #282a36;
}
QPushButton#successButton {
    background: #44475a;
    border-color: #50fa7b;
    color: #50fa7b;
}
QPushButton#successButton:hover {
    background: #50fa7b;
    color: #282a36;
}
QPushButton#secondaryButton {
    background: #21222c;
    border: 1px solid #44475a;
    color: #f8f8f2;
}
QPushButton#secondaryButton:hover {
    background: #44475a;
    border-color: #6272a4;
}
QPushButton#accentButton {
    background: #bd93f9;
    color: #282a36;
    border: none;
    font-weight: bold;
}
QPushButton#accentButton:hover {
    background: #caa4ff;
}
QTableWidget {
    background-color: #21222c;
    alternate-background-color: #282a36;
    gridline-color: transparent;
    border: 1px solid #44475a;
    border-radius: 8px;
    selection-background-color: #44475a;
}
QTableWidget::item {
    padding: 8px;
    border: none;
}
QTableWidget::item:selected {
    background-color: #44475a;
    color: #f8f8f2;
}
QTableWidget::item:hover {
    background-color: #2d2f3d;
}
QHeaderView {
    background: #21222c;
}
QHeaderView::section {
    background: #21222c;
    color: #bd93f9;
    padding: 12px 10px;
    border: none;
    border-right: 1px solid #44475a;
    border-bottom: 1px solid #44475a;
    font-weight: 600;
    font-size: 10pt;
}
QHeaderView::section:last {
    border-right: none;
}
QTreeWidget {
    background-color: #21222c;
    alternate-background-color: #282a36;
    border: 1px solid #44475a;
    border-radius: 8px;
    outline: none;
}
QTreeWidget::item {
    padding: 8px 4px;
    border: none;
}
QTreeWidget::item:selected {
    background-color: #44475a;
    color: #f8f8f2;
}
QTreeWidget::item:hover {
    background-color: #2d2f3d;
}
QTreeWidget::branch {
    background: transparent;
}
QTextEdit {
    background-color: #21222c;
    border: 1px solid #44475a;
    border-radius: 8px;
    padding: 10px;
    selection-background-color: #44475a;
    font-family: 'Cascadia Code', 'Consolas', monospace;
    color: #f8f8f2;
}
QScrollBar:vertical {
    background: #21222c;
    width: 14px;
    border-radius: 7px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #44475a;
    border-radius: 6px;
    min-height: 30px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #6272a4;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background: #21222c;
    height: 14px;
    border-radius: 7px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: #44475a;
    border-radius: 6px;
    min-width: 30px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background: #6272a4;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
QProgressBar {
    background: #21222c;
    border: 1px solid #44475a;
    border-radius: 6px;
    height: 10px;
    text-align: center;
    color: #f8f8f2;
}
QProgressBar::chunk {
    background: #bd93f9;
    border-radius: 5px;
}
QGroupBox {
    background: #21222c;
    border: 1px solid #44475a;
    border-radius: 8px;
    margin-top: 16px;
    padding: 16px 12px 12px 12px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    top: 4px;
    padding: 2px 10px;
    background: #bd93f9;
    color: #282a36;
    border-radius: 4px;
}
QStatusBar {
    background: #21222c;
    color: #6272a4;
    border-top: 1px solid #44475a;
    padding: 4px;
}
QListWidget {
    background: #21222c;
    border: 1px solid #44475a;
    border-radius: 8px;
    outline: none;
}
QListWidget::item {
    padding: 12px;
    border-bottom: 1px solid #44475a;
}
QListWidget::item:selected {
    background: #44475a;
}
QListWidget::item:hover {
    background: #2d2f3d;
}
QComboBox {
    background: #21222c;
    border: 1px solid #44475a;
    border-radius: 6px;
    padding: 8px 12px;
    color: #f8f8f2;
    min-width: 100px;
}
QComboBox:hover {
    border: 1px solid #bd93f9;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background: #21222c;
    border: 1px solid #44475a;
    border-radius: 6px;
    selection-background-color: #44475a;
}
QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid #6272a4;
    background: #21222c;
}
QCheckBox::indicator:checked {
    background: #bd93f9;
    border-color: #bd93f9;
}
QCheckBox::indicator:hover {
    border-color: #bd93f9;
}
QDialog {
    background: #282a36;
}
QToolTip {
    background: #21222c;
    color: #f8f8f2;
    border: 1px solid #44475a;
    border-radius: 4px;
    padding: 6px;
    font-size: 9pt;
}
QMessageBox {
    background: #282a36;
}
QMessageBox QLabel {
    color: #f8f8f2;
}
"""


class ScanType(Enum):
    """Types of scans available"""
    DRIVERS = "Installed Drivers"
    WINDOWS_UPDATE = "Windows Update"
    ONLINE_SOURCES = "Online Sources"
    PROBLEMS = "Problem Devices"
    CLEANUP = "Driver Cleanup"
    HEALTH = "System Health"
    DISK = "Disk Analysis"
    FULL = "Full System Scan"


class ScanStatus(Enum):
    """Status of a scan"""
    PENDING = "Pending"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


@dataclass
class ScanTask:
    """Represents a scan task"""
    id: str
    scan_type: ScanType
    status: ScanStatus = ScanStatus.PENDING
    progress: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    result: Optional[object] = None
    error: Optional[str] = None
    log_messages: List[str] = field(default_factory=list)
    
    @property
    def duration(self) -> str:
        if not self.start_time:
            return "--:--"
        end = self.end_time or datetime.now()
        delta = end - self.start_time
        minutes, seconds = divmod(int(delta.total_seconds()), 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    @property
    def status_icon(self) -> str:
        icons = {
            ScanStatus.PENDING: "⏳",
            ScanStatus.RUNNING: "🔄",
            ScanStatus.COMPLETED: "✅",
            ScanStatus.FAILED: "❌",
            ScanStatus.CANCELLED: "⏹️"
        }
        return icons.get(self.status, "❓")


class ScanWorker(QThread):
    """Worker thread for running scans"""
    progress_updated = pyqtSignal(str, int)  # task_id, progress
    status_changed = pyqtSignal(str, str)  # task_id, status
    log_message = pyqtSignal(str, str)  # task_id, message
    scan_completed = pyqtSignal(str, object)  # task_id, result
    scan_failed = pyqtSignal(str, str)  # task_id, error
    
    def __init__(self, task: ScanTask, scanner: DriverScanner, 
                 online_checker: OnlineDriverChecker,
                 health_checker: HealthChecker,
                 disk_manager: DiskManager):
        super().__init__()
        self.task = task
        self.scanner = scanner
        self.online_checker = online_checker
        self.health_checker = health_checker
        self.disk_manager = disk_manager
        self._cancelled = False
    
    def cancel(self):
        self._cancelled = True
    
    def log(self, message: str):
        self.log_message.emit(self.task.id, message)
    
    def update_progress(self, progress: int):
        self.progress_updated.emit(self.task.id, progress)
    
    def run(self):
        try:
            self.status_changed.emit(self.task.id, ScanStatus.RUNNING.value)
            result = None
            
            if self.task.scan_type == ScanType.DRIVERS:
                result = self._scan_drivers()
            elif self.task.scan_type == ScanType.WINDOWS_UPDATE:
                result = self._scan_windows_update()
            elif self.task.scan_type == ScanType.ONLINE_SOURCES:
                result = self._scan_online()
            elif self.task.scan_type == ScanType.PROBLEMS:
                result = self._scan_problems()
            elif self.task.scan_type == ScanType.CLEANUP:
                result = self._scan_cleanup()
            elif self.task.scan_type == ScanType.HEALTH:
                result = self._scan_health()
            elif self.task.scan_type == ScanType.DISK:
                result = self._scan_disk()
            elif self.task.scan_type == ScanType.FULL:
                result = self._full_scan()
            
            if self._cancelled:
                self.status_changed.emit(self.task.id, ScanStatus.CANCELLED.value)
            else:
                self.scan_completed.emit(self.task.id, result)
                
        except Exception as e:
            self.scan_failed.emit(self.task.id, str(e))
    
    def _scan_drivers(self):
        self.log("Starting driver scan...")
        self.update_progress(10)
        drivers = self.scanner.scan_installed_drivers()
        self.update_progress(100)
        self.log(f"Found {len(drivers)} installed drivers")
        return {"type": "drivers", "data": drivers}
    
    def _scan_windows_update(self):
        self.log("Checking Windows Update for drivers...")
        self.update_progress(10)
        updates = self.scanner.check_windows_update_drivers()
        self.update_progress(100)
        self.log(f"Found {len(updates)} driver updates")
        return {"type": "updates", "data": updates}
    
    def _scan_online(self):
        self.log("Scanning online driver sources...")
        self.update_progress(10)
        drivers = self.scanner.scan_installed_drivers()
        self.update_progress(30)
        
        results = []
        total = len(drivers)
        for i, driver in enumerate(drivers):
            if self._cancelled:
                break
            online_info = self.online_checker.check_driver(driver)
            if online_info:
                results.append({
                    "device_name": driver.device_name,
                    "current_version": driver.version,
                    "online_info": online_info
                })
            progress = 30 + int((i / total) * 70)
            self.update_progress(progress)
        
        self.log(f"Found {len(results)} drivers with online sources")
        return {"type": "online", "data": results}
    
    def _scan_problems(self):
        self.log("Scanning for problem devices...")
        self.update_progress(10)
        problems = self.scanner.scan_problem_devices()
        self.update_progress(100)
        self.log(f"Found {len(problems)} problem devices")
        return {"type": "problems", "data": problems}
    
    def _scan_cleanup(self):
        self.log("Finding unused drivers...")
        self.update_progress(10)
        unused = self.scanner.find_unused_drivers()
        self.update_progress(100)
        self.log(f"Found {len(unused)} potentially removable drivers")
        return {"type": "cleanup", "data": unused}
    
    def _scan_health(self):
        self.log("Running system health checks...")
        self.update_progress(10)
        health = self.health_checker.run_all_checks()
        self.update_progress(100)
        self.log("Health check complete")
        return {"type": "health", "data": health}
    
    def _scan_disk(self):
        self.log("Analyzing disk volumes...")
        self.update_progress(10)
        volumes = self.disk_manager.get_volumes()
        self.update_progress(100)
        self.log(f"Found {len(volumes)} volumes")
        return {"type": "disk", "data": volumes}
    
    def _full_scan(self):
        self.log("Starting full system scan...")
        results = {}
        
        # Drivers (0-15%)
        self.log("Phase 1/6: Scanning drivers...")
        self.update_progress(5)
        results["drivers"] = self.scanner.scan_installed_drivers()
        self.update_progress(15)
        
        if self._cancelled:
            return results
        
        # Windows Update (15-30%)
        self.log("Phase 2/6: Checking Windows Update...")
        results["updates"] = self.scanner.check_windows_update_drivers()
        self.update_progress(30)
        
        if self._cancelled:
            return results
        
        # Problems (30-45%)
        self.log("Phase 3/6: Scanning for problems...")
        results["problems"] = self.scanner.scan_problem_devices()
        self.update_progress(45)
        
        if self._cancelled:
            return results
        
        # Cleanup (45-60%)
        self.log("Phase 4/6: Finding unused drivers...")
        results["cleanup"] = self.scanner.find_unused_drivers()
        self.update_progress(60)
        
        if self._cancelled:
            return results
        
        # Health (60-80%)
        self.log("Phase 5/6: Running health checks...")
        results["health"] = self.health_checker.run_all_checks()
        self.update_progress(80)
        
        if self._cancelled:
            return results
        
        # Disk (80-100%)
        self.log("Phase 6/6: Analyzing disks...")
        results["disk"] = self.disk_manager.get_volumes()
        self.update_progress(100)
        
        self.log("Full system scan complete!")
        return {"type": "full", "data": results}


class ScanManager(QObject):
    """Manages multiple concurrent scans"""
    task_added = pyqtSignal(str)  # task_id
    task_updated = pyqtSignal(str)  # task_id
    task_completed = pyqtSignal(str)  # task_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tasks: Dict[str, ScanTask] = {}
        self.workers: Dict[str, ScanWorker] = {}
        
        # Backend services
        self.scanner = DriverScanner()
        self.online_checker = OnlineDriverChecker()
        self.health_checker = HealthChecker()
        self.disk_manager = DiskManager()
    
    def create_scan(self, scan_type: ScanType) -> str:
        """Create a new scan task"""
        task_id = str(uuid.uuid4())[:8]
        task = ScanTask(id=task_id, scan_type=scan_type)
        self.tasks[task_id] = task
        self.task_added.emit(task_id)
        return task_id
    
    def start_scan(self, task_id: str):
        """Start a scan task"""
        task = self.tasks.get(task_id)
        if not task:
            return
        
        task.status = ScanStatus.RUNNING
        task.start_time = datetime.now()
        
        worker = ScanWorker(
            task, self.scanner, self.online_checker,
            self.health_checker, self.disk_manager
        )
        
        worker.progress_updated.connect(self._on_progress)
        worker.status_changed.connect(self._on_status_changed)
        worker.log_message.connect(self._on_log)
        worker.scan_completed.connect(self._on_completed)
        worker.scan_failed.connect(self._on_failed)
        
        self.workers[task_id] = worker
        worker.start()
        self.task_updated.emit(task_id)
    
    def cancel_scan(self, task_id: str):
        """Cancel a running scan"""
        worker = self.workers.get(task_id)
        if worker and worker.isRunning():
            worker.cancel()
    
    def get_task(self, task_id: str) -> Optional[ScanTask]:
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[ScanTask]:
        return list(self.tasks.values())
    
    def get_running_count(self) -> int:
        return sum(1 for t in self.tasks.values() if t.status == ScanStatus.RUNNING)
    
    def _on_progress(self, task_id: str, progress: int):
        task = self.tasks.get(task_id)
        if task:
            task.progress = progress
            self.task_updated.emit(task_id)
    
    def _on_status_changed(self, task_id: str, status: str):
        task = self.tasks.get(task_id)
        if task:
            task.status = ScanStatus(status)
            self.task_updated.emit(task_id)
    
    def _on_log(self, task_id: str, message: str):
        task = self.tasks.get(task_id)
        if task:
            timestamp = datetime.now().strftime("%H:%M:%S")
            task.log_messages.append(f"[{timestamp}] {message}")
            self.task_updated.emit(task_id)
    
    def _on_completed(self, task_id: str, result: object):
        task = self.tasks.get(task_id)
        if task:
            task.status = ScanStatus.COMPLETED
            task.end_time = datetime.now()
            task.progress = 100
            task.result = result
            self.task_completed.emit(task_id)
    
    def _on_failed(self, task_id: str, error: str):
        task = self.tasks.get(task_id)
        if task:
            task.status = ScanStatus.FAILED
            task.end_time = datetime.now()
            task.error = error
            self.task_updated.emit(task_id)


class NewScanDialog(QDialog):
    """Dialog for creating a new scan - modal popup"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Scan")
        self.setModal(True)
        self.setFixedSize(420, 520)
        # Set window flags to make it a proper popup dialog
        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Select Scan Type")
        title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #bd93f9;")
        layout.addWidget(title)
        
        # Scroll area for scan types
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(8)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        
        # Scan type checkboxes
        self.checkboxes = {}
        scan_types = [
            (ScanType.FULL, "🔍 Full System Scan", "Complete scan of all components"),
            (ScanType.DRIVERS, "💿 Installed Drivers", "Scan all installed drivers"),
            (ScanType.WINDOWS_UPDATE, "📥 Windows Update", "Check for driver updates"),
            (ScanType.ONLINE_SOURCES, "🌐 Online Sources", "Check manufacturer websites"),
            (ScanType.PROBLEMS, "⚠️ Problem Devices", "Find devices with issues"),
            (ScanType.CLEANUP, "🧹 Driver Cleanup", "Find unused drivers"),
            (ScanType.HEALTH, "🏥 System Health", "Run health diagnostics"),
            (ScanType.DISK, "💾 Disk Analysis", "Analyze disk volumes"),
        ]
        
        for scan_type, label, description in scan_types:
            frame = QFrame()
            frame.setStyleSheet("""
                QFrame {
                    background: #21222c;
                    border: 1px solid #44475a;
                    border-radius: 6px;
                    padding: 6px;
                }
                QFrame:hover {
                    border-color: #bd93f9;
                }
            """)
            frame_layout = QHBoxLayout(frame)
            frame_layout.setContentsMargins(8, 6, 8, 6)
            
            cb = QCheckBox()
            cb.setStyleSheet("QCheckBox { background: transparent; }")
            self.checkboxes[scan_type] = cb
            frame_layout.addWidget(cb)
            
            text_layout = QVBoxLayout()
            text_layout.setSpacing(1)
            
            label_widget = QLabel(label)
            label_widget.setStyleSheet("font-weight: 600; font-size: 10pt; background: transparent;")
            text_layout.addWidget(label_widget)
            
            desc_widget = QLabel(description)
            desc_widget.setStyleSheet("color: #6272a4; font-size: 8pt; background: transparent;")
            text_layout.addWidget(desc_widget)
            
            frame_layout.addLayout(text_layout)
            frame_layout.addStretch()
            
            scroll_layout.addWidget(frame)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Buttons at bottom
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        start_btn = QPushButton("▶ Start Scan")
        start_btn.setStyleSheet("""
            QPushButton {
                background: #bd93f9;
                color: #282a36;
                border: none;
                padding: 10px 24px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #caa4ff;
            }
        """)
        start_btn.clicked.connect(self.accept)
        button_layout.addWidget(start_btn)
        
        layout.addLayout(button_layout)
    
    def get_selected_types(self) -> List[ScanType]:
        return [st for st, cb in self.checkboxes.items() if cb.isChecked()]


class ProcessTreeWidget(QWidget):
    """Widget showing the process tree of running scans"""
    
    scan_selected = pyqtSignal(str)  # task_id
    
    def __init__(self, scan_manager: ScanManager, parent=None):
        super().__init__(parent)
        self.scan_manager = scan_manager
        self.setup_ui()
        
        # Connect signals
        scan_manager.task_added.connect(self.add_task)
        scan_manager.task_updated.connect(self.update_task)
        scan_manager.task_completed.connect(self.update_task)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header = QFrame()
        header.setStyleSheet("background: #21222c; border-radius: 8px;")
        header_layout = QHBoxLayout(header)
        
        title = QLabel("🔄 Active Scans")
        title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #bd93f9;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        self.running_label = QLabel("0 running")
        self.running_label.setStyleSheet("color: #6272a4;")
        header_layout.addWidget(self.running_label)
        
        layout.addWidget(header)
        
        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Task", "Type", "Status", "Progress", "Duration"])
        self.tree.setColumnCount(5)
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        
        header_view = self.tree.header()
        if header_view:
            header_view.setStretchLastSection(False)
            header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
            header_view.resizeSection(3, 150)
            header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)
        
        self.task_items: Dict[str, QTreeWidgetItem] = {}
    
    def add_task(self, task_id: str):
        task = self.scan_manager.get_task(task_id)
        if not task:
            return
        
        item = QTreeWidgetItem()
        item.setData(0, Qt.ItemDataRole.UserRole, task_id)
        self._update_item(item, task)
        
        self.tree.addTopLevelItem(item)
        self.task_items[task_id] = item
        self._update_running_count()
    
    def update_task(self, task_id: str):
        task = self.scan_manager.get_task(task_id)
        item = self.task_items.get(task_id)
        if not task or not item:
            return
        
        self._update_item(item, task)
        self._update_running_count()
    
    def _update_item(self, item: QTreeWidgetItem, task: ScanTask):
        item.setText(0, f"{task.status_icon} {task.id}")
        item.setText(1, task.scan_type.value)
        item.setText(2, task.status.value)
        item.setText(4, task.duration)
        
        # Progress bar widget
        progress_widget = QProgressBar()
        progress_widget.setMaximum(100)
        progress_widget.setValue(task.progress)
        progress_widget.setTextVisible(True)
        progress_widget.setFormat(f"{task.progress}%")
        progress_widget.setStyleSheet("""
            QProgressBar {
                background: #21222c;
                border: 1px solid #44475a;
                border-radius: 4px;
                height: 16px;
            }
            QProgressBar::chunk {
                background: #bd93f9;
                border-radius: 3px;
            }
        """)
        self.tree.setItemWidget(item, 3, progress_widget)
        
        # Color based on status
        status_colors = {
            ScanStatus.PENDING: "#6272a4",
            ScanStatus.RUNNING: "#8be9fd",
            ScanStatus.COMPLETED: "#50fa7b",
            ScanStatus.FAILED: "#ff5555",
            ScanStatus.CANCELLED: "#ffb86c"
        }
        color = QColor(status_colors.get(task.status, "#f8f8f2"))
        item.setForeground(2, color)
    
    def _update_running_count(self):
        count = self.scan_manager.get_running_count()
        self.running_label.setText(f"{count} running")
        if count > 0:
            self.running_label.setStyleSheet("color: #50fa7b; font-weight: bold;")
        else:
            self.running_label.setStyleSheet("color: #6272a4;")
    
    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        task_id = item.data(0, Qt.ItemDataRole.UserRole)
        if task_id:
            self.scan_selected.emit(task_id)


class ScanDetailWidget(QWidget):
    """Widget showing details of a selected scan"""
    
    def __init__(self, scan_manager: ScanManager, parent=None):
        super().__init__(parent)
        self.scan_manager = scan_manager
        self.current_task_id = None
        self.setup_ui()
        
        scan_manager.task_updated.connect(self._on_task_updated)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        self.header = QFrame()
        self.header.setStyleSheet("background: #21222c; border-radius: 8px; padding: 12px;")
        header_layout = QVBoxLayout(self.header)
        
        self.title_label = QLabel("Select a scan to view details")
        self.title_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        header_layout.addWidget(self.title_label)
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #6272a4;")
        header_layout.addWidget(self.status_label)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        self.cancel_btn = QPushButton("⏹️ Cancel")
        self.cancel_btn.setObjectName("dangerButton")
        self.cancel_btn.clicked.connect(self._cancel_scan)
        self.cancel_btn.setEnabled(False)
        btn_layout.addWidget(self.cancel_btn)
        
        self.view_results_btn = QPushButton("📊 View Results")
        self.view_results_btn.setObjectName("successButton")
        self.view_results_btn.clicked.connect(self._view_results)
        self.view_results_btn.setEnabled(False)
        btn_layout.addWidget(self.view_results_btn)
        
        btn_layout.addStretch()
        header_layout.addLayout(btn_layout)
        
        layout.addWidget(self.header)
        
        # Log output
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Cascadia Code", 10))
        self.log_output.setStyleSheet("""
            QTextEdit {
                background: #21222c;
                border: 1px solid #44475a;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        layout.addWidget(self.log_output)
    
    def show_task(self, task_id: str):
        self.current_task_id = task_id
        self._update_display()
    
    def _update_display(self):
        if not self.current_task_id:
            return
        
        task = self.scan_manager.get_task(self.current_task_id)
        if not task:
            return
        
        self.title_label.setText(f"{task.status_icon} {task.scan_type.value}")
        self.status_label.setText(
            f"Status: {task.status.value} | Duration: {task.duration} | Progress: {task.progress}%"
        )
        
        # Update buttons
        self.cancel_btn.setEnabled(task.status == ScanStatus.RUNNING)
        self.view_results_btn.setEnabled(task.status == ScanStatus.COMPLETED)
        
        # Update log
        self.log_output.clear()
        for msg in task.log_messages:
            self.log_output.append(msg)
        
        if task.error:
            self.log_output.append(f"\n❌ Error: {task.error}")
    
    def _on_task_updated(self, task_id: str):
        if task_id == self.current_task_id:
            self._update_display()
    
    def _cancel_scan(self):
        if self.current_task_id:
            self.scan_manager.cancel_scan(self.current_task_id)
    
    def _view_results(self):
        if self.current_task_id:
            task = self.scan_manager.get_task(self.current_task_id)
            if task and task.result:
                # Emit signal or show results dialog
                QMessageBox.information(
                    self, "Scan Results",
                    f"Scan completed successfully!\n\nType: {task.scan_type.value}\n"
                    f"Duration: {task.duration}\n\nResults are available in the main view."
                )


class DashboardWidget(QWidget):
    """Main dashboard with process tree and quick actions"""
    
    def __init__(self, scan_manager: ScanManager, parent=None):
        super().__init__(parent)
        self.scan_manager = scan_manager
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Header with quick actions
        header = QFrame()
        header.setStyleSheet("background: #21222c; border-radius: 12px; padding: 20px;")
        header_layout = QVBoxLayout(header)
        
        # Title row
        title_row = QHBoxLayout()
        
        # Logo and title
        logo = QLabel("🔧")
        logo.setStyleSheet("font-size: 36pt;")
        title_row.addWidget(logo)
        
        title_text = QVBoxLayout()
        title = QLabel("Driver Updater Pro MK3")
        title.setStyleSheet("font-size: 24pt; font-weight: bold; color: #f8f8f2;")
        title_text.addWidget(title)
        
        subtitle = QLabel("Multi-Scan Dashboard")
        subtitle.setStyleSheet("font-size: 12pt; color: #6272a4;")
        title_text.addWidget(subtitle)
        title_row.addLayout(title_text)
        
        title_row.addStretch()
        
        # New scan button
        new_scan_btn = QPushButton("➕ New Scan")
        new_scan_btn.setObjectName("accentButton")
        new_scan_btn.setStyleSheet("""
            QPushButton {
                background: #bd93f9;
                color: #282a36;
                border: none;
                padding: 16px 32px;
                border-radius: 8px;
                font-size: 12pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #caa4ff;
            }
        """)
        new_scan_btn.clicked.connect(self._new_scan)
        title_row.addWidget(new_scan_btn)
        
        header_layout.addLayout(title_row)
        
        # Quick scan buttons
        header_layout.addSpacing(16)
        quick_label = QLabel("Quick Scans:")
        quick_label.setStyleSheet("color: #6272a4; font-weight: 600;")
        header_layout.addWidget(quick_label)
        
        quick_btns = QHBoxLayout()
        quick_btns.setSpacing(8)
        
        quick_scans = [
            ("🔍 Full Scan", ScanType.FULL),
            ("💿 Drivers", ScanType.DRIVERS),
            ("📥 Updates", ScanType.WINDOWS_UPDATE),
            ("⚠️ Problems", ScanType.PROBLEMS),
            ("🏥 Health", ScanType.HEALTH),
        ]
        
        for label, scan_type in quick_scans:
            btn = QPushButton(label)
            btn.setObjectName("secondaryButton")
            btn.clicked.connect(lambda checked, st=scan_type: self._quick_scan(st))
            quick_btns.addWidget(btn)
        
        quick_btns.addStretch()
        header_layout.addLayout(quick_btns)
        
        layout.addWidget(header)
        
        # Main content splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Process tree (left)
        self.process_tree = ProcessTreeWidget(self.scan_manager)
        self.process_tree.setMinimumWidth(400)
        splitter.addWidget(self.process_tree)
        
        # Scan details (right)
        self.scan_detail = ScanDetailWidget(self.scan_manager)
        splitter.addWidget(self.scan_detail)
        
        # Connect selection
        self.process_tree.scan_selected.connect(self.scan_detail.show_task)
        
        splitter.setSizes([500, 500])
        layout.addWidget(splitter)
    
    def _new_scan(self):
        dialog = NewScanDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected = dialog.get_selected_types()
            for scan_type in selected:
                task_id = self.scan_manager.create_scan(scan_type)
                self.scan_manager.start_scan(task_id)
    
    def _quick_scan(self, scan_type: ScanType):
        task_id = self.scan_manager.create_scan(scan_type)
        self.scan_manager.start_scan(task_id)


class ResultsWidget(QWidget):
    """Widget showing aggregated results from all scans"""
    
    def __init__(self, scan_manager: ScanManager, parent=None):
        super().__init__(parent)
        self.scan_manager = scan_manager
        self.setup_ui()
        
        scan_manager.task_completed.connect(self._on_scan_completed)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Tabs for different result types
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        
        # Drivers tab
        self.drivers_table = self._create_table(
            ["Device Name", "Manufacturer", "Version", "Date", "Status", "INF"]
        )
        self.tabs.addTab(self.drivers_table, "💿 Drivers")
        
        # Updates tab
        self.updates_table = self._create_table(
            ["Device Name", "Current Version", "Available Version", "Source"]
        )
        self.tabs.addTab(self.updates_table, "📥 Updates")
        
        # Problems tab
        self.problems_table = self._create_table(
            ["Device Name", "Status", "Error Code", "Device ID"]
        )
        self.tabs.addTab(self.problems_table, "⚠️ Problems")
        
        # Cleanup tab
        self.cleanup_tree = QTreeWidget()
        self.cleanup_tree.setHeaderLabels(["Driver", "Category", "Provider", "Version", "Risk", "Reason"])
        self.cleanup_tree.setAlternatingRowColors(True)
        self.tabs.addTab(self.cleanup_tree, "🧹 Cleanup")
        
        # Health tab
        self.health_output = QTextEdit()
        self.health_output.setReadOnly(True)
        self.health_output.setFont(QFont("Cascadia Code", 10))
        self.tabs.addTab(self.health_output, "🏥 Health")
        
        # Disk tab
        self.disk_table = self._create_table(
            ["Drive", "Label", "File System", "Size (GB)", "Free (GB)", "Health"]
        )
        self.tabs.addTab(self.disk_table, "💾 Disks")
        
        layout.addWidget(self.tabs)
    
    def _create_table(self, headers: List[str]) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        
        header = table.horizontalHeader()
        if header and len(headers) > 0:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        
        return table
    
    def _on_scan_completed(self, task_id: str):
        task = self.scan_manager.get_task(task_id)
        if not task or not task.result:
            return
        
        result_type = task.result.get("type")
        data = task.result.get("data")
        
        if result_type == "drivers":
            self._populate_drivers(data)
        elif result_type == "updates":
            self._populate_updates(data)
        elif result_type == "problems":
            self._populate_problems(data)
        elif result_type == "cleanup":
            self._populate_cleanup(data)
        elif result_type == "health":
            self._populate_health(data)
        elif result_type == "disk":
            self._populate_disk(data)
        elif result_type == "full":
            # Full scan contains all types
            if "drivers" in data:
                self._populate_drivers(data["drivers"])
            if "updates" in data:
                self._populate_updates(data["updates"])
            if "problems" in data:
                self._populate_problems(data["problems"])
            if "cleanup" in data:
                self._populate_cleanup(data["cleanup"])
            if "health" in data:
                self._populate_health(data["health"])
            if "disk" in data:
                self._populate_disk(data["disk"])
    
    def _populate_drivers(self, drivers: List):
        self.drivers_table.setRowCount(0)
        for driver in drivers:
            row = self.drivers_table.rowCount()
            self.drivers_table.insertRow(row)
            
            self.drivers_table.setItem(row, 0, QTableWidgetItem(driver.device_name))
            self.drivers_table.setItem(row, 1, QTableWidgetItem(driver.manufacturer))
            self.drivers_table.setItem(row, 2, QTableWidgetItem(driver.version))
            self.drivers_table.setItem(row, 3, QTableWidgetItem(driver.date))
            
            status_item = QTableWidgetItem(driver.status)
            if driver.status == "OK":
                status_item.setForeground(QColor("#50fa7b"))
            else:
                status_item.setForeground(QColor("#ffb86c"))
            self.drivers_table.setItem(row, 4, status_item)
            
            self.drivers_table.setItem(row, 5, QTableWidgetItem(driver.inf_name))
    
    def _populate_updates(self, updates: List):
        self.updates_table.setRowCount(0)
        for update in updates:
            row = self.updates_table.rowCount()
            self.updates_table.insertRow(row)
            
            self.updates_table.setItem(row, 0, QTableWidgetItem(update.get('Title', '')))
            self.updates_table.setItem(row, 1, QTableWidgetItem(update.get('DriverVersion', '')))
            self.updates_table.setItem(row, 2, QTableWidgetItem(update.get('DriverVersion', '')))
            self.updates_table.setItem(row, 3, QTableWidgetItem("Windows Update"))
    
    def _populate_problems(self, problems: List):
        self.problems_table.setRowCount(0)
        for problem in problems:
            row = self.problems_table.rowCount()
            self.problems_table.insertRow(row)
            
            self.problems_table.setItem(row, 0, QTableWidgetItem(problem.get('name', '')))
            self.problems_table.setItem(row, 1, QTableWidgetItem(problem.get('status', '')))
            self.problems_table.setItem(row, 2, QTableWidgetItem(str(problem.get('error_code', ''))))
            self.problems_table.setItem(row, 3, QTableWidgetItem(problem.get('device_id', '')))
    
    def _populate_cleanup(self, drivers: List):
        self.cleanup_tree.clear()
        
        categories = {}
        for driver in drivers:
            cat = driver.get('category', 'Other')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(driver)
        
        for category, cat_drivers in categories.items():
            cat_item = QTreeWidgetItem([f"{category} ({len(cat_drivers)})", "", "", "", "", ""])
            cat_item.setExpanded(True)
            
            for driver in cat_drivers:
                item = QTreeWidgetItem([
                    driver['driver'],
                    driver['category'],
                    driver['provider'],
                    driver['version'],
                    driver['risk'].upper(),
                    driver['reason']
                ])
                
                if driver['risk'] == 'caution':
                    item.setForeground(4, QColor("#ffb86c"))
                elif driver['risk'] == 'safe':
                    item.setForeground(4, QColor("#50fa7b"))
                
                cat_item.addChild(item)
            
            self.cleanup_tree.addTopLevelItem(cat_item)
    
    def _populate_health(self, health: dict):
        self.health_output.clear()
        
        # Defender
        defender = health.get('defender', {})
        self.health_output.append("=== Windows Defender ===")
        if 'Error' in defender:
            self.health_output.append(f"Error: {defender['Error']}")
        else:
            rtp = "Enabled" if defender.get('RealTimeProtection') else "Disabled"
            self.health_output.append(f"Real-time Protection: {rtp}")
            self.health_output.append(f"Signature Age: {defender.get('SignatureAge', 'N/A')} days")
        
        # Updates
        updates = health.get('updates', {})
        self.health_output.append("\n=== Windows Update ===")
        self.health_output.append(f"Pending Updates: {updates.get('PendingUpdates', 'N/A')}")
        
        # Disks
        disks = health.get('disks', [])
        self.health_output.append("\n=== Disk Health ===")
        for disk in disks:
            self.health_output.append(f"{disk.get('Model', 'Unknown')}: {disk.get('Status', 'Unknown')}")
    
    def _populate_disk(self, volumes: List):
        self.disk_table.setRowCount(0)
        for vol in volumes:
            row = self.disk_table.rowCount()
            self.disk_table.insertRow(row)
            
            self.disk_table.setItem(row, 0, QTableWidgetItem(vol.get('DriveLetter', '')))
            self.disk_table.setItem(row, 1, QTableWidgetItem(vol.get('FileSystemLabel', '')))
            self.disk_table.setItem(row, 2, QTableWidgetItem(vol.get('FileSystem', '')))
            self.disk_table.setItem(row, 3, QTableWidgetItem(str(vol.get('SizeGB', 0))))
            self.disk_table.setItem(row, 4, QTableWidgetItem(str(vol.get('FreeSpaceGB', 0))))
            
            health = vol.get('HealthStatus', 'Unknown')
            health_item = QTableWidgetItem(health)
            if health == 'Healthy':
                health_item.setForeground(QColor("#50fa7b"))
            else:
                health_item.setForeground(QColor("#ffb86c"))
            self.disk_table.setItem(row, 5, health_item)


class DriverUpdaterMK3(QMainWindow):
    """Main application window - MK3 with multi-scan support"""
    
    def __init__(self):
        super().__init__()
        
        # Check admin privileges
        if not is_admin():
            reply = QMessageBox.question(
                self,
                "Administrator Required",
                "This application requires administrator privileges to manage drivers.\n\n"
                "Would you like to restart as administrator?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                run_as_admin()
            else:
                sys.exit()
        
        # Initialize scan manager
        self.scan_manager = ScanManager(self)
        
        # Setup UI
        self.setWindowTitle("Driver Updater Pro MK3")
        self.setMinimumSize(1400, 900)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the main UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Main tabs
        self.main_tabs = QTabWidget()
        self.main_tabs.setDocumentMode(True)
        
        # Dashboard tab
        self.dashboard = DashboardWidget(self.scan_manager)
        self.main_tabs.addTab(self.dashboard, "🏠 Dashboard")
        
        # Results tab
        self.results = ResultsWidget(self.scan_manager)
        self.main_tabs.addTab(self.results, "📊 Results")
        
        layout.addWidget(self.main_tabs)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)
        
        # Update status on scan changes
        self.scan_manager.task_added.connect(self._update_status)
        self.scan_manager.task_updated.connect(self._update_status)
        self.scan_manager.task_completed.connect(self._update_status)
    
    def _update_status(self, task_id: str = None):
        running = self.scan_manager.get_running_count()
        total = len(self.scan_manager.tasks)
        completed = sum(1 for t in self.scan_manager.tasks.values() 
                       if t.status == ScanStatus.COMPLETED)
        
        self.status_label.setText(
            f"Tasks: {total} | Running: {running} | Completed: {completed}"
        )


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLE)
    
    window = DriverUpdaterMK3()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
