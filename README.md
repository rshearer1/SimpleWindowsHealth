# Windows Health Checker Pro

A modern, comprehensive Windows system health monitoring application built with Python and PyQt6.

![Windows 10/11](https://img.shields.io/badge/Windows-10%2F11-blue)
![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Features

### 🔍 Full System Scan
Run a comprehensive health check that analyzes all aspects of your system **in parallel**:

| Module | Description |
|--------|-------------|
| **Windows Updates** | Check for pending updates and update history |
| **Security** | Windows Defender, Firewall, UAC, Secure Boot, BitLocker status |
| **Storage** | Drive usage, health status, and free space warnings |
| **Hardware** | CPU, GPU, RAM, and storage device information |
| **Events** | System event log analysis for errors and warnings |
| **System Files** | Integrity verification with SFC/DISM tools |
| **Startup Items** | Manage programs that run at startup |
| **Drivers** | Scan for outdated or problematic drivers |

### ⚡ Performance Optimized
- **Parallel scanning** - All 7 checks run simultaneously
- **Background threading** - UI never freezes during operations
- **Fast startup** - Optimized from 59s to ~8s with parallel initialization

### 🎨 Modern UI
- Dark theme with clean, intuitive interface
- Real-time progress indicators
- Detailed results with actionable recommendations
- Responsive splash screen with task timing

## Installation

### Option 1: Download Executable (Recommended)
1. Go to [Releases](https://github.com/rshearer1/SimpleWindowsHealth/releases)
2. Download `WindowsHealthCheckerPro.exe`
3. Run directly - **no installation required!**

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

## System Requirements

### For Executable
- Windows 10 or Windows 11
- No additional software required
- Administrator privileges recommended for full functionality

### For Running from Source
- Python 3.10 or higher
- PyQt6
- psutil
- wmi (optional, for enhanced hardware detection)

## Usage

1. **Launch** the application
2. Click **"Full System Scan"** on the Overview page to run all checks
3. View results on individual pages by clicking modules in the sidebar
4. Use **action buttons** to fix issues or open system tools

### Page Guide

| Page | Features |
|------|----------|
| **Overview** | Health score dashboard, quick actions, real-time graphs |
| **Windows Update** | Update status, pending count, check/install updates |
| **Security** | Defender, Firewall profiles, UAC, Secure Boot, BitLocker, Credential Guard |
| **Storage** | Drive usage bars, health status, free space warnings |
| **Hardware** | CPU, GPU, RAM details with real-time monitoring |
| **Events** | Critical/Error/Warning counts, recent event details |
| **System Files** | Run SFC and DISM scans with one click |
| **Startup** | Enable/disable startup programs, view impact |
| **Drivers** | Driver status, signing info, problem detection |

## Building from Source

```bash
# Install PyInstaller
pip install pyinstaller

# Build the executable
pyinstaller --onefile --windowed --name "WindowsHealthCheckerPro" driver_updater_qt_mk5.py
```

The executable will be created in the `dist` folder.

## Version History

### v2.0.0 (December 2025)
- **Parallel full system scan** - All checks run simultaneously
- **Parallel startup scanner** - 59s → 8s startup time
- **Enhanced splash screen** with task timing display
- **All pages populate** from full scan automatically
- **Expanded Security page** - Firewall, UAC, Secure Boot, BitLocker info
- **Event log scanning** with detailed error/warning display
- **Background threading** for all operations (no UI freeze)
- Fixed startup enable/disable functionality
- Fixed Windows Update button functionality

### v1.0.0 (December 2025)
- Initial release
- Modern dark theme UI
- Real-time system monitoring
- Hardware detection and display
- Driver scanning and management
- Startup program management
- SFC/DISM integration

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

If you encounter any issues or have suggestions, please [open an issue](https://github.com/rshearer1/SimpleWindowsHealth/issues).

---

**Made with ❤️ for Windows users who want to keep their systems healthy**
