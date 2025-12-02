# Windows Health Checker Pro v1.0.0

A comprehensive Windows system diagnostics and optimization tool with a modern, professional UI.

## Features

### System Health Monitoring
- **Overview Dashboard** - Real-time health score and quick status cards
- **Real-time Graphs** - CPU, RAM, and Disk activity monitoring (runs in background thread)
- **Event Log Analysis** - Check for errors and warnings

### Hardware & Drivers
- **Hardware Scanner** - Detailed hardware information (CPU, GPU, RAM, Storage, Network)
- **Driver Manager** - Scan installed drivers, detect problems, identify unsigned drivers
- **Device Manager Integration** - Quick access to fix problematic drivers

### System Maintenance
- **Windows Updates** - Check update status
- **Windows Defender** - Security status monitoring
- **Storage Analysis** - Disk space and health
- **System File Integrity** - Run SFC and DISM repairs

### Startup Management
- **Startup Programs** - View and manage startup items
- **Impact Analysis** - See which programs slow down boot time
- **Enable/Disable Controls** - Manage startup items via Task Manager

## Installation

1. Download `WindowsHealthCheckerPro.exe`
2. Run as Administrator for full functionality
3. No installation required - it's a standalone executable

## System Requirements

- Windows 10 or Windows 11
- Administrator privileges recommended
- ~40 MB disk space

## Usage

1. Launch the application
2. Click "Run Full Scan" on the Overview page for a complete system check
3. Use the sidebar to navigate to specific modules
4. Hardware and Startup pages require manual refresh (click the Refresh button)

## Technical Details

- Built with Python 3.14 and PyQt6
- Splash screen runs in separate process for responsiveness
- Background threading for real-time metrics
- WMI-based hardware detection
- Registry and Task Scheduler scanning for startup items

## Version History

### v1.0.0 (December 2025)
- Initial production release
- Modern dark theme UI
- Real-time system monitoring
- Hardware detection and display
- Driver scanning and management
- Startup program management
- SFC/DISM integration
- Performance optimized with background threading

## License

Copyright © 2025. All rights reserved.

---

*Built with ❤️ for Windows system administrators and power users*
