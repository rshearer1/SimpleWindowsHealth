"""
Driver Update Scanner & Installer - PyQt6 UI
Modern desktop application for Windows driver management
"""

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QTextEdit, QProgressBar, QMessageBox, QHeaderView, QFrame,
    QSplitter, QTreeWidget, QTreeWidgetItem, QGroupBox, QScrollArea,
    QStatusBar, QToolBar, QMenu, QStyle, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette, QAction, QIcon
import threading

from driver_backend import (
    DriverScanner, OnlineDriverChecker, ManufacturerSupport,
    HealthChecker, DiskManager, DriverInfo,
    is_admin, run_as_admin, open_url
)


# Dracula Theme - Premium dark color scheme
# Colors: Background #282a36, Current Line #44475a, Foreground #f8f8f2
# Comment #6272a4, Cyan #8be9fd, Green #50fa7b, Orange #ffb86c
# Pink #ff79c6, Purple #bd93f9, Red #ff5555, Yellow #f1fa8c

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
    padding: 6px 4px;
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
QTreeWidget::branch:has-children:closed {
    image: url(none);
    border-image: none;
}
QTreeWidget::branch:has-children:open {
    image: url(none);
    border-image: none;
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
QLabel#titleLabel {
    font-size: 26pt;
    font-weight: bold;
    color: #f8f8f2;
}
QLabel#subtitleLabel {
    font-size: 11pt;
    color: #6272a4;
    font-weight: 400;
}
QLabel#cardTitle {
    font-size: 12pt;
    font-weight: 600;
    color: #f8f8f2;
}
QLabel#successLabel {
    color: #50fa7b;
}
QLabel#warningLabel {
    color: #ffb86c;
}
QLabel#errorLabel {
    color: #ff5555;
}
QFrame#card {
    background: #21222c;
    border: 1px solid #44475a;
    border-radius: 12px;
    padding: 16px;
}
QFrame#glassCard {
    background: rgba(68, 71, 90, 0.5);
    border: 1px solid #44475a;
    border-radius: 12px;
    padding: 16px;
}
QFrame#statusCard {
    background: #21222c;
    border: 1px solid #44475a;
    border-radius: 10px;
    padding: 14px;
}
QFrame#statusCardGood {
    background: #21222c;
    border: 1px solid #50fa7b;
    border-radius: 10px;
    padding: 14px;
}
QFrame#statusCardWarning {
    background: #21222c;
    border: 1px solid #ffb86c;
    border-radius: 10px;
    padding: 14px;
}
QFrame#statusCardError {
    background: #21222c;
    border: 1px solid #ff5555;
    border-radius: 10px;
    padding: 14px;
}
QFrame#headerFrame {
    background: #21222c;
    border: none;
}
QFrame#toolbarFrame {
    background: #21222c;
    border: 1px solid #44475a;
    border-radius: 8px;
    padding: 6px;
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


