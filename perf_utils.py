"""
Performance Utilities for Windows Health Checker Pro
=====================================================
Provides threading helpers, caching, timing instrumentation, and debouncing.
"""

import time
import functools
import threading
from typing import Any, Callable, Optional, Dict
from datetime import datetime
from dataclasses import dataclass, field


# =============================================================================
# TIMING INSTRUMENTATION
# =============================================================================

@dataclass
class TimingResult:
    """Result of a timed operation"""
    operation: str
    duration_ms: float
    timestamp: str
    success: bool = True
    error: Optional[str] = None


class PerfLogger:
    """Simple performance logger for tracking operation durations"""
    
    _instance: Optional['PerfLogger'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.enabled = True
        self.results: list[TimingResult] = []
        self.max_results = 100  # Keep last N results
    
    def log(self, result: TimingResult):
        """Log a timing result"""
        if not self.enabled:
            return
        
        self.results.append(result)
        if len(self.results) > self.max_results:
            self.results.pop(0)
        
        # Print to console
        status = "OK" if result.success else f"FAIL: {result.error}"
        print(f"[PERF] {result.operation}: {result.duration_ms:.1f}ms [{status}]")
    
    def get_summary(self) -> Dict[str, Dict]:
        """Get summary statistics by operation"""
        summary = {}
        for result in self.results:
            if result.operation not in summary:
                summary[result.operation] = {
                    'count': 0,
                    'total_ms': 0.0,
                    'min_ms': float('inf'),
                    'max_ms': 0.0,
                    'failures': 0
                }
            
            s = summary[result.operation]
            s['count'] += 1
            s['total_ms'] += result.duration_ms
            s['min_ms'] = min(s['min_ms'], result.duration_ms)
            s['max_ms'] = max(s['max_ms'], result.duration_ms)
            if not result.success:
                s['failures'] += 1
        
        # Calculate averages
        for op, s in summary.items():
            s['avg_ms'] = s['total_ms'] / s['count'] if s['count'] > 0 else 0
        
        return summary
    
    def clear(self):
        """Clear all logged results"""
        self.results.clear()


# Global perf logger instance
perf_logger = PerfLogger()


def timed(operation_name: Optional[str] = None):
    """Decorator to time function execution"""
    def decorator(func: Callable) -> Callable:
        op_name = operation_name or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            error = None
            success = True
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error = str(e)
                success = False
                raise
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                perf_logger.log(TimingResult(
                    operation=op_name,
                    duration_ms=duration_ms,
                    timestamp=datetime.now().isoformat(),
                    success=success,
                    error=error
                ))
        
        return wrapper
    return decorator


class TimingContext:
    """Context manager for timing code blocks"""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = 0.0
        self.duration_ms = 0.0
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.perf_counter() - self.start_time) * 1000
        perf_logger.log(TimingResult(
            operation=self.operation_name,
            duration_ms=self.duration_ms,
            timestamp=datetime.now().isoformat(),
            success=exc_type is None,
            error=str(exc_val) if exc_val else None
        ))
        return False  # Don't suppress exceptions


# =============================================================================
# CACHING
# =============================================================================

@dataclass
class CacheEntry:
    """Single cache entry with TTL"""
    value: Any
    expires_at: float  # time.time() timestamp
    
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class DataCache:
    """Thread-safe cache for expensive data with TTL"""
    
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired"""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None or entry.is_expired():
                return None
            return entry.value
    
    def set(self, key: str, value: Any, ttl_seconds: float = 300.0):
        """Set cached value with TTL (default 5 minutes)"""
        with self._lock:
            self._cache[key] = CacheEntry(
                value=value,
                expires_at=time.time() + ttl_seconds
            )
    
    def invalidate(self, key: str):
        """Remove a specific cache entry"""
        with self._lock:
            self._cache.pop(key, None)
    
    def clear(self):
        """Clear all cached data"""
        with self._lock:
            self._cache.clear()
    
    def cleanup_expired(self):
        """Remove all expired entries"""
        with self._lock:
            expired = [k for k, v in self._cache.items() if v.is_expired()]
            for k in expired:
                del self._cache[k]


# Global cache instance
data_cache = DataCache()


class CachedFunction:
    """Wrapper for cached function with refresh and invalidate methods"""
    
    def __init__(self, func: Callable, key: str, ttl_seconds: float):
        self._func = func
        self._key = key
        self._ttl_seconds = ttl_seconds
        functools.update_wrapper(self, func)
    
    def __call__(self, *args, **kwargs):
        # Check cache first
        cached_value = data_cache.get(self._key)
        if cached_value is not None:
            print(f"[CACHE] HIT: {self._key}")
            return cached_value
        
        # Execute function and cache result
        print(f"[CACHE] MISS: {self._key}")
        result = self._func(*args, **kwargs)
        data_cache.set(self._key, result, self._ttl_seconds)
        return result
    
    def refresh(self, *args, **kwargs):
        """Force refresh by invalidating cache and calling function"""
        data_cache.invalidate(self._key)
        return self(*args, **kwargs)
    
    def invalidate(self):
        """Invalidate the cached value"""
        data_cache.invalidate(self._key)


def cached(key: str, ttl_seconds: float = 300.0):
    """Decorator to cache function results"""
    def decorator(func: Callable) -> CachedFunction:
        return CachedFunction(func, key, ttl_seconds)
    
    return decorator


# =============================================================================
# DEBOUNCING
# =============================================================================

class Debouncer:
    """Debounce rapid function calls"""
    
    def __init__(self, delay_ms: float = 100.0):
        self.delay_ms = delay_ms
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator to debounce function calls"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with self._lock:
                if self._timer is not None:
                    self._timer.cancel()
                
                self._timer = threading.Timer(
                    self.delay_ms / 1000.0,
                    lambda: func(*args, **kwargs)
                )
                self._timer.start()
        
        return wrapper
    
    def cancel(self):
        """Cancel pending call"""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None


def debounced(delay_ms: float = 100.0):
    """Decorator factory for debouncing"""
    return Debouncer(delay_ms)


# =============================================================================
# BATCH UPDATE HELPER
# =============================================================================

class BatchUpdater:
    """
    Batch multiple UI updates into single repaint.
    Usage:
        with BatchUpdater(widget) as batch:
            batch.queue(lambda: label1.setText("foo"))
            batch.queue(lambda: label2.setText("bar"))
        # All updates applied at once when context exits
    """
    
    def __init__(self, widget):
        self.widget = widget
        self.updates: list[Callable] = []
    
    def __enter__(self):
        # Disable updates
        if hasattr(self.widget, 'setUpdatesEnabled'):
            self.widget.setUpdatesEnabled(False)
        return self
    
    def __exit__(self, *args):
        # Apply all queued updates
        for update in self.updates:
            try:
                update()
            except Exception as e:
                print(f"[BatchUpdater] Error: {e}")
        
        # Re-enable updates and trigger single repaint
        if hasattr(self.widget, 'setUpdatesEnabled'):
            self.widget.setUpdatesEnabled(True)
        
        return False
    
    def queue(self, update: Callable):
        """Queue an update function"""
        self.updates.append(update)
