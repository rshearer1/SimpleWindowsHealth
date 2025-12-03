# Windows Health Checker

A comprehensive Windows system health monitoring tool with a modern dark-themed interface. Scan your entire system with one click and get actionable insights to keep your PC running smoothly.

![Windows 10/11](https://img.shields.io/badge/Windows-10%2F11-blue)
![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Release](https://img.shields.io/github/v/release/rshearer1/SimpleWindowsHealth)

## 📥 Download

**[⬇️ Download Latest Release](https://github.com/rshearer1/SimpleWindowsHealth/releases/latest)**

No installation required - just download `WindowsHealthChecker.exe` and run!

---

## ✨ Features

### 🔍 One-Click Full System Scan

Run a comprehensive health check that analyzes all aspects of your system simultaneously:

| Module | What It Checks |
|--------|----------------|
| **Drivers** | Outdated, unsigned, or problematic drivers with signing status |
| **Startup** | Programs running at boot - enable/disable directly from the app |
| **Windows Updates** | Pending updates, update history, and service status |
| **Storage** | Drive health, SMART status, free space warnings, cleanup tools |
| **Security** | Windows Defender, Firewall profiles & rules, UAC, BitLocker, Secure Boot |
| **Hardware** | CPU, GPU, RAM, motherboard details with real-time usage graphs |
| **System** | OS info, restore points, SFC/DISM integrity checks |
| **Events** | Critical errors, warnings, and system log analysis (last 24 hours) |
| **Audio** | Audio device detection, speaker test, and troubleshooting |

### 📊 Real-Time Monitoring

- Live CPU, RAM, and Disk usage graphs on the Overview page
- Auto-refreshing metrics every few seconds
- Visual indicators for system health status

### 🎨 Modern Dark Theme UI

- Clean, intuitive sidebar navigation
- Color-coded status indicators (green/yellow/red)
- Responsive cards with detailed breakdowns
- Progress dialogs with task timing

### 🛠️ Quick Actions & Tools

Access common Windows tools directly from the app:

- Task Manager
- Device Manager
- Disk Cleanup
- Windows Update Settings
- Windows Security
- System Properties
- Event Viewer
- Sound Settings

---

## 📸 Screenshots

*Coming soon*

---

## 🚀 Getting Started

### Option 1: Download Executable (Recommended)

1. Go to [Releases](https://github.com/rshearer1/SimpleWindowsHealth/releases/latest)
2. Download `WindowsHealthChecker.exe`
3. Run the executable - no installation needed!
4. Click "Run Full Scan" to check your system

> **Note:** Administrator privileges are recommended for full functionality (driver details, system file checks, etc.)

### Option 2: Run from Source

```bash
# Clone the repository
git clone https://github.com/rshearer1/SimpleWindowsHealth.git
cd SimpleWindowsHealth

# Install dependencies
pip install PyQt6 psutil wmi

# Run the application
python driver_updater_qt_mk5.py
```

---

## 💻 System Requirements

| Requirement | Details |
|-------------|---------|
| **OS** | Windows 10 or Windows 11 |
| **Privileges** | Administrator (recommended) |
| **Disk Space** | ~50 MB for executable |
| **RAM** | Minimal - runs efficiently in background |

### For Running from Source

- Python 3.10 or higher
- PyQt6
- psutil
- wmi (optional, for enhanced hardware detection)

---

## 📖 Usage Guide

### Overview Page

The main dashboard shows:
- **Health Score** - Overall system health at a glance
- **Quick Stats** - CPU, RAM, Disk usage with live graphs
- **Recent Activity** - Latest scan results and actions
- **Quick Tools** - One-click access to common Windows utilities

### Running a Scan

1. Click **"Run Full Scan"** on the Overview page
2. Watch the progress dialog as all 7 checks run in parallel
3. Results automatically populate all module pages
4. Click any module in the sidebar to see detailed results

### Module Pages

Each page provides:
- **Summary stats** at the top
- **Detailed results** in expandable cards
- **Action buttons** to fix issues or open related tools

### Security Page (3 Tabs)

- **Windows Defender** - Real-time protection, scan status, definition updates
- **Firewall Status** - Domain/Private/Public profile status
- **Firewall Rules** - View active inbound/outbound rules with protocol details

### Storage Page

- Drive usage bars with color-coded warnings
- SMART health status for SSDs/HDDs
- Quick access to Disk Cleanup and Storage Sense
- Empty Recycle Bin option

### Startup Page

- View all startup programs with impact ratings
- Enable/disable items directly (requires admin)
- See program publisher and file location

---

## 🔧 Building from Source

```bash
# Install PyInstaller
pip install pyinstaller

# Build single-file executable
pyinstaller --onefile --windowed --name "WindowsHealthChecker" driver_updater_qt_mk5.py

# Or use the included spec file
pyinstaller WindowsHealthChecker.spec
```

The executable will be created in the `dist` folder.

---

## 📋 Changelog

### v2.0.1 (Latest)
- Fixed console window briefly appearing during scans
- All background operations now fully hidden

### v2.1.0
- Added Firewall rules viewer with protocol/port details
- Enhanced Security page with 3-tab layout
- Improved UI consistency and color coding across all pages
- Fixed Windows Update status check performance

### v2.0.0
- Complete UI redesign with modern dark theme
- Parallel scanning - all checks run simultaneously
- Added Event log analysis with error/warning breakdown
- Enhanced hardware monitoring with live graphs
- Added restore point management
- Splash screen with loading progress

### v1.0.0
- Initial release
- Basic system scanning
- Driver and startup management
- SFC/DISM integration

---

## 🤝 Contributing

Contributions are welcome! Here's how:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/YourFeature`)
3. Commit your changes (`git commit -m 'Add YourFeature'`)
4. Push to the branch (`git push origin feature/YourFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🐛 Support

Found a bug or have a suggestion?

- [Open an Issue](https://github.com/rshearer1/SimpleWindowsHealth/issues)
- Check existing issues before creating a new one

---

## ⭐ Star History

If you find this tool useful, please consider giving it a star!

---

**Made for Windows users who want to keep their systems healthy.**
