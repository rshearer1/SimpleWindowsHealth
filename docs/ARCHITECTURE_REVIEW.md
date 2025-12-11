# Windows Health Checker Pro - Architecture & Performance Review

**Date:** December 2025  
**Version:** 3.0.2  
**Author:** Architecture Review

---

## Executive Summary

This document provides a comprehensive analysis of the Windows Health Checker Pro codebase, identifying architectural issues, performance bottlenecks, and providing actionable recommendations for improvement. The goal is to transform the application into a maintainable, responsive desktop app.

### Current State Overview

| Metric | Current Value | Concern Level |
|--------|---------------|---------------|
| Main file size | 18,465 lines | 🔴 Critical |
| `setStyleSheet()` calls | 699 | 🔴 Critical |
| Subprocess calls | 170 | 🟡 Warning |
| Page classes | 14+ | 🟡 Warning |
| Background workers | 10+ | 🟢 Good pattern |

---

## Table of Contents

1. [Architectural Issues](#1-architectural-issues)
2. [Threading & Responsiveness](#2-threading--responsiveness)
3. [Performance Optimizations](#3-performance-optimizations)
4. [Profiling & Monitoring](#4-profiling--monitoring)
5. [Quick Wins](#5-quick-wins)
6. [Implementation Priority](#6-implementation-priority)
7. [Code Examples](#7-code-examples)

---

## 1. Architectural Issues

### 1.1 Monolithic Single-File Structure

**Current State:** The entire application exists in a single 18,465-line file (`driver_updater_qt_mk5.py`).

**Problems:**
- Extremely difficult to navigate and maintain
- Slow for IDEs to parse and provide intellisense
- Impossible to unit test individual components
- High risk of merge conflicts in team environments
- Circular import issues when trying to split

**Recommended Structure:**

```
healthchecker/
├── __init__.py
├── app.py                    # Entry point, QApplication setup
├── main_window.py            # MainWindow class only
│
├── theme/
│   ├── __init__.py
│   ├── colors.py             # Theme class, color definitions
│   ├── styles.py             # GLOBAL_STYLE, StyleManager
│   └── icons.py              # IconPainter, icon utilities
│
├── workers/
│   ├── __init__.py
│   ├── base.py               # Base worker class, ThreadPool
│   ├── metrics.py            # MetricsWorker, MetricsCollector
│   ├── scanners.py           # HardwareScanWorker, EventScanWorker, etc.
│   └── winget.py             # Winget-specific workers
│
├── widgets/
│   ├── __init__.py
│   ├── cards.py              # GlassCard, HealthSummaryCard, StatusCard
│   ├── navigation.py         # NavItem, CustomTitleBar, Sidebar
│   ├── graphs.py             # MiniGraph, ScoreRing, PerformanceGraph
│   └── common.py             # StatusRow, ResultCard, DebouncedLineEdit
│
├── pages/
│   ├── __init__.py
│   ├── overview.py           # OverviewPage
│   ├── drivers.py            # DriversPage
│   ├── startup.py            # StartupPage
│   ├── storage.py            # StoragePage
│   ├── security.py           # SecurityPage
│   ├── hardware.py           # HardwarePage
│   ├── events.py             # EventsPage
│   ├── audio.py              # AudioPage
│   ├── winget.py             # WingetPage
│   ├── tools.py              # WindowsToolsPage
│   ├── settings.py           # SettingsPage
│   └── updates.py            # WindowsUpdatePage
│
├── models/
│   ├── __init__.py
│   ├── scan_results.py       # Data classes for scan results
│   └── settings.py           # Settings model
│
└── utils/
    ├── __init__.py
    ├── subprocess_utils.py   # Centralized async subprocess handling
    ├── cache.py              # Caching utilities
    └── profiler.py           # Performance profiling
```

**Benefits:**
- Each file is < 500 lines (manageable)
- Clear separation of concerns
- Easy to test individual components
- Faster IDE performance
- Parallel development possible

---

### 1.2 Excessive Inline Stylesheets (699 `setStyleSheet()` calls)

**Current State:** Stylesheets are scattered throughout the codebase, using f-strings evaluated at runtime.

**Example of Current Anti-Pattern:**
```python
# This pattern appears 699 times in the codebase
self.title_label.setStyleSheet(f"""
    background: transparent;
    color: {Theme.TEXT_PRIMARY};
    font-size: 16px;
    font-weight: 600;
""")
```

**Problems:**
- Each `setStyleSheet()` triggers CSS parsing by Qt
- F-strings are evaluated every time (string allocation)
- Theme changes require hunting through 699 locations
- Inconsistent styling across similar widgets
- Memory churn from repeated string creation

**Recommended Solution: StyleManager**

```python
# theme/styles.py
class StyleManager:
    """Centralized stylesheet management with caching."""
    
    _cache: dict[str, str] = {}
    
    @classmethod
    def get(cls, widget_type: str, variant: str = "default") -> str:
        """Get cached stylesheet for widget type."""
        key = f"{widget_type}:{variant}"
        if key not in cls._cache:
            cls._cache[key] = cls._generate(widget_type, variant)
        return cls._cache[key]
    
    @classmethod
    def clear_cache(cls):
        """Clear cache when theme changes."""
        cls._cache.clear()
    
    @classmethod
    def _generate(cls, widget_type: str, variant: str) -> str:
        """Generate stylesheet once per widget type."""
        styles = {
            "nav_item": f"""
                QFrame {{
                    background: transparent;
                    border-radius: {Theme.RADIUS_SM}px;
                    padding: 8px 12px;
                }}
                QFrame:hover {{
                    background: {Theme.BG_CARD_HOVER};
                }}
            """,
            "nav_item:active": f"""
                QFrame {{
                    background: {Theme.ACCENT_SUBTLE};
                    border-left: 3px solid {Theme.ACCENT};
                }}
            """,
            "card": f"""
                QFrame {{
                    background: {Theme.BG_CARD};
                    border-radius: {Theme.RADIUS_MD}px;
                    border: 1px solid {Theme.BORDER};
                }}
            """,
            "label:primary": f"""
                QLabel {{
                    background: transparent;
                    color: {Theme.TEXT_PRIMARY};
                    font-size: 14px;
                    font-weight: 600;
                }}
            """,
            "label:secondary": f"""
                QLabel {{
                    background: transparent;
                    color: {Theme.TEXT_SECONDARY};
                    font-size: 13px;
                }}
            """,
            # ... more styles defined once
        }
        full_key = f"{widget_type}:{variant}" if variant != "default" else widget_type
        return styles.get(full_key, styles.get(widget_type, ""))
```

**Usage:**
```python
# Before (repeated 699 times)
self.title.setStyleSheet(f"background: transparent; color: {Theme.TEXT_PRIMARY}; ...")

# After (clean, cached)
self.title.setStyleSheet(StyleManager.get("label", "primary"))
```

**Impact:** Reduces CSS parsing from 699 times to ~50 unique styles.

---

### 1.3 No Separation of Concerns (MVC/MVP)

**Current State:** Pages mix UI setup, data fetching, business logic, and state management.

**Example of Current Anti-Pattern:**
```python
class WingetPage(QWidget):
    def __init__(self):
        super().__init__()
        # Data loading in UI constructor!
        self.favorites = self._load_favorites()  
        self.search_results = []
        self.setup_ui()
        # System call in UI constructor!
        self._check_winget_available()
```

**Problems:**
- Can't test UI without running actual system commands
- Can't test business logic without creating UI
- State scattered across widget properties
- Hard to reason about data flow

**Recommended Solution: Lightweight MVP Pattern**

```python
# models/winget_model.py
class WingetModel(QObject):
    """Data model - holds state, emits changes."""
    
    favorites_changed = pyqtSignal(list)
    search_completed = pyqtSignal(list)
    install_progress = pyqtSignal(str, int)
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self._favorites: list[dict] = []
        self._search_results: list[dict] = []
        self._winget_available: bool = False
    
    @property
    def favorites(self) -> list[dict]:
        return self._favorites.copy()
    
    def set_favorites(self, favorites: list[dict]):
        self._favorites = favorites
        self.favorites_changed.emit(self._favorites)
    
    def set_search_results(self, results: list[dict]):
        self._search_results = results
        self.search_completed.emit(results)


# pages/winget.py
class WingetPage(QWidget):
    """Pure UI - receives model, emits user actions."""
    
    search_requested = pyqtSignal(str)
    install_requested = pyqtSignal(str)  # app_id
    
    def __init__(self, model: WingetModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.setup_ui()
        self._connect_model()
    
    def _connect_model(self):
        """Connect model signals to UI updates."""
        self.model.favorites_changed.connect(self._refresh_favorites_list)
        self.model.search_completed.connect(self._display_search_results)
        self.model.error_occurred.connect(self._show_error)
    
    def _on_search_clicked(self):
        """User action - emit signal, don't do work."""
        query = self.search_input.text().strip()
        if query:
            self.search_requested.emit(query)
```

---

## 2. Threading & Responsiveness

### 2.1 Subprocess Calls Blocking Main Thread

**Current State:** 170 subprocess calls, many executed on the main (UI) thread.

**Problematic Pattern:**
```python
# This blocks the UI for up to 30 seconds!
result = subprocess.run(
    ["powershell", "-Command", "..."],
    capture_output=True,
    timeout=30
)
```

**Safe Pattern (already used in some places):**
```python
# Launch without waiting - OK
subprocess.Popen(["taskmgr"])
```

**Recommended Solution: Async Subprocess Utility**

```python
# utils/subprocess_utils.py
from PyQt6.QtCore import QObject, QThread, pyqtSignal
import subprocess

class SubprocessWorker(QObject):
    """Execute subprocess in background thread."""
    
    finished = pyqtSignal(int, str, str)  # returncode, stdout, stderr
    error = pyqtSignal(str)
    
    def __init__(self, cmd: list[str], timeout: int = 30, shell: bool = False):
        super().__init__()
        self.cmd = cmd
        self.timeout = timeout
        self.shell = shell
    
    def run(self):
        try:
            result = subprocess.run(
                self.cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                shell=self.shell,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self.finished.emit(result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            self.error.emit(f"Command timed out after {self.timeout}s")
        except Exception as e:
            self.error.emit(str(e))


class AsyncSubprocess:
    """Convenience API for async subprocess execution."""
    
    @staticmethod
    def run(cmd: list[str], 
            on_complete: callable,
            on_error: callable = None,
            timeout: int = 30,
            shell: bool = False,
            parent: QObject = None) -> QThread:
        """
        Run subprocess asynchronously.
        
        Args:
            cmd: Command to execute
            on_complete: Callback(returncode, stdout, stderr)
            on_error: Callback(error_message)
            timeout: Timeout in seconds
            shell: Use shell execution
            parent: Parent QObject for thread ownership
            
        Returns:
            QThread instance (for cancellation if needed)
        """
        thread = QThread(parent)
        worker = SubprocessWorker(cmd, timeout, shell)
        worker.moveToThread(thread)
        
        # Connect signals
        thread.started.connect(worker.run)
        worker.finished.connect(on_complete)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        
        if on_error:
            worker.error.connect(on_error)
        
        thread.start()
        return thread
```

**Usage:**
```python
# Before (blocks UI)
result = subprocess.run(["powershell", "-Command", "Get-Process"], ...)
self.process_data(result.stdout)

# After (non-blocking)
AsyncSubprocess.run(
    ["powershell", "-Command", "Get-Process"],
    on_complete=lambda rc, out, err: self.process_data(out),
    on_error=lambda msg: self.show_error(msg),
    parent=self
)
```

---

### 2.2 Thread Cleanup Issues

**Current State:** Thread cleanup has race conditions and potential memory leaks.

**Problematic Pattern:**
```python
# Current code - missing thread cleanup
self._update_thread.started.connect(self._update_worker.run)
self._update_worker.finished.connect(self._update_thread.quit)
self._update_worker.finished.connect(self._update_worker.deleteLater)
# ❌ Thread itself is never deleted!
```

**Recommended Solution: Self-Cleaning Worker Thread**

```python
# workers/base.py
class WorkerThread(QThread):
    """Self-cleaning worker thread with proper lifecycle management."""
    
    def __init__(self, worker: QObject, parent: QObject = None):
        super().__init__(parent)
        self.worker = worker
        self.worker.moveToThread(self)
        
        # Setup auto-cleanup
        self.started.connect(self._on_started)
        self.finished.connect(self._cleanup)
    
    def _on_started(self):
        """Called when thread starts - invoke worker.run()."""
        if hasattr(self.worker, 'run'):
            self.worker.run()
    
    def _cleanup(self):
        """Clean up worker and self when finished."""
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        self.deleteLater()


class ThreadPool:
    """
    Manages a pool of worker threads.
    Prevents spawning too many threads and handles cleanup.
    """
    
    def __init__(self, max_threads: int = 4):
        self.max_threads = max_threads
        self._active: list[QThread] = []
        self._queue: list[tuple[QObject, callable]] = []
    
    def submit(self, worker: QObject, on_complete: callable = None) -> bool:
        """
        Submit a worker for execution.
        
        Returns True if started immediately, False if queued.
        """
        self._cleanup_finished()
        
        if len(self._active) >= self.max_threads:
            self._queue.append((worker, on_complete))
            return False
        
        self._start_worker(worker, on_complete)
        return True
    
    def _start_worker(self, worker: QObject, on_complete: callable):
        thread = WorkerThread(worker)
        
        if on_complete and hasattr(worker, 'finished'):
            worker.finished.connect(on_complete)
        
        thread.finished.connect(lambda: self._on_thread_finished(thread))
        self._active.append(thread)
        thread.start()
    
    def _cleanup_finished(self):
        self._active = [t for t in self._active if t.isRunning()]
    
    def _on_thread_finished(self, thread: QThread):
        if thread in self._active:
            self._active.remove(thread)
        
        # Start next queued worker
        if self._queue:
            worker, callback = self._queue.pop(0)
            self._start_worker(worker, callback)
    
    def shutdown(self, wait_ms: int = 5000):
        """Shutdown all threads gracefully."""
        for thread in self._active:
            thread.quit()
        
        for thread in self._active:
            thread.wait(wait_ms // len(self._active) if self._active else wait_ms)
```

---

### 2.3 MetricsWorker Using `time.sleep()`

**Current State:** Background metrics collection uses `time.sleep()` in a loop.

```python
# Current implementation
def start_collecting(self):
    self._running = True
    while self._running:
        # ... collect metrics
        time.sleep(1.5)  # Blocks thread, hard to interrupt
```

**Problems:**
- `time.sleep()` blocks the thread completely
- Can't interrupt cleanly (must wait for sleep to finish)
- Not idiomatic Qt

**Recommended Solution: QTimer in Worker Thread**

```python
class MetricsWorker(QObject):
    """Collects system metrics using QTimer for clean control."""
    
    metrics_ready = pyqtSignal(float, float, float)  # cpu, ram, disk
    
    def __init__(self):
        super().__init__()
        self._timer: QTimer = None
        self._perf_counters = PerformanceCounters()
    
    def start(self):
        """Start collecting - must be called after moveToThread."""
        self._timer = QTimer()
        self._timer.timeout.connect(self._collect)
        self._timer.start(1500)  # 1.5 second interval
    
    def stop(self):
        """Stop collecting - clean and immediate."""
        if self._timer:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None
    
    def _collect(self):
        """Collect metrics - called by timer."""
        cpu = self._perf_counters.get_cpu_percent()
        ram = self._perf_counters.get_ram_percent()
        disk = self._perf_counters.get_disk_percent()
        self.metrics_ready.emit(cpu, ram, disk)
```

---

## 3. Performance Optimizations

### 3.1 Replace Subprocess Metrics with Native Calls

**Current State:** CPU and disk metrics spawn PowerShell every 1.5 seconds.

```python
# Current - spawns 2 processes every 1.5 seconds (inefficient)
cpu_result = subprocess.run('wmic cpu get loadpercentage /value', ...)
disk_result = subprocess.run('wmic path Win32_PerfFormattedData...', ...)
```

**Impact:** ~100-200ms overhead per subprocess = constant background lag

**Recommended Solution: Native Windows API via ctypes**

```python
import ctypes
from ctypes import wintypes

class PerformanceCounters:
    """Native Windows performance counters - no subprocess needed."""
    
    def __init__(self):
        # For CPU calculation
        self._last_idle = 0
        self._last_kernel = 0
        self._last_user = 0
        
        # For RAM - pre-allocate structure
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
    
    def get_cpu_percent(self) -> float:
        """
        Get CPU usage using GetSystemTimes.
        Instant call - no subprocess overhead.
        """
        idle = ctypes.c_ulonglong()
        kernel = ctypes.c_ulonglong()
        user = ctypes.c_ulonglong()
        
        ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle),
            ctypes.byref(kernel),
            ctypes.byref(user)
        )
        
        idle_diff = idle.value - self._last_idle
        kernel_diff = kernel.value - self._last_kernel
        user_diff = user.value - self._last_user
        
        self._last_idle = idle.value
        self._last_kernel = kernel.value
        self._last_user = user.value
        
        total = kernel_diff + user_diff
        if total == 0:
            return 0.0
        
        return round(100.0 * (1.0 - idle_diff / total), 1)
    
    def get_ram_percent(self) -> float:
        """
        Get RAM usage using GlobalMemoryStatusEx.
        Instant call - no subprocess overhead.
        """
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(self._mem_status))
        return float(self._mem_status.dwMemoryLoad)
    
    def get_disk_percent(self) -> float:
        """
        Get disk activity.
        Note: This still requires WMI/subprocess for accurate disk I/O %.
        Consider using psutil if acceptable dependency.
        """
        # Option 1: Use psutil (recommended if already a dependency)
        # import psutil
        # return psutil.disk_io_counters().read_percent
        
        # Option 2: Keep subprocess but call less frequently
        # This is the one metric that's hard to get natively
        return 0.0  # Placeholder
```

**Performance Gain:** 60%+ reduction in background CPU usage.

---

### 3.2 Pre-compile PowerShell Scripts

**Current State:** Large PowerShell scripts are embedded as strings and parsed each execution.

```python
# Current - 40+ line script parsed every call
cmd = '''
$output = @{
    ErrorCount = 0
    WarningCount = 0
    ...
}
# ... 40 more lines
'''
subprocess.run(["powershell", "-Command", cmd], ...)
```

**Recommended Solution: Pre-create Script Files**

```python
import tempfile
import os
import atexit

class PowerShellScripts:
    """Manages pre-created PowerShell script files."""
    
    _scripts: dict[str, str] = {}  # name -> file path
    _temp_dir: str = None
    
    @classmethod
    def initialize(cls):
        """Create all script files once at startup."""
        cls._temp_dir = tempfile.mkdtemp(prefix="healthchecker_")
        atexit.register(cls.cleanup)
        
        # Event log scanner script
        cls._create_script("event_scan", '''
            param(
                [int]$Hours = 24,
                [int]$MaxErrors = 100,
                [int]$MaxWarnings = 100
            )
            
            $output = @{
                ErrorCount = 0
                WarningCount = 0
                CriticalCount = 0
                RecentErrors = @()
                RecentWarnings = @()
            }
            
            $since = (Get-Date).AddHours(-$Hours)
            
            # ... rest of script
            
            $output | ConvertTo-Json -Depth 4
        ''')
        
        # Add more scripts...
        cls._create_script("defender_status", '''
            # Defender check script
        ''')
    
    @classmethod
    def _create_script(cls, name: str, content: str):
        """Create a script file."""
        path = os.path.join(cls._temp_dir, f"{name}.ps1")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        cls._scripts[name] = path
    
    @classmethod
    def get_path(cls, name: str) -> str:
        """Get path to a script file."""
        return cls._scripts.get(name)
    
    @classmethod
    def run(cls, name: str, **params) -> subprocess.CompletedProcess:
        """Run a pre-created script with parameters."""
        path = cls.get_path(name)
        if not path:
            raise ValueError(f"Unknown script: {name}")
        
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", path]
        for key, value in params.items():
            cmd.extend([f"-{key}", str(value)])
        
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    
    @classmethod
    def cleanup(cls):
        """Remove temp script files."""
        if cls._temp_dir and os.path.exists(cls._temp_dir):
            import shutil
            shutil.rmtree(cls._temp_dir, ignore_errors=True)
```

---

## 4. Profiling & Monitoring

### 4.1 Built-in Profiler

```python
# utils/profiler.py
import time
from functools import wraps
from collections import defaultdict
from typing import Optional
import threading

class Profiler:
    """
    Simple profiler for identifying performance bottlenecks.
    Thread-safe and minimal overhead when disabled.
    """
    
    _timings: dict[str, list[float]] = defaultdict(list)
    _enabled: bool = False  # Disabled by default in production
    _lock = threading.Lock()
    
    @classmethod
    def enable(cls):
        cls._enabled = True
    
    @classmethod
    def disable(cls):
        cls._enabled = False
    
    @classmethod
    def time(cls, name: str = None):
        """
        Decorator to time a function.
        
        Usage:
            @Profiler.time("my_function")
            def my_function():
                ...
        """
        def decorator(func):
            func_name = name or f"{func.__module__}.{func.__name__}"
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not cls._enabled:
                    return func(*args, **kwargs)
                
                start = time.perf_counter()
                try:
                    return func(*args, **kwargs)
                finally:
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    
                    with cls._lock:
                        cls._timings[func_name].append(elapsed_ms)
                    
                    # Warn about slow operations (> 16ms = frame drop at 60fps)
                    if elapsed_ms > 16:
                        print(f"⚠️ SLOW: {func_name} took {elapsed_ms:.1f}ms")
            
            return wrapper
        return decorator
    
    @classmethod
    def context(cls, name: str):
        """
        Context manager for timing code blocks.
        
        Usage:
            with Profiler.context("expensive_operation"):
                do_something()
        """
        return TimingContext(name, cls)
    
    @classmethod
    def report(cls, top_n: int = 20) -> str:
        """Generate a performance report."""
        lines = [
            "=" * 60,
            "PERFORMANCE REPORT",
            "=" * 60,
            f"{'Function':<40} {'Avg (ms)':<10} {'Total (ms)':<12} {'Calls':<8}",
            "-" * 60
        ]
        
        # Sort by total time descending
        sorted_items = sorted(
            cls._timings.items(),
            key=lambda x: sum(x[1]),
            reverse=True
        )[:top_n]
        
        for name, times in sorted_items:
            avg = sum(times) / len(times)
            total = sum(times)
            calls = len(times)
            
            # Truncate long names
            display_name = name[:38] + ".." if len(name) > 40 else name
            lines.append(f"{display_name:<40} {avg:<10.1f} {total:<12.1f} {calls:<8}")
        
        lines.append("=" * 60)
        return "\n".join(lines)
    
    @classmethod
    def reset(cls):
        """Clear all timing data."""
        with cls._lock:
            cls._timings.clear()


class TimingContext:
    """Context manager for timing code blocks."""
    
    def __init__(self, name: str, profiler: type):
        self.name = name
        self.profiler = profiler
        self.start: Optional[float] = None
    
    def __enter__(self):
        if self.profiler._enabled:
            self.start = time.perf_counter()
        return self
    
    def __exit__(self, *args):
        if self.start is not None:
            elapsed_ms = (time.perf_counter() - self.start) * 1000
            with self.profiler._lock:
                self.profiler._timings[self.name].append(elapsed_ms)
```

### 4.2 Frame Timer (UI Responsiveness Monitor)

```python
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
import time

class FrameTimer(QObject):
    """
    Monitors UI frame timing to detect stutters.
    Ideal frame time at 60fps = 16.67ms
    """
    
    frame_drop = pyqtSignal(float)  # Emitted when frame > 32ms
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_time = time.perf_counter()
        self._frame_times: list[float] = []
        self._max_samples = 120  # 2 seconds at 60fps
        
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
    
    def start(self):
        """Start monitoring."""
        self._last_time = time.perf_counter()
        self._timer.start(0)  # As fast as the event loop allows
    
    def stop(self):
        """Stop monitoring."""
        self._timer.stop()
    
    def _tick(self):
        now = time.perf_counter()
        delta_ms = (now - self._last_time) * 1000
        self._last_time = now
        
        self._frame_times.append(delta_ms)
        if len(self._frame_times) > self._max_samples:
            self._frame_times.pop(0)
        
        # Frame drop detection (less than 30fps)
        if delta_ms > 32:
            self.frame_drop.emit(delta_ms)
    
    @property
    def avg_frame_time(self) -> float:
        """Average frame time in ms."""
        if not self._frame_times:
            return 0.0
        return sum(self._frame_times) / len(self._frame_times)
    
    @property
    def fps(self) -> float:
        """Estimated frames per second."""
        avg = self.avg_frame_time
        return 1000.0 / avg if avg > 0 else 0.0
    
    @property
    def percentile_95(self) -> float:
        """95th percentile frame time (for detecting outliers)."""
        if not self._frame_times:
            return 0.0
        sorted_times = sorted(self._frame_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[idx]
```

### 4.3 Key Metrics to Monitor

| Metric | Target | Warning | Critical | Tool |
|--------|--------|---------|----------|------|
| Frame time | < 16ms | > 32ms | > 100ms | FrameTimer |
| `setStyleSheet` calls/sec | < 10 | > 50 | > 100 | Profiler |
| Active threads | < 10 | > 15 | > 20 | `threading.active_count()` |
| Memory (RSS) | Stable | +10%/min | +50%/min | `psutil.Process().memory_info()` |
| Subprocess calls/min | < 30 | > 60 | > 100 | Profiler |
| Signal connections | Stable | Growing | Runaway | Manual audit |

---

## 5. Quick Wins

### 5.1 Lazy Page Loading

**Current:** All 14 pages created at startup.  
**Impact:** Slow startup, wasted memory for unvisited pages.

```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Page factories - pages created on first access
        self._page_factories: dict[str, type] = {
            "overview": OverviewPage,
            "drivers": DriversPage,
            "startup": StartupPage,
            "updates": WindowsUpdatePage,
            "storage": StoragePage,
            "security": SecurityPage,
            "hardware": HardwarePage,
            "events": EventsPage,
            "audio": AudioPage,
            "software": WingetPage,
            "tools": WindowsToolsPage,
            "settings": SettingsPage,
        }
        
        # Only overview created initially
        self._pages: dict[str, QWidget] = {}
        self._pages["overview"] = OverviewPage()
        self.content_stack.addWidget(self._pages["overview"])
    
    def navigate(self, page_id: str):
        """Navigate to a page, creating it if needed."""
        if page_id not in self._pages:
            factory = self._page_factories.get(page_id)
            if factory:
                # Create page on first access
                page = factory()
                self._pages[page_id] = page
                self.content_stack.addWidget(page)
        
        if page_id in self._pages:
            self.content_stack.setCurrentWidget(self._pages[page_id])
            self.current_nav = page_id
```

**Impact:** 50%+ faster startup, lower initial memory.

---

### 5.2 Debounced Search Input

**Current:** Search triggers immediately on each keystroke.  
**Impact:** Unnecessary API calls, UI lag during typing.

```python
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtCore import QTimer, pyqtSignal

class DebouncedLineEdit(QLineEdit):
    """
    Line edit that waits for typing to pause before emitting.
    Prevents excessive search calls while user is typing.
    """
    
    debounced_text = pyqtSignal(str)
    
    def __init__(self, delay_ms: int = 400, parent=None):
        super().__init__(parent)
        
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._emit_debounced)
        self._delay = delay_ms
        
        self.textChanged.connect(self._on_text_changed)
    
    def _on_text_changed(self, text: str):
        """Reset timer on each keystroke."""
        self._timer.stop()
        self._timer.start(self._delay)
    
    def _emit_debounced(self):
        """Emit after typing pause."""
        self.debounced_text.emit(self.text())

# Usage:
class WingetPage(QWidget):
    def setup_ui(self):
        # Use debounced input
        self.search_input = DebouncedLineEdit(delay_ms=400)
        self.search_input.setPlaceholderText("Search packages...")
        
        # Connect to debounced signal, not textChanged
        self.search_input.debounced_text.connect(self._perform_search)
```

---

### 5.3 Virtual List for Large Data Sets

**Current:** Creating a widget for each item (startup programs, events, etc.)  
**Impact:** Slow rendering with 100+ items, high memory usage.

```python
from PyQt6.QtWidgets import QListView, QStyledItemDelegate, QStyle
from PyQt6.QtCore import QAbstractListModel, Qt, QSize, QModelIndex
from PyQt6.QtGui import QPainter, QColor

class VirtualListModel(QAbstractListModel):
    """
    Model for efficiently displaying large lists.
    Only visible items are rendered.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[dict] = []
    
    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._items)
    
    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._items):
            return None
        
        item = self._items[index.row()]
        
        if role == Qt.ItemDataRole.DisplayRole:
            return item.get("name", "")
        elif role == Qt.ItemDataRole.UserRole:
            return item  # Full data for custom delegate
        
        return None
    
    def set_items(self, items: list[dict]):
        """Replace all items."""
        self.beginResetModel()
        self._items = items
        self.endResetModel()
    
    def get_item(self, row: int) -> dict:
        """Get item at row."""
        if 0 <= row < len(self._items):
            return self._items[row]
        return {}


class StartupItemDelegate(QStyledItemDelegate):
    """
    Custom delegate for rendering startup items.
    Much faster than creating QWidget for each item.
    """
    
    ROW_HEIGHT = 64
    
    def paint(self, painter: QPainter, option, index: QModelIndex):
        item = index.data(Qt.ItemDataRole.UserRole)
        if not item:
            return super().paint(painter, option, index)
        
        painter.save()
        rect = option.rect
        
        # Background
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, QColor(Theme.ACCENT_SUBTLE))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect, QColor(Theme.BG_CARD_HOVER))
        
        # Icon area
        icon_rect = rect.adjusted(12, 12, -rect.width() + 52, -12)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(Theme.BG_ELEVATED))
        painter.drawRoundedRect(icon_rect, 6, 6)
        
        # Name
        painter.setPen(QColor(Theme.TEXT_PRIMARY))
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        name_rect = rect.adjusted(60, 10, -100, -30)
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignLeft, item.get("name", ""))
        
        # Publisher
        painter.setPen(QColor(Theme.TEXT_SECONDARY))
        painter.setFont(QFont("Segoe UI", 9))
        pub_rect = rect.adjusted(60, 30, -100, -10)
        painter.drawText(pub_rect, Qt.AlignmentFlag.AlignLeft, item.get("publisher", "Unknown"))
        
        # Status badge
        enabled = item.get("enabled", False)
        badge_color = QColor(Theme.SUCCESS if enabled else Theme.TEXT_TERTIARY)
        badge_text = "Enabled" if enabled else "Disabled"
        badge_rect = rect.adjusted(rect.width() - 90, 20, -12, -20)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(badge_color.lighter(150) if enabled else QColor(Theme.BG_ELEVATED))
        painter.drawRoundedRect(badge_rect, 4, 4)
        painter.setPen(badge_color if enabled else QColor(Theme.TEXT_TERTIARY))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)
        
        painter.restore()
    
    def sizeHint(self, option, index: QModelIndex) -> QSize:
        return QSize(0, self.ROW_HEIGHT)


# Usage:
class StartupPage(QWidget):
    def setup_ui(self):
        # Use QListView with virtual rendering
        self.list_view = QListView()
        self.list_model = VirtualListModel()
        self.list_delegate = StartupItemDelegate()
        
        self.list_view.setModel(self.list_model)
        self.list_view.setItemDelegate(self.list_delegate)
        self.list_view.setUniformItemSizes(True)  # Performance optimization
        
    def set_items(self, items: list[dict]):
        # Efficiently update list
        self.list_model.set_items(items)
```

---

## 6. Implementation Priority

### 🔴 High Priority (Week 1)

| Task | Impact | Effort | Details |
|------|--------|--------|---------|
| Extract workers to separate file | Maintainability | Low | Move all `*Worker` classes to `workers/` |
| Implement lazy page loading | 50% faster startup | Low | See Quick Win 5.1 |
| Replace subprocess metrics with native | 60% CPU reduction | Medium | See Section 3.1 |
| Add StyleManager | Reduce 699→50 calls | Medium | See Section 1.2 |

### 🟡 Medium Priority (Week 2-3)

| Task | Impact | Effort | Details |
|------|--------|--------|---------|
| Split into package structure | Testability | High | See Section 1.1 |
| Implement ThreadPool | Thread safety | Medium | See Section 2.2 |
| Add debounced inputs | Better UX | Low | See Quick Win 5.2 |
| Add Profiler | Performance visibility | Low | See Section 4.1 |

### 🟢 Lower Priority (Month 2)

| Task | Impact | Effort | Details |
|------|--------|--------|---------|
| Virtual lists for large data | Handle 1000+ items | Medium | See Quick Win 5.3 |
| Implement MVP pattern | Architecture | High | See Section 1.3 |
| Pre-compile PowerShell scripts | Minor perf gain | Low | See Section 3.2 |
| Add comprehensive unit tests | Quality | High | Requires refactoring first |

---

## 7. Code Examples

### Example: Complete AsyncSubprocess Implementation

See `utils/subprocess_utils.py` template in Section 2.1.

### Example: Complete Profiler Implementation

See `utils/profiler.py` template in Section 4.1.

### Example: StyleManager with Theme Support

See `theme/styles.py` template in Section 1.2.

---

## Appendix A: File Size Analysis

| Component | Current Lines | Target Lines |
|-----------|---------------|--------------|
| Main file | 18,465 | Split into 30+ files |
| Theme/Colors | ~400 | ~150 (colors.py) |
| Styles | ~300 | ~200 (styles.py) |
| Workers | ~500 | ~300 (workers/) |
| Widgets | ~2,000 | ~1,500 (widgets/) |
| Pages | ~10,000 | ~8,000 (pages/) |
| MainWindow | ~2,000 | ~500 (main_window.py) |
| Utilities | ~200 | ~400 (utils/) |

---

## Appendix B: Recommended Dependencies

Current dependencies are good. Consider adding:

| Package | Purpose | Notes |
|---------|---------|-------|
| `pytest` | Testing | Essential for refactored code |
| `pytest-qt` | Qt testing | Test UI components |
| `line_profiler` | Detailed profiling | Dev only |

---

## Conclusion

The Windows Health Checker Pro application has a solid feature set but suffers from architectural debt that causes sluggishness. The primary issues are:

1. **Monolithic structure** - Makes maintenance difficult
2. **Excessive inline styles** - Causes repeated CSS parsing
3. **Subprocess overuse** - Blocks UI and wastes resources
4. **No lazy loading** - Slow startup

By implementing the recommended changes in priority order, you can expect:

- **50%+ faster startup** (lazy loading)
- **60%+ reduction in background CPU** (native metrics)
- **Smoother UI** (threaded subprocess, debouncing)
- **Easier maintenance** (modular structure, StyleManager)

The quick wins (Section 5) can be implemented in days with minimal risk, while the architectural changes (Section 1) are a longer-term investment that pays dividends in maintainability and testability.
