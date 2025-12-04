# Windows Health Checker Pro

## Application Details

| Property | Value |
|----------|-------|
| **App Name** | Windows Health Checker Pro |
| **Version** | MK5 |
| **Executable Name** | `WindowsHealthChecker.exe` |
| **Main Script** | `driver_updater_qt_mk5.py` |

## Build Command

```powershell
python -m PyInstaller --noconfirm --onefile --windowed --name "WindowsHealthChecker" driver_updater_qt_mk5.py
```

### With Icon (if icon.ico exists):
```powershell
python -m PyInstaller --noconfirm --onefile --windowed --icon "icon.ico" --name "WindowsHealthChecker" --add-data "icon.ico;." driver_updater_qt_mk5.py
```

## Output Location

After building, the executable will be at:
```
dist\WindowsHealthChecker.exe
```

## Key Files

| File | Purpose |
|------|---------|
| `driver_updater_qt_mk5.py` | Main application (PyQt6 UI) |
| `hardware_scanner.py` | Hardware information collection via WMI |
| `startup_scanner.py` | Startup programs scanner |
| `driver_backend.py` | Driver scanning and health checks |
| `perf_utils.py` | Performance timing utilities |

## Features

- System health overview with score
- Hardware information (CPU, GPU, RAM, Storage, Network, etc.)
- Driver scanning and updates
- Startup program management
- Windows security status
- Event log viewer
- Real-time system metrics (CPU, RAM, Disk usage)

## Notes

- The repository/folder is named "DriverUpdater" for historical reasons
- The actual application name displayed to users is **Windows Health Checker Pro**
- Always export as `WindowsHealthChecker.exe`, not `DriverUpdater.exe`