class WorkerThread(QThread):
    """Generic worker thread for background operations"""
    finished = pyqtSignal(object)
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class DriverUpdaterApp(QMainWindow):
    """Main application window"""
    
    log_signal = pyqtSignal(str)
    
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
        
        # Initialize backend
        self.scanner = DriverScanner(callback=self.log_message)
        self.online_checker = OnlineDriverChecker(callback=self.log_message)
        self.health_checker = HealthChecker(callback=self.log_message)
        self.disk_manager = DiskManager(callback=self.log_message)
        
        # Data storage
        self.installed_drivers = []
        self.available_updates = []
        self.online_updates = []
        self.problem_devices = []
        self.unused_drivers = []
        self.system_info = {}
        
        # Setup UI
        self.setWindowTitle("Driver Updater Pro")
        self.setMinimumSize(1200, 800)
        self.setup_ui()
        
        # Connect log signal
        self.log_signal.connect(self._append_log)
        
        # Initial scan
        QTimer.singleShot(500, self.initial_scan)
    
    def log_message(self, message: str):
        """Thread-safe logging"""
        self.log_signal.emit(message)
    
    def _append_log(self, message: str):
        """Append message to log (must be called from main thread)"""
        self.log_text.append(f"[{self._get_timestamp()}] {message}")
    
    def _get_timestamp(self):
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")
    
    def setup_ui(self):
        """Setup the main UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = self.create_header()
        layout.addWidget(header)
        
        # Main content with tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        layout.addWidget(self.tabs)
        
        # Create tabs
        self.create_installed_tab()
        self.create_updates_tab()
        self.create_online_tab()
        self.create_issues_tab()
        self.create_cleanup_tab()
        self.create_health_tab()
        self.create_disks_tab()
        self.create_log_tab()
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)
    
    def create_header(self) -> QWidget:
        """Create the header section"""
        header = QFrame()
        header.setObjectName("headerFrame")
        header.setFixedHeight(120)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(24, 20, 24, 20)
        
        # Icon/Logo area
        logo_label = QLabel("🔧")
        logo_label.setStyleSheet("font-size: 42pt; margin-right: 16px;")
        layout.addWidget(logo_label)
        
        # Title section
        title_section = QVBoxLayout()
        title_section.setSpacing(4)
        title = QLabel("Driver Updater Pro")
        title.setStyleSheet("""
            font-size: 26pt;
            font-weight: bold;
            color: #ffffff;
            background: transparent;
        """)
        subtitle = QLabel("Windows Driver Management & System Health")
        subtitle.setStyleSheet("font-size: 11pt; color: #6272a4; background: transparent;")
        title_section.addWidget(title)
        title_section.addWidget(subtitle)
        layout.addLayout(title_section)
        
        layout.addStretch()
        
        # System info card
        info_card = QFrame()
        info_card.setStyleSheet("""
            QFrame {
                background: #21222c;
                border: 1px solid #44475a;
                border-radius: 10px;
                padding: 12px 20px;
            }
        """)
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(12, 8, 12, 8)
        info_layout.setSpacing(2)
        
        self.system_label = QLabel("🖥️ Loading system info...")
        self.system_label.setStyleSheet("color: #6272a4; font-size: 10pt; background: transparent;")
        self.admin_label = QLabel("🛡️ Running as Administrator")
        self.admin_label.setStyleSheet("color: #50fa7b; font-size: 9pt; background: transparent;")
        
        info_layout.addWidget(self.system_label)
        info_layout.addWidget(self.admin_label)
        layout.addWidget(info_card)
        
        layout.addSpacing(16)
        
        # Quick actions
        scan_btn = QPushButton("⚡ Scan All")
        scan_btn.setStyleSheet("""
            QPushButton {
                background: #bd93f9;
                color: #282a36;
                padding: 14px 28px;
                border-radius: 10px;
                font-size: 11pt;
                font-weight: 600;
                border: none;
            }
            QPushButton:hover {
                background: #caa4ff;
            }
        """)
        scan_btn.clicked.connect(self.scan_all)
        layout.addWidget(scan_btn)
        
        return header
    
    def create_toolbar_frame(self) -> QFrame:
        """Create a styled toolbar frame"""
        frame = QFrame()
        frame.setObjectName("toolbarFrame")
        return frame
    
    def create_stat_badge(self, icon: str, text: str, color: str = "#8be9fd") -> QLabel:
        """Create a stat badge label"""
        label = QLabel(f"{icon}  {text}")
        label.setStyleSheet(f"""
            QLabel {{
                background: #21222c;
                border: 1px solid {color};
                border-radius: 6px;
                padding: 8px 16px;
                color: {color};
                font-weight: 600;
                font-size: 10pt;
            }}
        """)
        return label
    
    def create_installed_tab(self):
        """Create the installed drivers tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Toolbar frame
        toolbar_frame = self.create_toolbar_frame()
        toolbar = QHBoxLayout(toolbar_frame)
        toolbar.setContentsMargins(12, 8, 12, 8)
        
        scan_btn = QPushButton("🔄  Refresh Drivers")
        scan_btn.setObjectName("secondaryButton")
        scan_btn.clicked.connect(self.scan_drivers)
        toolbar.addWidget(scan_btn)
        
        export_btn = QPushButton("📋  Export List")
        export_btn.setObjectName("secondaryButton")
        toolbar.addWidget(export_btn)
        
        toolbar.addStretch()
        
        self.driver_count_label = self.create_stat_badge("📦", "0 drivers")
        toolbar.addWidget(self.driver_count_label)
        
        layout.addWidget(toolbar_frame)
        
        # Drivers table
        self.drivers_table = QTableWidget()
        self.drivers_table.setAlternatingRowColors(True)
        self.drivers_table.setColumnCount(6)
        self.drivers_table.setHorizontalHeaderLabels([
            "Device Name", "Manufacturer", "Version", "Date", "Status", "INF"
        ])
        self.drivers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.drivers_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.drivers_table.verticalHeader().setVisible(False)
        self.drivers_table.setShowGrid(False)
        layout.addWidget(self.drivers_table)
        
        self.tabs.addTab(tab, "📁  Installed")
    
    def create_updates_tab(self):
        """Create the Windows Update drivers tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Toolbar frame
        toolbar_frame = self.create_toolbar_frame()
        toolbar = QHBoxLayout(toolbar_frame)
        toolbar.setContentsMargins(12, 8, 12, 8)
        
        check_btn = QPushButton("🔍  Check Windows Update")
        check_btn.clicked.connect(self.check_windows_updates)
        toolbar.addWidget(check_btn)
        
        install_btn = QPushButton("⬇️  Install Selected")
        install_btn.setObjectName("successButton")
        install_btn.clicked.connect(self.install_updates)
        toolbar.addWidget(install_btn)
        
        toolbar.addStretch()
        
        self.updates_count_label = self.create_stat_badge("📥", "0 updates", "#50fa7b")
        toolbar.addWidget(self.updates_count_label)
        
        layout.addWidget(toolbar_frame)
        
        # Updates table
        self.updates_table = QTableWidget()
        self.updates_table.setAlternatingRowColors(True)
        self.updates_table.setColumnCount(5)
        self.updates_table.setHorizontalHeaderLabels([
            "Driver", "Provider", "Date", "Mandatory", "Reboot"
        ])
        self.updates_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.updates_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.updates_table.verticalHeader().setVisible(False)
        self.updates_table.setShowGrid(False)
        layout.addWidget(self.updates_table)
        
        self.tabs.addTab(tab, "⬇️  Updates")
    
    def create_online_tab(self):
        """Create the online driver sources tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Info card with gradient
        info_card = QFrame()
        info_card.setStyleSheet("""
            QFrame {
                background: #21222c;
                border: 1px solid #8be9fd;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        info_layout = QVBoxLayout(info_card)
        
        info_title = QLabel("🌐  Online Driver Sources")
        info_title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #8be9fd; background: transparent;")
        info_layout.addWidget(info_title)
        
        info_text = QLabel(
            "Check manufacturer websites for the latest driver versions. "
            "Click 'Check Online' to scan your hardware against vendor databases."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("color: #f8f8f2; background: transparent;")
        info_layout.addWidget(info_text)
        
        layout.addWidget(info_card)
        
        # Toolbar frame
        toolbar_frame = self.create_toolbar_frame()
        toolbar = QHBoxLayout(toolbar_frame)
        toolbar.setContentsMargins(12, 8, 12, 8)
        
        check_btn = QPushButton("🔍  Check Online Sources")
        check_btn.clicked.connect(self.check_online_drivers)
        toolbar.addWidget(check_btn)
        
        toolbar.addStretch()
        layout.addWidget(toolbar_frame)
        
        # Online sources table
        self.online_table = QTableWidget()
        self.online_table.setAlternatingRowColors(True)
        self.online_table.setColumnCount(5)
        self.online_table.setHorizontalHeaderLabels([
            "Device", "Current Version", "Source", "Description", "Action"
        ])
        self.online_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.online_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.online_table.verticalHeader().setVisible(False)
        self.online_table.setShowGrid(False)
        layout.addWidget(self.online_table)
        
        # Manufacturer tools section
        mfr_group = QGroupBox("🏭  Manufacturer Support Tools")
        mfr_layout = QHBoxLayout(mfr_group)
        
        self.mfr_tool_label = QLabel("Detecting manufacturer...")
        mfr_layout.addWidget(self.mfr_tool_label)
        
        mfr_layout.addStretch()
        
        self.mfr_tool_btn = QPushButton("🔗  Open Manufacturer Tool")
        self.mfr_tool_btn.setEnabled(False)
        mfr_layout.addWidget(self.mfr_tool_btn)
        
        layout.addWidget(mfr_group)
        
        self.tabs.addTab(tab, "🌐  Online")
    
    def create_issues_tab(self):
        """Create the problem devices tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Toolbar frame
        toolbar_frame = self.create_toolbar_frame()
        toolbar = QHBoxLayout(toolbar_frame)
        toolbar.setContentsMargins(12, 8, 12, 8)
        
        scan_btn = QPushButton("🔍  Scan for Problems")
        scan_btn.clicked.connect(self.scan_problems)
        toolbar.addWidget(scan_btn)
        
        toolbar.addStretch()
        
        self.problems_count_label = self.create_stat_badge("⚠️", "0 issues", "#f0c060")
        toolbar.addWidget(self.problems_count_label)
        
        layout.addWidget(toolbar_frame)
        
        # Problems table
        self.problems_table = QTableWidget()
        self.problems_table.setAlternatingRowColors(True)
        self.problems_table.setColumnCount(4)
        self.problems_table.setHorizontalHeaderLabels([
            "Device Name", "Status", "Error Code", "Device ID"
        ])
        self.problems_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.problems_table.verticalHeader().setVisible(False)
        self.problems_table.setShowGrid(False)
        layout.addWidget(self.problems_table)
        
        self.tabs.addTab(tab, "⚠️  Issues")
    
    def create_cleanup_tab(self):
        """Create the driver cleanup tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Warning card with amber border
        warning_card = QFrame()
        warning_card.setStyleSheet("""
            QFrame {
                background: #21222c;
                border: 1px solid #ffb86c;
                border-left: 4px solid #ffb86c;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        warning_layout = QVBoxLayout(warning_card)
        
        warning_title = QLabel("🧹  Driver Cleanup")
        warning_title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #ffb86c; background: transparent;")
        warning_layout.addWidget(warning_title)
        
        warning_text = QLabel(
            "Remove unused, old, or orphaned drivers from your system. "
            "Only remove drivers you're confident are not needed. "
            "Protected system drivers cannot be removed."
        )
        warning_text.setWordWrap(True)
        warning_text.setStyleSheet("color: #f8f8f2; background: transparent;")
        warning_layout.addWidget(warning_text)
        
        layout.addWidget(warning_card)
        
        # Toolbar frame
        toolbar_frame = self.create_toolbar_frame()
        toolbar = QHBoxLayout(toolbar_frame)
        toolbar.setContentsMargins(12, 8, 12, 8)
        
        scan_btn = QPushButton("🔍  Scan Unused Drivers")
        scan_btn.clicked.connect(self.scan_unused_drivers)
        toolbar.addWidget(scan_btn)
        
        remove_btn = QPushButton("🗑️  Remove Selected")
        remove_btn.setObjectName("dangerButton")
        remove_btn.clicked.connect(self.remove_selected_drivers)
        toolbar.addWidget(remove_btn)
        
        toolbar.addStretch()
        
        self.cleanup_count_label = self.create_stat_badge("🗑️", "0 removable", "#e05070")
        toolbar.addWidget(self.cleanup_count_label)
        
        layout.addWidget(toolbar_frame)
        
        # Unused drivers tree
        self.cleanup_tree = QTreeWidget()
        self.cleanup_tree.setAlternatingRowColors(True)
        self.cleanup_tree.setHeaderLabels([
            "Driver", "Category", "Provider", "Version", "Risk", "Reason"
        ])
        self.cleanup_tree.setColumnWidth(0, 300)
        self.cleanup_tree.setColumnWidth(1, 100)
        self.cleanup_tree.setColumnWidth(2, 150)
        self.cleanup_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.cleanup_tree)
        
        self.tabs.addTab(tab, "🧹  Cleanup")
    
    def create_health_tab(self):
        """Create the system health tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Toolbar frame
        toolbar_frame = self.create_toolbar_frame()
        toolbar = QHBoxLayout(toolbar_frame)
        toolbar.setContentsMargins(12, 8, 12, 8)
        
        scan_btn = QPushButton("🏥  Run Health Check")
        scan_btn.clicked.connect(self.run_health_check)
        toolbar.addWidget(scan_btn)
        
        sfc_btn = QPushButton("🔧  Run SFC Scan")
        sfc_btn.setObjectName("secondaryButton")
        sfc_btn.clicked.connect(self.run_sfc)
        toolbar.addWidget(sfc_btn)
        
        dism_btn = QPushButton("🛠️  Run DISM Check")
        dism_btn.setObjectName("secondaryButton")
        dism_btn.clicked.connect(self.run_dism)
        toolbar.addWidget(dism_btn)
        
        toolbar.addStretch()
        layout.addWidget(toolbar_frame)
        
        # Health status cards with better styling
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)
        
        # Defender card
        self.defender_card, self.defender_status = self.create_health_card(
            "🛡️", "Windows Defender", "Checking...", "#8be9fd")
        cards_layout.addWidget(self.defender_card)
        
        # Updates card
        self.updates_card, self.updates_status = self.create_health_card(
            "📥", "Windows Update", "Checking...", "#50fa7b")
        cards_layout.addWidget(self.updates_card)
        
        # Disk health card
        self.disk_health_card, self.disk_health_status = self.create_health_card(
            "💾", "Disk Health", "Checking...", "#bd93f9")
        cards_layout.addWidget(self.disk_health_card)
        
        layout.addLayout(cards_layout)
        
        # Health output
        self.health_output = QTextEdit()
        self.health_output.setReadOnly(True)
        self.health_output.setFont(QFont("Cascadia Code", 10))
        self.health_output.setStyleSheet("""
            QTextEdit {
                background: #21222c;
                border: 1px solid #44475a;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        layout.addWidget(self.health_output)
        
        self.tabs.addTab(tab, "🏥  Health")
    
    def create_health_card(self, icon: str, title: str, status: str, color: str) -> tuple:
        """Create a premium health status card"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: #21222c;
                border: 1px solid #44475a;
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        
        # Icon
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"font-size: 28pt; color: {color}; background: transparent;")
        layout.addWidget(icon_label)
        
        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {color}; background: transparent;")
        layout.addWidget(title_label)
        
        # Status
        status_label = QLabel(status)
        status_label.setStyleSheet("color: #6272a4; font-size: 10pt; background: transparent;")
        layout.addWidget(status_label)
        
        layout.addStretch()
        
        return card, status_label
    
    def create_status_card(self, title: str, status: str) -> QFrame:
        """Create a status card widget (legacy)"""
        card, _ = self.create_health_card("📊", title, status, "#8be9fd")
        return card
    
    def create_disks_tab(self):
        """Create the disk management tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Toolbar frame
        toolbar_frame = self.create_toolbar_frame()
        toolbar = QHBoxLayout(toolbar_frame)
        toolbar.setContentsMargins(12, 8, 12, 8)
        
        refresh_btn = QPushButton("🔄  Refresh")
        refresh_btn.setObjectName("secondaryButton")
        refresh_btn.clicked.connect(self.refresh_disks)
        toolbar.addWidget(refresh_btn)
        
        chkdsk_btn = QPushButton("🔍  CHKDSK")
        chkdsk_btn.clicked.connect(self.run_chkdsk)
        toolbar.addWidget(chkdsk_btn)
        
        optimize_btn = QPushButton("⚡  Optimize")
        optimize_btn.clicked.connect(self.optimize_disk)
        toolbar.addWidget(optimize_btn)
        
        cleanup_btn = QPushButton("🧹  Disk Cleanup")
        cleanup_btn.setObjectName("secondaryButton")
        cleanup_btn.clicked.connect(self.run_disk_cleanup)
        toolbar.addWidget(cleanup_btn)
        
        toolbar.addStretch()
        layout.addWidget(toolbar_frame)
        
        # Disks table
        self.disks_table = QTableWidget()
        self.disks_table.setAlternatingRowColors(True)
        self.disks_table.setColumnCount(6)
        self.disks_table.setHorizontalHeaderLabels([
            "Drive", "Label", "File System", "Size (GB)", "Free (GB)", "Health"
        ])
        self.disks_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.disks_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.disks_table.verticalHeader().setVisible(False)
        self.disks_table.setShowGrid(False)
        layout.addWidget(self.disks_table)
        
        # Disk output
        self.disk_output = QTextEdit()
        self.disk_output.setReadOnly(True)
        self.disk_output.setMaximumHeight(200)
        self.disk_output.setFont(QFont("Cascadia Code", 10))
        self.disk_output.setStyleSheet("""
            QTextEdit {
                background: #21222c;
                border: 1px solid #44475a;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        layout.addWidget(self.disk_output)
        
        self.tabs.addTab(tab, "💾  Disks")
    
    def create_log_tab(self):
        """Create the log tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Toolbar frame
        toolbar_frame = self.create_toolbar_frame()
        toolbar = QHBoxLayout(toolbar_frame)
        toolbar.setContentsMargins(12, 8, 12, 8)
        
        clear_btn = QPushButton("🗑️  Clear Log")
        clear_btn.setObjectName("secondaryButton")
        clear_btn.clicked.connect(lambda: self.log_text.clear())
        toolbar.addWidget(clear_btn)
        
        export_btn = QPushButton("📤  Export")
        export_btn.setObjectName("secondaryButton")
        export_btn.clicked.connect(self.export_log)
        toolbar.addWidget(export_btn)
        
        toolbar.addStretch()
        
        # Log level filter
        level_label = QLabel("Filter:")
        level_label.setStyleSheet("color: #6272a4;")
        toolbar.addWidget(level_label)
        
        self.log_filter = QComboBox()
        self.log_filter.addItems(["All", "Info", "Warning", "Error"])
        toolbar.addWidget(self.log_filter)
        
        layout.addWidget(toolbar_frame)
        
        # Log text
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Cascadia Code", 10))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background: #21222c;
                border: 1px solid #44475a;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        layout.addWidget(self.log_text)
        
        self.tabs.addTab(tab, "📋  Log")
    
    def export_log(self):
        """Export log to file"""
        from PyQt6.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Log", "driver_updater_log.txt", "Text Files (*.txt)"
        )
        if filename:
            with open(filename, 'w') as f:
                f.write(self.log_text.toPlainText())
            self.set_status(f"Log exported to {filename}")
    
    def set_status(self, message: str, show_progress: bool = False):
        """Update status bar"""
        self.status_label.setText(message)
        self.progress_bar.setVisible(show_progress)
        if show_progress:
            self.progress_bar.setRange(0, 0)  # Indeterminate
    
    def initial_scan(self):
        """Run initial system scan"""
        self.set_status("Initializing...", True)
        
        # Get system info
        def get_info():
            return self.scanner.get_system_info()
        
        self.worker = WorkerThread(get_info)
        self.worker.finished.connect(self.on_system_info)
        self.worker.start()
    
    def on_system_info(self, info):
        """Handle system info result"""
        self.system_info = info
        manufacturer = info.get('Manufacturer', 'Unknown')
        model = info.get('Model', 'Unknown')
        self.system_label.setText(f"{manufacturer} {model}")
        
        # Update manufacturer tool
        support = ManufacturerSupport.get_support_urls(manufacturer, model)
        if support.get('name'):
            tool = support.get('manufacturer_tool', {})
            if tool.get('name'):
                self.mfr_tool_label.setText(f"Recommended: {tool['name']}")
                self.mfr_tool_btn.setEnabled(True)
                self.mfr_tool_btn.clicked.connect(lambda: open_url(tool['url']))
        
        # Continue with driver scan
        self.scan_drivers()
    
    def scan_all(self):
        """Scan everything"""
        self.scan_drivers()
    
    def scan_drivers(self):
        """Scan installed drivers"""
        self.set_status("Scanning drivers...", True)
        
        def scan():
            return self.scanner.scan_installed_drivers()
        
        self.worker = WorkerThread(scan)
        self.worker.finished.connect(self.on_drivers_scanned)
        self.worker.start()
    
    def on_drivers_scanned(self, drivers):
        """Handle driver scan results"""
        self.installed_drivers = drivers
        self.drivers_table.setRowCount(0)
        
        for driver in drivers:
            row = self.drivers_table.rowCount()
            self.drivers_table.insertRow(row)
            
            self.drivers_table.setItem(row, 0, QTableWidgetItem(driver.device_name))
            self.drivers_table.setItem(row, 1, QTableWidgetItem(driver.manufacturer))
            self.drivers_table.setItem(row, 2, QTableWidgetItem(driver.driver_version))
            self.drivers_table.setItem(row, 3, QTableWidgetItem(driver.driver_date))
            
            status_item = QTableWidgetItem(driver.status)
            if driver.status != "OK":
                status_item.setForeground(QColor("#ffb86c"))
            else:
                status_item.setForeground(QColor("#50fa7b"))
            self.drivers_table.setItem(row, 4, status_item)
            
            self.drivers_table.setItem(row, 5, QTableWidgetItem(driver.inf_name))
        
        self.driver_count_label.setText(f"{len(drivers)} drivers")
        self.set_status(f"Found {len(drivers)} installed drivers")
    
    def check_windows_updates(self):
        """Check Windows Update for driver updates"""
        self.set_status("Checking Windows Update...", True)
        
        def check():
            return self.scanner.check_windows_update_drivers()
        
        self.worker = WorkerThread(check)
        self.worker.finished.connect(self.on_updates_checked)
        self.worker.start()
    
    def on_updates_checked(self, updates):
        """Handle Windows Update results"""
        self.available_updates = updates
        self.updates_table.setRowCount(0)
        
        for update in updates:
            row = self.updates_table.rowCount()
            self.updates_table.insertRow(row)
            
            self.updates_table.setItem(row, 0, QTableWidgetItem(update['title']))
            self.updates_table.setItem(row, 1, QTableWidgetItem(update['provider']))
            self.updates_table.setItem(row, 2, QTableWidgetItem(update['date']))
            self.updates_table.setItem(row, 3, QTableWidgetItem("Yes" if update['mandatory'] else "No"))
            self.updates_table.setItem(row, 4, QTableWidgetItem("Yes" if update['reboot_required'] else "No"))
        
        self.updates_count_label.setText(f"{len(updates)} updates available")
        self.set_status(f"Found {len(updates)} driver updates available")
    
    def install_updates(self):
        """Install Windows Update drivers"""
        if not self.available_updates:
            QMessageBox.information(self, "No Updates", "No driver updates available to install.")
            return
        
        reply = QMessageBox.question(
            self,
            "Install Updates",
            f"Install {len(self.available_updates)} driver update(s)?\n\n"
            "This may require a system restart.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.set_status("Installing updates...", True)
            
            def install():
                return self.scanner.install_windows_updates()
            
            self.worker = WorkerThread(install)
            self.worker.finished.connect(lambda result: (
                QMessageBox.information(self, "Complete", "Driver updates installed."),
                self.check_windows_updates()
            ))
            self.worker.start()
    
    def check_online_drivers(self):
        """Check online sources for driver updates"""
        if not self.installed_drivers:
            QMessageBox.warning(self, "Scan Required", "Please scan installed drivers first.")
            return
        
        self.set_status("Checking online sources...", True)
        
        def check():
            return self.online_checker.scan_all_drivers_online(self.installed_drivers)
        
        self.worker = WorkerThread(check)
        self.worker.finished.connect(self.on_online_checked)
        self.worker.start()
    
    def on_online_checked(self, results):
        """Handle online check results"""
        self.online_updates = results
        self.online_table.setRowCount(0)
        
        for item in results:
            row = self.online_table.rowCount()
            self.online_table.insertRow(row)
            
            online_info = item['online_info']
            
            self.online_table.setItem(row, 0, QTableWidgetItem(item['device_name']))
            self.online_table.setItem(row, 1, QTableWidgetItem(item['current_version']))
            self.online_table.setItem(row, 2, QTableWidgetItem(online_info.source))
            self.online_table.setItem(row, 3, QTableWidgetItem(online_info.description))
            
            # Add download button
            download_btn = QPushButton("Download")
            download_btn.clicked.connect(lambda checked, url=online_info.download_url: open_url(url))
            self.online_table.setCellWidget(row, 4, download_btn)
        
        self.set_status(f"Found {len(results)} drivers with online sources")
    
    def scan_problems(self):
        """Scan for problem devices"""
        self.set_status("Scanning for problems...", True)
        
        def scan():
            return self.scanner.scan_problem_devices()
        
        self.worker = WorkerThread(scan)
        self.worker.finished.connect(self.on_problems_scanned)
        self.worker.start()
    
    def on_problems_scanned(self, problems):
        """Handle problem scan results"""
        self.problem_devices = problems
        self.problems_table.setRowCount(0)
        
        for problem in problems:
            row = self.problems_table.rowCount()
            self.problems_table.insertRow(row)
            
            self.problems_table.setItem(row, 0, QTableWidgetItem(problem['name']))
            self.problems_table.setItem(row, 1, QTableWidgetItem(problem['status']))
            self.problems_table.setItem(row, 2, QTableWidgetItem(str(problem['error_code'])))
            self.problems_table.setItem(row, 3, QTableWidgetItem(problem['device_id']))
        
        self.problems_count_label.setText(f"{len(problems)} issues found")
        
        if problems:
            self.set_status(f"Found {len(problems)} devices with problems", False)
        else:
            self.set_status("No problem devices found", False)
    
    def scan_unused_drivers(self):
        """Scan for unused drivers"""
        self.set_status("Scanning for unused drivers...", True)
        
        def scan():
            return self.scanner.find_unused_drivers()
        
        self.worker = WorkerThread(scan)
        self.worker.finished.connect(self.on_unused_scanned)
        self.worker.start()
    
    def on_unused_scanned(self, drivers):
        """Handle unused driver scan results"""
        self.unused_drivers = drivers
        self.cleanup_tree.clear()
        
        # Group by category
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
                
                # Color by risk
                if driver['risk'] == 'caution':
                    item.setForeground(4, QColor("#ffb86c"))
                elif driver['risk'] == 'safe':
                    item.setForeground(4, QColor("#50fa7b"))
                
                item.setData(0, Qt.ItemDataRole.UserRole, driver['driver'])
                cat_item.addChild(item)
            
            self.cleanup_tree.addTopLevelItem(cat_item)
        
        self.cleanup_count_label.setText(f"{len(drivers)} removable drivers")
        self.set_status(f"Found {len(drivers)} potentially removable drivers")
    
    def remove_selected_drivers(self):
        """Remove selected drivers"""
        selected = self.cleanup_tree.selectedItems()
        inf_files = []
        
        for item in selected:
            inf = item.data(0, Qt.ItemDataRole.UserRole)
            if inf:
                inf_files.append(inf)
        
        if not inf_files:
            QMessageBox.warning(self, "No Selection", "Please select drivers to remove.")
            return
        
        reply = QMessageBox.warning(
            self,
            "Confirm Removal",
            f"Remove {len(inf_files)} driver(s)?\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.set_status("Removing drivers...", True)
            
            def remove():
                removed = 0
                skipped = 0
                for inf in inf_files:
                    if self.scanner.check_driver_in_use(inf):
                        skipped += 1
                        continue
                    success, msg = self.scanner.remove_driver(inf)
                    if success:
                        removed += 1
                    elif "in use" in msg.lower():
                        skipped += 1
                return removed, skipped
            
            self.worker = WorkerThread(remove)
            self.worker.finished.connect(lambda result: (
                QMessageBox.information(
                    self, "Complete",
                    f"Removed {result[0]} driver(s).\nSkipped {result[1]} driver(s) (in use)."
                ),
                self.scan_unused_drivers()
            ))
            self.worker.start()
    
    def run_health_check(self):
        """Run system health check"""
        self.set_status("Running health check...", True)
        self.health_output.clear()
        
        def check():
            results = {
                'defender': self.health_checker.check_defender_status(),
                'updates': self.health_checker.check_windows_update_status(),
                'disks': self.health_checker.check_disk_health()
            }
            return results
        
        self.worker = WorkerThread(check)
        self.worker.finished.connect(self.on_health_checked)
        self.worker.start()
    
    def on_health_checked(self, results):
        """Handle health check results"""
        # Update cards
        defender = results.get('defender', {})
        if defender.get('RealTimeProtection'):
            self.defender_status.setText("✓ Protected")
            self.defender_status.setStyleSheet("color: #50fa7b; font-size: 10pt; background: transparent;")
        else:
            self.defender_status.setText("✗ Not Protected")
            self.defender_status.setStyleSheet("color: #ff5555; font-size: 10pt; background: transparent;")
        
        updates = results.get('updates', {})
        pending = updates.get('PendingUpdates', 0)
        if pending == 0:
            self.updates_status.setText("✓ Up to date")
            self.updates_status.setStyleSheet("color: #50fa7b; font-size: 10pt; background: transparent;")
        else:
            self.updates_status.setText(f"⚠ {pending} pending")
            self.updates_status.setStyleSheet("color: #ffb86c; font-size: 10pt; background: transparent;")
        
        disks = results.get('disks', [])
        all_healthy = all(d.get('Status') == 'OK' for d in disks)
        if all_healthy:
            self.disk_health_status.setText("✓ All disks healthy")
            self.disk_health_status.setStyleSheet("color: #50fa7b; font-size: 10pt; background: transparent;")
        else:
            self.disk_health_status.setText("⚠ Check disks")
            self.disk_health_status.setStyleSheet("color: #ffb86c; font-size: 10pt; background: transparent;")
        
        # Output details
        self.health_output.append("=== Windows Defender ===")
        if 'Error' in defender:
            self.health_output.append(f"Error: {defender['Error']}")
        else:
            self.health_output.append(f"Real-time Protection: {'Enabled' if defender.get('RealTimeProtection') else 'Disabled'}")
            self.health_output.append(f"Signature Age: {defender.get('SignatureAge', 'N/A')} days")
            self.health_output.append(f"Last Scan: {defender.get('LastScan', 'N/A')}")
        
        self.health_output.append("\n=== Windows Update ===")
        self.health_output.append(f"Pending Updates: {updates.get('PendingUpdates', 'N/A')}")
        
        self.health_output.append("\n=== Disk Health ===")
        for disk in disks:
            self.health_output.append(f"{disk.get('Model', 'Unknown')}: {disk.get('Status', 'Unknown')}")
        
        self.set_status("Health check complete")
    
    def run_sfc(self):
        """Run System File Checker"""
        reply = QMessageBox.question(
            self,
            "Run SFC",
            "Run System File Checker?\n\nThis may take several minutes.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.set_status("Running SFC scan...", True)
            self.health_output.append("\n=== Running SFC Scan ===\n")
            
            def run():
                return self.health_checker.run_sfc_scan()
            
            self.worker = WorkerThread(run)
            self.worker.finished.connect(lambda result: (
                self.health_output.append(result),
                self.set_status("SFC scan complete")
            ))
            self.worker.start()
    
    def run_dism(self):
        """Run DISM health check"""
        self.set_status("Running DISM...", True)
        self.health_output.append("\n=== Running DISM Health Check ===\n")
        
        def run():
            return self.health_checker.run_dism_scan()
        
        self.worker = WorkerThread(run)
        self.worker.finished.connect(lambda result: (
            self.health_output.append(result),
            self.set_status("DISM check complete")
        ))
        self.worker.start()
    
    def refresh_disks(self):
        """Refresh disk information"""
        self.set_status("Refreshing disk info...", True)
        
        def get_disks():
            return self.health_checker.get_volume_info()
        
        self.worker = WorkerThread(get_disks)
        self.worker.finished.connect(self.on_disks_refreshed)
        self.worker.start()
    
    def on_disks_refreshed(self, volumes):
        """Handle disk refresh results"""
        self.disks_table.setRowCount(0)
        
        for vol in volumes:
            row = self.disks_table.rowCount()
            self.disks_table.insertRow(row)
            
            self.disks_table.setItem(row, 0, QTableWidgetItem(f"{vol.get('DriveLetter', '')}:"))
            self.disks_table.setItem(row, 1, QTableWidgetItem(vol.get('FileSystemLabel', '')))
            self.disks_table.setItem(row, 2, QTableWidgetItem(vol.get('FileSystem', '')))
            self.disks_table.setItem(row, 3, QTableWidgetItem(str(vol.get('SizeGB', 0))))
            self.disks_table.setItem(row, 4, QTableWidgetItem(str(vol.get('FreeSpaceGB', 0))))
            
            health = vol.get('HealthStatus', 'Unknown')
            health_item = QTableWidgetItem(health)
            if health == 'Healthy':
                health_item.setForeground(QColor("#50fa7b"))
            else:
                health_item.setForeground(QColor("#ffb86c"))
            self.disks_table.setItem(row, 5, health_item)
        
        self.set_status(f"Found {len(volumes)} volumes")
    
    def get_selected_drive(self) -> str:
        """Get the selected drive letter"""
        selected = self.disks_table.selectedItems()
        if selected:
            drive = selected[0].text().replace(":", "")
            return drive
        return ""
    
    def run_chkdsk(self):
        """Run CHKDSK on selected drive"""
        drive = self.get_selected_drive()
        if not drive:
            QMessageBox.warning(self, "No Selection", "Please select a drive first.")
            return
        
        self.set_status(f"Running CHKDSK on {drive}:...", True)
        self.disk_output.append(f"\n=== CHKDSK {drive}: ===\n")
        
        def run():
            return self.disk_manager.run_chkdsk(drive)
        
        self.worker = WorkerThread(run)
        self.worker.finished.connect(lambda result: (
            self.disk_output.append(result),
            self.set_status("CHKDSK complete")
        ))
        self.worker.start()
    
    def optimize_disk(self):
        """Optimize selected drive"""
        drive = self.get_selected_drive()
        if not drive:
            QMessageBox.warning(self, "No Selection", "Please select a drive first.")
            return
        
        self.set_status(f"Optimizing {drive}:...", True)
        self.disk_output.append(f"\n=== Optimizing {drive}: ===\n")
        
        def run():
            return self.disk_manager.optimize_drive(drive)
        
        self.worker = WorkerThread(run)
        self.worker.finished.connect(lambda result: (
            self.disk_output.append(result),
            self.set_status("Optimization complete")
        ))
        self.worker.start()
    
    def run_disk_cleanup(self):
        """Run disk cleanup on selected drive"""
        drive = self.get_selected_drive()
        if not drive:
            QMessageBox.warning(self, "No Selection", "Please select a drive first.")
            return
        
        self.disk_manager.run_disk_cleanup(drive)
        self.disk_output.append(f"\nDisk Cleanup launched for {drive}:\n")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLE)
    
    window = DriverUpdaterApp()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
