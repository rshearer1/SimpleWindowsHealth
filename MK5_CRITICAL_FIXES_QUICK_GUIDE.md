# MK5 Critical Fixes - Quick Implementation Guide

**URGENT**: These 5 fixes must be completed before any production use.

---

## 🔴 FIX #1: Make Dialog Actually Modal (5 minutes)

**File**: `driver_updater_qt_mk5.py`  
**Lines**: 1221, ~1153

### Current Code (line 1221):
```python
def run_scan(self):
    """Run full system scan"""
    dialog = ScanProgressDialog(self)
    dialog.show()  # ❌ WRONG - not blocking
```

### Fixed Code:
```python
def run_scan(self):
    """Run full system scan"""
    # Prevent multiple scans
    if hasattr(self, 'scan_timer') and self.scan_timer is not None:
        if self.scan_timer.isActive():
            self.statusBar().showMessage("Scan already in progress")
            return
    
    dialog = ScanProgressDialog(self)
    
    # Connect cancel handler
    dialog.rejected.connect(self.cancel_scan)
    
    self.scan_dialog = dialog
    self.scan_progress = 0
    self.scan_task_index = 0
    self.scan_tasks = ["update", "defender", "sfc", "smart", "memory", "events", "services"]
    
    # Start scan simulation
    self.scan_timer = QTimer()
    self.scan_timer.timeout.connect(self._update_scan)
    self.scan_timer.start(400)
    
    # Show as modal - blocks main window
    result = dialog.exec()  # ✅ CORRECT - blocks until closed
    
    # Cleanup if cancelled
    if result == QDialog.DialogCode.Rejected:
        self.cancel_scan()
```

---

## 🔴 FIX #2: Implement Cancel Handler (5 minutes)

**File**: `driver_updater_qt_mk5.py`  
**Location**: Add new method after `run_scan()`

### Add This Method:
```python
def cancel_scan(self):
    """Cancel ongoing scan and cleanup resources"""
    # Stop the timer
    if hasattr(self, 'scan_timer') and self.scan_timer is not None:
        if self.scan_timer.isActive():
            self.scan_timer.stop()
        self.scan_timer = None
    
    # Clear dialog reference
    if hasattr(self, 'scan_dialog'):
        self.scan_dialog = None
    
    # Reset progress tracking
    self.scan_progress = 0
    self.scan_task_index = 0
    
    # Update status bar
    self.statusBar().showMessage("Scan cancelled")
```

---

## 🔴 FIX #3: Add Safety Check in Update Method (3 minutes)

**File**: `driver_updater_qt_mk5.py`  
**Lines**: 1233-1235

### Current Code:
```python
def _update_scan(self):
    tasks = self.scan_tasks
    
    # Complete previous task
    if self.scan_task_index > 0:
        prev_task = tasks[self.scan_task_index - 1]
        self.scan_dialog.update_task(prev_task, "complete")  # ❌ Can crash!
```

### Fixed Code:
```python
def _update_scan(self):
    # Safety check - ensure dialog still exists
    if not hasattr(self, 'scan_dialog') or self.scan_dialog is None:
        if hasattr(self, 'scan_timer') and self.scan_timer is not None:
            if self.scan_timer.isActive():
                self.scan_timer.stop()
        return  # ✅ Safe early exit
    
    tasks = self.scan_tasks
    
    # Complete previous task
    if self.scan_task_index > 0:
        prev_task = tasks[self.scan_task_index - 1]
        self.scan_dialog.update_task(prev_task, "complete")  # Now safe
    
    # ... rest of method unchanged
```

---

## 🔴 FIX #4: Make Quick Cards Clickable (10 minutes)

**File**: `driver_updater_qt_mk5.py`  
**Lines**: 505, 930-936

### Step 1: Add Signal to StatusCard Class (after line 505)
```python
from PyQt6.QtCore import pyqtSignal

class StatusCard(QFrame):
    """Quick status card for overview grid"""
    
    clicked = pyqtSignal()  # ✅ Add this
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        # ... existing code ...
    
    def mousePressEvent(self, event):
        """Handle click"""
        self.clicked.emit()  # ✅ Add this
        super().mousePressEvent(event)
```

### Step 2: Connect Cards in OverviewPage (after line 936)
```python
# After grid.addWidget(card, i // 3, i % 3)
# Add this mapping and connections:

# Map card IDs to navigation IDs
cards_mapping = {
    "updates": "updates",
    "defender": "security",
    "storage": "storage",
    "drives": "hardware",
    "memory": "hardware",
    "system": "system"
}

# Connect each card to navigation
for card_id, card in self.status_cards.items():
    if card_id in cards_mapping:
        nav_id = cards_mapping[card_id]
        # Get reference to main window and navigate
        card.clicked.connect(lambda nid=nav_id: self.window().navigate(nid))
```

---

## 🔴 FIX #5: Clean Up on Window Close (5 minutes)

**File**: `driver_updater_qt_mk5.py`  
**Location**: Add to MainWindow class (after line ~1200)

### Add This Method:
```python
def closeEvent(self, event):
    """Clean up resources before closing"""
    # Stop scan timer if running
    if hasattr(self, 'scan_timer') and self.scan_timer is not None:
        if self.scan_timer.isActive():
            self.scan_timer.stop()
        self.scan_timer = None
    
    # Stop animation timer in score ring
    if hasattr(self, 'overview'):
        score_ring = self.overview.health_card.score_ring
        if hasattr(score_ring, 'anim_timer') and score_ring.anim_timer is not None:
            if score_ring.anim_timer.isActive():
                score_ring.anim_timer.stop()
    
    # Accept the close event
    event.accept()
```

---

## ✅ VERIFICATION CHECKLIST

After implementing all 5 fixes, test these scenarios:

### Test 1: Cancel During Scan
1. Click "Run Full Scan"
2. Wait for scan to reach ~50%
3. Click "Cancel" button
4. **Expected**: Dialog closes, no crash, status bar shows "Scan cancelled"

### Test 2: Close Dialog with X
1. Click "Run Full Scan"
2. Click the X button on dialog
3. **Expected**: Same as Test 1

### Test 3: Multiple Scan Prevention
1. Click "Run Full Scan"
2. Quickly click "Run Full Scan" again (5 times)
3. **Expected**: Only one scan runs, status bar shows "Scan already in progress"

### Test 4: Status Card Navigation
1. Click "Windows Update" card
2. **Expected**: Navigate to Updates page, sidebar highlights "Updates"
3. Click back to "Overview"
4. Click "Defender" card
5. **Expected**: Navigate to Security page
6. Repeat for all 6 cards

### Test 5: Clean Window Close
1. Click "Run Full Scan"
2. While scan running, close entire window (Alt+F4 or X)
3. **Expected**: Window closes cleanly, no errors

### Test 6: Complete Scan
1. Click "Run Full Scan"
2. Let it complete naturally
3. **Expected**: Results shown, dialog auto-closes after 800ms

---

## 🎯 SUCCESS CRITERIA

All fixes are complete when:
- [ ] No crashes when cancelling scan
- [ ] No crashes when closing window
- [ ] Can't start multiple scans
- [ ] All status cards navigate correctly
- [ ] Clean shutdown always

---

## 📞 NEED HELP?

If you encounter issues:

1. Check console/terminal for Python errors
2. Add debug prints to verify methods are called
3. Use PyQt debugger to inspect widget states
4. Verify imports are correct (especially pyqtSignal)

Common gotchas:
- Lambda capture: Use `lambda nid=nav_id: func(nid)` not `lambda: func(nav_id)`
- Check `self.scan_dialog is not None` not just `hasattr()`
- Remember to call `super().mousePressEvent(event)` after emitting signal

---

**Time Estimate**: 30-45 minutes total for all 5 fixes  
**Complexity**: Low to Medium  
**Risk**: Low (all fixes are defensive/additive)
